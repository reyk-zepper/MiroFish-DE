"""Entity reading and filtering service.

Historically this read directly from Zep Cloud. In MiroFish-DE it is a provider
facade so the simulation code can use either Zep Cloud or the local
Graphiti/Neo4j backend without changes.
"""

from typing import Any, Dict, List, Optional, Set

from ..utils.logger import get_logger
from .graph_memory import EntityNode, FilteredEntities, get_graph_provider

logger = get_logger('mirofish.entity_reader')


class ZepEntityReader:
    """Backward-compatible entity reader backed by the active graph provider."""

    def __init__(self, api_key: Optional[str] = None):
        # api_key is kept for upstream API compatibility; provider selection is
        # controlled by Config.GRAPH_PROVIDER.
        self.provider = get_graph_provider()

    def get_all_nodes(self, graph_id: str) -> List[Dict[str, Any]]:
        logger.info(f"Loading graph nodes: graph_id={graph_id}, provider={self.provider.provider_name}")
        return self.provider.get_all_nodes(graph_id)

    def get_all_edges(self, graph_id: str) -> List[Dict[str, Any]]:
        logger.info(f"Loading graph edges: graph_id={graph_id}, provider={self.provider.provider_name}")
        return self.provider.get_all_edges(graph_id)

    def get_node_edges(self, node_uuid: str) -> List[Dict[str, Any]]:
        # The local provider exposes edges via graph-level reads. This method is
        # retained for callers that still expect the old Zep facade.
        return []

    def filter_defined_entities(
        self,
        graph_id: str,
        defined_entity_types: Optional[List[str]] = None,
        enrich_with_edges: bool = True,
    ) -> FilteredEntities:
        logger.info(f"Filtering graph entities: graph_id={graph_id}, provider={self.provider.provider_name}")
        all_nodes = self.get_all_nodes(graph_id)
        total_count = len(all_nodes)
        all_edges = self.get_all_edges(graph_id) if enrich_with_edges else []
        node_map = {n.get("uuid"): n for n in all_nodes}

        filtered_entities: List[EntityNode] = []
        entity_types_found: Set[str] = set()

        for node in all_nodes:
            labels = node.get("labels", []) or []
            custom_labels = [label for label in labels if label not in ["Entity", "Node"]]
            if not custom_labels:
                continue
            if defined_entity_types and not any(label in defined_entity_types for label in custom_labels):
                continue

            entity = EntityNode(
                uuid=node.get("uuid", ""),
                name=node.get("name", ""),
                labels=labels,
                summary=node.get("summary", ""),
                attributes=node.get("attributes", {}) or {},
            )
            entity_types_found.update(custom_labels)

            if enrich_with_edges:
                related_edges = []
                related_nodes = []
                seen_nodes = set()
                for edge in all_edges:
                    source_uuid = edge.get("source_node_uuid")
                    target_uuid = edge.get("target_node_uuid")
                    if source_uuid == entity.uuid or target_uuid == entity.uuid:
                        related_edges.append(edge)
                        other_uuid = target_uuid if source_uuid == entity.uuid else source_uuid
                        if other_uuid and other_uuid not in seen_nodes and other_uuid in node_map:
                            related_nodes.append(node_map[other_uuid])
                            seen_nodes.add(other_uuid)
                entity.related_edges = related_edges
                entity.related_nodes = related_nodes

            filtered_entities.append(entity)

        logger.info(f"Filtered entities: {len(filtered_entities)}/{total_count}, types={sorted(entity_types_found)}")
        return FilteredEntities(
            entities=filtered_entities,
            entity_types=entity_types_found,
            total_count=total_count,
            filtered_count=len(filtered_entities),
        )

    def get_entity_with_context(self, graph_id: str, entity_uuid: str) -> Optional[EntityNode]:
        all_nodes = self.get_all_nodes(graph_id)
        all_edges = self.get_all_edges(graph_id)
        node_map = {n.get("uuid"): n for n in all_nodes}
        node = node_map.get(entity_uuid)
        if not node:
            return None
        entity = EntityNode(
            uuid=node.get("uuid", ""),
            name=node.get("name", ""),
            labels=node.get("labels", []) or [],
            summary=node.get("summary", ""),
            attributes=node.get("attributes", {}) or {},
        )
        related_edges = []
        related_nodes = []
        seen_nodes = set()
        for edge in all_edges:
            source_uuid = edge.get("source_node_uuid")
            target_uuid = edge.get("target_node_uuid")
            if source_uuid == entity.uuid or target_uuid == entity.uuid:
                related_edges.append(edge)
                other_uuid = target_uuid if source_uuid == entity.uuid else source_uuid
                if other_uuid and other_uuid not in seen_nodes and other_uuid in node_map:
                    related_nodes.append(node_map[other_uuid])
                    seen_nodes.add(other_uuid)
        entity.related_edges = related_edges
        entity.related_nodes = related_nodes
        return entity

    def get_entities_by_type(
        self,
        graph_id: str,
        entity_type: str,
        enrich_with_edges: bool = True,
    ) -> List[EntityNode]:
        filtered = self.filter_defined_entities(
            graph_id=graph_id,
            defined_entity_types=[entity_type],
            enrich_with_edges=enrich_with_edges,
        )
        return filtered.entities

    def get_entity_context(self, entity_uuid: str) -> Optional[EntityNode]:
        # Backward-compatible method kept for old callers without graph_id.
        logger.warning("get_entity_context(entity_uuid) needs graph_id; use get_entity_with_context(graph_id, entity_uuid)")
        return None
