"""
entity_association.py
---------------------
Spatial Entity Association Engine.
Associates OCR text labels (equipment tags, instrument tags, line specs) with nearby
detected symbols and piping lines using bounding-box spatial proximity and engineering rules.
"""

import math
from typing import List, Tuple

from app.pid.canonical_schema import PIDConnection, PIDLine, PIDSymbol, PIDText


def center_of_bbox(bbox: List[int]) -> Tuple[float, float]:
    x1, y1, x2, y2 = bbox
    return (x1 + x2) / 2.0, (y1 + y2) / 2.0


def euclidean_dist(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    return math.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)


def associate_entities(
    symbols: List[PIDSymbol],
    texts: List[PIDText],
    lines: List[PIDLine],
    max_distance_px: float = 150.0,
) -> Tuple[List[PIDSymbol], List[PIDConnection]]:
    """
    Associates OCR tags with closest symbols and builds connectivity relationships.
    """
    connections: List[PIDConnection] = []

    # 1. Associate tags with nearby symbols
    for text in texts:
        if text.category not in ("equipment_tag", "instrument_tag", "general"):
            continue

        text_center = center_of_bbox(text.bbox)
        closest_symbol = None
        min_dist = float("inf")

        for symbol in symbols:
            symbol_center = center_of_bbox(symbol.bbox)
            dist = euclidean_dist(text_center, symbol_center)
            if dist < min_dist and dist <= max_distance_px:
                min_dist = dist
                closest_symbol = symbol

        if closest_symbol and not closest_symbol.tag:
            closest_symbol.tag = text.text
            conn_rel = "monitored_by" if text.category == "instrument_tag" else "associated_with"
            connections.append(
                PIDConnection(
                    from_id=closest_symbol.id,
                    to_id=text.id,
                    relationship=conn_rel,
                    confidence=max(0.5, round(1.0 - (min_dist / max_distance_px), 2)),
                )
            )

    # 2. Derive piping connections between adjacent symbols along piping lines
    for i in range(len(symbols)):
        for j in range(i + 1, len(symbols)):
            s1 = symbols[i]
            s2 = symbols[j]
            c1 = center_of_bbox(s1.bbox)
            c2 = center_of_bbox(s2.bbox)
            dist = euclidean_dist(c1, c2)

            # Heuristic: connect symbols within reasonable proximity
            if dist < 450.0:
                # Assign flow relationship: valves/pumps upstream of vessels/tanks
                rel = "connected_to"
                if s1.type in ("pump", "gate_valve", "ball_valve") and s2.type in ("vessel", "tank", "heat_exchanger"):
                    rel = "upstream_of"
                elif s2.type in ("pump", "gate_valve", "ball_valve") and s1.type in ("vessel", "tank", "heat_exchanger"):
                    rel = "downstream_of"

                connections.append(
                    PIDConnection(
                        from_id=s1.tag or s1.id,
                        to_id=s2.tag or s2.id,
                        relationship=rel,
                        confidence=round(max(0.4, 1.0 - (dist / 600.0)), 2),
                    )
                )

    return symbols, connections
