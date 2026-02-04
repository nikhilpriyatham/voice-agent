"""
Singleton module for PayerLookup to avoid loading CSV on every call.
This module loads the payer database once when first imported.
"""

import os
from loguru import logger
from utils.payer_lookup import PayerLookup

# Global singleton instance
_PAYER_LOOKUP_INSTANCE = None
_CSV_PATH = "./stedi_payers_2026-01-13.csv"


def get_payer_lookup() -> PayerLookup:
    """
    Get the singleton PayerLookup instance.
    Loads CSV on first call, then returns cached instance.
    """
    global _PAYER_LOOKUP_INSTANCE

    if _PAYER_LOOKUP_INSTANCE is None:
        try:
            logger.info(f"Loading payer lookup database from {_CSV_PATH}...")
            _PAYER_LOOKUP_INSTANCE = PayerLookup(_CSV_PATH)
            logger.info(
                f"Payer lookup loaded: {len(_PAYER_LOOKUP_INSTANCE.payers)} payers indexed"
            )
        except Exception as e:
            logger.error(f"Failed to load payer lookup: {e}")
            raise

    return _PAYER_LOOKUP_INSTANCE


# Pre-load on module import for faster first access
try:
    logger.info("Pre-loading payer lookup singleton...")
    get_payer_lookup()
except Exception as e:
    logger.warning(f"Failed to pre-load payer lookup: {e}")
