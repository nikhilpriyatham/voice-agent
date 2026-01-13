"""
Date Parser Utility - Parses various date formats and converts to mm/dd/yyyy.

This utility handles spoken dates, various formats, and edge cases like:
- "June 8th, 1996"
- "6/8/96"
- "06-08-1996"
- "August 15 1990"
- "1996-06-08" (ISO format)
"""

import re
from datetime import datetime
from typing import Optional

from dateutil import parser as dateutil_parser
from loguru import logger


def parse_and_format_date(date_string: str) -> Optional[str]:
    """
    Parse a date string in various formats and return it in mm/dd/yyyy format.

    Args:
        date_string: The date string to parse (e.g., "June 8th 1996", "6/8/96")

    Returns:
        Date in mm/dd/yyyy format, or None if parsing fails
    """
    if not date_string or not date_string.strip():
        return None

    # Clean the input
    cleaned = date_string.strip()

    # Remove ordinal suffixes (1st, 2nd, 3rd, 4th, etc.)
    cleaned = re.sub(r"(\d+)(st|nd|rd|th)\b", r"\1", cleaned, flags=re.IGNORECASE)

    # Remove extra whitespace
    cleaned = re.sub(r"\s+", " ", cleaned)

    try:
        # Use dateutil parser which handles many formats
        # dayfirst=False ensures American date format (month/day/year)
        parsed_date = dateutil_parser.parse(cleaned, dayfirst=False, fuzzy=True)

        # Handle 2-digit years - assume 1920-2020 range
        if parsed_date.year < 100:
            if parsed_date.year > 30:
                parsed_date = parsed_date.replace(year=1900 + parsed_date.year)
            else:
                parsed_date = parsed_date.replace(year=2000 + parsed_date.year)

        # Format as mm/dd/yyyy
        formatted = parsed_date.strftime("%m/%d/%Y")
        logger.debug(f"Parsed date '{date_string}' -> '{formatted}'")
        return formatted

    except (ValueError, TypeError) as e:
        logger.warning(f"Failed to parse date '{date_string}': {e}")
        return None


def is_valid_date_format(date_string: str) -> bool:
    """
    Check if a date string is already in mm/dd/yyyy format.

    Args:
        date_string: The date string to check

    Returns:
        True if the date is in mm/dd/yyyy format
    """
    if not date_string:
        return False

    # Check pattern mm/dd/yyyy
    pattern = r"^\d{2}/\d{2}/\d{4}$"
    if not re.match(pattern, date_string):
        return False

    # Validate it's a real date
    try:
        datetime.strptime(date_string, "%m/%d/%Y")
        return True
    except ValueError:
        return False


def format_date_for_speech(date_string: str) -> str:
    """
    Format a date string for natural speech output.

    Args:
        date_string: Date in mm/dd/yyyy format

    Returns:
        Date formatted for speech (e.g., "06/08/1996" -> "June 8th, 1996")
    """
    try:
        parsed = datetime.strptime(date_string, "%m/%d/%Y")

        # Get ordinal suffix for day
        day = parsed.day
        if 10 <= day % 100 <= 20:
            suffix = "th"
        else:
            suffix = {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")

        # Format as "Month Day, Year"
        return parsed.strftime(f"%B {day}{suffix}, %Y")
    except (ValueError, TypeError):
        return date_string
