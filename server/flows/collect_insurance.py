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
        policy_holder_name = args["policy_holder_name"]
        flow_manager.state["insurance_data"]["policy_holder_name"] = policy_holder_name
        # Update the patient_name in state to use the name they provided
        # This ensures we address them by their actual name for the rest of the call
        flow_manager.state["patient_name"] = policy_holder_name
        logger.info(f"Updated patient_name to: {policy_holder_name}")

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
        # Try to match against known payers - require 85%+ confidence
        best_match = payer_lookup.get_best_match(raw_provider, threshold=85.0)

        if best_match:
            matched_name = best_match.payer.display_name
            stedi_id = best_match.payer.stedi_id
            payer_id = best_match.payer.primary_payer_id
            match_score = best_match.score
            logger.info(
                f"Insurance provider matched: '{raw_provider}' -> '{matched_name}' (score: {match_score:.1f}%)"
            )
        else:
            # Log when we don't find a good match
            logger.info(f"No match found for '{raw_provider}' with >= 85% confidence")

    # If no good match (< 85%), ask the user to clarify
    if not matched_name:
        # Track retry count
        retry_count = flow_manager.state.get("insurance_retry_count", 0) + 1
        flow_manager.state["insurance_retry_count"] = retry_count

        logger.info(
            f"Asking user to clarify insurance name: '{raw_provider}' (retry #{retry_count})"
        )
        patient_name = flow_manager.state.get("patient_name", "the patient")
        device_ordered = flow_manager.state.get("device_ordered", "medical equipment")
        await flow_manager.set_node(
            "collect_insurance_provider",
            create_collect_insurance_provider_node(
                patient_name,
                device_ordered,
                is_retry=True,
                unclear_name=raw_provider,
                retry_count=retry_count,
            ),
        )
        return

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

    # Get the raw name before clearing pending state
    pending = flow_manager.state.get("pending_insurance", {})
    raw_name = pending.get("raw_name", "")

    # Clear pending state
    if "pending_insurance" in flow_manager.state:
        del flow_manager.state["pending_insurance"]

    # Track retry count
    retry_count = flow_manager.state.get("insurance_retry_count", 0) + 1
    flow_manager.state["insurance_retry_count"] = retry_count

    patient_name = flow_manager.state.get("patient_name", "the patient")
    device_ordered = flow_manager.state.get("device_ordered", "medical equipment")

    # Go back to insurance collection with a clarification prompt
    await flow_manager.set_node(
        "collect_insurance_provider",
        create_collect_insurance_provider_node(
            patient_name,
            device_ordered,
            is_retry=True,
            unclear_name=raw_name,
            retry_count=retry_count,
        ),
    )


@handle_flow_error
async def handle_save_unverified_direct(
    args: Dict, result: dict, flow_manager: FlowManager
):
    """Handle directly saving an unverified insurance name (skip lookup)."""
    logger.info(f"Saving unverified insurance directly: {args}")

    insurance_provider = args.get("insurance_provider", "Unknown")

    flow_manager.state["insurance_data"]["insurance_provider"] = insurance_provider
    flow_manager.state["insurance_data"]["insurance_provider_unverified"] = True
    logger.info(f"Insurance provider saved (unverified): '{insurance_provider}'")

    # Log all collected data
    insurance_data = flow_manager.state.get("insurance_data", {})
    logger.info(f"All insurance data collected: {insurance_data}")

    # Transition to end conversation
    from flows.end import handle_end_conversation

    await handle_end_conversation(args, result, flow_manager)


@handle_flow_error
async def handle_finish_collection(args: Dict, result: dict, flow_manager: FlowManager):
    """Handle finishing collection when no database match was found."""
    logger.info(f"Finishing collection with raw provider: {args}")

    # Get the raw name from state (pending_insurance) since we don't include it in prompt
    pending = flow_manager.state.get("pending_insurance", {})
    raw_name = pending.get("raw_name") or args.get("insurance_provider", "Unknown")

    flow_manager.state["insurance_data"]["insurance_provider"] = raw_name
    flow_manager.state["insurance_data"]["insurance_provider_unverified"] = True
    logger.warning(f"Insurance provider stored as unverified: '{raw_name}'")

    # Clean up pending state
    if "pending_insurance" in flow_manager.state:
        del flow_manager.state["pending_insurance"]

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

Ask: "<emotion value="curious"/>Great! <break time="200ms"/> So first things first. <break time="200ms"/> Could you tell me the name of the policy holder on your insurance?"

Wait for their response.

If they pause or give incomplete response (like "It's..." or "The name is..."):
- Just say "<emotion value="calm"/>Take your time..." and wait
- Do NOT repeat the question

HANDLING PLAYFUL/SILLY RESPONSES:
If they give a silly name (like "Batman", "Superman", "Darth Vader", random words, etc.):
- Respond with [laughter]! Say "[laughter] Oh, that's a good one!" or "[laughter] Okay, I see you..."
- Then gently ask for real info: "<break time="200ms"/> But seriously, what's the name on your insurance card?"
- Stay warm and playful but redirect

CRITICAL RULE - When they give you a REAL name (e.g., "John Smith"):
1. Say their name out loud briefly and IMMEDIATELY save
2. Say: "<emotion value="excited"/>Got it, [NAME]!" and IMMEDIATELY call save_policy_holder
3. Do NOT ask for confirmation - just move on

The policy holder may be DIFFERENT from {patient_name}. Use what they tell you.
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

Say something like: "<emotion value="excited"/>Perfect, got it! <break time="300ms"/> And what's the policy holder's date of birth?"

Wait for their response. Listen carefully to EXACTLY what date they say.

IMPORTANT - If they pause mid-sentence or seem to be thinking:
- DO NOT repeat or rephrase the question
- Simply say "<emotion value="calm"/>Take your time..." and wait
- Only re-ask if they explicitly ask you to repeat

HANDLING PLAYFUL/SILLY RESPONSES:
If they give a silly answer (like "the year 3000", "yesterday", random nonsense, etc.):
- Respond with [laughter]! Say "[laughter] Oh, nice try!" or "[laughter] You're funny..."
- Then gently redirect: "<break time="200ms"/> But for real, what's the date of birth on the insurance?"
- Stay warm and keep it light

Once they provide the COMPLETE date:
- Convert their response to mm/dd/yyyy format internally
- Say "<emotion value="excited"/>Got it!" and IMMEDIATELY call save_dob with the date
- Do NOT ask for confirmation - just move on

IMPORTANT - Date format conversion examples:
- "June 8th, 1996" -> save as "06/08/1996"
- "August 15 1990" -> save as "08/15/1990"
- "6/8/96" -> save as "06/08/1996"
- Always use 4-digit years
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

Say something like: "Alright. <break time="300ms"/> Now I'll need the policy number. <break time="200ms"/> Take your time. <break time="200ms"/> It should be on your insurance card."

Wait for their response.

CRITICAL - HANDLING LETTER-BY-LETTER SPELLING:
If they're spelling it out one letter/number at a time (e.g., "X", then "1", then "2"):
- Say "Mmhmm..." or "Got it..." after each piece and WAIT for more
- Do NOT try to confirm or save after just one letter
- Keep listening until they indicate they're done (pause, say "that's it", etc.)
- Collect ALL the pieces before reading back the full number

HANDLING PLAYFUL/SILLY RESPONSES:
If they give a silly answer (like "a million", "12345678910", "my phone number", random words, etc.):
- Respond with [laughter]! Say "[laughter] Oh, I wish it was that easy!" or "[laughter] Good one..."
- Then redirect: "<break time="200ms"/> But what's the actual policy number on your card?"
- Stay playful but get the real info

HANDLING FRUSTRATION (sighing, "ugh", "this is so long", impatient tone):
- Use <emotion value="sympathetic"/> and acknowledge: "I know. <break time="200ms"/> Insurance cards can be a maze of numbers."
- Offer help: "It's usually the longest number on there. <break time="200ms"/> Often labeled Member ID or Policy Number."
- Reassure: "We're getting close to the end, I promise!"
- Be patient: "<emotion value="calm"/>No rush. <break time="200ms"/> Take your time finding it."

IMPORTANT - If they pause while looking it up or reading:
- DO NOT repeat the question or prompt them again
- Stay silent or just say "Mmhmm..." and wait patiently
- Only speak if they ask you to repeat or seem confused

Once they provide the COMPLETE policy number (multiple characters, or they indicate they're done):
- Say "<emotion value="excited"/>Got it!" and IMMEDIATELY call save_policy_number
- Do NOT ask for confirmation - just move on
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

Say something like: "<emotion value="excited"/>Great! <break time="200ms"/> And the group number? <break time="200ms"/> That should be on there too. <break time="200ms"/> But no worries if you don't have one!"

Wait for their response.

CRITICAL - HANDLING LETTER-BY-LETTER SPELLING:
If they're spelling it out one letter/number at a time (e.g., "G", then "R", then "P"):
- Say "Mmhmm..." or "Got it..." after each piece and WAIT for more
- Do NOT try to confirm or save after just one letter
- Keep listening until they indicate they're done (pause, say "that's it", etc.)
- Collect ALL the pieces before reading back the full number

HANDLING PLAYFUL/SILLY/FLIRTY RESPONSES:
If they give a silly answer, make jokes, flirt, or go off-topic (like "I want to see you", random words, etc.):
- Respond with [laughter]! Say "[laughter] You're too sweet!" or "[laughter] You're keeping me entertained..."
- Then redirect firmly: "<break time="200ms"/> But back to business. <break time="200ms"/> Is there a group number on your card, or no?"
- If they say no after being redirected, call save_group_number with "N/A" immediately
- Stay warm but keep the conversation moving forward

HANDLING CONFUSION ("what's a group number?", "I don't see it", uncertain tone):
- Use <emotion value="calm"/> and help them: "No worries! <break time="200ms"/> It might say Group or GRP on your card. <break time="200ms"/> Sometimes it's near the policy number."
- Reassure: "If you don't see one, that's totally fine! <break time="200ms"/> Not all cards have it."
- Be patient: "<emotion value="calm"/>Take your time looking. <break time="200ms"/> It's usually a shorter number than the policy number."

IMPORTANT - If they pause while looking for it:
- DO NOT repeat the question
- Stay silent or say "<emotion value="calm"/>Take your time..." and wait
- Only re-ask if they explicitly ask you to repeat

Once they provide the COMPLETE group number (multiple characters, or they indicate they're done):
- Say "<emotion value="excited"/>Got it!" and IMMEDIATELY call save_group_number
- Do NOT ask for confirmation - just move on

CRITICAL - If they say they DON'T HAVE a group number (e.g., "I don't have one", "there's no group number", "I don't see one", "no", "nope"):
- Say something brief like: "<emotion value="calm"/>No problem at all!"
- You MUST call save_group_number with "N/A" IN THE SAME RESPONSE - do not wait for another turn
- The ONLY way to proceed is by calling save_group_number - there is no other transition
"""

    custom_functions = [
        {
            "type": "function",
            "function": {
                "name": "save_group_number",
                "description": "Save the group number and proceed. Call this when: (1) user confirms their group number, OR (2) user says they don't have one (pass 'N/A'). This is the ONLY way to move forward.",
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
    patient_name: str,
    device_ordered: str,
    is_retry: bool = False,
    unclear_name: str = "",
    retry_count: int = 0,
) -> dict:
    """Create node for collecting insurance provider/company name."""

    if is_retry and retry_count >= 1:
        # After 1 failed attempt, offer to just note it down
        task_message = """We've tried but can't find their insurance in our system. Offer to just note it down.

Say something like: "Hmm. <break time="200ms"/> It's not coming up in our system. <break time="200ms"/> But that's totally okay! <break time="200ms"/> It might just not be listed yet. <break time="300ms"/> I can take a note of exactly what it says on your card. <break time="200ms"/> What's the name of your insurance company exactly as it appears?"

Wait for their response.

Once they provide the name:
- Say "<emotion value="excited"/>Perfect! <break time="200ms"/> I've got that noted down. <break time="200ms"/> We'll verify it on our end."
- Use the save_unverified_insurance function to save it (no need to look it up again)
"""
    elif is_retry:
        task_message = """We couldn't find that insurance in our system. Ask them to clarify.

Say something like: "Hmm. <break time="200ms"/> I'm not finding that one. <break time="200ms"/> Could you tell me the exact name as it appears on your insurance card?"

Wait for their response and listen carefully.

Once they provide the insurance name:
- Say "Let me check that..." 
- Use the lookup_insurance_provider function with exactly what they said
"""
    else:
        task_message = """For this step, collect the name of the insurance provider/company.

Say something like: "<emotion value="excited"/>Almost done! <break time="200ms"/> You're doing great. <break time="300ms"/> Last one. <break time="200ms"/> What's the name of your insurance company?"

Wait for their response. Listen carefully to EXACTLY what insurance name they say.

IMPORTANT - If they pause or seem to be thinking:
- DO NOT repeat the question
- Simply wait or say "<emotion value="calm"/>Take your time..." 
- Only re-ask if they explicitly ask you to repeat

HANDLING PLAYFUL/SILLY RESPONSES:
If they give a silly or fake insurance name (like random words, jokes, made-up names):
- Respond with [laughter]! Say "[laughter] Oh, that would be a fun insurance company!" or "[laughter] I don't think we have that one in our system..."
- Then redirect warmly: "<break time="200ms"/> But really, what insurance company is it? <break time="200ms"/> Should be on your card."
- Stay playful but get the real info

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

    # Add save_unverified option for retry scenarios
    if is_retry and retry_count >= 1:
        custom_functions.append(
            {
                "type": "function",
                "function": {
                    "name": "save_unverified_insurance",
                    "description": "Save the insurance name as-is when we can't find it in our system. We'll verify it later.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "insurance_provider": {
                                "type": "string",
                                "description": "The exact insurance name as it appears on their card",
                            }
                        },
                        "required": ["insurance_provider"],
                    },
                    "transition_callback": handle_save_unverified_direct,
                },
            }
        )

    return create_node(
        task_message=task_message,
        custom_functions=custom_functions,
        include_end=True,
    )


def create_confirm_insurance_node(
    patient_name: str, matched_name: Optional[str], raw_name: str
) -> dict:
    """Create node for confirming the matched insurance provider."""

    # Note: We intentionally do NOT include raw_name in the prompt to avoid
    # triggering content filters with unusual user input. The matched_name
    # from our database is safe to include.

    if matched_name:
        task_message = f"""We found a match in our database! Accept it and move on.

We matched their insurance to: "{matched_name}"

Say: "<emotion value="excited"/>Got it, {matched_name}! <break time="200ms"/> That's everything I need!" and IMMEDIATELY call confirm_insurance
- Do NOT ask for confirmation
- Just call the function and move on
"""
    else:
        task_message = """We couldn't find an exact match in our database for their insurance.

Say: "<emotion value="calm"/>I don't see that one in our system. <break time="200ms"/> But that's okay! <break time="200ms"/> I'll make a note of it." and IMMEDIATELY call save_unverified_insurance
- Do NOT ask for confirmation
- Just call the function and move on
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
                "description": "Save the insurance name as-is (unverified) when no database match was found. The name is retrieved from the previous lookup.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
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
