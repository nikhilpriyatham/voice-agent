"""Collect insurance flow - Collects insurance details one field at a time."""

from typing import Dict, Optional

from loguru import logger
from pipecat_flows import FlowManager
from utils.date_parser import parse_and_format_date
from utils.node_factory import create_node
from utils.payer_lookup import PayerLookup

from flows.utils import handle_flow_error

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
        "collect_policy_holder",
        create_collect_policy_holder_node(patient_name, device_ordered),
    )


@handle_flow_error
async def handle_collect_dob(args: Dict, result: dict, flow_manager: FlowManager):
    """Handle collecting date of birth after policy holder name."""
    logger.info(f"Collected policy holder name: {args}")

    # Store the collected data
    if "policy_holder_name" in args:
        flow_manager.state["insurance_data"]["policy_holder_name"] = args[
            "policy_holder_name"
        ]

    patient_name = flow_manager.state.get("patient_name", "the patient")
    device_ordered = flow_manager.state.get("device_ordered", "medical equipment")
    await flow_manager.set_node(
        "collect_dob", create_collect_dob_node(patient_name, device_ordered)
    )


@handle_flow_error
async def handle_collect_policy_number(
    args: Dict, result: dict, flow_manager: FlowManager
):
    """Handle collecting policy number after DOB."""
    logger.info(f"Collected DOB: {args}")

    # Store the collected data with date validation
    if "date_of_birth" in args:
        raw_dob = args["date_of_birth"]
        # Parse and format to mm/dd/yyyy
        formatted_dob = parse_and_format_date(raw_dob)
        if formatted_dob:
            flow_manager.state["insurance_data"]["date_of_birth"] = formatted_dob
            logger.info(f"DOB formatted: '{raw_dob}' -> '{formatted_dob}'")
        else:
            # If parsing fails, store raw value
            flow_manager.state["insurance_data"]["date_of_birth"] = raw_dob
            logger.warning(f"Could not parse DOB: '{raw_dob}', storing as-is")

    patient_name = flow_manager.state.get("patient_name", "the patient")
    device_ordered = flow_manager.state.get("device_ordered", "medical equipment")
    await flow_manager.set_node(
        "collect_policy_number",
        create_collect_policy_number_node(patient_name, device_ordered),
    )


@handle_flow_error
async def handle_collect_group_number(
    args: Dict, result: dict, flow_manager: FlowManager
):
    """Handle collecting group number after policy number."""
    logger.info(f"Collected policy number: {args}")

    # Store the collected data
    if "policy_number" in args:
        flow_manager.state["insurance_data"]["policy_number"] = args["policy_number"]

    patient_name = flow_manager.state.get("patient_name", "the patient")
    device_ordered = flow_manager.state.get("device_ordered", "medical equipment")
    await flow_manager.set_node(
        "collect_group_number",
        create_collect_group_number_node(patient_name, device_ordered),
    )


@handle_flow_error
async def handle_collect_insurance_provider(
    args: Dict, result: dict, flow_manager: FlowManager
):
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
async def handle_lookup_insurance(args: Dict, result: dict, flow_manager: FlowManager):
    """Handle looking up insurance provider in our database."""
    logger.info(f"Looking up insurance provider: {args}")

    raw_provider = args.get("insurance_provider", "")
    payer_lookup: Optional[PayerLookup] = flow_manager.state.get("payer_lookup")

    matched_name = None
    stedi_id = None
    payer_id = None
    match_score = 0.0

    if payer_lookup and raw_provider:
        # Try to match against known payers
        best_match = payer_lookup.get_best_match(raw_provider, threshold=70.0)
        if best_match:
            matched_name = best_match.payer.display_name
            stedi_id = best_match.payer.stedi_id
            payer_id = best_match.payer.primary_payer_id
            match_score = best_match.score
            logger.info(
                f"Insurance provider matched: '{raw_provider}' -> '{matched_name}' (score: {match_score:.1f}%)"
            )

    # Store lookup results in state for the confirmation node
    flow_manager.state["pending_insurance"] = {
        "raw_name": raw_provider,
        "matched_name": matched_name,
        "stedi_id": stedi_id,
        "payer_id": payer_id,
        "match_score": match_score,
    }

    patient_name = flow_manager.state.get("patient_name", "the patient")
    await flow_manager.set_node(
        "confirm_insurance",
        create_confirm_insurance_node(patient_name, matched_name, raw_provider),
    )


@handle_flow_error
async def handle_confirm_insurance(args: Dict, result: dict, flow_manager: FlowManager):
    """Handle user confirming the matched insurance provider."""
    logger.info(f"User confirmed insurance: {args}")

    pending = flow_manager.state.get("pending_insurance", {})

    # Store the confirmed insurance data
    if pending.get("matched_name"):
        flow_manager.state["insurance_data"]["insurance_provider"] = pending[
            "matched_name"
        ]
        flow_manager.state["insurance_data"]["insurance_provider_stedi_id"] = pending[
            "stedi_id"
        ]
        flow_manager.state["insurance_data"]["insurance_provider_payer_id"] = pending[
            "payer_id"
        ]
        flow_manager.state["insurance_data"]["insurance_provider_match_score"] = (
            pending["match_score"]
        )
    else:
        # No match was found, use raw name
        flow_manager.state["insurance_data"]["insurance_provider"] = pending["raw_name"]
        flow_manager.state["insurance_data"]["insurance_provider_unverified"] = True

    # Clean up pending state
    del flow_manager.state["pending_insurance"]

    # Log all collected data
    insurance_data = flow_manager.state.get("insurance_data", {})
    logger.info(f"All insurance data collected: {insurance_data}")

    # Transition to end conversation
    from flows.end import handle_end_conversation

    await handle_end_conversation(args, result, flow_manager)


@handle_flow_error
async def handle_reject_insurance_match(
    args: Dict, result: dict, flow_manager: FlowManager
):
    """Handle user rejecting the matched insurance - ask them to clarify."""
    logger.info(f"User rejected insurance match: {args}")

    # Clear pending and go back to collect insurance
    if "pending_insurance" in flow_manager.state:
        del flow_manager.state["pending_insurance"]

    patient_name = flow_manager.state.get("patient_name", "the patient")
    device_ordered = flow_manager.state.get("device_ordered", "medical equipment")

    # Go back to insurance collection with a clarification prompt
    await flow_manager.set_node(
        "collect_insurance_provider",
        create_collect_insurance_provider_node(
            patient_name, device_ordered, is_retry=True
        ),
    )


@handle_flow_error
async def handle_finish_collection(args: Dict, result: dict, flow_manager: FlowManager):
    """Handle finishing collection when no database match was found."""
    logger.info(f"Finishing collection with raw provider: {args}")

    if "insurance_provider" in args:
        flow_manager.state["insurance_data"]["insurance_provider"] = args[
            "insurance_provider"
        ]
        flow_manager.state["insurance_data"]["insurance_provider_unverified"] = True
        logger.warning(
            f"Insurance provider stored as unverified: '{args['insurance_provider']}'"
        )

    # Log all collected data
    insurance_data = flow_manager.state.get("insurance_data", {})
    logger.info(f"All insurance data collected: {insurance_data}")

    # Transition to end conversation
    from flows.end import handle_end_conversation

    await handle_end_conversation(args, result, flow_manager)


# ============ Node Creation Functions ============


def create_collect_policy_holder_node(patient_name: str, device_ordered: str) -> dict:
    """Create node for collecting policy holder name."""

    task_message = f"""Collect the insurance policy holder's name from {patient_name}.

Ask: "Great! So... first things first — could you tell me the name of the policy holder on your insurance?"

Wait for their response.

If they pause or give incomplete response (like "It's..." or "The name is..."):
- Just say "Take your time..." and wait
- Do NOT repeat the question

CRITICAL RULE - When they give you a name (e.g., "John Smith"):
1. You MUST say their name out loud in your response
2. Say: "Wonderful! So that's John Smith... let me just make sure I got that right. Is that correct?"
3. NEVER say "So that's..." without the actual name - always include the name!

CRITICAL - WHEN THEY CONFIRM (say "yes", "yeah", "yep", "correct", "that's right", "uh-huh", etc.):
- Say "Perfect!" and IMMEDIATELY call save_policy_holder with the name
- Do NOT repeat the confirmation question
- Do NOT ask again if it's correct
- Just call the function and move on

The policy holder may be DIFFERENT from {patient_name}. Use what they tell you.

If they correct you:
- Say the corrected name: "Oh, got it! So that's Sarah Johnson!"
- Call save_policy_holder immediately with the corrected name
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
- Convert their response to mm/dd/yyyy format for confirmation
- For example: "June 8th, 1996" becomes "06/08/1996"
- Confirm: "Okay great... so that's 06/08/1996. Did I get that right?"

CRITICAL - WHEN THEY CONFIRM (say "yes", "yeah", "yep", "correct", "that's right", etc.):
- Say "Wonderful!" and IMMEDIATELY call save_dob with the date
- Do NOT repeat the confirmation question
- Do NOT ask again if it's correct
- Just call the function and move on

IMPORTANT - Date format conversion examples:
- "June 8th, 1996" -> save as "06/08/1996"
- "August 15 1990" -> save as "08/15/1990"
- "6/8/96" -> save as "06/08/1996"
- Always use 4-digit years

IMPORTANT - If they CORRECT the date:
- Acknowledge: "Oh, got it! So [corrected date in mm/dd/yyyy]... thank you!"
- IMMEDIATELY use the save_dob function with the CORRECTED date in mm/dd/yyyy format
- Do NOT ask for confirmation again after a correction
"""

    custom_functions = [
        {
            "type": "function",
            "function": {
                "name": "save_dob",
                "description": "Save the date of birth in mm/dd/yyyy format and proceed to collect policy number.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "date_of_birth": {
                            "type": "string",
                            "description": "The policy holder's date of birth in mm/dd/yyyy format (e.g., 06/08/1996)",
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

CRITICAL - WHEN THEY CONFIRM (say "yes", "yeah", "yep", "correct", "that's right", etc.):
- Say "Perfect, thank you!" and IMMEDIATELY call save_policy_number
- Do NOT repeat the confirmation question
- Do NOT ask again if it's correct
- Just call the function and move on

IMPORTANT - When reading back numbers/codes:
- Read numbers naturally, in pairs or small groups like a human would
- Example: "X1234567" → "X, twelve thirty-four, five sixty-seven"
- Example: "ABC123" → "A-B-C, one twenty-three"
- Be conversational, not robotic

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

CRITICAL - WHEN THEY CONFIRM (say "yes", "yeah", "yep", "correct", "that's right", etc.):
- Say "Got it!" and IMMEDIATELY call save_group_number
- Do NOT repeat the confirmation question
- Do NOT ask again if it's correct
- Just call the function and move on

If they say they don't have one:
- Respond warmly: "Oh, no problem at all! Not everyone has one on their card..."
- IMMEDIATELY call save_group_number with "N/A"

IMPORTANT - When reading back numbers/codes:
- Read numbers naturally, in pairs or small groups like a human would
- Example: "GRP12345" → "G-R-P, twelve three forty-five" or "G-R-P, one-two-three-four-five"
- Be conversational, not robotic

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


def create_collect_insurance_provider_node(
    patient_name: str, device_ordered: str, is_retry: bool = False
) -> dict:
    """Create node for collecting insurance provider/company name."""

    if is_retry:
        task_message = """The user said that wasn't their insurance. Ask them to clarify.

Say something like: "Oh, I'm sorry about that! Could you tell me the name of your insurance company again? Maybe spell it out if it's an unusual name?"

Wait for their response and listen carefully.

Once they provide the insurance name:
- Use the lookup_insurance_provider function with exactly what they said
- We'll check our database for a match
"""
    else:
        task_message = """For this step, collect the name of the insurance provider/company.

Say something like: "Almost done! You're doing great... last one — what's the name of your insurance company?"

Wait for their response. Listen carefully to EXACTLY what insurance name they say.

IMPORTANT - If they pause or seem to be thinking:
- DO NOT repeat the question
- Simply wait or say "Take your time..." 
- Only re-ask if they explicitly ask you to repeat

HANDLING INSURANCE NAMES:
- Common abbreviations: BCBS = Blue Cross Blue Shield, UHC = UnitedHealthcare, etc.
- If they say just "Blue Cross" or "BCBS", that's sufficient - accept it
- If they give a partial name that's recognizable, accept it

Once they provide the insurance provider name:
- Say "Let me look that up in our system..." 
- Use the lookup_insurance_provider function with exactly what they said
- We'll check our database and confirm the match with them
"""

    custom_functions = [
        {
            "type": "function",
            "function": {
                "name": "lookup_insurance_provider",
                "description": "Look up the insurance provider in our database to verify the name.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "insurance_provider": {
                            "type": "string",
                            "description": "The name of the insurance company/provider as the user said it",
                        }
                    },
                    "required": ["insurance_provider"],
                },
                "transition_callback": handle_lookup_insurance,
            },
        },
    ]

    return create_node(
        task_message=task_message,
        custom_functions=custom_functions,
        include_end=True,
    )


def create_confirm_insurance_node(
    patient_name: str, matched_name: Optional[str], raw_name: str
) -> dict:
    """Create node for confirming the matched insurance provider."""

    if matched_name:
        task_message = f"""We found a match in our database! Confirm with the user.

The user said: "{raw_name}"
We found in our system: "{matched_name}"

Say something like: "I found {matched_name} in our system — is that the one you meant?"

CRITICAL - WHEN THEY CONFIRM (say "yes", "yeah", "yep", "correct", "that's right", "that's it", etc.):
- Say "Perfect! That's everything I need!" and IMMEDIATELY call confirm_insurance
- Do NOT repeat the question or ask again
- Just call the function and move on

If they say NO or that's not right:
- Say "Oh, I'm sorry about that!" and IMMEDIATELY call reject_insurance_match
"""
    else:
        task_message = f"""We couldn't find an exact match in our database.

The user said: "{raw_name}"

Say something like: "I don't see {raw_name} in our system, but that's okay! I'll make a note of it and we can verify it on our end. So your insurance is through {raw_name}... is that right?"

CRITICAL - WHEN THEY CONFIRM (say "yes", "yeah", "yep", "correct", "that's right", etc.):
- IMMEDIATELY call save_unverified_insurance with "{raw_name}"
- Do NOT repeat the question or ask again
- Just call the function and move on

If they say NO or want to correct it:
- IMMEDIATELY call reject_insurance_match
"""

    custom_functions = [
        {
            "type": "function",
            "function": {
                "name": "confirm_insurance",
                "description": "Confirm the matched insurance provider and finish collection.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
                "transition_callback": handle_confirm_insurance,
            },
        },
        {
            "type": "function",
            "function": {
                "name": "reject_insurance_match",
                "description": "User says this is NOT their insurance - go back and ask again.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
                "transition_callback": handle_reject_insurance_match,
            },
        },
        {
            "type": "function",
            "function": {
                "name": "save_unverified_insurance",
                "description": "Save the insurance name as-is (unverified) when no database match was found.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "insurance_provider": {
                            "type": "string",
                            "description": "The insurance name to save",
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
