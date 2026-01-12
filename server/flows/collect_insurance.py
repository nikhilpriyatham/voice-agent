"""Collect insurance flow - Collects insurance details one field at a time."""

from typing import Dict

from loguru import logger
from pipecat_flows import FlowManager

from flows.utils import handle_flow_error
from utils.node_factory import create_function_transition, create_node

# Configure logging
logger = logger.bind(name=__name__)


@handle_flow_error
async def handle_collect_insurance(args: Dict, result: dict, flow_manager: FlowManager):
    """Handle the insurance collection flow - starts from the first field."""
    logger.info("Starting insurance collection flow")
    patient_name = flow_manager.state.get("patient_name", "the patient")
    device_ordered = flow_manager.state.get("device_ordered", "medical equipment")

    # Initialize collected data in state
    if "insurance_data" not in flow_manager.state:
        flow_manager.state["insurance_data"] = {}

    await flow_manager.set_node(
        "collect_policy_holder", create_collect_policy_holder_node(patient_name, device_ordered)
    )


@handle_flow_error
async def handle_collect_dob(args: Dict, result: dict, flow_manager: FlowManager):
    """Handle collecting date of birth after policy holder name."""
    logger.info(f"Collected policy holder name: {args}")

    # Store the collected data
    if "policy_holder_name" in args:
        flow_manager.state["insurance_data"]["policy_holder_name"] = args["policy_holder_name"]

    patient_name = flow_manager.state.get("patient_name", "the patient")
    device_ordered = flow_manager.state.get("device_ordered", "medical equipment")
    await flow_manager.set_node(
        "collect_dob", create_collect_dob_node(patient_name, device_ordered)
    )


@handle_flow_error
async def handle_collect_policy_number(args: Dict, result: dict, flow_manager: FlowManager):
    """Handle collecting policy number after DOB."""
    logger.info(f"Collected DOB: {args}")

    # Store the collected data
    if "date_of_birth" in args:
        flow_manager.state["insurance_data"]["date_of_birth"] = args["date_of_birth"]

    patient_name = flow_manager.state.get("patient_name", "the patient")
    device_ordered = flow_manager.state.get("device_ordered", "medical equipment")
    await flow_manager.set_node(
        "collect_policy_number", create_collect_policy_number_node(patient_name, device_ordered)
    )


@handle_flow_error
async def handle_collect_group_number(args: Dict, result: dict, flow_manager: FlowManager):
    """Handle collecting group number after policy number."""
    logger.info(f"Collected policy number: {args}")

    # Store the collected data
    if "policy_number" in args:
        flow_manager.state["insurance_data"]["policy_number"] = args["policy_number"]

    patient_name = flow_manager.state.get("patient_name", "the patient")
    device_ordered = flow_manager.state.get("device_ordered", "medical equipment")
    await flow_manager.set_node(
        "collect_group_number", create_collect_group_number_node(patient_name, device_ordered)
    )


@handle_flow_error
async def handle_collect_insurance_provider(args: Dict, result: dict, flow_manager: FlowManager):
    """Handle collecting insurance provider name after group number."""
    logger.info(f"Collected group number: {args}")

    # Store the collected data
    if "group_number" in args:
        flow_manager.state["insurance_data"]["group_number"] = args["group_number"]

    patient_name = flow_manager.state.get("patient_name", "the patient")
    device_ordered = flow_manager.state.get("device_ordered", "medical equipment")
    await flow_manager.set_node(
        "collect_insurance_provider",
        create_collect_insurance_provider_node(patient_name, device_ordered),
    )


@handle_flow_error
async def handle_finish_collection(args: Dict, result: dict, flow_manager: FlowManager):
    """Handle finishing the insurance collection - all data collected."""
    logger.info(f"Collected insurance provider: {args}")

    # Store the final piece of data
    if "insurance_provider" in args:
        flow_manager.state["insurance_data"]["insurance_provider"] = args["insurance_provider"]

    # Log all collected data
    insurance_data = flow_manager.state.get("insurance_data", {})
    logger.info(f"All insurance data collected: {insurance_data}")

    # Transition to end conversation
    from flows.end import handle_end_conversation

    await handle_end_conversation(args, result, flow_manager)


# ============ Node Creation Functions ============


def create_collect_policy_holder_node(patient_name: str, device_ordered: str) -> dict:
    """Create node for collecting policy holder name."""

    task_message = f"""For this step, collect the insurance policy holder's name from {patient_name}.

Say something like: "Great! So... first things first — could you tell me the name of the policy holder on your insurance?"

Wait for their response. Listen carefully to EXACTLY what name they say.

IMPORTANT - If they pause mid-sentence or give an incomplete response (like "It's..." or "The name is..."):
- DO NOT repeat or rephrase the question
- Simply say "Take your time..." or "Mmhmm..." and wait for them to continue
- Only re-ask if they explicitly say "What?" or "Can you repeat that?"

Once they provide the COMPLETE policy holder name:
- You MUST repeat back the EXACT name they just told you (not the patient name "{patient_name}")
- Confirm warmly: "Wonderful! So that's [repeat the EXACT name they said]... let me just make sure I got that right. Is that correct?"
- If they say YES or confirm, respond with "Perfect!" and use the save_policy_holder function with the EXACT name they provided

IMPORTANT - The policy holder may be DIFFERENT from {patient_name}. Always use what they tell you.

IMPORTANT - If they CORRECT you or spell out their name:
- Listen carefully to the correction or spelling
- Repeat the CORRECTED name back: "Oh, got it! So that's [corrected name]... thank you for clarifying!"
- Then IMMEDIATELY use the save_policy_holder function with the CORRECTED name
- Do NOT ask for confirmation again after a correction - just save it

Examples of corrections to watch for:
- "No, it's actually Smith, not Smyth"
- "It's spelled P-R-I-Y-A-D-H-A-M"
- "Close! But it's Johnson with an H"
"""

    custom_functions = [
        {
            "type": "function",
            "function": {
                "name": "save_policy_holder",
                "description": "Save the policy holder name and proceed to collect date of birth.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "policy_holder_name": {
                            "type": "string",
                            "description": "The full name of the insurance policy holder",
                        }
                    },
                    "required": ["policy_holder_name"],
                },
                "transition_callback": handle_collect_dob,
            },
        },
    ]

    return create_node(
        task_message=task_message,
        custom_functions=custom_functions,
        include_end=True,
    )


def create_collect_dob_node(patient_name: str, device_ordered: str) -> dict:
    """Create node for collecting policy holder's date of birth."""

    task_message = """For this step, collect the policy holder's date of birth.

Say something like: "Perfect, got it! And... what's the policy holder's date of birth?"

Wait for their response. Listen carefully to EXACTLY what date they say.

IMPORTANT - If they pause mid-sentence or seem to be thinking:
- DO NOT repeat or rephrase the question
- Simply say "Take your time..." or "No rush..." and wait
- Only re-ask if they explicitly ask you to repeat

Once they provide the COMPLETE date:
- You MUST repeat back the EXACT date they just told you
- Confirm warmly: "Okay great... so that's [repeat the EXACT date they said]. Did I get that right?"
- If they say YES or confirm, respond "Wonderful!" and use the save_dob function with the EXACT date
- Accept various date formats (month/day/year, spoken dates, etc.)

IMPORTANT - If they CORRECT the date:
- Acknowledge: "Oh, got it! So [corrected date]... thank you!"
- IMMEDIATELY use the save_dob function with the CORRECTED date
- Do NOT ask for confirmation again after a correction
"""

    custom_functions = [
        {
            "type": "function",
            "function": {
                "name": "save_dob",
                "description": "Save the date of birth and proceed to collect policy number.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "date_of_birth": {
                            "type": "string",
                            "description": "The policy holder's date of birth",
                        }
                    },
                    "required": ["date_of_birth"],
                },
                "transition_callback": handle_collect_policy_number,
            },
        },
    ]

    return create_node(
        task_message=task_message,
        custom_functions=custom_functions,
        include_end=True,
    )


def create_collect_policy_number_node(patient_name: str, device_ordered: str) -> dict:
    """Create node for collecting policy number."""

    task_message = """For this step, collect the insurance policy number.

Say something like: "Alright... now I'll need the policy number. Take your time — it should be on your insurance card."

Wait for their response.

IMPORTANT - If they pause while looking it up or reading:
- DO NOT repeat the question or prompt them again
- Stay silent or just say "Mmhmm..." and wait patiently
- Only speak if they ask you to repeat or seem confused

Once they provide the COMPLETE policy number:
- Read it back warmly: "Let me just read that back to make sure... [number]. Did I get that right?"
- If they say YES or confirm, respond "Perfect, thank you!" and use the save_policy_number function

IMPORTANT - When reading back numbers/codes:
- Read alphanumeric codes CHARACTER BY CHARACTER with pauses
- Example: "X12345678" should be read as "X... 1... 2... 3... 4... 5... 6... 7... 8"
- Example: "ABC123" should be read as "A... B... C... 1... 2... 3"
- Group long numbers in sets of 3-4 for clarity: "1234567890" as "1-2-3-4... 5-6-7... 8-9-0"

IMPORTANT - If they CORRECT the number:
- Acknowledge: "Oh, let me fix that... so it's [corrected number]. Got it!"
- IMMEDIATELY use the save_policy_number function with the CORRECTED number
- Do NOT ask for confirmation again after a correction
"""

    custom_functions = [
        {
            "type": "function",
            "function": {
                "name": "save_policy_number",
                "description": "Save the policy number and proceed to collect group number.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "policy_number": {
                            "type": "string",
                            "description": "The insurance policy number",
                        }
                    },
                    "required": ["policy_number"],
                },
                "transition_callback": handle_collect_group_number,
            },
        },
    ]

    return create_node(
        task_message=task_message,
        custom_functions=custom_functions,
        include_end=True,
    )


def create_collect_group_number_node(patient_name: str, device_ordered: str) -> dict:
    """Create node for collecting group number."""

    task_message = """For this step, collect the insurance group number.

Say something like: "Great! And the group number? That should be on there too... but no worries if you don't have one!"

Wait for their response.

IMPORTANT - If they pause while looking for it:
- DO NOT repeat the question
- Stay silent or say "Take your time..." and wait
- Only re-ask if they explicitly ask you to repeat

Once they provide the group number:
- Confirm warmly: "Okay... so the group number is [number]. Is that right?"
- If they say YES or confirm, respond "Got it!" and use the save_group_number function
- If they say they don't have one, respond cheerfully: "Oh, that's totally fine! Not all cards have one..." and use "N/A" or "none"

IMPORTANT - When reading back numbers/codes:
- Read alphanumeric codes CHARACTER BY CHARACTER with pauses
- Example: "GRP12345" should be read as "G... R... P... 1... 2... 3... 4... 5"
- Group long numbers in sets of 3-4 for clarity

IMPORTANT - If they CORRECT the number:
- Acknowledge: "Oh, my mistake! So it's [corrected number]... got it!"
- IMMEDIATELY use the save_group_number function with the CORRECTED number
- Do NOT ask for confirmation again after a correction
"""

    custom_functions = [
        {
            "type": "function",
            "function": {
                "name": "save_group_number",
                "description": "Save the group number and proceed to collect insurance provider name.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "group_number": {
                            "type": "string",
                            "description": "The insurance group number (or 'N/A' if none)",
                        }
                    },
                    "required": ["group_number"],
                },
                "transition_callback": handle_collect_insurance_provider,
            },
        },
    ]

    return create_node(
        task_message=task_message,
        custom_functions=custom_functions,
        include_end=True,
    )


def create_collect_insurance_provider_node(patient_name: str, device_ordered: str) -> dict:
    """Create node for collecting insurance provider/company name."""

    task_message = """For this step, collect the name of the insurance provider/company.

Say something like: "Almost done! You're doing great... last one — what's the name of your insurance company?"

Wait for their response. Listen carefully to EXACTLY what insurance name they say.

IMPORTANT - If they pause or seem to be thinking:
- DO NOT repeat the question
- Simply wait or say "Take your time..." 
- Only re-ask if they explicitly ask you to repeat

Once they provide the COMPLETE insurance provider name:
- You MUST repeat back the EXACT insurance name they just told you
- Confirm warmly: "So your insurance is through [repeat the EXACT name they said]... is that right?"
- If they say YES or confirm, respond enthusiastically "Perfect! That's everything I need!" and use the save_insurance_provider function with the EXACT name
- Common examples: Blue Cross Blue Shield, Aetna, UnitedHealthcare, Cigna, Humana, Medicare, Medicaid, etc.

IMPORTANT - If they CORRECT the insurance name:
- Acknowledge: "Oh, got it! So it's [corrected name]... thank you for clarifying!"
- IMMEDIATELY use the save_insurance_provider function with the CORRECTED name
- Do NOT ask for confirmation again after a correction
"""

    custom_functions = [
        {
            "type": "function",
            "function": {
                "name": "save_insurance_provider",
                "description": "Save the insurance provider name and finish the collection process.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "insurance_provider": {
                            "type": "string",
                            "description": "The name of the insurance company/provider",
                        }
                    },
                    "required": ["insurance_provider"],
                },
                "transition_callback": handle_finish_collection,
            },
        },
    ]

    return create_node(
        task_message=task_message,
        custom_functions=custom_functions,
        include_end=True,
    )
