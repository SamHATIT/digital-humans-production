"""Vague 2 / file B — OPS-01 et demarrage du backend en ~2 min.

Mesures (detail et commandes dans docs/missions/RAPPORT_VAGUE2_B.md) :

- journal de production : demarrages du 21/10 et du 23/10, imports finis en
  5 s, ligne `[RAG HEALTH] OK` apres 119 s et 89 s ; la sonde des
  fournisseurs locaux (3 s de delai par fournisseur) finit 0,1 s APRES le
  comptage RAG, alors qu'elle tourne dans un autre fil ;
- reproduction dans le worktree (copie du Chroma de production, cache disque
  de la copie evince) : `count()` de chromadb 1.3.4 tient le GIL ; une boucle
  asyncio qui tique toutes les 100 ms n'a tique que 9 fois en 11,3 s de
  comptage en `asyncio.to_thread` ; uvicorn ouvre son port en ~4,5 s puis le
  premier `GET /` attend 10,0 s.

Cause : `asyncio.to_thread` ne libere pas la boucle d'un appel C qui garde le
GIL. Le test A6 (`test_vague_a_a6_rag_count_off_loop.py`) simulait le
comptage par `time.sleep`, qui RELACHE le GIL : il etait vert pour une raison
qui n'existe pas en production.

Constats OPS-01 (Astra L906) couverts ici : comptage synchrone au premier
`/health` sur cache vide ; une seule collection non vide suffisait a rendre
`ok` ; un rafraichissement bloque laissait servir le dernier vert sans fin.

Le comptage part desormais dans un PROCESSUS enfant (`app.services.sonde_rag`),
borne par un delai, tue a l'arret. Les tests remplacent la commande de l'enfant
par un petit programme Python qui imprime un resultat donne (ou dort) : c'est
le vrai mecanisme (sous-processus, delai, lecture du resultat) qui est teste.
Ceux qui decrivent un constat d'avant correctif posent aussi l'etat par
l'ancien chemin (`rag_service.set_rag_health_cache`) pour etre rouges au
commit parent pour la raison du constat, pas pour une importation manquante.
"""
from __future__ import annotations

import asyncio
import json
import re
import sys
import threading
import time

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.main import app
from app.services import rag_service

try:
    from app.services import sonde_rag
except ImportError:  # commit parent : le module n'existe pas
    sonde_rag = None

MARQUEUR = "@@DH_RAG_SONDE@@"

RESULTAT_OK = {
    "ok": True,
    "total_chunks": 500,
    "collections": {"technical": 100, "operations": 100, "business": 100, "apex": 100, "lwc": 100},
    "error": None,
    "chroma_path": "/faux/chroma",
}


def _enfant(resultat=None, duree=0.0, code=0):
    """Commande d'un enfant qui dort `duree` s puis imprime `resultat`."""
    corps = json.dumps(resultat) if resultat is not None else None
    script = f"import time, sys\ntime.sleep({duree})\n"
    if corps is not None:
        script += f"sys.stdout.write('bruit\\n' + {MARQUEUR!r} + {corps!r} + '\\n')\n"
    script += f"sys.exit({code})\n"
    return [sys.executable, "-c", script]


class _Horloge:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


@pytest.fixture(autouse=True)
def etat_propre(monkeypatch):
    rag_service.reset_rag_health_cache()
    yield
    rag_service.reset_rag_health_cache()


@pytest.fixture
def pas_de_sonde_spark(monkeypatch):
    """Le demarrage sonde les fournisseurs locaux (127.0.0.1:18084 = tunnel
    vers le Spark reel). Bouchonne ici : aucun appel au Spark depuis ces tests."""

    class _RouteurMuet:
        providers = {}
        profile = "cloud"
        config = {"profiles": {"cloud": {}}}

        def verifier_fournisseurs_locaux(self, *a, **k):
            return []

    monkeypatch.setattr(
        "app.services.llm_router_service.get_llm_router", lambda: _RouteurMuet()
    )


def _installer_sonde(monkeypatch, **kw):
    s = sonde_rag.SondeRAG(**kw)
    monkeypatch.setattr(sonde_rag, "sonde", s)
    return s


# ---------------------------------------------------------------------------
# Demarrage : la boucle n'est plus tenue par le comptage
# ---------------------------------------------------------------------------

class _ChromaQuiTientLeGil:
    """Faux client dont `count()` execute une expression reguliere a retour
    arriere catastrophique : `re` ne relache pas le GIL (mesure : temoin
    asyncio retarde de la duree du motif). C'est le comportement constate de
    chromadb 1.3.4, et ce que le faux `time.sleep` d'A6 ne reproduisait pas."""

    def __init__(self, repetitions=4):
        self.appels = 0
        self.repetitions = repetitions

    def get_collection(self, name):  # noqa: ARG002
        return self

    def count(self):
        self.appels += 1
        if self.appels == 1:
            for _ in range(self.repetitions):
                re.match(r"(a+)+$", "a" * 24 + "b")
        return 7


def test_controle_un_appel_qui_tient_le_gil_bloque_la_boucle_meme_en_to_thread():
    """Controle de sens : le faux ci-dessus bloque bien la boucle via
    to_thread (sinon le test suivant ne discriminerait rien)."""
    faux = _ChromaQuiTientLeGil(repetitions=3)

    async def scenario():
        mesure = {}

        async def temoin():
            await asyncio.sleep(0.05)
            t0 = time.monotonic()
            await asyncio.sleep(0.05)
            mesure["latence"] = time.monotonic() - t0

        async def comptage():
            debut = time.monotonic()
            await asyncio.to_thread(faux.count)
            mesure["duree"] = time.monotonic() - debut

        await asyncio.gather(temoin(), comptage())
        return mesure

    m = asyncio.run(scenario())
    assert m["latence"] > 0.3, m


def test_le_demarrage_ne_compte_pas_chroma_dans_le_processus(monkeypatch, pas_de_sonde_spark):
    faux = _ChromaQuiTientLeGil()
    monkeypatch.setattr(rag_service, "get_client", lambda: faux)
    if sonde_rag is not None:
        _installer_sonde(monkeypatch, commande=_enfant(RESULTAT_OK, duree=0.3))
    with TestClient(app) as http:
        time.sleep(0.1)
        t0 = time.monotonic()
        r = http.get("/")
        latence = time.monotonic() - t0
        time.sleep(0.5)
        appels = faux.appels
    assert r.status_code == 200
    assert appels == 0, "le comptage Chroma a tourne dans le processus de l'API"
    assert latence < 0.3, f"GET / a attendu {latence:.2f} s pendant la sonde de demarrage"


# ---------------------------------------------------------------------------
# OPS-01 : etats honnetes de /health
# ---------------------------------------------------------------------------

def test_premier_health_sans_sonde_terminee_ne_compte_pas_en_synchrone(monkeypatch):
    """Astra : avant la fin de la sonde de boot, chaque /health trouvant le
    cache vide lancait son propre comptage synchrone."""
    appels = {"n": 0}

    def espion():
        appels["n"] += 1
        return dict(RESULTAT_OK)

    monkeypatch.setattr(rag_service, "rag_health_check", espion)
    if sonde_rag is not None:
        s = _installer_sonde(monkeypatch, commande=_enfant(RESULTAT_OK, duree=5))
    ok, detail = main._check_chroma()
    if sonde_rag is not None:
        s.arreter()
    assert appels["n"] == 0, "comptage synchrone dans /health"
    assert not ok and detail.startswith("warming"), detail


def test_health_warming_pendant_la_sonde_de_demarrage(monkeypatch):
    s = _installer_sonde(monkeypatch, commande=_enfant(RESULTAT_OK, duree=5))
    s.lancer()
    ok, detail = main._check_chroma()
    s.arreter()
    assert not ok
    assert detail.startswith("warming"), detail


def test_une_collection_vide_rend_chroma_down(monkeypatch):
    """Astra : une seule collection non vide rendait ok=True."""
    resultat = json.loads(json.dumps(RESULTAT_OK))
    resultat["collections"]["lwc"] = 0
    resultat["collections"]["apex"] = "error: Collection apex_collection does not exist"
    resultat["total_chunks"] = 300
    rag_service.set_rag_health_cache(resultat)  # chemin d'avant correctif
    if sonde_rag is not None:
        s = _installer_sonde(monkeypatch, commande=_enfant(resultat))
        s.lancer()
        assert s.attendre(30)
    ok, detail = main._check_chroma()
    assert not ok, detail
    assert "lwc=0" in detail and "apex=" in detail, detail


def test_toutes_les_collections_peuplees_rendent_chroma_up(monkeypatch):
    """Controle positif du test precedent."""
    rag_service.set_rag_health_cache(dict(RESULTAT_OK))
    if sonde_rag is not None:
        s = _installer_sonde(monkeypatch, commande=_enfant(RESULTAT_OK))
        s.lancer()
        assert s.attendre(30)
    ok, detail = main._check_chroma()
    assert ok, detail
    assert "500 chunks" in detail


def test_rafraichissement_bloque_ne_sert_pas_le_vert_indefiniment(monkeypatch):
    """Astra : un rafraichissement bloque laissait servir le dernier vert."""
    bloque = threading.Event()

    def comptage_bloque():
        bloque.wait(5)
        return dict(RESULTAT_OK)

    if sonde_rag is None:
        rag_service.set_rag_health_cache(dict(RESULTAT_OK))
        rag_service._rag_health_cache_at = time.monotonic() - 3 * 3600
        monkeypatch.setattr(rag_service, "rag_health_check", comptage_bloque)
        ok, detail = main._check_chroma()
        bloque.set()
    else:
        horloge = _Horloge()
        s = _installer_sonde(monkeypatch, commande=_enfant(RESULTAT_OK), horloge=horloge)
        s.lancer()
        assert s.attendre(30)
        assert s.etat_pour_health()[0]
        s.commande = _enfant(RESULTAT_OK, duree=30)  # le rafraichissement va bloquer
        horloge.t += 3 * 3600
        ok, detail = main._check_chroma()
        s.arreter()
    assert not ok, detail
    assert detail.startswith("stale"), detail


def test_sonde_hors_delai_est_tuee_et_rend_down(monkeypatch):
    s = _installer_sonde(monkeypatch, commande=_enfant(RESULTAT_OK, duree=30), delai_s=1.0)
    debut = time.monotonic()
    s.lancer()
    assert s.attendre(15)
    assert time.monotonic() - debut < 10
    ok, detail = s.etat_pour_health()
    assert not ok and "délai" in detail, detail
    assert s.instantane()["code_retour"] is not None, "l'enfant n'a pas ete arrete"


def test_enfant_sans_resultat_est_un_echec_dit(monkeypatch):
    s = _installer_sonde(monkeypatch, commande=_enfant(None, code=3))
    s.lancer()
    assert s.attendre(15)
    ok, detail = s.etat_pour_health()
    assert not ok and "code 3" in detail, detail


def test_echec_puis_retour_redevient_up(monkeypatch):
    horloge = _Horloge()
    s = _installer_sonde(monkeypatch, commande=_enfant(None, code=1), horloge=horloge)
    s.lancer()
    assert s.attendre(15)
    assert not s.etat_pour_health()[0]
    s.commande = _enfant(RESULTAT_OK)
    horloge.t += s.intervalle_echec_s + 1
    s.etat_pour_health()  # relance la sonde apres l'intervalle d'echec
    assert s.attendre(15)
    ok, detail = s.etat_pour_health()
    assert ok, detail


def test_enfant_reel_sur_le_chroma_de_session():
    """Le vrai programme enfant (rag_service dans un interpreteur neuf) sur le
    Chroma vide de la session hermetique : les cinq collections sont absentes,
    la sonde le dit."""
    s = sonde_rag.SondeRAG()
    s.lancer()
    assert s.attendre(120), "l'enfant reel n'a pas fini en 120 s"
    ok, detail = s.etat_pour_health()
    inst = s.instantane()
    assert inst["resultat"] is not None, inst
    assert inst["resultat"]["chroma_path"] == rag_service.CHROMA_PATH
    assert not ok and "collections vides ou en erreur" in detail, detail


def test_l_enfant_n_envoie_pas_de_telemetrie():
    env = sonde_rag._env_enfant()
    assert env["ANONYMIZED_TELEMETRY"] == "False"


def test_le_demarrage_lance_la_sonde_et_l_arret_la_coupe(monkeypatch, pas_de_sonde_spark):
    s = _installer_sonde(monkeypatch, commande=_enfant(RESULTAT_OK, duree=30))
    with TestClient(app):
        assert s.instantane()["en_cours"], "le demarrage n'a pas lance la sonde"
    assert s.attendre(10)
    assert s.instantane()["code_retour"] is not None
