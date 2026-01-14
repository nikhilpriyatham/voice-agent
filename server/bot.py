#
# Copyright (c) 2024–2025, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

"""Dasco Insurance Verification Bot.

This bot implements a flow-based architecture for collecting insurance
verification details from patients. It uses pipecat-flows for conversation
state management and transitions between different conversation nodes.

Required AI services:
- Deepgram (Speech-to-Text)
- Azure OpenAI (LLM)
- Cartesia (Text-to-Speech)

The example connects between client and server using a P2P WebRTC connection.

Run the bot using::

    python bot.py
"""

import os
import ssl

import nltk

# Fix SSL certificate issues on macOS
try:
    ssl_context = ssl.create_default_context()
    if ssl_context.get_default_verify_paths().cafile:
        os.environ["SSL_CERT_FILE"] = ssl_context.get_default_verify_paths().cafile
        os.environ["REQUESTS_CA_BUNDLE"] = ssl_context.get_default_verify_paths().cafile
except Exception:
    pass

# Configure NLTK data path
try:
    nltk.data.path.append(os.path.expanduser("~/nltk_data"))
    nltk.download("punkt", quiet=True)
    nltk.download("punkt_tab", quiet=True)
except Exception:
    pass

from dotenv import load_dotenv
from flows.start_call import create_start_call_node
from loguru import logger
from mem0 import MemoryClient
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from pipecat.processors.frameworks.rtvi import RTVIConfig, RTVIObserver, RTVIProcessor
from pipecat.runner.types import RunnerArguments
from pipecat.services.azure.llm import AzureLLMService
from pipecat.services.cartesia.tts import CartesiaTTSService
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.transports.base_transport import BaseTransport, TransportParams
from pipecat.transports.network.small_webrtc import SmallWebRTCTransport
from pipecat_flows import FlowManager
from utils.payer_lookup import PayerLookup

load_dotenv(override=True)


async def run_bot(transport: BaseTransport, patient_name: str, device_ordered: str):
    logger.info(f"Starting bot for patient: {patient_name}, device: {device_ordered}")

    # Initialize mem0 client for conversation memory
    mem0_api_key = os.getenv("MEM0_API_KEY")
    mem0_client = MemoryClient(api_key=mem0_api_key) if mem0_api_key else None
    if mem0_client:
        logger.info("Mem0 memory client initialized")
    else:
        logger.warning("MEM0_API_KEY not set, conversation memory disabled")

    stt = DeepgramSTTService(
        api_key=os.getenv("DEEPGRAM_API_KEY"),
        model="nova-2",  # Best model for diarization
        language="en-US",
        smart_format=True,  # Better formatting
        diarize=True,  # Enable speaker diarization for multi-speaker scenarios
    )

    tts = CartesiaTTSService(
        api_key=os.getenv("CARTESIA_API_KEY"),
        voice_id="9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
        voice_speed=1.1,
        voice_volume=1.0,
    )

    llm = AzureLLMService(
        api_key=os.getenv("OPENAI_AZURE_GPT41_API_KEY"),
        endpoint=os.getenv("OPENAI_AZURE_GPT41_ENDPOINT"),
        model=os.getenv("OPENAI_AZURE_MODEL", "gpt-4o-mini"),
        api_version=os.getenv("OPENAI_AZURE_GPT41_API_VERSION", "2024-12-01-preview"),
    )

    # Initial context - FlowManager will manage the conversation flow
    context = OpenAILLMContext([])
    context_aggregator = llm.create_context_aggregator(context)

    rtvi = RTVIProcessor(config=RTVIConfig(config=[]))

    pipeline = Pipeline(
        [
            transport.input(),
            rtvi,
            stt,
            context_aggregator.user(),
            llm,
            tts,
            transport.output(),
            context_aggregator.assistant(),
        ]
    )

    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            allow_interruptions=True,
            enable_metrics=True,
            enable_usage_metrics=True,
        ),
        observers=[RTVIObserver(rtvi)],
    )

    # Initialize FlowManager for conversation state management
    flow_manager = FlowManager(
        task=task,
        llm=llm,
        context_aggregator=context_aggregator,
        tts=tts,
    )

    # Store patient info and services in flow state
    flow_manager.state["patient_name"] = patient_name
    flow_manager.state["device_ordered"] = device_ordered
    flow_manager.state["llm"] = llm
    flow_manager.state["tts"] = tts
    flow_manager.state["task"] = task
    flow_manager.state["mem0_client"] = mem0_client

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        logger.info("Client connected")

        # Initialize payer lookup (RAG) for insurance validation
        try:
            payer_lookup = PayerLookup("./stedi_payers_2026-01-13.csv")
            flow_manager.state["payer_lookup"] = payer_lookup
            logger.info(
                f"Loaded {len(payer_lookup.payers)} payers for insurance lookup"
            )
        except Exception as e:
            logger.error(f"Failed to initialize payer lookup: {e}")
            flow_manager.state["payer_lookup"] = None

        # Retrieve past conversation history from Mem0 for personalization
        past_context = None
        if mem0_client:
            try:
                user_id = patient_name.lower().replace(" ", "_")
                memories = mem0_client.search(
                    query=f"insurance verification for {patient_name}",
                    user_id=user_id,
                    limit=3,
                )
                if memories and len(memories) > 0:
                    past_context = "\n".join(
                        [m.get("memory", "") for m in memories if m.get("memory")]
                    )
                    logger.info(
                        f"Retrieved {len(memories)} past memories for {patient_name}"
                    )
                    flow_manager.state["past_context"] = past_context
            except Exception as e:
                logger.warning(f"Failed to retrieve Mem0 memories: {e}")

        # Initialize FlowManager and set the initial node
        await flow_manager.initialize()
        await flow_manager.set_node(
            "start_call",
            create_start_call_node(patient_name, device_ordered, past_context),
        )

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.info("Client disconnected")

        # Save conversation to mem0 memory
        if mem0_client:
            try:
                # Get collected insurance data from flow state
                insurance_data = flow_manager.state.get("insurance_data", {})

                # Get conversation messages from context
                messages = (
                    context.get_messages() if hasattr(context, "get_messages") else []
                )
                conversation_messages = [
                    msg for msg in messages if msg.get("role") in ["user", "assistant"]
                ]

                if conversation_messages or insurance_data:
                    user_id = patient_name.lower().replace(" ", "_")
                    mem0_client.add(
                        conversation_messages
                        if conversation_messages
                        else [
                            {
                                "role": "system",
                                "content": f"Insurance data collected: {insurance_data}",
                            }
                        ],
                        user_id=user_id,
                        metadata={
                            "device_ordered": device_ordered,
                            "call_type": "insurance_verification",
                            "insurance_data": insurance_data,
                        },
                    )
                    logger.info(f"Conversation saved to mem0 for user: {user_id}")
            except Exception as e:
                logger.error(f"Failed to save conversation to mem0: {e}")

        await task.cancel()

    runner = PipelineRunner(handle_sigint=False)

    await runner.run(task)


async def bot(runner_args: RunnerArguments):
    """Main bot entry point for the bot starter."""

    # Extract patient info from request body or environment variables (with defaults)
    body = getattr(runner_args, "body", None) or {}
    patient_name = body.get("patient_name", os.getenv("PATIENT_NAME", "the patient"))
    device_ordered = body.get(
        "device_ordered", os.getenv("DEVICE_ORDERED", "medical equipment")
    )

    # Configure VAD to be more patient - wait for users to finish speaking
    vad_params = VADParams(
        confidence=0.7,  # Confidence threshold for voice detection
        min_volume=0.6,  # Higher = less sensitive to quiet sounds
        start_secs=0.3,  # Require 300ms of speech to trigger (filters short sounds)
        stop_secs=0.8,  # Wait 800ms of silence before stopping
    )
    vad_analyzer = SileroVADAnalyzer(params=vad_params)

    transport = SmallWebRTCTransport(
        params=TransportParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            vad_analyzer=vad_analyzer,
        ),
        webrtc_connection=runner_args.webrtc_connection,
    )

    await run_bot(transport, patient_name, device_ordered)


if __name__ == "__main__":
    from pipecat.runner.run import main

    main()
