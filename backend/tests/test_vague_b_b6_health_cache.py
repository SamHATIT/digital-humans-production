"""VAGUE B / LOT B6 — `/health` ne doit plus recompter les chunks RAG a chaque appel.

Defaut vise
-----------
`_check_chroma()` (app/main.py) appelait `rag_service.rag_health_check()` en
direct a chaque `GET /health`. Cette fonction ouvre le client ChromaDB puis
fait un `coll.count()` par collection (cinq collections : voir
`rag_service.COLLECTIONS`). Mesure du 27/08 : ~50 ms a chaud, 11-16 s dans les
pics (disque + SQLite charges) — assez pour que le watchdog, qui sonde
`/health` a intervalle court, voie des timeouts et remonte de fausses alertes
`000` alors que le backend est vivant.

Ce que ces tests mesurent
--------------------------
1. `test_get_cached_rag_health_ne_recompte_pas_au_second_appel` : au niveau
   unite, deux appels consecutifs a `rag_service.get_cached_rag_health()` ne
   declenchent qu'un seul appel a `rag_health_check()` (espion sur la
   fonction elle-meme, pas sur `count()` : un seul `rag_health_check()`
   equivaut a un seul comptage complet des cinq collections).
2. `test_deux_appels_http_health_consecutifs_ne_declenchent_pas_de_second_comptage` :
   la meme propriete vue par la route reelle. Le demarrage de l'app compte
   deja une fois (A6, reutilise comme premiere valeur du cache — voir le
   choix documente au test 3) ; les deux `GET /health` qui suivent ne doivent
   ajouter aucun comptage.
3. `test_cache_vide_au_premier_appel_declenche_un_comptage_synchrone` :
   controle negatif. Choix retenu : quand le cache n'a **jamais** ete peuple
   (aucun demarrage n'a encore fini, ou appel direct hors du cycle de vie de
   l'app), `get_cached_rag_health()` fait un comptage synchrone une fois,
   plutot que de renvoyer un etat invente ou vide qui ferait passer `/health`
   a 503 a tort. C'est le seul cas ou cette fonction peut couter aussi cher
   que l'ancien code — et il ne se produit qu'une fois par processus dans la
   pratique, puisque le demarrage (A6) peuple le cache avant le premier appel
   client.
4. `test_cache_perime_declenche_un_recomptage_en_tache_de_fond` : TTL force a
   une valeur infime (horloge simulee via monkeypatch de la constante, pas de
   sleep reel) ; le prochain appel voit le cache perime et relance un
   comptage — en tache de fond (voir test 5), donc on attend sa fin avant de
   verifier que le cache a change.
5. `test_health_ne_bloque_pas_sur_le_rafraichissement_de_fond` : reprend le
   protocole du test A6 (`_ClientChromaLent`, `threading.Event`) pour prouver
   que le rafraichissement du cache perime tourne en tache de fond et que
   `/health` ne l'attend pas — sa duree reste sous le seuil pendant que le
   faux `count()` dort encore.

Pourquoi les sondes base/redis sont remplacees
------------------------------------------------
Comme dans `test_vague_a_a6_rag_count_off_loop.py`, `_check_database` et
`_check_redis` sont stubbees rapides : ces tests ne portent que sur la sonde
chroma, pas sur Postgres/Redis reels.
"""

import threading
import time

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import rag_service


SEUIL_REPONSE = 1.0
DUREE_COMPTAGE_LENT = 3.0


# ---------------------------------------------------------------------------
# Fixtures communes
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def cache_rag_health_propre():
    """Le cache est un etat global du module : on part propre, on repart propre."""
    rag_service.reset_rag_health_cache()
    yield
    rag_service.reset_rag_health_cache()


@pytest.fixture
def sondes_db_redis_rapides(monkeypatch):
    """Neutralise les sondes base/redis de `/health` (hors sujet de ce lot)."""
    monkeypatch.setattr("app.main._check_database", lambda: (True, "ok"))
    monkeypatch.setattr("app.main._check_redis", lambda: (True, "ok"))


def _espionner_rag_health_check(monkeypatch, chunks=42):
    """Remplace `rag_service.rag_health_check` par un espion qui compte ses appels.

    Un appel a cet espion vaut un comptage complet (les cinq collections),
    exactement ce que `_check_chroma` declenchait a chaque `/health` avant
    correctif.
    """
    appels = {"n": 0}

    def espion():
        appels["n"] += 1
        return {
            "ok": True,
            "total_chunks": chunks,
            "collections": {"technical": chunks},
            "error": None,
            "chroma_path": "test",
        }

    monkeypatch.setattr(rag_service, "rag_health_check", espion)
    return appels


class _ClientChromaLent:
    """Faux client ChromaDB dont le premier `count()` dort `duree` secondes.

    Repris du protocole de `test_vague_a_a6_rag_count_off_loop.py`.
    """

    def __init__(self, duree: float = DUREE_COMPTAGE_LENT, chunks: int = 99):
        self.duree = duree
        self.chunks = chunks
        self.appels = 0
        self.comptage_demarre = threading.Event()
        self.comptage_termine = threading.Event()
        self._verrou = threading.Lock()

    def get_collection(self, name):  # noqa: ARG002
        return self

    def count(self):
        with self._verrou:
            self.appels += 1
            premier = self.appels == 1
        if premier:
            self.comptage_demarre.set()
            time.sleep(self.duree)
            self.comptage_termine.set()
        return self.chunks


def _attendre(predicat, timeout=15.0, pas=0.05):
    fin = time.monotonic() + timeout
    while time.monotonic() < fin:
        if predicat():
            return True
        time.sleep(pas)
    return predicat()


def _attendre_tache_rag(timeout=15.0):
    """Attend la fin de la tache de fond de demarrage (`app.state.rag_health_task`)."""
    tache = getattr(app.state, "rag_health_task", None)
    if tache is None:
        return False
    return _attendre(tache.done, timeout=timeout)


# ---------------------------------------------------------------------------
# 1. Critere de fin — niveau unite
# ---------------------------------------------------------------------------

def test_get_cached_rag_health_ne_recompte_pas_au_second_appel(monkeypatch):
    """Deux appels consecutifs a `get_cached_rag_health()` : un seul comptage."""
    appels = _espionner_rag_health_check(monkeypatch, chunks=17)

    premier = rag_service.get_cached_rag_health()
    second = rag_service.get_cached_rag_health()

    assert appels["n"] == 1, (
        f"get_cached_rag_health a declenche {appels['n']} comptage(s) pour deux "
        f"appels consecutifs avec un cache frais : le cache n'est pas lu"
    )
    assert premier == second
    assert premier["total_chunks"] == 17


# ---------------------------------------------------------------------------
# 2. Critere de fin — niveau HTTP (la route reelle)
# ---------------------------------------------------------------------------

def test_deux_appels_http_health_consecutifs_ne_declenchent_pas_de_second_comptage(
    monkeypatch, sondes_db_redis_rapides
):
    """Le demarrage compte une fois (A6, reutilisee comme cache) ; deux `/health` n'ajoutent rien."""
    appels = _espionner_rag_health_check(monkeypatch, chunks=5)

    with TestClient(app) as http:
        assert _attendre_tache_rag(), "la sonde de demarrage ne s'est jamais terminee"
        apres_demarrage = appels["n"]

        r1 = http.get("/health")
        apres_premier_appel = appels["n"]

        r2 = http.get("/health")
        apres_second_appel = appels["n"]

    assert r1.status_code == 200, r1.text
    assert r2.status_code == 200, r2.text
    assert apres_demarrage == 1, (
        f"le demarrage a compte {apres_demarrage} fois : la sonde de "
        f"demarrage (A6) devrait rester un comptage unique"
    )
    assert apres_premier_appel == apres_demarrage, (
        "le premier GET /health a declenche un comptage alors que le cache "
        "venait d'etre peuple par le demarrage"
    )
    assert apres_second_appel == apres_premier_appel, (
        "le second GET /health a declenche un comptage : le cache n'est pas "
        "reutilise entre deux appels consecutifs"
    )


# ---------------------------------------------------------------------------
# 3. Controle negatif — cache jamais peuple
# ---------------------------------------------------------------------------

def test_cache_vide_au_premier_appel_declenche_un_comptage_synchrone(monkeypatch):
    """Cache jamais peuple (hors cycle de vie de l'app) : un comptage a lieu, une fois.

    Choix documente en tete de fichier : synchrone plutot que « valeur du
    demarrage », parce qu'ici aucun demarrage n'a eu lieu — l'appel est fait
    en dehors de tout `TestClient(app)`. Sans ce controle, une implementation
    qui renverrait toujours un etat vide (et ne compterait donc jamais)
    passerait quand meme les tests 1 et 2 si l'espion n'etait jamais invoque
    au bon moment.
    """
    appels = _espionner_rag_health_check(monkeypatch, chunks=3)

    assert rag_service._rag_health_cache is None  # etat de depart, garanti par la fixture

    resultat = rag_service.get_cached_rag_health()

    assert appels["n"] == 1, (
        "un cache jamais peuple n'a declenche aucun comptage : /health "
        "servirait un etat invente"
    )
    assert resultat["total_chunks"] == 3


# ---------------------------------------------------------------------------
# 4. Cache perime → recomptage
# ---------------------------------------------------------------------------

def test_cache_perime_declenche_un_recomptage_en_tache_de_fond(monkeypatch):
    """TTL force a 0 (horloge simulee) : le prochain appel voit le cache perime et le rafraichit."""
    appels = _espionner_rag_health_check(monkeypatch, chunks=1)

    # Peuple le cache une premiere fois (comptage n'1, cache "frais" a cet instant).
    premier = rag_service.get_cached_rag_health()
    assert appels["n"] == 1
    assert premier["total_chunks"] == 1

    # Change la valeur que l'espion rendra au prochain comptage, pour distinguer
    # sans ambiguite l'ancien cache du nouveau.
    def espion_v2():
        appels["n"] += 1
        return {
            "ok": True,
            "total_chunks": 2,
            "collections": {},
            "error": None,
            "chroma_path": "test",
        }

    monkeypatch.setattr(rag_service, "rag_health_check", espion_v2)
    # Horloge simulee : TTL a 0 rend le cache immediatement perime, sans sleep reel.
    monkeypatch.setattr(rag_service, "RAG_HEALTH_CACHE_TTL_SECONDS", 0)

    resultat_immediat = rag_service.get_cached_rag_health()
    # Le cache perime est quand meme rendu tel quel (pas d'attente) : l'ancienne
    # valeur, pas la nouvelle — le rafraichissement est en tache de fond.
    assert resultat_immediat["total_chunks"] == 1

    rafraichi = _attendre(lambda: appels["n"] >= 2, timeout=15.0)
    assert rafraichi, "le cache perime n'a declenche aucun second comptage"

    apres_rafraichissement = _attendre(
        lambda: rag_service._rag_health_cache is not None
        and rag_service._rag_health_cache["total_chunks"] == 2,
        timeout=15.0,
    )
    assert apres_rafraichissement, (
        "le second comptage a eu lieu mais le cache n'a pas ete mis a jour "
        f"avec sa valeur (cache actuel : {rag_service._rag_health_cache})"
    )


# ---------------------------------------------------------------------------
# 5. Le rafraichissement de fond n'est pas attendu par /health
# ---------------------------------------------------------------------------

def test_health_ne_bloque_pas_sur_le_rafraichissement_de_fond(
    monkeypatch, sondes_db_redis_rapides
):
    """Cache perime + comptage lent : /health repond vite, le rafraichissement continue seul.

    Le Chroma du bac a sable est vide ou absent (regle 10) : `rag_health_check()`
    y trouverait 0 chunk et `_check_chroma` rendrait `down`, ce qui casserait la
    lecture de `/health` (503) independamment du sujet teste ici. Le demarrage
    est donc lui-meme branche sur un faux client rapide et non vide, pour que le
    seul parametre qui varie dans ce test soit la lenteur du rafraichissement.
    """
    rapide = _ClientChromaLent(duree=0.0, chunks=10)
    monkeypatch.setattr(rag_service, "get_client", lambda: rapide)

    with TestClient(app) as http:
        assert _attendre_tache_rag(), "la sonde de demarrage ne s'est jamais terminee"
        cache_demarrage = rag_service._rag_health_cache
        assert cache_demarrage is not None and cache_demarrage["ok"], (
            f"le demarrage n'a pas peuple un cache sain : precondition du test "
            f"absente (cache={cache_demarrage})"
        )

        # Rend le cache perime (horloge simulee) et branche un comptage lent
        # pour le prochain rafraichissement.
        monkeypatch.setattr(rag_service, "RAG_HEALTH_CACHE_TTL_SECONDS", 0)
        lent = _ClientChromaLent(duree=DUREE_COMPTAGE_LENT, chunks=99)
        monkeypatch.setattr(rag_service, "get_client", lambda: lent)

        t0 = time.monotonic()
        reponse = http.get("/health")
        duree_health = time.monotonic() - t0

        # La mesure ci-dessus ne vaut que si le rafraichissement lent est bien
        # en cours a cet instant : on le constate, on ne le suppose pas.
        demarre = lent.comptage_demarre.wait(timeout=SEUIL_REPONSE)
        encore_en_cours = demarre and not lent.comptage_termine.is_set()

        # Laisse le rafraichissement de fond aboutir avant de fermer la boucle.
        lent.comptage_termine.wait(timeout=15.0)
        # 5 collections comptees a 99 chacune (voir _ClientChromaLent.get_collection) : 495 au total.
        _attendre(lambda: rag_service._rag_health_cache is not None
                  and rag_service._rag_health_cache.get("total_chunks") == 99 * 5,
                  timeout=15.0)

    assert reponse.status_code == 200, reponse.text
    assert duree_health < SEUIL_REPONSE, (
        f"/health a repondu en {duree_health:.2f} s : il a attendu le "
        f"rafraichissement de fond au lieu de servir le cache perime"
    )
    assert encore_en_cours, (
        "le comptage lent n'etait plus en cours au moment de la mesure : le "
        "test ne prouve rien (demarre=%s, termine=%s)"
        % (lent.comptage_demarre.is_set(), lent.comptage_termine.is_set())
    )
    assert rag_service._rag_health_cache["total_chunks"] == 99 * 5, (
        "le rafraichissement de fond ne s'est jamais reflete dans le cache"
    )
