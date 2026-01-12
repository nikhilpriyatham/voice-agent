"""
bot_daily.py

Dasco Insurance Verification Bot using Daily.co transport.
This bot connects to a Daily room for WebRTC communication.

Run with:
    python bot_daily.py --room-url <url> --token <token> --patient-name <name> --device-ordered <device>
"""

import argparse
import asyncio
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
from pipecat.audio.mixers.soundfile_mixer import SoundfileMixer
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.frames.frames import EndTaskFrame, TTSSpeakFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from pipecat.processors.frameworks.rtvi import RTVIObserver, RTVIProcessor
from pipecat.services.azure.llm import AzureLLMService
from pipecat.services.cartesia.tts import CartesiaTTSService
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.transports.daily.transport import DailyParams, DailyTransport
from pipecat_flows import FlowManager
from utils.user_idle_processor import UserIdleProcessor

# Try to import KrispFilter (requires commercial SDK)
try:
    from pipecat.audio.filters.krisp_filter import KrispFilter

    KRISP_AVAILABLE = True
except Exception:
    KRISP_AVAILABLE = False
    logger.warning("KrispFilter not available - noise cancellation disabled")

load_dotenv(override=True)


async def run_bot(room_url: str, token: str, patient_name: str, device_ordered: str):
    """Run the bot with Daily transport."""
    logger.info(f"Starting bot for patient: {patient_name}, device: {device_ordered}")
    logger.info(f"Connecting to room: {room_url}")

    # Initialize mem0 client for conversation memory
    mem0_api_key = os.getenv("MEM0_API_KEY")
    mem0_client = MemoryClient(api_key=mem0_api_key) if mem0_api_key else None
    if mem0_client:
        logger.info("Mem0 memory client initialized")
    else:
        logger.warning("MEM0_API_KEY not set, conversation memory disabled")

    # Configure VAD - balanced to ignore noise but catch real speech
    vad_params = VADParams(
        confidence=0.7,  # Higher threshold to filter out noise
        min_volume=0.5,  # Ignore quiet background sounds
        start_secs=0.2,  # Require sustained speech before interrupting
        stop_secs=0.7,  # Slightly longer to avoid cutting off mid-word
    )
    vad_analyzer = SileroVADAnalyzer(sample_rate=16000, params=vad_params)

    # Initialize SoundfileMixer for background audio
    # Note: Audio file must match Cartesia TTS sample rate (24kHz)
    soundfile_mixer = SoundfileMixer(
        sound_files={"office": "./assets/office-ambience-24khz-short.mp3"},
        default_sound="office",
        volume=0.3,  # Low volume so bot voice is clear
        loop=True,  # Loop the background audio continuously
        mixing=True,  # Mix with bot speech (both play together)
    )

    # Get Daily API credentials for transport
    daily_api_key = os.getenv("DAILY_API_KEY", "")
    daily_api_url = os.getenv("DAILY_API_URL", "https://api.daily.co/v1")

    # Create Daily transport with enhanced audio features
    daily_params = DailyParams(
        api_key=daily_api_key,
        api_url=daily_api_url,
        audio_in_enabled=True,
        audio_out_enabled=True,
        video_out_enabled=False,
        audio_out_mixer=soundfile_mixer,  # Background audio
        vad_enabled=True,
        vad_analyzer=vad_analyzer,
        vad_audio_passthrough=True,  # For transcript handling
        transcription_enabled=False,  # We use Deepgram directly
    )

    # Add Krisp noise cancellation if available
    if KRISP_AVAILABLE:
        daily_params.audio_in_filter = KrispFilter()
        logger.info("Krisp noise cancellation enabled")

    transport = DailyTransport(
        room_url,
        token,
        "Amanda",  # Bot's display name
        daily_params,
    )

    stt = DeepgramSTTService(api_key=os.getenv("DEEPGRAM_API_KEY"))

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

    # Initial context
    context = OpenAILLMContext([])
    context_aggregator = llm.create_context_aggregator(context)

    # RTVI processor and observer for real-time transcript display in UI
    rtvi = RTVIProcessor()
    rtvi_observer = RTVIObserver(rtvi)

    # User idle callback - prompts user when they're silent too long
    async def handle_user_idle(processor: UserIdleProcessor, retry_count: int) -> bool:
        """Handle user idle timeout with escalating prompts."""
        if retry_count == 1:
            logger.info("User idle - first prompt")
            await processor.push_frame(TTSSpeakFrame("Hello... are you still there?"))
            return True  # Continue monitoring
        elif retry_count == 2:
            logger.info("User idle - second prompt")
            await processor.push_frame(
                TTSSpeakFrame(
                    "I haven't heard from you in a while... are you still there?"
                )
            )
            return True  # Continue monitoring
        else:
            logger.info("User idle - ending call")
            await processor.push_frame(
                TTSSpeakFrame(
                    "It looks like you might be busy. Feel free to call us back whenever you're ready. Take care!"
                )
            )
            # Give time for the message to play before ending
            await processor.push_frame(EndTaskFrame())
            return False  # Stop monitoring

    # Create user idle processor (15 second timeout)
    user_idle = UserIdleProcessor(
        callback=handle_user_idle,
        timeout=15.0,  # 15 seconds of silence triggers prompt
    )

    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            user_idle,  # Monitor for user silence
            rtvi,  # Captures transcripts for UI display
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
        observers=[rtvi_observer],  # Observer translates events for client
    )

    # Initialize FlowManager
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

    @transport.event_handler("on_first_participant_joined")
    async def on_first_participant_joined(transport, participant):
        logger.info(f"Participant joined: {participant['id']}")
        # Background audio plays automatically via default_sound with loop=True
        # Start the conversation when user joins
        await transport.capture_participant_transcription(participant["id"])
        await flow_manager.initialize()
        await flow_manager.set_node(
            "start_call", create_start_call_node(patient_name, device_ordered)
        )

    @transport.event_handler("on_participant_left")
    async def on_participant_left(transport, participant, reason):
        logger.info(f"Participant left: {participant['id']}, reason: {reason}")

        # Save conversation to mem0
        if mem0_client:
            try:
                insurance_data = flow_manager.state.get("insurance_data", {})
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
                                "content": f"Insurance data: {insurance_data}",
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

    @transport.event_handler("on_call_state_updated")
    async def on_call_state_updated(transport, state):
        logger.info(f"Call state: {state}")
        if state == "left":
            await task.cancel()

    runner = PipelineRunner(handle_sigint=True)
    await runner.run(task)


def main():
    parser = argparse.ArgumentParser(description="Dasco Insurance Bot (Daily)")
    parser.add_argument("--room-url", required=True, help="Daily room URL")
    parser.add_argument("--token", required=True, help="Daily room token")
    parser.add_argument("--patient-name", default="the patient", help="Patient name")
    parser.add_argument(
        "--device-ordered", default="medical equipment", help="Device ordered"
    )

    args = parser.parse_args()

    asyncio.run(
        run_bot(args.room_url, args.token, args.patient_name, args.device_ordered)
    )


if __name__ == "__main__":
    main()
