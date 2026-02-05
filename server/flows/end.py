"""End call flow - Wrap up and end the conversation."""

from typing import Dict, List

from loguru import logger
from pipecat.frames.frames import EndTaskFrame
from pipecat.processors.frame_processor import FrameDirection
from pipecat_flows import FlowManager
from utils.node_factory import NodeFunction, create_node

from flows.utils import handle_flow_error

# Configure logging
logger = logger.bind(name=__name__)


@handle_flow_error
async def handle_end_conversation(args: Dict, result: dict, flow_manager: FlowManager):
    """Handle ending the conversation - transition to wrap up node."""
    logger.info("Transitioning to end conversation")

    patient_name = flow_manager.state.get("patient_name", "there")
    device_ordered = flow_manager.state.get("device_ordered", "your order")
    insurance_data = flow_manager.state.get("insurance_data", {})

    # Check if we collected any insurance data
    has_insurance_data = bool(insurance_data)

    await flow_manager.set_node(
        "wrap_up", create_wrap_up_node(patient_name, device_ordered, has_insurance_data)
    )


async def handle_end_task(args: Dict, result: dict, flow_manager: FlowManager):
    """Handle ending the task by pushing EndTaskFrame upstream."""
    logger.info("Ending task - pushing EndTaskFrame")

    llm = flow_manager.state.get("llm")
    if llm:
        await llm.push_frame(EndTaskFrame(), FrameDirection.UPSTREAM)
    else:
        logger.error("No LLM available in flow manager state to push EndTaskFrame")


def create_wrap_up_node(
    patient_name: str, device_ordered: str, has_insurance_data: bool = False
) -> dict:
    """
    Create a node for wrapping up the conversation with a closing message.

    Args:
        patient_name: The patient's name for personalization
        device_ordered: The device that was ordered
        has_insurance_data: Whether insurance data was collected in this call
    """
    # Use first name only for more personal touch
    first_name = (
        patient_name.split()[0]
        if patient_name and patient_name != "the patient"
        else "there"
    )

    logger.info(
        f"Creating wrap up node for {first_name}, has_insurance_data: {has_insurance_data}"
    )

    if has_insurance_data:
        task_message = f"""Wrap up after collecting insurance info.

Thank them: "Perfect! I've got everything... thank you so much, {first_name}!"

Explain next steps: "We'll verify this with your insurance and get your {device_ordered} processed. You'll hear from us in a few days!"

Ask: "Anything else I can help with today?"

If they say YES or have a question:
- Answer briefly if it's about the {device_ordered} order or insurance
- If unrelated: "I'm only able to help with the {device_ordered} order today... you can call our main line for other questions!"
- After answering, ask again: "Anything else?"

If they say NO/nothing else/I'm good:
FIRST: Say goodbye: "Thank you again, {first_name}... have a great day! Take care!"
SECOND: Call end_task

CRITICAL: Say goodbye BEFORE calling end_task.
"""
    else:
        task_message = f"""Wrap up - they declined.

Say: "No problem, {first_name}! Life gets busy! Want us to call back later about the {device_ordered} insurance?"

When ready to end:
FIRST: Say goodbye: "Thank you for your time! Have a wonderful day, take care!"
SECOND: Call end_task

CRITICAL: Say goodbye BEFORE calling end_task.
"""

    base_functions: List[NodeFunction] = [
        {
            "type": "function",
            "function": {
                "name": "end_task",
                "description": "End the conversation and hang up the call. IMPORTANT: Only call this AFTER you have said a complete goodbye message out loud. Never call this function without first saying 'Take care!' or similar farewell.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                },
                "transition_callback": handle_end_task,
            },
        },
    ]

    return create_node(
        task_message=task_message,
        custom_functions=base_functions,
        include_default_transitions=False,  # Don't add end_conversation again
    )


def create_error_end_node() -> dict:
    """
    Create a node for gracefully ending the conversation when an error occurs.
    """
    logger.info("Creating error end node")

    task_message = """Error occurred. End gracefully.

Say: "Oh, I'm so sorry... technical difficulties! Someone will follow up shortly about your order. Thank you for your patience... have a wonderful day!"

Then call end_task.
"""

    base_functions: List[NodeFunction] = [
        {
            "type": "function",
            "function": {
                "name": "end_task",
                "description": "End the conversation after the error message.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                },
                "transition_callback": handle_end_task,
            },
        },
    ]

    return create_node(
        task_message=task_message,
        custom_functions=base_functions,
        include_default_transitions=False,
    )
