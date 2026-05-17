"""Local Neo4j-backed graph provider for MiroFish-DE.

This is the local-first replacement for Zep Cloud. It stores graph metadata,
episodes, extracted entities and coarse relationships in Neo4j. The extraction
step uses the configured OpenAI-compatible LLM endpoint, so Ollama works out of
the box via Config.LLM_BASE_URL.

The provider is intentionally Graphiti-compatible at the boundary: episodes are
stored as first-class inputs and entity/relation materialization can later be
swapped to graphiti-core without changing MiroFish's callers.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from openai import OpenAI

from ...config import Config
from ...utils.locale import get_language_instruction, t
from ...utils.logger import get_logger
from .base import GraphInfo, GraphMemoryProvider

logger = get_logger('mirofish.graph_memory.neo4j')


class GraphitiNeo4jProvider(GraphMemoryProvider):
    provider_name = "graphiti_neo4j"

    def __init__(self, config=Config):
        self.config = config
        self.uri = getattr(config, 'NEO4J_URI', 'bolt://localhost:7687')
        self.user = getattr(config, 'NEO4J_USER', 'neo4j')
        self.password = getattr(config, 'NEO4J_PASSWORD', 'change-me')
        self.database = getattr(config, 'NEO4J_DATABASE', 'neo4j')
        self.client = OpenAI(api_key=config.LLM_API_KEY or 'dummy', base_url=config.LLM_BASE_URL)
        self.model = config.LLM_MODEL_NAME
        self._driver = None

    def _get_driver(self):
        if self._driver is None:
            try:
                from neo4j import GraphDatabase
            except ImportError as exc:
                raise RuntimeError(
                    "neo4j Python package is required for GRAPH_PROVIDER=graphiti_neo4j. "
                    "Install backend requirements and run Neo4j locally."
                ) from exc
            self._driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
        return self._driver

    def _run_write(self, query: str, **params):
        with self._get_driver().session(database=self.database) as session:
            return session.execute_write(lambda tx: list(tx.run(query, **params)))

    def _run_read(self, query: str, **params):
        with self._get_driver().session(database=self.database) as session:
            return session.execute_read(lambda tx: list(tx.run(query, **params)))

    def _ensure_constraints(self) -> None:
        statements = [
            "CREATE CONSTRAINT mirofish_graph_id IF NOT EXISTS FOR (g:MiroFishGraph) REQUIRE g.graph_id IS UNIQUE",
            "CREATE CONSTRAINT mirofish_entity_uuid IF NOT EXISTS FOR (e:Entity) REQUIRE e.uuid IS UNIQUE",
            "CREATE CONSTRAINT mirofish_episode_uuid IF NOT EXISTS FOR (e:Episode) REQUIRE e.uuid IS UNIQUE",
        ]
        for statement in statements:
            self._run_write(statement)

    def create_graph(self, name: str) -> str:
        self._ensure_constraints()
        graph_id = f"mirofish_{uuid.uuid4().hex[:16]}"
        self._run_write(
            """
            MERGE (g:MiroFishGraph {graph_id: $graph_id})
            SET g.name = $name, g.description = $description, g.created_at = $created_at
            """,
            graph_id=graph_id,
            name=name,
            description="MiroFish-DE local Neo4j graph",
            created_at=datetime.utcnow().isoformat(),
        )
        return graph_id

    def set_ontology(self, graph_id: str, ontology: Dict[str, Any]) -> None:
        self._run_write(
            """
            MERGE (g:MiroFishGraph {graph_id: $graph_id})
            SET g.ontology = $ontology_json, g.updated_at = $updated_at
            """,
            graph_id=graph_id,
            ontology_json=json.dumps(ontology or {}, ensure_ascii=False),
            updated_at=datetime.utcnow().isoformat(),
        )

    def add_text_batches(self, graph_id: str, chunks: List[str], batch_size: int = 3, progress_callback: Optional[Callable[[str, float], None]] = None) -> List[str]:
        episode_ids: List[str] = []
        total = len(chunks)
        if total == 0:
            return episode_ids
        for i in range(0, total, batch_size):
            batch = chunks[i:i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (total + batch_size - 1) // batch_size
            for chunk in batch:
                episode_id = self.add_episode(graph_id, chunk, metadata={"source": "document"})
                episode_ids.append(episode_id)
                try:
                    self._extract_and_store(graph_id, chunk, episode_id)
                except Exception as exc:
                    logger.warning(f"Local graph extraction failed for episode {episode_id}: {exc}")
            if progress_callback:
                progress_callback(
                    t('progress.sendingBatch', current=batch_num, total=total_batches, chunks=len(batch)),
                    min(1.0, (i + len(batch)) / total),
                )
        return episode_ids

    def wait_for_episodes(self, episode_ids: List[str], progress_callback: Optional[Callable[[str, float], None]] = None, timeout: int = 600) -> None:
        if progress_callback:
            progress_callback(t('progress.processingComplete', completed=len(episode_ids), total=len(episode_ids)), 1.0)

    def add_episode(self, graph_id: str, text: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        episode_id = f"episode_{uuid.uuid4().hex[:16]}"
        self._run_write(
            """
            MERGE (g:MiroFishGraph {graph_id: $graph_id})
            CREATE (ep:Episode {
                uuid: $episode_id,
                graph_id: $graph_id,
                text: $text,
                metadata: $metadata,
                created_at: $created_at,
                processed: true
            })
            MERGE (g)-[:HAS_EPISODE]->(ep)
            """,
            graph_id=graph_id,
            episode_id=episode_id,
            text=text,
            metadata=json.dumps(metadata or {}, ensure_ascii=False),
            created_at=datetime.utcnow().isoformat(),
        )
        return episode_id

    def _load_ontology(self, graph_id: str) -> Dict[str, Any]:
        rows = self._run_read("MATCH (g:MiroFishGraph {graph_id: $graph_id}) RETURN g.ontology AS ontology", graph_id=graph_id)
        if not rows:
            return {}
        raw = rows[0].get("ontology")
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}

    def _extract_and_store(self, graph_id: str, text: str, episode_id: str) -> None:
        ontology = self._load_ontology(graph_id)
        extracted = self._extract_entities_and_edges(text, ontology)
        for entity in extracted.get("entities", []):
            self._store_entity(graph_id, episode_id, entity)
        for edge in extracted.get("edges", []):
            self._store_edge(graph_id, episode_id, edge)

    def _extract_entities_and_edges(self, text: str, ontology: Dict[str, Any]) -> Dict[str, Any]:
        entity_types = [item.get("name") for item in ontology.get("entity_types", []) if item.get("name")]
        edge_types = [item.get("name") for item in ontology.get("edge_types", []) if item.get("name")]
        system = (
            f"{get_language_instruction()}\n"
            "Extrahiere aus dem Text ein kompaktes Knowledge-Graph-JSON. "
            "Antworte ausschließlich mit JSON ohne Markdown. Schema: "
            "{\"entities\":[{\"name\":str,\"labels\":[str],\"summary\":str,\"attributes\":object}],"
            "\"edges\":[{\"source\":str,\"target\":str,\"name\":str,\"fact\":str,\"attributes\":object}]}"
        )
        user = (
            f"Erlaubte Entity-Typen: {entity_types or ['Entity']}\n"
            f"Erlaubte Relationstypen: {edge_types or ['RELATED_TO']}\n"
            f"Text:\n{text[:6000]}"
        )
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0.1,
        )
        content = response.choices[0].message.content or "{}"
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", content, flags=re.S)
            if match:
                return json.loads(match.group(0))
            return {"entities": [], "edges": []}

    def _entity_uuid(self, graph_id: str, name: str) -> str:
        return f"entity_{uuid.uuid5(uuid.NAMESPACE_URL, graph_id + ':' + name).hex}"

    def _store_entity(self, graph_id: str, episode_id: str, entity: Dict[str, Any]) -> None:
        name = str(entity.get("name") or "").strip()
        if not name:
            return
        labels = entity.get("labels") or ["Entity"]
        if "Entity" not in labels:
            labels = ["Entity"] + labels
        entity_uuid = self._entity_uuid(graph_id, name)
        self._run_write(
            """
            MATCH (g:MiroFishGraph {graph_id: $graph_id})
            MATCH (ep:Episode {uuid: $episode_id})
            MERGE (e:Entity {uuid: $uuid})
            SET e.graph_id = $graph_id,
                e.name = $name,
                e.labels = $labels,
                e.summary = coalesce(e.summary, $summary),
                e.attributes = $attributes,
                e.updated_at = $updated_at
            MERGE (g)-[:HAS_ENTITY]->(e)
            MERGE (ep)-[:MENTIONS]->(e)
            """,
            graph_id=graph_id,
            episode_id=episode_id,
            uuid=entity_uuid,
            name=name,
            labels=labels,
            summary=entity.get("summary", ""),
            attributes=json.dumps(entity.get("attributes") or {}, ensure_ascii=False),
            updated_at=datetime.utcnow().isoformat(),
        )

    def _store_edge(self, graph_id: str, episode_id: str, edge: Dict[str, Any]) -> None:
        source = str(edge.get("source") or "").strip()
        target = str(edge.get("target") or "").strip()
        if not source or not target:
            return
        source_uuid = self._entity_uuid(graph_id, source)
        target_uuid = self._entity_uuid(graph_id, target)
        edge_uuid = f"edge_{uuid.uuid5(uuid.NAMESPACE_URL, graph_id + ':' + source + ':' + target + ':' + str(edge.get('name', 'RELATED_TO'))).hex}"
        self._run_write(
            """
            MATCH (ep:Episode {uuid: $episode_id})
            MERGE (s:Entity {uuid: $source_uuid})
            SET s.graph_id = $graph_id, s.name = $source, s.labels = coalesce(s.labels, ['Entity'])
            MERGE (t:Entity {uuid: $target_uuid})
            SET t.graph_id = $graph_id, t.name = $target, t.labels = coalesce(t.labels, ['Entity'])
            MERGE (s)-[r:RELATED_TO {uuid: $edge_uuid}]->(t)
            SET r.graph_id = $graph_id,
                r.name = $name,
                r.fact = $fact,
                r.attributes = $attributes,
                r.updated_at = $updated_at
            MERGE (ep)-[:SUPPORTS_FACT]->(s)
            MERGE (ep)-[:SUPPORTS_FACT]->(t)
            """,
            graph_id=graph_id,
            episode_id=episode_id,
            source_uuid=source_uuid,
            target_uuid=target_uuid,
            edge_uuid=edge_uuid,
            source=source,
            target=target,
            name=edge.get("name") or "RELATED_TO",
            fact=edge.get("fact") or f"{source} is related to {target}",
            attributes=json.dumps(edge.get("attributes") or {}, ensure_ascii=False),
            updated_at=datetime.utcnow().isoformat(),
        )

    def get_graph_info(self, graph_id: str) -> GraphInfo:
        data = self.get_graph_data(graph_id)
        entity_types = sorted({label for node in data.get("nodes", []) for label in node.get("labels", []) if label not in ["Entity", "Node"]})
        return GraphInfo(graph_id=graph_id, node_count=data["node_count"], edge_count=data["edge_count"], entity_types=entity_types)

    def get_graph_data(self, graph_id: str) -> Dict[str, Any]:
        node_rows = self._run_read(
            """
            MATCH (:MiroFishGraph {graph_id: $graph_id})-[:HAS_ENTITY]->(e:Entity)
            RETURN e.uuid AS uuid, e.name AS name, e.labels AS labels, e.summary AS summary,
                   e.attributes AS attributes, e.updated_at AS created_at
            ORDER BY e.name
            """,
            graph_id=graph_id,
        )
        edge_rows = self._run_read(
            """
            MATCH (s:Entity {graph_id: $graph_id})-[r:RELATED_TO]->(t:Entity {graph_id: $graph_id})
            RETURN r.uuid AS uuid, r.name AS name, r.fact AS fact, r.attributes AS attributes,
                   s.uuid AS source_node_uuid, t.uuid AS target_node_uuid,
                   s.name AS source_node_name, t.name AS target_node_name, r.updated_at AS created_at
            ORDER BY r.name
            """,
            graph_id=graph_id,
        )
        nodes = [
            {
                "uuid": row["uuid"],
                "name": row["name"],
                "labels": row["labels"] or ["Entity"],
                "summary": row["summary"] or "",
                "attributes": self._json_or_empty(row["attributes"]),
                "created_at": row["created_at"],
            }
            for row in node_rows
        ]
        edges = [
            {
                "uuid": row["uuid"],
                "name": row["name"] or "RELATED_TO",
                "fact": row["fact"] or "",
                "fact_type": row["name"] or "RELATED_TO",
                "source_node_uuid": row["source_node_uuid"],
                "target_node_uuid": row["target_node_uuid"],
                "source_node_name": row["source_node_name"],
                "target_node_name": row["target_node_name"],
                "attributes": self._json_or_empty(row["attributes"]),
                "created_at": row["created_at"],
                "episodes": [],
            }
            for row in edge_rows
        ]
        return {"graph_id": graph_id, "nodes": nodes, "edges": edges, "node_count": len(nodes), "edge_count": len(edges)}

    def search(self, graph_id: str, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        rows = self._run_read(
            """
            MATCH (e:Entity {graph_id: $graph_id})
            WHERE toLower(e.name) CONTAINS toLower($query) OR toLower(coalesce(e.summary, '')) CONTAINS toLower($query)
            RETURN e.uuid AS uuid, e.name AS name, e.labels AS labels, e.summary AS summary
            LIMIT $limit
            """,
            graph_id=graph_id,
            query=query,
            limit=limit,
        )
        return [dict(row) for row in rows]

    def delete_graph(self, graph_id: str) -> None:
        self._run_write(
            """
            MATCH (g:MiroFishGraph {graph_id: $graph_id})
            OPTIONAL MATCH (g)-[:HAS_EPISODE]->(ep:Episode)
            OPTIONAL MATCH (g)-[:HAS_ENTITY]->(e:Entity)
            DETACH DELETE g, ep, e
            """,
            graph_id=graph_id,
        )

    def _json_or_empty(self, raw: Any) -> Dict[str, Any]:
        if isinstance(raw, dict):
            return raw
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except Exception:
            return {}
