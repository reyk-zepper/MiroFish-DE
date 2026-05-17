# MiroFish-DE lokal auf Mac mini betreiben

Diese Anleitung ist für den lokalen Betrieb ohne Zep-Cloud-Registrierung gedacht.

## 1. Ollama installieren

Auf deinem Mac-mini-Setup ist Ollama bereits vorbereitet:

- Host: `rAIk.mini`
- Ollama: `127.0.0.1:11434`, Version `0.23.2`
- Modelle: `qwen2.5:7b-instruct`, `nomic-embed-text:latest`, außerdem `llama3.2:3b`
- Docker/OrbStack erreicht Ollama über `http://host.docker.internal:11434`

Falls du es auf einem frischen System neu aufsetzt:

```bash
brew install ollama
ollama serve
```

In einem zweiten Terminal:

```bash
ollama pull qwen2.5:7b-instruct
ollama pull nomic-embed-text
```

Für deinen Mac mini M4 mit 16 GB RAM ist `qwen2.5:7b-instruct` der empfohlene Startpunkt. `qwen2.5:14b-instruct` kann später getestet werden, wird bei vielen Agenten aber deutlich träger.

## 2. Neo4j starten

Im Repo:

```bash
docker compose -f docker-compose.local.yml up -d neo4j
```

Neo4j Browser:

```text
http://localhost:7474
```

Default-Zugang aus `docker-compose.local.yml`:

```text
User: neo4j
Passwort: change-me
```

Für produktiven Betrieb Passwort ändern.

## 3. Environment konfigurieren

```bash
cp .env.local.example .env
```

Wichtige Defaults:

```env
LLM_PROVIDER=local
# Backend direkt auf dem Mac:
# LOCAL_LLM_BASE_URL=http://localhost:11434/v1
# Backend in Docker/OrbStack:
LOCAL_LLM_BASE_URL=http://host.docker.internal:11434/v1
LOCAL_LLM_MODEL=qwen2.5:7b-instruct

GRAPH_PROVIDER=graphiti_neo4j
NEO4J_URI=bolt://localhost:7687
```

`ZEP_API_KEY` ist für den lokalen Default nicht erforderlich.

## 4. Backend/Frontend starten

Backend-Abhängigkeiten installieren:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

Frontend:

```bash
npm install
cd frontend
npm install
cd ..
npm run dev
```

## 5. Erste sinnvolle Testwerte

Für den Mac mini M4 16 GB:

```text
Agenten: 10–20
Runden: 20–40
Parallel generierte Profile: 2–3
```

Erst wenn das stabil läuft, Agenten/Runden erhöhen.

## 6. Provider wechseln

Lokaler Default:

```env
GRAPH_PROVIDER=graphiti_neo4j
```

Optionaler Legacy-Modus:

```env
GRAPH_PROVIDER=zep_cloud
ZEP_API_KEY=...
```

## 7. Aktueller Stand des lokalen Graph-Providers

Der lokale Provider speichert:

- Graph-Metadaten
- Dokument-Episoden
- extrahierte Entities
- einfache `RELATED_TO`-Relationen
- Simulationsepisoden

Die Grenze ist bewusst so gesetzt, dass später `graphiti-core` als Extraktions-/Materialisierungsschicht ergänzt werden kann, ohne die Simulation erneut umzubauen.
