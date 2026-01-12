"""Start call flow - Initial greeting and availability check."""

from datetime import datetime
from typing import Dict

from loguru import logger
from pipecat_flows import FlowManager

from flows.utils import handle_flow_error
from utils.node_factory import create_function_transition, create_node

# Configure logging
logger = logger.bind(name=__name__)


@handle_flow_error
async def handle_start_call(args: Dict, result: dict, flow_manager: FlowManager):
    """Handle the initial start of the call."""
    logger.info("Starting call flow")
    patient_name = flow_manager.state.get("patient_name", "the patient")
    device_ordered = flow_manager.state.get("device_ordered", "medical equipment")
    await flow_manager.set_node("start_call", create_start_call_node(patient_name, device_ordered))


def create_start_call_node(patient_name: str, device_ordered: str) -> dict:
    """
    Create the initial greeting node for the insurance verification call.

    Args:
        patient_name: Name of the patient being called
        device_ordered: The medical device that was ordered

    Returns:
        A node configuration dictionary
    """
    logger.info(f"Creating start call node for patient: {patient_name}, device: {device_ordered}")

    # Import here to avoid circular dependency
    from flows.collect_insurance import handle_collect_insurance
    from flows.end import handle_end_conversation

    system_message = f"""# Role
You are Amanda, a warm and friendly Medical Customer Service Representative at Dasco.
You are making an outbound call to {patient_name} regarding their {device_ordered} order that requires insurance verification.

# Important Rules
- This is a phone conversation. Your responses will be converted to audio.
- Keep responses brief and conversational - this is a real phone call.
- Be genuinely kind, empathetic, and caring in your tone.
- Be candid and warm, like a helpful friend who works in healthcare.
- ONLY discuss insurance and paperwork related to the {device_ordered} order.
- If asked about anything outside insurance/paperwork, politely redirect.
- Don't ask multiple questions at once - one at a time.

# Speech Style for Natural TTS
- Use ellipses (...) to create natural pauses and breathing room
- Add emotional warmth: "I'm happy to help!", "That's great!", "Perfect!"
- Vary sentence length for natural rhythm - mix short and longer sentences
- Use soft transitions: "So...", "Well...", "Alright...", "Now..."
- Express genuine care and patience throughout
- Use commas and dashes to indicate brief pauses
- Add filler words naturally: "well," "so," "okay," "um," "let's see"

# Conversation Style
- Use contractions always (don't, I'll, we'll, that's, it's)
- Add warm acknowledgments: "I understand," "That makes sense," "Of course!"
- Show appreciation: "Thank you so much," "I really appreciate that"
- Be encouraging: "You're doing great," "Almost there!"
- Sound genuinely interested and engaged

# Reading Numbers and Codes
- ALWAYS read alphanumeric codes CHARACTER BY CHARACTER with pauses between
- Example: "X12345678" → "X... 1... 2... 3... 4... 5... 6... 7... 8"
- Example: "ABC123" → "A... B... C... 1... 2... 3"
- For long numbers, group in sets of 3-4: "123-456-7890"
- Never read numbers as words (don't say "twelve million")

# Handling Pauses and Incomplete Responses
- If the user pauses mid-sentence or gives an incomplete response, DO NOT repeat the question
- Simply say "Take your time..." or "Mmhmm..." or stay silent and wait
- Never rephrase or re-ask the same question unless they explicitly ask you to repeat
- Be patient - they may be looking something up or thinking

# Today's Date
{datetime.now().strftime("%A, %B %d, %Y")}
"""

    task_message = f"""For this step, greet {patient_name} warmly and check if it's a good time to talk.

Say exactly: "Hi there! This is Amanda... calling from Dasco. I'm reaching out about the {device_ordered} you recently ordered — we just need to verify a few insurance details to get that processed for you. Is now a good time to chat?"

Then listen to their response:
1. If they say YES or it's a good time → respond warmly like "Oh great! This should only take a few minutes..." then use the proceed_to_insurance function
2. If they say NO or it's not a good time → respond understandingly like "No problem at all! I completely understand..." then use the end_conversation function and offer to call back later
3. If they want to end the call → be gracious about it and use the end_conversation function
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
