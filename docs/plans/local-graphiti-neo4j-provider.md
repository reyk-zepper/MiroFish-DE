# MiroFish-DE Local-First Plan: Ollama + Neo4j Graph Provider

## Entscheidung

MiroFish-DE soll standardmäßig ohne Zep-Cloud-Registrierung laufen. Zep Cloud bleibt als optionaler Legacy-Provider erhalten, damit Upstream-Updates und Vergleichstests möglich bleiben.

Default-Ziel:

```env
LLM_PROVIDER=local
GRAPH_PROVIDER=graphiti_neo4j
EMBEDDING_PROVIDER=local
```

## Zielarchitektur

```text
MiroFish-DE
├── Frontend: deutsche UI + Simulationsgrößensteuerung
├── Backend
│   ├── LLM: OpenAI-kompatibel
│   │   └── Ollama auf dem Mac mini
│   ├── GraphMemoryProvider
│   │   ├── graphiti_neo4j  # Default, lokal
│   │   └── zep_cloud       # optional/legacy
│   └── Simulation
│       ├── max_agents
│       ├── max_rounds
│       └── parallel_profile_count
├── Neo4j
└── Ollama
    ├── qwen2.5:7b-instruct
    └── nomic-embed-text
```

## Mac-mini-M4-16GB-Empfehlung

Für Agenten-Simulationen zählt Durchsatz stärker als Maximalqualität.

Empfohlener Start:

```bash
ollama pull qwen2.5:7b-instruct
ollama pull nomic-embed-text
```

Startwerte:

```text
Agenten: 10–20
Runden: 20–40
Parallel generierte Profile: 2–3
```

`qwen2.5:14b-instruct` kann später für Reports/Konfiguration getestet werden, ist aber auf 16 GB Unified Memory nicht der beste Default für viele parallele Agenten.

## Implementierungsphasen

### Phase 1 — Provider-Abstraktion

- `GraphMemoryProvider` Interface
- `ZepCloudGraphProvider` als Legacy-Adapter
- `GraphitiNeo4jProvider` als lokaler Default
- `GRAPH_PROVIDER` in `Config`
- `ZEP_API_KEY` nur noch erforderlich, wenn `GRAPH_PROVIDER=zep_cloud`

### Phase 2 — Anbindung bestehender Services

- `GraphBuilderService` baut Graphen über den aktiven Provider.
- `ZepEntityReader` bleibt als kompatibler Name erhalten, liest aber über Provider.
- `ZepGraphMemoryUpdater` schreibt Simulationsepisoden über Provider.
- `ZepToolsService`/Report-Agent nutzt Provider für lokale Suche und Statistiken.
- `OasisProfileGenerator` holt Kontext über Provider statt direkt Zep.

### Phase 3 — Lokaler Stack

- `docker-compose.local.yml` für Neo4j
- `.env.local.example` für Ollama + Neo4j
- Dokumentation für Mac mini Setup

### Phase 4 — Ausbau Richtung echtes Graphiti

Der lokale Provider speichert bereits Episodes, Entities und Relations in Neo4j. Die Extraktion ist bewusst an der Provider-Grenze gekapselt, damit später `graphiti-core` als Materialisierungsengine eingebunden werden kann, ohne Simulation/Report/Reader erneut umzubauen.

## Noch zu verbessern nach erstem Smoke-Test

- Entity-/Relation-Extraktion mit lokalem 7B-Modell bewerten.
- Falls Graph-Qualität zu schwach: separates stärkeres Modell für Graph-Extraktion einführen.
- Optional: echte lokale Embedding-Suche ergänzen statt Keyword-Fallback.
- Report-Tools sprachlich weiter eindeutschen.
