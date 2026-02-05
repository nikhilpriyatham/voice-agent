"""
Random ambient audio player for natural office background sounds.

Plays audio clips at random intervals to simulate real office environment
instead of continuous looping.
"""

import asyncio
import random
from typing import Optional

import numpy as np
import soundfile as sf
from loguru import logger
from pipecat.frames.frames import OutputAudioRawFrame, StartFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor


class RandomAmbienceProcessor(FrameProcessor):
    """
    Processor that plays ambient audio at random intervals.

    Instead of continuous looping, this plays short bursts of ambient sound
    with random pauses between them for a more natural feel.
    """

    def __init__(
        self,
        audio_file_path: str,
        play_duration: float = 10.0,  # How long to play each time (seconds)
        min_pause: float = 15.0,  # Minimum pause between plays (seconds)
        max_pause: float = 30.0,  # Maximum pause between plays (seconds)
        volume: float = 0.15,  # Volume (0.0 to 1.0)
        sample_rate: int = 24000,  # Must match TTS sample rate
    ):
        """
        Initialize random ambience processor.

        Args:
            audio_file_path: Path to audio file (must match TTS sample rate)
            play_duration: How many seconds to play each burst
            min_pause: Minimum seconds between bursts
            max_pause: Maximum seconds between bursts
            volume: Volume level (0.0 to 1.0)
            sample_rate: Audio sample rate (must match TTS)
        """
        super().__init__()

        self._audio_file_path = audio_file_path
        self._play_duration = play_duration
        self._min_pause = min_pause
        self._max_pause = max_pause
        self._volume = volume
        self._sample_rate = sample_rate

        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._audio_data: Optional[np.ndarray] = None

        logger.info(
            f"RandomAmbienceProcessor initialized: "
            f"play={play_duration}s, pause={min_pause}-{max_pause}s, "
            f"volume={volume}"
        )

    async def process_frame(self, frame, direction):
        """Process frames and start background task on StartFrame."""
        await super().process_frame(frame, direction)

        # Start the background ambience task when pipeline starts
        if isinstance(frame, StartFrame) and not self._running:
            logger.info("Starting random ambience background task")
            # Load audio file once at startup
            await self._load_audio()
            self._running = True
            self._task = asyncio.create_task(self._ambience_loop())

        # Pass all frames through unchanged
        await self.push_frame(frame, direction)

    async def _load_audio(self):
        """Load audio file into memory."""
        try:
            logger.info(f"Loading ambience audio from {self._audio_file_path}")
            sound, file_sample_rate = await asyncio.to_thread(
                sf.read, self._audio_file_path, dtype="int16"
            )

            if file_sample_rate != self._sample_rate:
                logger.warning(
                    f"Audio file sample rate {file_sample_rate} doesn't match "
                    f"expected {self._sample_rate}. Audio may sound incorrect."
                )

            # Store as numpy array
            self._audio_data = np.frombuffer(sound.tobytes(), dtype=np.int16)
            logger.info(f"Loaded {len(self._audio_data)} audio samples")

        except Exception as e:
            logger.error(f"Failed to load audio file: {e}")
            self._audio_data = None

    async def _ambience_loop(self):
        """Background task that plays ambience at random intervals."""
        try:
            while self._running:
                # Random pause before playing
                pause_duration = random.uniform(self._min_pause, self._max_pause)
                logger.debug(f"Ambience pausing for {pause_duration:.1f}s")
                await asyncio.sleep(pause_duration)

                if not self._running:
                    break

                # Play ambience for the specified duration
                logger.debug(f"Playing ambience for {self._play_duration}s")
                await self._play_ambience()

        except asyncio.CancelledError:
            logger.info("Random ambience task cancelled")
        except Exception as e:
            logger.error(f"Error in ambience loop: {e}")

    async def _play_ambience(self):
        """Play ambient audio for the configured duration."""
        if self._audio_data is None:
            logger.warning("No audio data loaded, skipping ambience playback")
            return

        try:
            # Calculate how many samples to play
            samples_to_play = int(self._play_duration * self._sample_rate)
            samples_played = 0
            audio_pos = 0

            chunk_size = 8192  # Samples per chunk

            # Play audio in chunks
            while samples_played < samples_to_play and self._running:
                # Calculate chunk boundaries
                chunk_start = audio_pos
                chunk_end = min(chunk_start + chunk_size, len(self._audio_data))

                # Loop back to start if we reach the end
                if chunk_start >= len(self._audio_data):
                    audio_pos = 0
                    continue

                # Get audio chunk
                audio_chunk = self._audio_data[chunk_start:chunk_end]

                # Apply volume
                audio_chunk = (audio_chunk * self._volume).astype(np.int16)

                # Create audio frame and push downstream
                frame = OutputAudioRawFrame(
                    audio=audio_chunk.tobytes(),
                    sample_rate=self._sample_rate,
                    num_channels=1
                )

                await self.push_frame(frame, FrameDirection.DOWNSTREAM)

                samples_played += len(audio_chunk)
                audio_pos += len(audio_chunk)

                # Small delay to avoid overwhelming the pipeline
                await asyncio.sleep(0.01)

            logger.debug("Finished playing ambience burst")

        except Exception as e:
            logger.error(f"Error in _play_ambience: {e}")

    async def cleanup(self):
        """Stop the background task on cleanup."""
        logger.info("Stopping random ambience processor")
        self._running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        await super().cleanup()
