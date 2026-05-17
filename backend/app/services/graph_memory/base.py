"""Graph memory provider interfaces for MiroFish-DE.

The rest of the application should depend on this small API instead of a
specific hosted graph backend. That keeps the German fork updateable while
allowing local-first Graphiti/Neo4j operation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set


@dataclass
class GraphInfo:
    graph_id: str
    node_count: int
    edge_count: int
    entity_types: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "graph_id": self.graph_id,
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "entity_types": self.entity_types,
        }


@dataclass
class EntityNode:
    uuid: str
    name: str
    labels: List[str]
    summary: str
    attributes: Dict[str, Any]
    related_edges: List[Dict[str, Any]] = field(default_factory=list)
    related_nodes: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uuid": self.uuid,
            "name": self.name,
            "labels": self.labels,
            "summary": self.summary,
            "attributes": self.attributes,
            "related_edges": self.related_edges,
            "related_nodes": self.related_nodes,
        }

    def get_entity_type(self) -> Optional[str]:
        for label in self.labels:
            if label not in ["Entity", "Node"]:
                return label
        return None


@dataclass
class FilteredEntities:
    entities: List[EntityNode]
    entity_types: Set[str]
    total_count: int
    filtered_count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entities": [e.to_dict() for e in self.entities],
            "entity_types": list(self.entity_types),
            "total_count": self.total_count,
            "filtered_count": self.filtered_count,
        }


class GraphMemoryProvider:
    provider_name = "base"

    def create_graph(self, name: str) -> str:
        raise NotImplementedError

    def set_ontology(self, graph_id: str, ontology: Dict[str, Any]) -> None:
        raise NotImplementedError

    def add_text_batches(
        self,
        graph_id: str,
        chunks: List[str],
        batch_size: int = 3,
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ) -> List[str]:
        raise NotImplementedError

    def wait_for_episodes(
        self,
        episode_ids: List[str],
        progress_callback: Optional[Callable[[str, float], None]] = None,
        timeout: int = 600,
    ) -> None:
        raise NotImplementedError

    def get_graph_info(self, graph_id: str) -> GraphInfo:
        raise NotImplementedError

    def get_graph_data(self, graph_id: str) -> Dict[str, Any]:
        raise NotImplementedError

    def get_all_nodes(self, graph_id: str) -> List[Dict[str, Any]]:
        return self.get_graph_data(graph_id).get("nodes", [])

    def get_all_edges(self, graph_id: str) -> List[Dict[str, Any]]:
        return self.get_graph_data(graph_id).get("edges", [])

    def add_episode(self, graph_id: str, text: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        raise NotImplementedError

    def search(self, graph_id: str, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def delete_graph(self, graph_id: str) -> None:
        raise NotImplementedError
