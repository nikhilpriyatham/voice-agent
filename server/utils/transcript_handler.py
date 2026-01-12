"""
Transcript handler for managing conversation transcripts.

This module handles transcript events from the TranscriptProcessor
and stores conversation messages for later use.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List

from loguru import logger


@dataclass
class TranscriptMessage:
    """Represents a single message in the transcript."""

    role: str  # "user" or "assistant"
    content: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class TranscriptHandler:
    """Handles transcript updates and stores conversation messages."""

    def __init__(self):
        self.messages: List[TranscriptMessage] = []
        self._current_user_text: str = ""
        self._current_assistant_text: str = ""

    async def on_transcript_update(self, processor, frame):
        """
        Handle transcript update events from TranscriptProcessor.

        Args:
            processor: The TranscriptProcessor instance
            frame: The transcript frame containing the update
        """
        try:
            # Extract transcript data from frame
            if hasattr(frame, "text") and frame.text:
                role = getattr(frame, "role", "user")
                text = frame.text.strip()

                if not text:
                    return

                # Check if this is a final transcript or interim
                is_final = getattr(frame, "is_final", True)

                if role == "user":
                    if is_final:
                        self._add_message("user", text)
                        self._current_user_text = ""
                    else:
                        self._current_user_text = text
                elif role == "assistant":
                    if is_final:
                        self._add_message("assistant", text)
                        self._current_assistant_text = ""
                    else:
                        self._current_assistant_text = text

        except Exception as e:
            logger.error(f"Error handling transcript update: {e}")

    def _add_message(self, role: str, content: str):
        """Add a message to the transcript."""
        if content.strip():
            msg = TranscriptMessage(role=role, content=content)
            self.messages.append(msg)
            logger.debug(f"Transcript [{role}]: {content[:50]}...")

    def get_transcript_text(self) -> str:
        """Get the full transcript as formatted text."""
        transcript_text = ""
        for msg in self.messages:
            timestamp = f"[{msg.timestamp}] " if msg.timestamp else ""
            transcript_text += f"{timestamp}{msg.role}: {msg.content}\n"
        return transcript_text

    def get_messages_for_context(self) -> List[dict]:
        """Get messages formatted for LLM context."""
        return [{"role": msg.role, "content": msg.content} for msg in self.messages]

    def clear(self):
        """Clear all stored messages."""
        self.messages = []
        self._current_user_text = ""
        self._current_assistant_text = ""
