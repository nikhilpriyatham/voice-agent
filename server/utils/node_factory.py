"""Node factory utilities for creating flow nodes."""

from typing import Any, Callable, Dict, List, Optional, TypedDict

from pipecat_flows import FlowManager


class NodeFunction(TypedDict):
    """Type definition for a node function/transition."""

    type: str
    function: dict


def create_node(
    task_message: str,
    system_message: str = None,
    custom_functions: List[NodeFunction] = None,
    include_default_transitions: bool = True,
    include_end: bool = True,
    pre_actions: List[dict] = None,
    post_actions: List[dict] = None,
) -> dict:
    """
    Create a complete node with system and task messages, and optional transitions.

    Args:
        task_message: The task message content for the node (instructions for this step)
        system_message: Optional system message content for the node (role context)
        custom_functions: Custom functions/transitions to be added to the node
        include_default_transitions: Whether to include default transitions
        include_end: Whether to include the end_conversation transition
        pre_actions: Optional pre actions to be included in the node
        post_actions: Optional post actions to be included in the node

    Returns:
        A complete node configuration dictionary
    """
    node_content = {"task_messages": [{"role": "system", "content": task_message}]}

    # Only add role_messages if system_message is provided
    if system_message:
        node_content["role_messages"] = [{"role": "system", "content": system_message}]

    # Add pre actions if provided
    if pre_actions:
        node_content["pre_actions"] = pre_actions

    # Add post actions if provided
    if post_actions:
        node_content["post_actions"] = post_actions

    # Add custom functions
    if custom_functions:
        # Ensure all custom functions have "strict": True
        for func in custom_functions:
            if "function" in func and isinstance(func["function"], dict):
                func["function"]["strict"] = True
        node_content["functions"] = custom_functions

    # Add default transitions if requested
    if include_default_transitions:
        return _add_default_transitions(node_content, include_end=include_end)

    return node_content


def _add_default_transitions(
    node_content: dict,
    include_end: bool = True,
) -> dict:
    """
    Add default transitions to a node.

    Args:
        node_content: The base node content dictionary
        include_end: Whether to include the end_conversation transition

    Returns:
        A node configuration dictionary with default transitions added
    """
    default_transitions = []

    if include_end:
        # Lazy import to avoid circular dependency
        from flows.end import handle_end_conversation

        default_transitions.append(
            {
                "type": "function",
                "function": {
                    "name": "end_conversation",
                    "description": "Use this function to wrap up the conversation when the caller wants to end the call or has no other questions.",
                    "parameters": {"type": "object", "properties": {}},
                    "strict": True,
                    "transition_callback": handle_end_conversation,
                },
            }
        )

    # Add any custom functions first, then default transitions
    if "functions" in node_content:
        node_content["functions"].extend(default_transitions)
    else:
        node_content["functions"] = default_transitions

    return node_content


def create_function_transition(
    name: str, description: str, transition_callback: Callable, parameters: dict = None
) -> NodeFunction:
    """
    Create a function transition object.

    Args:
        name: The name of the function
        description: The description of the function
        transition_callback: The callback function to be called when this function is triggered
        parameters: Optional parameters for the function

    Returns:
        A NodeFunction object
    """
    if parameters is None:
        parameters = {"type": "object", "properties": {}}

    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": parameters,
            "strict": True,
            "transition_callback": transition_callback,
        },
    }
