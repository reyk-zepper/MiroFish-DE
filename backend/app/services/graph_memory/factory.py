"""Graph provider factory."""

from __future__ import annotations

from typing import Optional

from ...config import Config
from .base import GraphMemoryProvider


_provider_singleton: Optional[GraphMemoryProvider] = None


def get_graph_provider(config=Config, *, fresh: bool = False) -> GraphMemoryProvider:
    global _provider_singleton
    if _provider_singleton is not None and not fresh:
        return _provider_singleton

    provider_name = config.GRAPH_PROVIDER
    if provider_name == 'zep_cloud':
        from .zep_cloud_provider import ZepCloudGraphProvider

        provider = ZepCloudGraphProvider()
    elif provider_name == 'graphiti_neo4j':
        from .graphiti_neo4j_provider import GraphitiNeo4jProvider

        provider = GraphitiNeo4jProvider(config=config)
    else:
        raise ValueError(f"Unknown GRAPH_PROVIDER '{provider_name}'. Use one of: zep_cloud, graphiti_neo4j")

    if not fresh:
        _provider_singleton = provider
    return provider


def reset_graph_provider() -> None:
    global _provider_singleton
    _provider_singleton = None
