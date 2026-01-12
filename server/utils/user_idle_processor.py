"""
User Idle Processor - Monitors for user silence and prompts them.

This processor detects when the user has been silent for too long after
the bot finishes speaking, and triggers escalating prompts to check if
they're still there.
"""

import asyncio
from typing import Awaitable, Callable

from loguru import logger
from pipecat.frames.frames import (
    Frame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor


class UserIdleProcessor(FrameProcessor):
    """
    Monitors user inactivity after bot stops speaking.

    Key behavior:
    - Starts monitoring when bot stops speaking
    - Pauses when bot starts speaking or user speaks
    - Resumes when user stops speaking
    - Triggers callback after timeout period
    """

    def __init__(
        self,
        *,
        callback: Callable[["UserIdleProcessor", int], Awaitable[bool]],
        timeout: float = 10.0,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._callback = callback
        self._timeout = timeout
        self._retry_count = 0
        self._idle_monitoring_active = False
        self._idle_task: asyncio.Task | None = None
        self._idle_event = asyncio.Event()

    async def start(self, frame: Frame):
        """Start the idle monitoring task."""
        await super().start(frame)
        self._idle_task = asyncio.create_task(self._idle_task_handler())

    async def stop(self, frame: Frame):
        """Stop the idle monitoring task."""
        await super().stop(frame)
        if self._idle_task:
            self._idle_task.cancel()
            try:
                await self._idle_task
            except asyncio.CancelledError:
                pass

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        await self.push_frame(frame, direction)

        frame_name = frame.__class__.__name__

        # Start monitoring when bot stops speaking
        if frame_name == "BotStoppedSpeakingFrame":
            logger.debug(
                "UserIdleProcessor: Bot stopped speaking, starting idle monitoring"
            )
            self._idle_monitoring_active = True
            self._idle_event.set()

        # Pause when bot starts speaking
        elif frame_name == "BotStartedSpeakingFrame":
            logger.debug(
                "UserIdleProcessor: Bot started speaking, pausing idle monitoring"
            )
            self._idle_monitoring_active = False
            self._idle_event.set()

        # Pause when user starts speaking and reset retry count
        elif frame_name == "UserStartedSpeakingFrame":
            logger.debug(
                "UserIdleProcessor: User started speaking, resetting idle monitoring"
            )
            self._idle_monitoring_active = False
            self._idle_event.set()
            self._retry_count = 0  # Reset retry count when user speaks

        # Resume monitoring when user stops speaking
        elif frame_name == "UserStoppedSpeakingFrame":
            logger.debug(
                "UserIdleProcessor: User stopped speaking, resuming idle monitoring"
            )
            self._idle_monitoring_active = True
            self._idle_event.set()

    async def _idle_task_handler(self):
        """Background task that monitors for timeout."""
        while True:
            self._idle_event.clear()
            try:
                await asyncio.wait_for(self._idle_event.wait(), timeout=self._timeout)
            except asyncio.TimeoutError:
                if self._idle_monitoring_active:
                    self._retry_count += 1
                    logger.info(
                        f"UserIdleProcessor: User idle timeout #{self._retry_count}"
                    )
                    try:
                        should_continue = await self._callback(self, self._retry_count)
                        if not should_continue:
                            logger.info("UserIdleProcessor: Callback requested stop")
                            break
                    except Exception as e:
                        logger.error(f"UserIdleProcessor: Callback error: {e}")
            except asyncio.CancelledError:
                break
