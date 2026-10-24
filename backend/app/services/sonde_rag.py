"""Sonde de sante du RAG, hors du processus de l'API.

Vague 2 / file B — OPS-01 (Astra L906) et « demarrage du backend en ~2 min ».

Mesure (rapport de la file B) : `count()` de chromadb 1.3.4 garde le GIL
pendant toute sa duree. Lance dans `asyncio.to_thread`, il immobilisait quand
meme la boucle d'evenements : au demarrage du 23/10, 89 s entre la fin des
imports et la ligne `[RAG HEALTH] OK`, pendant lesquelles l'API ne repondait
pas (reproduit dans le worktree : premier `GET /` servi apres 10,0 s sur une
copie du Chroma de production a froid).

Le comptage tourne donc dans un PROCESSUS enfant (un interpreteur neuf qui
importe `rag_service` et appelle `rag_health_check`). Le processus de l'API
n'ouvre jamais Chroma pour sa sante ; il attend le resultat sur un tube, ce
qui relache le GIL. La verification n'est pas retiree : elle est deplacee.

Etats rendus a `/health`, sans jamais inventer un succes :
  - ``warming`` : aucune sonde terminee depuis le demarrage -> dependance
    `down` (etat inconnu, pas un vert presume) ;
  - ``ok``      : chaque collection requise (`rag_service.COLLECTIONS`) existe
    et compte au moins un chunk ;
  - echec       : erreur Chroma, collection vide ou absente, enfant sorti sans
    resultat, ou delai depasse (l'enfant est tue) ;
  - ``stale``   : le dernier succes date de plus de `vetuste_max_s` (un
    rafraichissement bloque ne sert plus le dernier vert indefiniment).

Un seul calcul en vol ; rafraichissement toutes les `intervalle_s` (D8 :
30 min), relance plus rapide apres un echec pour constater le retour.

Ce qui n'est PAS sonde ici : l'API d'embeddings (OpenAI, payante) et une
recherche representative. Voir le rapport de la file B (decision de Sam).
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

MARQUEUR = "@@DH_RAG_SONDE@@"
RACINE_BACKEND = Path(__file__).resolve().parents[2]

_CODE_ENFANT = (
    "import json, sys\n"
    "from app.services import rag_service\n"
    "r = rag_service.rag_health_check()\n"
    f"sys.stdout.write('\\n{MARQUEUR}' + json.dumps(r, default=str) + '\\n')\n"
)


def _float_env(nom: str, defaut: float) -> float:
    brut = (os.environ.get(nom) or "").strip()
    if not brut:
        return defaut
    try:
        return float(brut)
    except ValueError:
        raise ValueError(f"{nom}={brut!r} : nombre de secondes attendu") from None


def commande_par_defaut() -> List[str]:
    return [sys.executable, "-c", _CODE_ENFANT]


def _env_enfant() -> Dict[str, str]:
    env = dict(os.environ)
    # chromadb envoie une telemetrie PostHog a la creation du client
    # (« Anonymized telemetry enabled » dans le journal de production).
    # L'enfant n'a aucune raison de sortir sur le reseau.
    env["ANONYMIZED_TELEMETRY"] = "False"
    return env


def _collections_requises() -> List[str]:
    from app.services import rag_service

    return list(rag_service.COLLECTIONS)


def evaluer(resultat: Dict, requises: List[str]) -> Tuple[bool, str]:
    """Juge un resultat de `rag_health_check`. Rend (ok, detail)."""
    if resultat.get("error"):
        return False, f"chroma en echec : {resultat['error']}"
    collections = resultat.get("collections") or {}
    total = resultat.get("total_chunks", 0)
    fautives = []
    for cle in requises:
        valeur = collections.get(cle, "absente")
        if not (isinstance(valeur, int) and not isinstance(valeur, bool) and valeur > 0):
            fautives.append(f"{cle}={valeur}")
    if fautives:
        return False, (
            f"collections vides ou en erreur : {', '.join(fautives)} "
            f"({total} chunks au total, {resultat.get('chroma_path')})"
        )
    return True, f"{total} chunks, {len(requises)} collections"


class SondeRAG:
    def __init__(
        self,
        commande: Optional[List[str]] = None,
        *,
        delai_s: Optional[float] = None,
        intervalle_s: Optional[float] = None,
        intervalle_echec_s: Optional[float] = None,
        vetuste_max_s: Optional[float] = None,
        horloge: Callable[[], float] = time.monotonic,
    ):
        self.commande = commande or commande_par_defaut()
        self.delai_s = delai_s if delai_s is not None else _float_env("DH_RAG_SONDE_DELAI_S", 600.0)
        self.intervalle_s = (
            intervalle_s if intervalle_s is not None else _float_env("DH_RAG_SONDE_INTERVALLE_S", 1800.0)
        )
        self.intervalle_echec_s = (
            intervalle_echec_s if intervalle_echec_s is not None
            else _float_env("DH_RAG_SONDE_INTERVALLE_ECHEC_S", 120.0)
        )
        self.vetuste_max_s = vetuste_max_s if vetuste_max_s is not None else 2 * self.intervalle_s
        self._horloge = horloge
        self._verrou = threading.Lock()
        self._termine = threading.Event()
        self._termine.set()
        self._reinit()

    def _reinit(self) -> None:
        self._en_cours = False
        self._lance_a: Optional[float] = None
        self._resultat: Optional[Dict] = None
        self._ok: Optional[bool] = None
        self._detail = ""
        self._mesure_a: Optional[float] = None      # fin de la derniere sonde
        self._succes_a: Optional[float] = None      # fin du dernier succes
        self._succes_detail = ""
        self._duree_s: Optional[float] = None
        self._proc: Optional[subprocess.Popen] = None
        self._code_retour: Optional[int] = None
        self._arret = False

    # -- cycle de vie -----------------------------------------------------
    def lancer(self) -> bool:
        """Lance une sonde si aucune n'est en vol. Ne bloque pas."""
        with self._verrou:
            if self._en_cours:
                return False
            self._en_cours = True
            self._arret = False
            self._lance_a = self._horloge()
            self._termine.clear()
        threading.Thread(target=self._executer, name="sonde-rag", daemon=True).start()
        return True

    def attendre(self, timeout: float) -> bool:
        """Attend la fin de la sonde en vol (tests, arret)."""
        return self._termine.wait(timeout)

    def arreter(self) -> None:
        """Tue l'enfant en vol (arret de l'application)."""
        with self._verrou:
            self._arret = True
            proc = self._proc
        if proc is not None and proc.poll() is None:
            proc.kill()

    def instantane(self) -> Dict:
        with self._verrou:
            return {
                "en_cours": self._en_cours,
                "ok": self._ok,
                "detail": self._detail,
                "resultat": self._resultat,
                "duree_s": self._duree_s,
                "code_retour": self._code_retour,
            }

    # -- execution --------------------------------------------------------
    def _executer(self) -> None:
        debut = time.monotonic()
        ok, detail, resultat, code = False, "", None, None
        try:
            proc = subprocess.Popen(
                self.commande,
                cwd=str(RACINE_BACKEND),
                env=_env_enfant(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            with self._verrou:
                self._proc = proc
                arret_demande = self._arret
            if arret_demande:
                proc.kill()
            try:
                sortie, erreurs = proc.communicate(timeout=self.delai_s)
            except subprocess.TimeoutExpired:
                proc.kill()
                sortie, erreurs = proc.communicate()
                code = proc.returncode
                detail = f"délai de la sonde dépassé ({self.delai_s:.0f} s) : comptage interrompu"
            else:
                code = proc.returncode
                resultat = self._lire(sortie)
                if resultat is not None:
                    ok, detail = evaluer(resultat, _collections_requises())
                elif self._arret:
                    detail = "sonde interrompue par l'arret de l'application"
                else:
                    queue = (erreurs or "").strip().splitlines()[-3:]
                    detail = f"sonde sortie sans resultat (code {code}) : {' | '.join(queue)}"
        except Exception as e:  # lancement impossible : dit, jamais avale
            detail = f"sonde non lancee : {type(e).__name__}: {e}"
        duree = time.monotonic() - debut
        maintenant = self._horloge()
        with self._verrou:
            self._resultat, self._ok, self._detail = resultat, ok, detail
            self._mesure_a, self._duree_s, self._code_retour = maintenant, duree, code
            if ok:
                self._succes_a, self._succes_detail = maintenant, detail
            self._proc = None
            self._en_cours = False
            self._termine.set()
        chemin = (resultat or {}).get("chroma_path", "?")
        if ok:
            logger.info("[RAG HEALTH] OK — %s at %s (sonde hors processus, %.1f s)", detail, chemin, duree)
        else:
            logger.error("[RAG HEALTH] FAILED — %s (sonde hors processus, %.1f s)", detail, duree)

    @staticmethod
    def _lire(sortie: str) -> Optional[Dict]:
        for ligne in reversed((sortie or "").splitlines()):
            if ligne.startswith(MARQUEUR):
                try:
                    return json.loads(ligne[len(MARQUEUR):])
                except ValueError:
                    return None
        return None

    # -- lecture pour /health --------------------------------------------
    def etat_pour_health(self) -> Tuple[bool, str]:
        """(ok, detail) pour `/health`. Ne compte jamais ; relance au besoin."""
        maintenant = self._horloge()
        with self._verrou:
            en_cours, mesure_a, ok = self._en_cours, self._mesure_a, self._ok
            detail, succes_a, succes_detail = self._detail, self._succes_a, self._succes_detail
            lance_a = self._lance_a

        if mesure_a is None:
            if not en_cours:
                self.lancer()
                return False, "warming: aucune sonde RAG terminee — comptage lance hors processus"
            return False, f"warming: sonde RAG en cours depuis {maintenant - (lance_a or maintenant):.0f} s"

        age = maintenant - mesure_a
        relance = (self.intervalle_s if ok else self.intervalle_echec_s)
        if age >= relance and not en_cours:
            self.lancer()
            en_cours = True
        suffixe = ", rafraichissement en cours" if en_cours else ""

        if not ok:
            return False, f"{detail} (sonde il y a {age:.0f} s{suffixe})"
        age_succes = maintenant - (succes_a or mesure_a)
        if age_succes > self.vetuste_max_s:
            return False, (
                f"stale: dernier comptage reussi il y a {age_succes:.0f} s "
                f"(> {self.vetuste_max_s:.0f} s){suffixe} — {succes_detail}"
            )
        return True, f"{detail} (age {age:.0f} s{suffixe})"


#: Instance du processus de l'API (lancee au demarrage par `app.main`).
sonde = SondeRAG()
