"""VAGUE A / LOT A6 — le comptage RAG ne doit pas bloquer la boucle d'evenements.

Defaut vise
-----------
`app.main.startup_event` est une coroutine, mais elle appelait
`rag_service.rag_health_check()` **en synchrone**. Cette fonction ouvre le
client ChromaDB puis fait un `coll.count()` par collection (cinq collections,
disque + SQLite). Tant qu'elle dure, la boucle d'evenements ne peut rien
servir ; et comme uvicorn n'ouvre le port qu'apres la fin du startup, le
serveur ne repond pas du tout pendant ce temps.

Ce que ces tests mesurent
-------------------------
1. `test_health_repond_pendant_le_comptage_rag` : avec un faux client ChromaDB
   dont `count()` dort 3 s, le temps d'entree dans `TestClient(app)` (donc le
   startup) et le temps d'un `GET /health` fait juste apres doivent tous deux
   rester sous 1 s, **pendant que le comptage lent est encore en cours** — ce
   dernier point est verifie par un `threading.Event` pose par le faux, sinon
   la mesure ne prouverait rien.
2. `test_journal_rag_health_emis_a_la_fin_du_comptage_de_fond` : sortir le
   comptage de la boucle ne doit pas le rendre muet. La ligne `[RAG HEALTH]`
   doit etre emise, apres coup, quand le comptage se termine.
3. `test_exception_dans_le_comptage_journalisee_probe_crashed` : une exception
   dans le comptage doit produire `[RAG HEALTH] probe crashed`, pas un silence
   (regle 6 de la discipline de preuve : jamais de repli silencieux).
4. `test_controle_negatif_...` : controle negatif de sens. Il prouve que le
   meme faux comptage lent, appele **en synchrone** sur une boucle, fait bien
   attendre une autre coroutine >= 3 s, alors qu'en `asyncio.to_thread` elle
   n'attend pas. Sans lui, les mesures des tests 1 et 2 pourraient etre vertes
   pour une raison qui n'a rien a voir avec la boucle.

Pourquoi les sondes de `/health` sont remplacees
------------------------------------------------
`/health` sonde trois dependances (`_check_database`, `_check_redis`,
`_check_chroma`) et **`_check_chroma` appelle lui-meme `rag_health_check`**.
Sans stub, `GET /health` mesurerait donc le faux comptage lent au lieu de
mesurer la disponibilite de la boucle d'evenements, et le test serait rouge
pour une raison qui n'est pas celle du lot. Les trois sondes sont donc
remplacees par des sondes rapides `(True, "ok")`. Le comportement reel des
sondes est couvert ailleurs (`test_lot_g_health_and_boot.py`,
`test_vague2_lot3_observabilite.py`), ces fichiers ne sont pas touches.
"""

import asyncio
import logging
import threading
import time

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import rag_service


DUREE_COMPTAGE_LENT = 3.0
SEUIL_REPONSE = 1.0


class _ClientChromaLent:
    """Faux client ChromaDB dont le premier `count()` dort `duree` secondes.

    Seul le premier appel dort : les cinq collections de `rag_service.COLLECTIONS`
    sont comptees a la suite, et on veut un blocage de 3 s au total, pas de 15 s.
    Les deux `threading.Event` permettent au test de savoir, a l'instant precis
    ou il le demande, si le comptage a demarre et s'il est deja fini.
    """

    def __init__(self, duree: float = DUREE_COMPTAGE_LENT, chunks: int = 42):
        self.duree = duree
        self.chunks = chunks
        self.comptage_demarre = threading.Event()
        self.comptage_termine = threading.Event()
        self._appels = 0
        self._verrou = threading.Lock()

    # API ChromaDB utilisee par rag_health_check
    def get_collection(self, name):  # noqa: ARG002 — la meme instance sert de collection
        return self

    def count(self):
        with self._verrou:
            self._appels += 1
            premier = self._appels == 1
        if premier:
            self.comptage_demarre.set()
            time.sleep(self.duree)
            self.comptage_termine.set()
        return self.chunks


def _messages(caplog, fragment):
    """Messages captures contenant `fragment` (copie : la liste bouge en fil)."""
    return [r.getMessage() for r in list(caplog.records) if fragment in r.getMessage()]


def _attendre_journal(caplog, fragment, timeout=15.0):
    """Attend qu'une ligne contenant `fragment` apparaisse. Rend la liste (vide si absente)."""
    fin = time.monotonic() + timeout
    while time.monotonic() < fin:
        trouve = _messages(caplog, fragment)
        if trouve:
            return trouve
        time.sleep(0.05)
    return []


def _attendre_tache_rag(timeout=15.0):
    """Attend la fin de la tache de fond du comptage, si elle existe.

    Avant correctif l'attribut n'existe pas : la fonction rend simplement False,
    elle ne doit pas etre ce qui fait echouer un test.
    """
    tache = getattr(app.state, "rag_health_task", None)
    if tache is None:
        return False
    fin = time.monotonic() + timeout
    while time.monotonic() < fin:
        if tache.done():
            return True
        time.sleep(0.05)
    return False


@pytest.fixture
def sondes_health_rapides(monkeypatch):
    """Remplace les trois sondes de `/health` par des sondes instantanees.

    Voir la docstring du module : `_check_chroma` appelle `rag_health_check`,
    donc sans ce stub `/health` mesurerait le faux comptage lent lui-meme.
    """
    monkeypatch.setattr("app.main._check_database", lambda: (True, "ok"))
    monkeypatch.setattr("app.main._check_redis", lambda: (True, "ok"))
    monkeypatch.setattr("app.main._check_chroma", lambda: (True, "ok"))


@pytest.fixture
def chroma_lent(monkeypatch):
    """Branche un faux client ChromaDB lent sur `rag_service.get_client`."""
    faux = _ClientChromaLent()
    monkeypatch.setattr(rag_service, "get_client", lambda: faux)
    return faux


# ---------------------------------------------------------------------------
# 1. Critere de fin du lot
# ---------------------------------------------------------------------------

def test_health_repond_pendant_le_comptage_rag(chroma_lent, sondes_health_rapides):
    """Startup < 1 s et `/health` < 1 s alors que le comptage de 3 s tourne encore."""
    debut = time.monotonic()
    with TestClient(app) as http:
        duree_startup = time.monotonic() - debut

        t0 = time.monotonic()
        reponse = http.get("/health")
        duree_health = time.monotonic() - t0

        # La mesure ci-dessus ne vaut que si le comptage lent est bien en cours
        # a cet instant. On le constate, on ne le suppose pas.
        demarre = chroma_lent.comptage_demarre.wait(timeout=SEUIL_REPONSE)
        encore_en_cours = demarre and not chroma_lent.comptage_termine.is_set()

        # Laisse la tache de fond aboutir avant de fermer la boucle.
        chroma_lent.comptage_termine.wait(timeout=15.0)
        _attendre_tache_rag()

    assert reponse.status_code == 200, reponse.text
    assert duree_startup < SEUIL_REPONSE, (
        f"le startup a dure {duree_startup:.2f} s : le comptage RAG est encore "
        f"sur la boucle d'evenements"
    )
    assert duree_health < SEUIL_REPONSE, (
        f"/health a repondu en {duree_health:.2f} s : la boucle etait occupee "
        f"par le comptage RAG"
    )
    assert encore_en_cours, (
        "le comptage lent n'etait plus en cours au moment de la mesure : "
        "le test ne prouve rien (demarre=%s, termine=%s)"
        % (chroma_lent.comptage_demarre.is_set(), chroma_lent.comptage_termine.is_set())
    )


# ---------------------------------------------------------------------------
# 2. Le passage en tache de fond ne doit pas rendre la sonde muette
# ---------------------------------------------------------------------------

def test_journal_rag_health_emis_a_la_fin_du_comptage_de_fond(
    chroma_lent, sondes_health_rapides, caplog
):
    """La ligne `[RAG HEALTH]` est emise apres coup, quand le comptage se termine."""
    caplog.set_level(logging.INFO)

    with TestClient(app) as http:  # noqa: F841 — le contexte declenche le startup
        assert chroma_lent.comptage_demarre.wait(timeout=15.0), (
            "le comptage n'a jamais demarre"
        )
        # Pendant le comptage, rien n'est encore journalise : la preuve que la
        # ligne qui suivra vient bien du comptage de fond et non du startup.
        assert not _messages(caplog, "[RAG HEALTH]"), (
            "le journal [RAG HEALTH] a ete emis avant la fin du comptage : "
            "le comptage a donc tourne sur la boucle pendant le startup"
        )

        assert chroma_lent.comptage_termine.wait(timeout=15.0)
        lignes = _attendre_journal(caplog, "[RAG HEALTH]")
        _attendre_tache_rag()

    assert lignes, "aucune ligne [RAG HEALTH] apres la fin du comptage de fond"
    assert any("[RAG HEALTH] OK" in ligne for ligne in lignes), lignes
    assert any("chunks" in ligne for ligne in lignes), lignes


# ---------------------------------------------------------------------------
# 3. Jamais de repli silencieux
# ---------------------------------------------------------------------------

def test_exception_dans_le_comptage_journalisee_probe_crashed(
    monkeypatch, sondes_health_rapides, caplog
):
    """Une exception du comptage produit `probe crashed`, pas un silence."""
    caplog.set_level(logging.INFO)

    def explose():
        raise RuntimeError("chroma injoignable (faux)")

    monkeypatch.setattr(rag_service, "rag_health_check", explose)

    with TestClient(app) as http:  # noqa: F841 — le contexte declenche le startup
        lignes = _attendre_journal(caplog, "probe crashed")
        _attendre_tache_rag()

    assert lignes, "l'exception du comptage n'a produit aucune ligne 'probe crashed'"
    assert any("chroma injoignable (faux)" in ligne for ligne in lignes), lignes


# ---------------------------------------------------------------------------
# 4. Controle negatif de sens
# ---------------------------------------------------------------------------

def _latence_temoin(monkeypatch, en_fil: bool) -> float:
    """Latence d'une coroutine temoin pendant que le comptage lent tourne.

    `en_fil=False` : `rag_health_check()` appele directement sur la boucle.
    `en_fil=True`  : le meme, via `asyncio.to_thread`.
    """
    faux = _ClientChromaLent()
    monkeypatch.setattr(rag_service, "get_client", lambda: faux)

    async def scenario():
        mesure = {}

        async def temoin():
            t0 = time.monotonic()
            await asyncio.sleep(0.05)
            mesure["latence"] = time.monotonic() - t0

        async def comptage():
            await asyncio.sleep(0)  # laisse le temoin armer son sleep en premier
            if en_fil:
                await asyncio.to_thread(rag_service.rag_health_check)
            else:
                rag_service.rag_health_check()

        await asyncio.gather(temoin(), comptage())
        return mesure["latence"]

    return asyncio.run(scenario())


def test_controle_negatif_le_comptage_synchrone_bloque_bien_la_boucle(monkeypatch):
    """Le faux comptage lent bloque la boucle en synchrone, pas via to_thread.

    Sans ce controle, un `/health` rapide au test 1 pourrait s'expliquer par un
    faux comptage qui ne bloque en realite rien du tout. Ici on mesure les deux
    branches avec le meme faux : l'ecart (>= 3 s contre < 1 s) montre que la
    mesure du test 1 discrimine bien.
    """
    latence_synchrone = _latence_temoin(monkeypatch, en_fil=False)
    latence_en_fil = _latence_temoin(monkeypatch, en_fil=True)

    assert latence_synchrone >= DUREE_COMPTAGE_LENT, (
        f"le faux comptage synchrone n'a fait attendre le temoin que "
        f"{latence_synchrone:.2f} s : il ne bloque pas la boucle, la mesure du "
        f"test 1 ne discriminerait rien"
    )
    assert latence_en_fil < SEUIL_REPONSE, (
        f"le meme comptage en asyncio.to_thread a fait attendre le temoin "
        f"{latence_en_fil:.2f} s"
    )
