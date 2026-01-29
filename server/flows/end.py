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
        task_message = f"""For this step, wrap up the conversation with {first_name} after successfully collecting their insurance information.

Follow this process:
1. Thank them with genuine warmth: "<emotion value="excited"/>Perfect! <break time="200ms"/> I've got everything I need. <break time="300ms"/> Thank you so much for taking the time to go through all of that with me, {first_name}. <break time="200ms"/> I really appreciate it!"

2. Explain next steps reassuringly: "<emotion value="calm"/>So. <break time="200ms"/> We'll verify this with your insurance provider and get your {device_ordered} order processed. <break time="300ms"/> You should hear from us within a few business days!"

3. Ask if they have questions: "<break time="300ms"/> Is there anything else I can help you with today?"

4. CRITICAL - When they say "no", "I'm good", "that's all", "nothing else", etc.:
   - You MUST say a warm goodbye OUT LOUD before ending
   - Say: "<emotion value="excited"/>Wonderful! <break time="200ms"/> Well, thank you again, {first_name}. <break time="200ms"/> It was so nice chatting with you! <break time="300ms"/> Have a great rest of your day. <break time="200ms"/> And please don't hesitate to call us if you have any questions. <break time="300ms"/> Take care!"
   - ONLY AFTER saying this goodbye message, call the end_task function
   - NEVER call end_task without saying goodbye first!

5. If they have questions about the {device_ordered} order or insurance, answer warmly and helpfully, then offer the goodbye again.

6. If they ask about something unrelated to their order, gently redirect: "[laughter] Oh, I wish I could help with that! <break time="200ms"/> But I'm only able to assist with the {device_ordered} order today. <break time="200ms"/> You can definitely call our main line for other questions though!"
"""
    else:
        task_message = f"""For this step, wrap up the conversation with {first_name} - they were not available or chose not to proceed with insurance verification.

Follow this process:
1. Be genuinely understanding: "<emotion value="calm"/>No problem at all, {first_name}! <break time="200ms"/> I completely understand. <break time="200ms"/> Life gets busy!"

2. Offer to call back warmly: "Would you like us to give you a call back at a better time? <break time="200ms"/> We'd be happy to go over the insurance details for your {device_ordered} order whenever works for you."

3. If yes, acknowledge cheerfully: "<emotion value="excited"/>Perfect! <break time="200ms"/> We'll definitely reach out again soon. <break time="200ms"/> Is this still the best number to reach you at?"

4. CRITICAL - When ready to end the call:
   - You MUST say a warm goodbye OUT LOUD before ending
   - Say: "Alright, {first_name}. <break time="200ms"/> Well, thank you so much for your time today! <break time="300ms"/> Have a wonderful day. <break time="200ms"/> And we'll be in touch soon. <break time="300ms"/> Take care!"
   - ONLY AFTER saying this goodbye message, call the end_task function
   - NEVER call end_task without saying goodbye first!

5. If they want to proceed now, respond enthusiastically: "<emotion value="excited"/>Oh, that's great! <break time="200ms"/> Let's do it now then..." but note that this node doesn't have that transition - just end politely and let them know we'll call back.
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

    task_message = """An error has occurred. Gracefully end the conversation with warmth.

Say something like: "<emotion value="apologetic"/>Oh, I'm so sorry. <break time="200ms"/> I seem to be experiencing some technical difficulties on my end! <break time="300ms"/> Someone from our team will definitely follow up with you shortly about your order. <break time="200ms"/> Thank you so much for your patience. <break time="300ms"/> And I hope you have a wonderful day!"

Then use the end_task function to end the call.
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
