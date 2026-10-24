"""
Classement des chunks RAG existants en `public` / `private` — vague 2, file A,
SEC-04 (audit Astra du 06/09, L86).

Depuis SEC-04, `rag_service.query_collection` ne rend que les chunks dont la
metadonnee `visibility` vaut `public` (sans projet) ou `private` + le projet de
l'appelant. Un chunk SANS cette metadonnee n'est rendu a personne, et la
collection qui en contient est signalee en panne RAG (GL-10). Ce module classe
les chunks anterieurs au correctif.

Regle de prudence (Astra : « ne pas classer automatiquement tous les chunks sans
metadonnee comme publics ») :
  - un chunk qui porte `project_id` ou `document_id`, ou dont l'identifiant a la
    forme `proj<P>_doc<D>_<i>` (celle de `ingest_document`), est PRIVE ; le
    projet et le document deduits de l'identifiant sont reportes en metadonnees ;
  - un chunk sans aucune trace de projet n'est classe PUBLIC que sur decision
    explicite (`--public-sans-projet`) ; sinon il est compte et laisse tel quel ;
  - une valeur de `visibility` inconnue n'est ni corrigee ni devinee : comptee.

Par defaut l'outil travaille A BLANC : il compte et ne modifie rien.

    python -m app.services.rag_visibilite                       # a blanc
    python -m app.services.rag_visibilite --appliquer           # prives seulement
    python -m app.services.rag_visibilite --appliquer --public-sans-projet

Il agit sur le Chroma de `settings.CHROMA_PATH` : en production, le lancer est
une decision d'exploitation, pas un geste de test.
"""
import argparse
import json
import re
import sys
from typing import Dict, Optional, Tuple

from app.services import rag_service

MOTIF_ID_PRIVE = re.compile(r"^proj(\d+)_doc(\d+)_\d+$")
TAILLE_PAGE = 1000
TAILLE_LOT_MAJ = 500


def _classer_chunk(
    identifiant: str, meta: Optional[dict], public_sans_projet: bool
) -> Tuple[Optional[dict], str]:
    """Rend (nouvelle metadonnee ou None si inchangee, categorie)."""
    meta = dict(meta or {})
    valeur = meta.get(rag_service.CLE_VISIBILITE)
    if valeur in rag_service.VISIBILITES:
        return None, "deja_classes"
    if valeur is not None:
        return None, "valeur_inconnue"

    trace = MOTIF_ID_PRIVE.match(identifiant or "")
    if meta.get("project_id") or meta.get("document_id") or trace:
        if trace:
            meta.setdefault("project_id", trace.group(1))
            meta.setdefault("document_id", trace.group(2))
        meta[rag_service.CLE_VISIBILITE] = rag_service.VISIBILITE_PRIVEE
        return meta, "prives_a_marquer"

    if public_sans_projet:
        meta[rag_service.CLE_VISIBILITE] = rag_service.VISIBILITE_PUBLIQUE
        return meta, "publics_a_marquer"
    return None, "sans_projet_non_classes"


def classer_collection(cle: str, appliquer: bool, public_sans_projet: bool) -> Dict:
    collection = rag_service.get_collection(cle)
    rapport = {
        "total": collection.count(),
        "deja_classes": 0,
        "prives_a_marquer": 0,
        "publics_a_marquer": 0,
        "sans_projet_non_classes": 0,
        "valeur_inconnue": 0,
        "modifies": 0,
    }
    a_modifier = []
    decalage = 0
    while True:
        page = collection.get(include=["metadatas"], limit=TAILLE_PAGE, offset=decalage)
        ids = page["ids"] or []
        if not ids:
            break
        for identifiant, meta in zip(ids, page["metadatas"] or [None] * len(ids)):
            nouvelle, categorie = _classer_chunk(identifiant, meta, public_sans_projet)
            rapport[categorie] += 1
            if nouvelle is not None:
                a_modifier.append((identifiant, nouvelle))
        decalage += len(ids)

    if appliquer:
        for debut in range(0, len(a_modifier), TAILLE_LOT_MAJ):
            lot = a_modifier[debut:debut + TAILLE_LOT_MAJ]
            collection.update(ids=[i for i, _ in lot], metadatas=[m for _, m in lot])
            rapport["modifies"] += len(lot)
        # Le verdict de classement mis en cache par query_collection est perime.
        cle_cache = (cle, str(getattr(collection, "id", "")))
        rag_service._collections_classees.discard(cle_cache)
        rag_service._collections_non_classees.pop(cle_cache, None)
    return rapport


def classer_collections(appliquer: bool = False, public_sans_projet: bool = False) -> Dict:
    """Classe les cinq collections de `rag_service.COLLECTIONS`.

    Une collection introuvable donne une entree `{"erreur": ...}` : elle n'est
    pas sautee en silence.
    """
    rapport = {}
    for cle in rag_service.COLLECTIONS:
        try:
            rapport[cle] = classer_collection(cle, appliquer, public_sans_projet)
        except Exception as exc:  # noqa: BLE001 — rapporte, pas avale
            rapport[cle] = {"erreur": f"{type(exc).__name__}: {exc}"}
    return rapport


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--appliquer", action="store_true", help="ecrire (sinon : a blanc)")
    parser.add_argument(
        "--public-sans-projet",
        action="store_true",
        help="classer PUBLIC les chunks sans aucune trace de projet (decision explicite)",
    )
    args = parser.parse_args(argv)
    rapport = classer_collections(args.appliquer, args.public_sans_projet)
    print(json.dumps(
        {"chroma_path": rag_service.CHROMA_PATH, "appliquer": args.appliquer,
         "public_sans_projet": args.public_sans_projet, "collections": rapport},
        indent=2, ensure_ascii=False,
    ))
    return 1 if any("erreur" in r for r in rapport.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
