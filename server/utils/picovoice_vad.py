"""
Picovoice Cobra VAD Analyzer for Pipecat.

Integrates Picovoice Cobra voice activity detection with Pipecat's VAD framework.
Cobra provides superior noise immunity and faster detection compared to Silero.
"""

import asyncio
import struct
from typing import Optional

import pvcobra
from loguru import logger
from pipecat.audio.vad.vad_analyzer import VADAnalyzer, VADParams


class PicovoiceCobraVADAnalyzer(VADAnalyzer):
    """
    VAD analyzer using Picovoice Cobra for voice activity detection.

    Cobra provides:
    - Ultra-low latency detection (< 50ms)
    - Superior noise immunity
    - Optimized for real-time conversations
    - Works in noisy environments
    """

    def __init__(
        self,
        access_key: str,
        *,
        sample_rate: int = 16000,
        params: Optional[VADParams] = None,
    ):
        """
        Initialize Picovoice Cobra VAD analyzer.

        Args:
            access_key: Picovoice access key
            sample_rate: Audio sample rate (must be 16kHz for Cobra)
            params: VAD parameters
        """
        super().__init__(sample_rate=sample_rate, params=params)

        self._access_key = access_key
        self._cobra = None

        # Cobra requires 16kHz sample rate
        if sample_rate != 16000:
            logger.warning(
                f"Picovoice Cobra requires 16kHz sample rate, got {sample_rate}. "
                "Adjusting to 16kHz."
            )
            sample_rate = 16000

        self._sample_rate = sample_rate
        self._initialize_cobra()

        logger.info("Picovoice Cobra VAD initialized (optimized for real-time)")

    def _initialize_cobra(self):
        """Initialize the Cobra engine."""
        try:
            self._cobra = pvcobra.create(access_key=self._access_key)
            logger.info(f"Cobra VAD initialized (version: {self._cobra.version})")
        except Exception as e:
            logger.error(f"Failed to initialize Picovoice Cobra: {e}")
            raise

    def voice_confidence(self, buffer: bytes) -> float:
        """
        Calculate voice confidence using Picovoice Cobra.

        Args:
            buffer: Audio buffer (16-bit PCM, 16kHz)

        Returns:
            Confidence score (0.0 - 1.0)
        """
        if not self._cobra:
            return 0.0

        try:
            # Convert bytes to int16 array
            pcm = struct.unpack(f"{len(buffer) // 2}h", buffer)

            # Get voice probability from Cobra
            # Cobra returns 0.0-1.0 probability
            voice_probability = self._cobra.process(list(pcm))

            return voice_probability

        except Exception as e:
            logger.error(f"Cobra VAD error: {e}")
            return 0.0

    def num_frames_required(self) -> int:
        """
        Get number of audio frames required for Cobra processing.

        Cobra typically processes 512 samples at a time for 16kHz audio.

        Returns:
            Number of samples required per analysis frame
        """
        if self._cobra:
            return self._cobra.frame_length
        return 512  # Default for 16kHz

    def __del__(self):
        """Clean up Cobra resources."""
        if self._cobra:
            try:
                self._cobra.delete()
            except Exception:
                pass
