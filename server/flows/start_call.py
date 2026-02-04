"""Start call flow - Initial greeting and availability check."""

from datetime import datetime
from typing import Dict

from loguru import logger
from pipecat_flows import FlowManager
from utils.node_factory import create_function_transition, create_node

from flows.utils import handle_flow_error

# Configure logging
logger = logger.bind(name=__name__)


@handle_flow_error
async def handle_start_call(args: Dict, result: dict, flow_manager: FlowManager):
    """Handle the initial start of the call."""
    logger.info("Starting call flow")
    patient_name = flow_manager.state.get("patient_name", "the patient")
    device_ordered = flow_manager.state.get("device_ordered", "medical equipment")
    await flow_manager.set_node(
        "start_call", create_start_call_node(patient_name, device_ordered)
    )


def create_start_call_node(
    patient_name: str, device_ordered: str, past_context: str = None
) -> dict:
    """
    Create the initial greeting node for the insurance verification call.

    Args:
        patient_name: Name of the patient being called
        device_ordered: The medical device that was ordered
        past_context: Optional past conversation context from Mem0

    Returns:
        A node configuration dictionary
    """
    logger.info(
        f"Creating start call node for patient: {patient_name}, device: {device_ordered}"
    )
    if past_context:
        logger.info(f"Using past context for personalization: {past_context[:100]}...")

    # Import here to avoid circular dependency
    from flows.collect_insurance import handle_collect_insurance

    system_message = f"""You are Amanda, friendly Medical CSR at Dasco calling {patient_name} about {device_ordered} insurance verification.

Phone Call Rules:
- Keep responses under 15 words per sentence
- Use contractions (don't, I'll, we'll)
- Use ellipses (...) for natural pauses
- Add [laughter] when they joke
- Never say you're AI

Speech Patterns:
- "Got it!" → move on immediately
- If they pause: "Take your time..."
- If silly answer: "[laughter] Okay... but seriously?"
- Read numbers naturally in pairs

Emotions:
- Frustrated: "I know... paperwork is a pain"
- Confused: "Let me explain differently..."
- Happy: Match their energy!

Today: {datetime.now().strftime("%A, %B %d, %Y")}
"""

    # Personalize greeting if we have past context
    if past_context:
        task_message = f"""For this step, greet {patient_name} warmly. You've spoken with them before!

PAST INTERACTION CONTEXT:
{past_context}

Use this context naturally if relevant. For example:
- "Hi {patient_name}! This is Amanda from Dasco again..."
- If they had issues before: "I hope things have been going smoothly since we last spoke!"

Say something like: "Hi there! This is Amanda calling from Dasco... good to connect with you again! I'm reaching out about the {device_ordered} you recently ordered. We just need to verify a few insurance details. Is now a good time to chat?"

IMPORTANT: Say the greeting ONLY ONCE. Do NOT repeat it.

Then listen to their response:

CRITICAL - Handle these responses:
- If they say "hey", "hi", "hello", or just acknowledge → They're engaged! Treat this as a YES and proceed.
- If they say "yes", "yeah", "sure", "okay", "good time", etc. → Respond "Oh great! This should only take a few minutes..." and IMMEDIATELY call proceed_to_insurance
- If they say "no", "not now", "busy", "bad time", etc. → Respond "No problem at all!" and use end_conversation
- If they want to end the call → Be gracious and use end_conversation

Do NOT repeat the greeting under any circumstances. If they responded at all, they heard you.
"""
    else:
        task_message = f"""For this step, greet {patient_name} warmly and check if it's a good time to talk.

Say exactly: "Hi there! This is Amanda calling from Dasco... I'm reaching out about the {device_ordered} you recently ordered. We just need to verify a few insurance details to get that processed for you. Is now a good time to chat?"

IMPORTANT: Say the greeting ONLY ONCE. Do NOT repeat it.

Then listen to their response:

CRITICAL - Handle these responses:
- If they say "hey", "hi", "hello", or just acknowledge → They're engaged! Treat this as a YES and proceed.
- If they say "yes", "yeah", "sure", "okay", "good time", etc. → Respond "Oh great! This should only take a few minutes..." and IMMEDIATELY call proceed_to_insurance
- If they say "no", "not now", "busy", "bad time", etc. → Respond "No problem at all!" and use end_conversation
- If they want to end the call → Be gracious and use end_conversation

Do NOT repeat the greeting under any circumstances. If they responded at all, they heard you.
"""

    custom_functions = [
        create_function_transition(
            name="proceed_to_insurance",
            description="The caller confirmed it's a good time to talk. Proceed to collect insurance information.",
            transition_callback=handle_collect_insurance,
        ),
    ]

    return create_node(
        system_message=system_message,
        task_message=task_message,
        custom_functions=custom_functions,
        include_end=True,
    )
