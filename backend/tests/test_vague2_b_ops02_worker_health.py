"""Vague 2 / file B — OPS-02 : la sonde « worker health » teste le worker.

Constat Astra (L924), re-lu dans le code au commit 388299a :
  - `worker_health` faisait `LLEN arq:queue:<file>` alors qu'ARQ range ses
    taches dans un ensemble trie nomme `<file>` : la sonde annoncait 0 tache
    en attente quoi qu'il arrive ;
  - elle ne regardait pas le battement du worker (cle `<file>:health-check`,
    posee par ARQ toutes les `health_check_interval` secondes, expiree
    ensuite) : un worker mort laissait la sonde verte ;
  - elle rendait HTTP 200 meme Redis injoignable (`{"redis": "error"}`) ;
  - chaque `get_redis_pool()` creait un pool, jamais ferme par les appelants.

Les tests utilisent le Redis de test (DB 9, file `test-<run_id>` posee par
le bootstrap hermetique) ; ils n'enfilent aucune vraie tache, ils ecrivent
les cles qu'ARQ ecrirait.
"""
from __future__ import annotations

import asyncio
import time

import pytest
import redis as redis_lib
from fastapi.testclient import TestClient

from app.main import app
from app.workers import arq_config
from app.workers.arq_config import ARQ_QUEUE_NAME, REDIS_SETTINGS

URL = "/api/pm-orchestrator/workers/health"
CLE_BATTEMENT = f"{ARQ_QUEUE_NAME}:health-check"


@pytest.fixture
def redis_test():
    assert REDIS_SETTINGS.database not in (0, 1), "Redis de production refuse"
    client = redis_lib.Redis(
        host=REDIS_SETTINGS.host, port=REDIS_SETTINGS.port, db=REDIS_SETTINGS.database
    )
    client.delete(ARQ_QUEUE_NAME, CLE_BATTEMENT)
    yield client
    client.delete(ARQ_QUEUE_NAME, CLE_BATTEMENT)
    client.close()


@pytest.fixture
def http():
    # Sans `with` : pas d'evenements de demarrage (sondes reseau), seulement la route.
    return TestClient(app)


def _battement(client, valeur="Oct-24 12:00:00 j_complete=3 j_failed=1 j_retried=0 j_ongoing=2 queued=2"):
    client.psetex(CLE_BATTEMENT, 31_000, valeur)


def test_les_taches_en_attente_sont_comptees_dans_la_vraie_file(redis_test, http):
    maintenant_ms = int(time.time() * 1000)
    redis_test.zadd(ARQ_QUEUE_NAME, {"job-a": maintenant_ms - 120_000, "job-b": maintenant_ms})
    _battement(redis_test)
    r = http.get(URL)
    corps = r.json()
    assert corps["queued_jobs"] == 2, corps
    assert corps["oldest_job_age_s"] >= 119, corps


def test_sans_battement_le_worker_est_declare_absent_en_503(redis_test, http):
    r = http.get(URL)
    assert r.status_code == 503, r.json()
    corps = r.json()
    assert corps["worker"] == "absent"
    assert CLE_BATTEMENT in corps["detail"]


def test_avec_battement_le_worker_est_vivant_en_200(redis_test, http):
    """Controle positif : le battement ARQ present rend 200 et ses compteurs."""
    _battement(redis_test)
    r = http.get(URL)
    assert r.status_code == 200, r.json()
    corps = r.json()
    assert corps["worker"] == "up"
    assert corps["heartbeat"]["j_ongoing"] == 2
    assert corps["heartbeat"]["j_failed"] == 1
    assert corps["queued_jobs"] == 0


def test_redis_injoignable_rend_503(monkeypatch, http):
    async def pool_mort():
        raise ConnectionError("Redis injoignable (bouchon)")

    monkeypatch.setattr(
        "app.api.routes.orchestrator.execution_routes.get_redis_pool", pool_mort
    )
    r = http.get(URL)
    assert r.status_code == 503
    assert r.json()["redis"] == "error"


def test_le_pool_redis_est_partage_dans_un_processus(monkeypatch):
    """Un pool par boucle d'evenements, pas un par appel."""
    crees = []

    class FauxPool:
        def __init__(self):
            self.ferme = False

        async def aclose(self):
            self.ferme = True

    async def faux_create_pool(_settings, **_kw):
        p = FauxPool()
        crees.append(p)
        return p

    monkeypatch.setattr(arq_config, "create_pool", faux_create_pool)
    reinitialiser = getattr(arq_config, "_reinitialiser_pool_pour_tests", None)
    if reinitialiser:
        reinitialiser()

    async def scenario():
        a = await arq_config.get_redis_pool()
        b = await arq_config.get_redis_pool()
        return a, b

    a, b = asyncio.run(scenario())
    assert a is b
    assert len(crees) == 1


def test_le_pool_partage_est_ferme_a_l_arret(monkeypatch):
    crees = []

    class FauxPool:
        def __init__(self):
            self.ferme = False

        async def aclose(self):
            self.ferme = True

    async def faux_create_pool(_settings, **_kw):
        p = FauxPool()
        crees.append(p)
        return p

    monkeypatch.setattr(arq_config, "create_pool", faux_create_pool)
    reinitialiser = getattr(arq_config, "_reinitialiser_pool_pour_tests", None)
    if reinitialiser:
        reinitialiser()

    async def scenario():
        a = await arq_config.get_redis_pool()
        await arq_config.close_redis_pool()
        b = await arq_config.get_redis_pool()
        await arq_config.close_redis_pool()
        return a, b

    a, b = asyncio.run(scenario())
    assert a.ferme and b.ferme
    assert a is not b


def test_le_cron_du_worker_est_en_utc():
    """Les purges de retention sont annoncees a 03:17 / 03:23 UTC ; sans
    `timezone`, ARQ prend le fuseau du systeme."""
    import datetime as dt

    from app.workers.worker import WorkerSettings

    assert getattr(WorkerSettings, "timezone", None) == dt.timezone.utc


def test_l_arret_de_l_application_ferme_le_pool_partage(monkeypatch):
    """Le cablage : `shutdown_event` de app.main ferme le pool partage."""
    import app.main as main

    fermetures = []

    async def faux_close():
        fermetures.append(True)

    async def rien():
        return None

    monkeypatch.setattr(arq_config, "close_redis_pool", faux_close)
    monkeypatch.setattr(main, "shutdown_notification_service", rien)
    asyncio.run(main.shutdown_event())
    assert fermetures == [True]
