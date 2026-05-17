"""Graph build service.

MiroFish-DE routes graph operations through GraphMemoryProvider so Zep Cloud is
optional and the default backend can be local Neo4j.
"""

import threading
from typing import Any, Callable, Dict, List, Optional

from ..models.task import TaskManager, TaskStatus
from ..utils.locale import get_locale, set_locale, t
from .graph_memory import GraphInfo, get_graph_provider
from .text_processor import TextProcessor


class GraphBuilderService:
    """Build and inspect knowledge graphs using the active graph provider."""

    def __init__(self, api_key: Optional[str] = None):
        # api_key is retained for backwards compatibility with older callers.
        self.provider = get_graph_provider()
        self.task_manager = TaskManager()

    def build_graph_async(
        self,
        text: str,
        ontology: Dict[str, Any],
        graph_name: str = "MiroFish Graph",
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        batch_size: int = 3,
    ) -> str:
        task_id = self.task_manager.create_task(
            task_type="graph_build",
            metadata={
                "graph_name": graph_name,
                "chunk_size": chunk_size,
                "text_length": len(text),
                "graph_provider": self.provider.provider_name,
            },
        )
        current_locale = get_locale()
        thread = threading.Thread(
            target=self._build_graph_worker,
            args=(task_id, text, ontology, graph_name, chunk_size, chunk_overlap, batch_size, current_locale),
            daemon=True,
        )
        thread.start()
        return task_id

    def _build_graph_worker(
        self,
        task_id: str,
        text: str,
        ontology: Dict[str, Any],
        graph_name: str,
        chunk_size: int,
        chunk_overlap: int,
        batch_size: int,
        locale: str = 'de',
    ):
        set_locale(locale)
        try:
            self.task_manager.update_task(task_id, status=TaskStatus.PROCESSING, progress=5, message=t('progress.startBuildingGraph'))
            graph_id = self.create_graph(graph_name)
            self.task_manager.update_task(task_id, progress=10, message=t('progress.graphCreated', graphId=graph_id))

            self.set_ontology(graph_id, ontology)
            self.task_manager.update_task(task_id, progress=15, message=t('progress.ontologySet'))

            chunks = TextProcessor.split_text(text, chunk_size, chunk_overlap)
            total_chunks = len(chunks)
            self.task_manager.update_task(task_id, progress=20, message=t('progress.textSplit', count=total_chunks))

            episode_ids = self.add_text_batches(
                graph_id,
                chunks,
                batch_size,
                lambda msg, prog: self.task_manager.update_task(task_id, progress=20 + int(prog * 0.4), message=msg),
            )

            self.task_manager.update_task(task_id, progress=60, message=t('progress.waitingZepProcess'))
            self._wait_for_episodes(
                episode_ids,
                lambda msg, prog: self.task_manager.update_task(task_id, progress=60 + int(prog * 0.3), message=msg),
            )

            self.task_manager.update_task(task_id, progress=90, message=t('progress.fetchingGraphInfo'))
            graph_info = self._get_graph_info(graph_id)
            self.task_manager.complete_task(task_id, {
                "graph_id": graph_id,
                "graph_info": graph_info.to_dict(),
                "chunks_processed": total_chunks,
                "graph_provider": self.provider.provider_name,
            })
        except Exception as e:
            import traceback

            self.task_manager.fail_task(task_id, f"{str(e)}\n{traceback.format_exc()}")

    def create_graph(self, name: str) -> str:
        return self.provider.create_graph(name)

    def set_ontology(self, graph_id: str, ontology: Dict[str, Any]):
        self.provider.set_ontology(graph_id, ontology)

    def add_text_batches(
        self,
        graph_id: str,
        chunks: List[str],
        batch_size: int = 3,
        progress_callback: Optional[Callable] = None,
    ) -> List[str]:
        return self.provider.add_text_batches(graph_id, chunks, batch_size, progress_callback)

    def _wait_for_episodes(
        self,
        episode_uuids: List[str],
        progress_callback: Optional[Callable] = None,
        timeout: int = 600,
    ):
        self.provider.wait_for_episodes(episode_uuids, progress_callback, timeout)

    def _get_graph_info(self, graph_id: str) -> GraphInfo:
        return self.provider.get_graph_info(graph_id)

    def get_graph_data(self, graph_id: str) -> Dict[str, Any]:
        return self.provider.get_graph_data(graph_id)

    def delete_graph(self, graph_id: str):
        self.provider.delete_graph(graph_id)
