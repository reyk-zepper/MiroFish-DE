"""Legacy Zep Cloud graph provider.

All imports of zep_cloud live here so local-first deployments can avoid a
ZEP_API_KEY unless GRAPH_PROVIDER=zep_cloud is selected.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Callable, Dict, List, Optional

from ...config import Config
from ...utils.locale import t
from ...utils.zep_paging import fetch_all_edges, fetch_all_nodes
from .base import GraphInfo, GraphMemoryProvider


class ZepCloudGraphProvider(GraphMemoryProvider):
    provider_name = "zep_cloud"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or Config.ZEP_API_KEY
        if not self.api_key:
            raise ValueError("ZEP_API_KEY is required when GRAPH_PROVIDER=zep_cloud")
        from zep_cloud.client import Zep

        self.client = Zep(api_key=self.api_key)

    def create_graph(self, name: str) -> str:
        graph_id = f"mirofish_{uuid.uuid4().hex[:16]}"
        self.client.graph.create(
            graph_id=graph_id,
            name=name,
            description="MiroFish Social Simulation Graph",
        )
        return graph_id

    def set_ontology(self, graph_id: str, ontology: Dict[str, Any]) -> None:
        import warnings
        from typing import Optional as TypingOptional

        from pydantic import Field
        from zep_cloud import EntityEdgeSourceTarget
        from zep_cloud.external_clients.ontology import EntityModel, EntityText, EdgeModel

        warnings.filterwarnings('ignore', category=UserWarning, module='pydantic')
        reserved_names = {'uuid', 'name', 'group_id', 'name_embedding', 'summary', 'created_at'}

        def safe_attr_name(attr_name: str) -> str:
            return f"entity_{attr_name}" if attr_name.lower() in reserved_names else attr_name

        entity_types = {}
        for entity_def in ontology.get("entity_types", []):
            name = entity_def["name"]
            description = entity_def.get("description", f"A {name} entity.")
            attrs = {"__doc__": description}
            annotations = {}
            for attr_def in entity_def.get("attributes", []):
                attr_name = safe_attr_name(attr_def["name"])
                attrs[attr_name] = Field(description=attr_def.get("description", attr_name), default=None)
                annotations[attr_name] = TypingOptional[EntityText]
            attrs["__annotations__"] = annotations
            entity_types[name] = type(name, (EntityModel,), attrs)

        edge_definitions = {}
        for edge_def in ontology.get("edge_types", []):
            name = edge_def["name"]
            attrs = {"__doc__": edge_def.get("description", f"A {name} relationship.")}
            annotations = {}
            for attr_def in edge_def.get("attributes", []):
                attr_name = safe_attr_name(attr_def["name"])
                attrs[attr_name] = Field(description=attr_def.get("description", attr_name), default=None)
                annotations[attr_name] = TypingOptional[str]
            attrs["__annotations__"] = annotations
            class_name = ''.join(word.capitalize() for word in name.split('_'))
            edge_class = type(class_name, (EdgeModel,), attrs)
            source_targets = [
                EntityEdgeSourceTarget(source=st.get("source", "Entity"), target=st.get("target", "Entity"))
                for st in edge_def.get("source_targets", [])
            ]
            if source_targets:
                edge_definitions[name] = (edge_class, source_targets)

        if entity_types or edge_definitions:
            self.client.graph.set_ontology(
                graph_ids=[graph_id],
                entities=entity_types if entity_types else None,
                edges=edge_definitions if edge_definitions else None,
            )

    def add_text_batches(self, graph_id: str, chunks: List[str], batch_size: int = 3, progress_callback: Optional[Callable[[str, float], None]] = None) -> List[str]:
        from zep_cloud import EpisodeData

        episode_uuids = []
        total_chunks = len(chunks)
        for i in range(0, total_chunks, batch_size):
            batch_chunks = chunks[i:i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (total_chunks + batch_size - 1) // batch_size
            if progress_callback:
                progress_callback(t('progress.sendingBatch', current=batch_num, total=total_batches, chunks=len(batch_chunks)), (i + len(batch_chunks)) / total_chunks)
            batch_result = self.client.graph.add_batch(
                graph_id=graph_id,
                episodes=[EpisodeData(data=chunk, type="text") for chunk in batch_chunks],
            )
            if batch_result and isinstance(batch_result, list):
                for ep in batch_result:
                    ep_uuid = getattr(ep, 'uuid_', None) or getattr(ep, 'uuid', None)
                    if ep_uuid:
                        episode_uuids.append(ep_uuid)
            time.sleep(1)
        return episode_uuids

    def wait_for_episodes(self, episode_ids: List[str], progress_callback: Optional[Callable[[str, float], None]] = None, timeout: int = 600) -> None:
        if not episode_ids:
            if progress_callback:
                progress_callback(t('progress.noEpisodesWait'), 1.0)
            return
        start_time = time.time()
        pending = set(episode_ids)
        completed = 0
        total = len(episode_ids)
        while pending:
            if time.time() - start_time > timeout:
                if progress_callback:
                    progress_callback(t('progress.episodesTimeout', completed=completed, total=total), completed / total)
                break
            for ep_uuid in list(pending):
                episode = self.client.graph.episode.get(uuid_=ep_uuid)
                if getattr(episode, 'processed', False):
                    pending.remove(ep_uuid)
                    completed += 1
            if progress_callback:
                progress_callback(t('progress.processingEpisodes', completed=completed, total=total), completed / total)
            if pending:
                time.sleep(5)
        if progress_callback:
            progress_callback(t('progress.processingComplete', completed=completed, total=total), 1.0)

    def get_graph_info(self, graph_id: str) -> GraphInfo:
        nodes = self.get_all_nodes(graph_id)
        edges = self.get_all_edges(graph_id)
        entity_types = sorted({label for node in nodes for label in node.get("labels", []) if label not in ["Entity", "Node"]})
        return GraphInfo(graph_id=graph_id, node_count=len(nodes), edge_count=len(edges), entity_types=entity_types)

    def get_graph_data(self, graph_id: str) -> Dict[str, Any]:
        nodes_raw = fetch_all_nodes(self.client, graph_id)
        edges_raw = fetch_all_edges(self.client, graph_id)
        node_map = {getattr(node, 'uuid_', None) or getattr(node, 'uuid', ''): node.name or "" for node in nodes_raw}
        nodes = []
        for node in nodes_raw:
            node_uuid = getattr(node, 'uuid_', None) or getattr(node, 'uuid', '')
            nodes.append({
                "uuid": node_uuid,
                "name": node.name or "",
                "labels": node.labels or [],
                "summary": node.summary or "",
                "attributes": node.attributes or {},
                "created_at": str(getattr(node, 'created_at', None)) if getattr(node, 'created_at', None) else None,
            })
        edges = []
        for edge in edges_raw:
            edge_uuid = getattr(edge, 'uuid_', None) or getattr(edge, 'uuid', '')
            edges.append({
                "uuid": edge_uuid,
                "name": edge.name or "",
                "fact": edge.fact or "",
                "fact_type": getattr(edge, 'fact_type', None) or edge.name or "",
                "source_node_uuid": edge.source_node_uuid,
                "target_node_uuid": edge.target_node_uuid,
                "source_node_name": node_map.get(edge.source_node_uuid, ""),
                "target_node_name": node_map.get(edge.target_node_uuid, ""),
                "attributes": edge.attributes or {},
                "created_at": str(getattr(edge, 'created_at', None)) if getattr(edge, 'created_at', None) else None,
                "episodes": [],
            })
        return {"graph_id": graph_id, "nodes": nodes, "edges": edges, "node_count": len(nodes), "edge_count": len(edges)}

    def add_episode(self, graph_id: str, text: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        result = self.client.graph.add(graph_id=graph_id, type="text", data=text)
        return getattr(result, 'uuid_', None) or getattr(result, 'uuid', None) or f"episode_{uuid.uuid4().hex[:12]}"

    def search(self, graph_id: str, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        results = self.client.graph.search(graph_id=graph_id, query=query, limit=limit)
        return [getattr(item, '__dict__', item) for item in results]

    def delete_graph(self, graph_id: str) -> None:
        self.client.graph.delete(graph_id=graph_id)
