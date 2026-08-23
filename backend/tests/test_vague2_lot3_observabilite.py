"""
VAGUE 2 — LOT 3 : observabilite et petits defauts reels (EXECUTION.md §5.4).

Volet backend. Le volet frontend (decodage SSE, enums de paliers) est prouve
par `frontend/tests/*.test.ts`, lances avec le runner integre de Node.

  3.1 `redis` et `chroma` absents de `/health`. Kimi demandait
      `SELECT 1` + `redis.ping` + `chroma.count` ; seule la base etait couverte.
      `/health` doit rendre 503 quand **une** dependance est morte.
  3.3 `AuditMiddleware` ecrit une ligne `audit_logs` par requete SSE, en SQL
      synchrone sur la boucle d'evenements.
"""
import asyncio

import pytest
from sqlalchemy.exc import OperationalError

from app.main import app


# ==========================================================================
# 3.1 — /health profond : base + redis + chroma
# ==========================================================================

@pytest.fixture
def deps_ok(monkeypatch):
    """Les deux dependances ajoutees repondent."""
    def _redis_ok():
        return True, "ok"

    def _chroma_ok():
        return True, "70251 chunks"

    monkeypatch.setattr("app.main._check_redis", _redis_ok)
    monkeypatch.setattr("app.main._check_chroma", _chroma_ok)


def test_health_declare_les_trois_dependances(client, deps_ok):
    """Le defaut : `/health` ne parlait que de la base. Un Redis mort ou un
    ChromaDB vide rendaient 200 alors que les executions echouaient."""
    r = client.get("/health")
    assert r.status_code == 200, r.text
    checks = r.json()["checks"]
    assert set(checks) == {"database", "redis", "chroma"}, (
        f"dependances declarees : {sorted(checks)}"
    )
    assert checks["redis"]["status"] == "up"
    assert checks["chroma"]["status"] == "up"


def test_health_rend_503_quand_redis_est_mort(client, monkeypatch):
    """« /health doit dire 503 quand une dependance est morte, pas seulement
    la base. » Redis porte la file ARQ : sans lui, aucune execution ne demarre."""
    monkeypatch.setattr("app.main._check_redis", lambda: (False, "ConnectionError: refused"))
    monkeypatch.setattr("app.main._check_chroma", lambda: (True, "ok"))

    r = client.get("/health")
    assert r.status_code == 503, f"attendu 503, obtenu {r.status_code} — {r.text[:300]}"
    body = r.json()
    assert body["status"] == "unhealthy"
    assert body["checks"]["redis"]["status"] == "down"
    assert body["checks"]["database"]["status"] == "up"
    assert "refused" in body["checks"]["redis"]["detail"]


def test_health_rend_503_quand_chroma_est_mort(client, monkeypatch):
    """Le RAG porte 70 K chunks : sans lui les agents tournent a l'aveugle."""
    monkeypatch.setattr("app.main._check_redis", lambda: (True, "ok"))
    monkeypatch.setattr("app.main._check_chroma", lambda: (False, "0 chunks"))

    r = client.get("/health")
    assert r.status_code == 503, r.text
    assert r.json()["checks"]["chroma"]["status"] == "down"


def test_health_rend_503_quand_la_base_est_morte(client, monkeypatch, deps_ok):
    """Non-regression du LOT-G : la base reste couverte."""
    class DeadSession:
        def execute(self, *_a, **_k):
            raise OperationalError("SELECT 1", {}, Exception("connection refused"))

        def close(self):
            pass

    monkeypatch.setattr("app.main.SessionLocal", lambda: DeadSession())

    r = client.get("/health")
    assert r.status_code == 503
    assert r.json()["checks"]["database"]["status"] == "down"


def test_les_sondes_ne_bloquent_pas_la_boucle(client, monkeypatch):
    """Les trois sondes sont synchrones et lentes par nature (socket, disque).
    Elles doivent partir en fil d'execution, pas sur la boucle."""
    appelants = []

    def _slow_redis():
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            appelants.append("hors-boucle")
            return True, "ok"
        appelants.append("sur-boucle")
        return True, "ok"

    monkeypatch.setattr("app.main._check_redis", _slow_redis)
    monkeypatch.setattr("app.main._check_chroma", lambda: (True, "ok"))

    r = client.get("/health")
    assert r.status_code == 200, r.text
    assert "hors-boucle" in appelants, (
        "la sonde redis s'est executee sur la boucle d'evenements"
    )


def test_root_reste_une_sonde_superficielle(client):
    """Non-regression : `/` ne doit toucher aucune dependance."""
    r = client.get("/")
    assert r.status_code == 200
    assert "checks" not in r.json()


# ==========================================================================
# 3.3 — AuditMiddleware et les flux SSE
# ==========================================================================

def test_les_flux_sse_n_ecrivent_plus_une_ligne_d_audit(monkeypatch):
    """Le defaut : une ligne `audit_logs` par requete SSE, ecrite en SQL
    synchrone sur la boucle d'evenements. `EventSource` se reconnecte tout
    seul : un onglet ouvert produisait une ligne par reconnexion."""
    from fastapi import FastAPI
    from fastapi.responses import StreamingResponse
    from fastapi.testclient import TestClient

    from app.middleware import AuditMiddleware

    ecrits = []

    def _capture(**kwargs):
        ecrits.append(kwargs)

    monkeypatch.setattr("app.services.audit_service.audit_service.log", _capture)

    petite_app = FastAPI()
    petite_app.add_middleware(AuditMiddleware)

    @petite_app.get("/flux")
    def flux():
        def gen():
            yield "data: {}\n\n"

        return StreamingResponse(gen(), media_type="text/event-stream")

    @petite_app.post("/ordinaire")
    def ordinaire():
        return {"ok": True}

    with TestClient(petite_app) as c:
        r = c.get("/flux")
        assert r.status_code == 200
        assert not ecrits, (
            f"un flux SSE a produit {len(ecrits)} ligne(s) d'audit : {ecrits}"
        )

        r = c.post("/ordinaire")
        assert r.status_code == 200

    assert len(ecrits) == 1, (
        "une requete ordinaire doit continuer d'etre auditee — "
        f"lignes ecrites : {len(ecrits)}"
    )
    assert ecrits[0]["extra_data"]["path"] == "/ordinaire"


def test_un_flux_sse_en_echec_reste_audite(monkeypatch):
    """On ne tait pas les echecs : seule la reussite d'un flux est du bruit."""
    from fastapi import FastAPI, HTTPException
    from fastapi.testclient import TestClient

    from app.middleware import AuditMiddleware

    ecrits = []
    monkeypatch.setattr(
        "app.services.audit_service.audit_service.log",
        lambda **kw: ecrits.append(kw),
    )

    petite_app = FastAPI()
    petite_app.add_middleware(AuditMiddleware)

    @petite_app.get("/flux-casse")
    def flux_casse():
        raise HTTPException(status_code=403, detail="nope")

    with TestClient(petite_app) as c:
        r = c.get("/flux-casse")
        assert r.status_code == 403

    assert len(ecrits) == 1
    assert ecrits[0]["success"] == "false"


def test_l_ecriture_d_audit_quitte_la_boucle_d_evenements(monkeypatch):
    """Second volet du constat : « en SQL synchrone sur la boucle
    d'evenements ». L'ecriture doit partir en fil d'execution."""
    import threading

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.middleware import AuditMiddleware

    fils = []

    def _capture(**kwargs):
        try:
            asyncio.get_running_loop()
            fils.append("sur-boucle")
        except RuntimeError:
            fils.append("hors-boucle")

    monkeypatch.setattr("app.services.audit_service.audit_service.log", _capture)

    petite_app = FastAPI()
    petite_app.add_middleware(AuditMiddleware)

    @petite_app.post("/ecrit")
    def ecrit():
        return {"ok": True}

    with TestClient(petite_app) as c:
        assert c.post("/ecrit").status_code == 200

    assert fils == ["hors-boucle"], (
        f"l'ecriture d'audit s'est faite sur la boucle d'evenements : {fils}"
    )
