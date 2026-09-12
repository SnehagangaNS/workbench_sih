"""
legend_processor.py
-------------------
Extensible Legend Processing Framework for P&ID drawings.
Identifies drawing legend tables (symbol keys, line types, abbreviations) and
builds company-specific symbol mapping tables to enhance classification accuracy.
"""

from typing import Dict, List
from app.pid.canonical_schema import PIDText


class LegendProcessor:
    def __init__(self):
        self.symbol_key_map: Dict[str, str] = {}
        self.abbreviations: Dict[str, str] = {}

    def process_legend_region(self, legend_texts: List[PIDText]) -> Dict[str, str]:
        """
        Parses text blocks in legend region to build abbreviation & symbol mappings.
        """
        mappings = {}
        for t in legend_texts:
            txt = t.text.strip()
            if "=" in txt:
                parts = txt.split("=", 1)
                mappings[parts[0].strip()] = parts[1].strip()
            elif ":" in txt:
                parts = txt.split(":", 1)
                mappings[parts[0].strip()] = parts[1].strip()
        self.abbreviations.update(mappings)
        return mappings
