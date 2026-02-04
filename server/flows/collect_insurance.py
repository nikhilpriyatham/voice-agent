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
        # Try to match against known payers - require 78%+ confidence (optimized threshold)
        best_match = payer_lookup.get_best_match(raw_provider, threshold=78.0)

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
            logger.info(f"No match found for '{raw_provider}' with >= 78% confidence")

    # If no good match (< 78%), ask the user to clarify
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

Ask: "Great! So first things first... could you tell me the name of the policy holder on your insurance?"

Wait for their response.

If they pause or give incomplete response (like "It's..." or "The name is..."):
- Just say "Take your time..." and wait
- Do NOT repeat the question

HANDLING PLAYFUL/SILLY RESPONSES:
If they give a silly name (like "Batman", "Superman", "Darth Vader", random words, etc.):
- Respond with [laughter]! Say "[laughter] Oh, that's a good one!" or "[laughter] Okay, I see you..."
- Then gently ask for real info: "But seriously, what's the name on your insurance card?"
- Stay warm and playful but redirect

CRITICAL RULE - When they give you a REAL name (e.g., "John Smith"):
1. Say their name out loud briefly and IMMEDIATELY save
2. Say: "Got it, [NAME]!" and IMMEDIATELY call save_policy_holder
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

    task_message = """Collect the policy holder's date of birth.

Say: "Perfect, got it! And... what's the policy holder's date of birth?"

Wait for response.

If spelling digit-by-digit: Say "Mmhmm..." after each piece. When they pause, ask "Is that the full date?"

If silly answer: [laughter] then redirect: "But for real, what's the date of birth?"

When they provide complete date: Call save_dob immediately in mm/dd/yyyy format (4-digit years).
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

Say something like: "Alright... now I'll need the policy number. Take your time, it should be on your insurance card."

Wait for their response.

If they're spelling it letter-by-letter, say "Mmhmm..." after each piece. If they pause, ask: "Is that the full number?"

If they give a silly answer, respond with [laughter] and redirect: "But what's the actual policy number?"

When they provide a policy number, call save_policy_number immediately with what they said.
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

    task_message = """Collect the insurance group number.

Say: "Great! And the group number? That should be on there too... but no worries if you don't have one!"

Wait for response.

If spelling letter-by-letter: Say "Mmhmm..." after each piece. If they pause, ask "Is that all?"

If silly answer: Respond with [laughter] and redirect: "But back to business... is there a group number?"

If confused: Help them: "It might say Group or GRP... if you don't see one, that's fine!"

When they confirm complete or say they don't have one: Call save_group_number immediately (use "N/A" if none).
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
        task_message = """Can't find their insurance. Offer to note it down.

Say: "Hmm... it's not coming up. But that's okay! I can note what's on your card... what's the exact name?"

When they provide it: Say "Perfect! I've got that noted..." and call save_unverified_insurance.
"""
    elif is_retry:
        task_message = """Not found. Ask to clarify.

Say: "Hmm... I'm not finding that one. Could you tell me the exact name on your card?"

When they provide it: Say "Let me check..." and call lookup_insurance_provider.
"""
    else:
        task_message = """Collect the insurance provider/company name.

Say: "Almost done! You're doing great... last one. What's the name of your insurance company?"

Wait for response. If they pause, say "Take your time..."

If silly answer: [laughter] then redirect: "But really, what insurance is it?"

Accept abbreviations (BCBS, UHC, etc.) and partial names.

When they provide the name: Say "Let me look that up..." and call lookup_insurance_provider with what they said.
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

Say: "Got it, {matched_name}! That's everything I need!" and IMMEDIATELY call confirm_insurance
- Do NOT ask for confirmation
- Just call the function and move on
"""
    else:
        task_message = """We couldn't find an exact match in our database for their insurance.

Say: "I don't see that one in our system... but that's okay! I'll make a note of it." and IMMEDIATELY call save_unverified_insurance
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
