# Digital Humans — Refonte 2026

## Stack
- Backend: FastAPI (Python 3.11) sur port 8002
- Frontend: React + Vite sur port 3000
- DB: PostgreSQL 16 (SQLAlchemy ORM)
- RAG: ChromaDB (70K chunks) sur /opt/digital-humans/rag/chromadb_data/
- LLM: Claude API + Ollama/Mistral (local)

## Repo
- Path: /root/workspace/digital-humans-production/
- Git remote: github.com/SamHATIT/digital-humans-production

## Règles absolues
1. JAMAIS de commit direct sur main — toujours une branche dédiée
2. JAMAIS déclarer "done" sans test vérifié
3. UN SEUL changement par branche
4. Smoke test après chaque merge (scripts/smoke_test.sh)
5. Tag git avant et après chaque sprint

## Conventions code
- Python: PEP 8, type hints, docstrings
- Imports: absolus depuis la racine backend/
- Config: via .env + app/config.py (Settings pydantic)
- Paths: pathlib.Path relatifs à PROJECT_ROOT — JAMAIS de chemins absolus
- Logs: logging standard Python, format JSON structuré
- DB: context managers `with db.begin():` pour les transactions

## Documents de référence
Lire les fichiers