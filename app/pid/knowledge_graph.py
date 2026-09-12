"""
knowledge_graph.py
------------------
NetworkX Knowledge Graph for P&ID engineering drawings.
Builds directed graph representation (nodes = pumps, vessels, valves, instruments;
edges = connected_to, upstream_of, downstream_of, monitored_by).
Provides fast, deterministic graph traversal queries (downstream, upstream, shortest path).
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import networkx as nx

from app.pid.canonical_schema import PIDDocument


class PIDKnowledgeGraph:
    def __init__(self):
        self.graph = nx.DiGraph()

    def build_from_document(self, doc: PIDDocument):
        """Populates NetworkX graph from a canonical PIDDocument object."""
        self.graph.clear()

        for page in doc.pages:
            # Add Symbol Nodes
            for s in page.symbols:
                node_id = s.tag or s.id
                self.graph.add_node(
                    node_id,
                    type=s.type,
                    tag=s.tag,
                    bbox=s.bbox,
                    page=s.page,
                    confidence=s.confidence,
                    category="equipment" if s.type in ("pump", "vessel", "tank", "compressor", "heat_exchanger") else "valve_instrument",
                )

            # Add Text Nodes
            for t in page.texts:
                self.graph.add_node(
                    t.id,
                    text=t.text,
                    bbox=t.bbox,
                    page=t.page,
                    category="text",
                )

            # Add Edges
            for conn in page.connections:
                if self.graph.has_node(conn.from_id) and self.graph.has_node(conn.to_id):
                    self.graph.add_edge(
                        conn.from_id,
                        conn.to_id,
                        relationship=conn.relationship,
                        confidence=conn.confidence,
                        line_id=conn.line_id,
                    )

    def save_graph(self, filepath: str | Path):
        data = nx.node_link_data(self.graph)
        p = Path(filepath)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def load_graph(self, filepath: str | Path):
        p = Path(filepath)
        if not p.exists():
            return
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.graph = nx.node_link_graph(data)

    def get_equipment_list(self) -> List[Dict[str, Any]]:
        equipment = []
        for n, d in self.graph.nodes(data=True):
            if d.get("category") == "equipment" or d.get("tag"):
                equipment.append({"id": n, **d})
        return equipment

    def get_node_by_tag_or_id(self, tag: str) -> Optional[str]:
        target = tag.strip().upper()
        for n, d in self.graph.nodes(data=True):
            if n.upper() == target:
                return n
            if d.get("tag") and d["tag"].upper() == target:
                return n
            if d.get("text") and d["text"].upper() == target:
                return n
        return None

    def get_downstream(self, tag_or_id: str) -> List[Dict[str, Any]]:
        node = self.get_node_by_tag_or_id(tag_or_id)
        if not node:
            return []

        downstream_nodes = []
        for successor in nx.descendants(self.graph, node):
            d = self.graph.nodes[successor]
            downstream_nodes.append({
                "id": successor,
                "type": d.get("type", "unknown"),
                "tag": d.get("tag"),
                "bbox": d.get("bbox"),
                "page": d.get("page", 1),
            })
        return downstream_nodes

    def get_upstream(self, tag_or_id: str) -> List[Dict[str, Any]]:
        node = self.get_node_by_tag_or_id(tag_or_id)
        if not node:
            return []

        upstream_nodes = []
        for ancestor in nx.ancestors(self.graph, node):
            d = self.graph.nodes[ancestor]
            upstream_nodes.append({
                "id": ancestor,
                "type": d.get("type", "unknown"),
                "tag": d.get("tag"),
                "bbox": d.get("bbox"),
                "page": d.get("page", 1),
            })
        return upstream_nodes

    def trace_path(self, start_tag: str, end_tag: str) -> List[Dict[str, Any]]:
        start_node = self.get_node_by_tag_or_id(start_tag)
        end_node = self.get_node_by_tag_or_id(end_tag)
        if not start_node or not end_node:
            return []

        try:
            path = nx.shortest_path(self.graph, source=start_node, target=end_node)
            path_nodes = []
            for n in path:
                d = self.graph.nodes[n]
                path_nodes.append({
                    "id": n,
                    "type": d.get("type", "unknown"),
                    "tag": d.get("tag"),
                    "bbox": d.get("bbox"),
                    "page": d.get("page", 1),
                })
            return path_nodes
        except nx.NetworkXNoPath:
            return []

    def get_associated_instruments(self, tag_or_id: str) -> List[Dict[str, Any]]:
        node = self.get_node_by_tag_or_id(tag_or_id)
        if not node:
            return []

        instruments = []
        neighbors = set(self.graph.successors(node)).union(set(self.graph.predecessors(node)))
        for n in neighbors:
            d = self.graph.nodes[n]
            if d.get("type") in ("pressure_transmitter", "pressure_indicator", "flow_transmitter", "level_transmitter", "temperature_transmitter") or "tag" in d:
                instruments.append({
                    "id": n,
                    "type": d.get("type", "instrument"),
                    "tag": d.get("tag") or d.get("text"),
                    "bbox": d.get("bbox"),
                })
        return instruments
