"""
Payer Lookup Utility - Fuzzy matching against Stedi payers database.

This utility loads the Stedi payers CSV and provides fuzzy search
functionality to match user-provided insurance names against known payers.
"""

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from loguru import logger
from rapidfuzz import fuzz, process


@dataclass
class Payer:
    """Represents an insurance payer from the Stedi database."""

    stedi_id: str
    primary_payer_id: str
    display_name: str
    names: List[str]
    aliases: List[str]
    coverage_types: List[str]

    @property
    def all_searchable_names(self) -> List[str]:
        """Get all names that can be searched."""
        all_names = [self.display_name]
        all_names.extend(self.names)
        all_names.extend(self.aliases)
        return [n for n in all_names if n]


@dataclass
class PayerMatch:
    """Represents a payer match result."""

    payer: Payer
    score: float
    matched_name: str


class PayerLookup:
    """
    Payer lookup service with fuzzy matching capabilities.

    Loads payers from Stedi CSV and provides search functionality
    to match user-provided insurance names.
    """

    def __init__(self, csv_path: str):
        """
        Initialize the payer lookup with a CSV file.

        Args:
            csv_path: Path to the Stedi payers CSV file
        """
        self.csv_path = Path(csv_path)
        self.payers: List[Payer] = []
        self._name_to_payer: dict[str, Payer] = {}
        self._load_payers()

    def _load_payers(self):
        """Load and parse the payers CSV file."""
        if not self.csv_path.exists():
            logger.error(f"Payers CSV not found: {self.csv_path}")
            return

        try:
            with open(self.csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    payer = self._parse_payer_row(row)
                    if payer:
                        self.payers.append(payer)
                        # Index all searchable names
                        for name in payer.all_searchable_names:
                            name_lower = name.lower().strip()
                            if name_lower:
                                self._name_to_payer[name_lower] = payer

            logger.info(f"Loaded {len(self.payers)} payers from {self.csv_path}")
            logger.info(f"Indexed {len(self._name_to_payer)} searchable names")

        except Exception as e:
            logger.error(f"Failed to load payers CSV: {e}")

    def _parse_payer_row(self, row: dict) -> Optional[Payer]:
        """Parse a CSV row into a Payer object."""
        try:
            # Parse names (pipe-separated)
            names_str = row.get("Names", "")
            names = [n.strip() for n in names_str.split("|") if n.strip()]

            # Parse aliases (pipe-separated)
            aliases_str = row.get("Aliases", "")
            aliases = [a.strip() for a in aliases_str.split("|") if a.strip()]

            # Parse coverage types (pipe-separated)
            coverage_str = row.get("CoverageTypes", "")
            coverage = [c.strip() for c in coverage_str.split("|") if c.strip()]

            return Payer(
                stedi_id=row.get("StediId", ""),
                primary_payer_id=row.get("PrimaryPayerId", ""),
                display_name=row.get("DisplayName", ""),
                names=names,
                aliases=aliases,
                coverage_types=coverage,
            )
        except Exception as e:
            logger.warning(f"Failed to parse payer row: {e}")
            return None

    def search(
        self, query: str, top_k: int = 5, min_score: float = 50.0
    ) -> List[PayerMatch]:
        """
        Search for payers matching the query using fuzzy matching.

        Args:
            query: The insurance name to search for
            top_k: Maximum number of results to return
            min_score: Minimum fuzzy match score (0-100)

        Returns:
            List of PayerMatch objects sorted by score (highest first)
        """
        if not query or not self._name_to_payer:
            return []

        query_lower = query.lower().strip()

        # First check for exact match
        if query_lower in self._name_to_payer:
            payer = self._name_to_payer[query_lower]
            return [
                PayerMatch(payer=payer, score=100.0, matched_name=payer.display_name)
            ]

        # Fuzzy match against all indexed names
        all_names = list(self._name_to_payer.keys())

        # Use rapidfuzz for fast fuzzy matching
        results = process.extract(
            query_lower,
            all_names,
            scorer=fuzz.WRatio,  # Weighted ratio handles partial matches well
            limit=top_k * 2,  # Get extra to filter duplicates
        )

        # Build matches, deduplicating by payer
        seen_payers = set()
        matches = []

        for matched_name, score, _ in results:
            if score < min_score:
                continue

            payer = self._name_to_payer.get(matched_name)
            if payer and payer.stedi_id not in seen_payers:
                seen_payers.add(payer.stedi_id)
                matches.append(
                    PayerMatch(
                        payer=payer,
                        score=score,
                        matched_name=payer.display_name,
                    )
                )

                if len(matches) >= top_k:
                    break

        logger.debug(f"Search '{query}' found {len(matches)} matches")
        return matches

    def get_payer_by_id(self, stedi_id: str) -> Optional[Payer]:
        """
        Get a payer by its Stedi ID.

        Args:
            stedi_id: The Stedi ID to look up

        Returns:
            Payer object or None if not found
        """
        for payer in self.payers:
            if payer.stedi_id == stedi_id:
                return payer
        return None

    def format_matches_for_llm(self, matches: List[PayerMatch]) -> str:
        """
        Format matches for inclusion in LLM prompt.

        Args:
            matches: List of PayerMatch objects

        Returns:
            Formatted string for LLM context
        """
        if not matches:
            return "No matching insurance providers found in our database."

        lines = ["Found these potential matches:"]
        for i, match in enumerate(matches, 1):
            coverage = (
                ", ".join(match.payer.coverage_types)
                if match.payer.coverage_types
                else "general"
            )
            lines.append(
                f"{i}. {match.payer.display_name} (confidence: {match.score:.0f}%, coverage: {coverage})"
            )

        return "\n".join(lines)

    def get_best_match(
        self, query: str, threshold: float = 85.0
    ) -> Optional[PayerMatch]:
        """
        Get the best match if it exceeds the confidence threshold.

        Args:
            query: Insurance name to search
            threshold: Minimum score for a confident match

        Returns:
            Best PayerMatch if above threshold, None otherwise
        """
        matches = self.search(query, top_k=1, min_score=threshold)
        return matches[0] if matches else None
