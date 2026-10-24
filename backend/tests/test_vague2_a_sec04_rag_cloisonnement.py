"""
Vague 2 / file A — SEC-04 : le RAG « global » incluait les documents privés.

Audit Astra du 06/09, L86 (`rag_service.py`, `where_filter = ... if project_id
else None`). `project_id=None` ne voulait pas dire « documentation publique »
mais « aucun filtre » : tous les chunks, privés compris. À l'inverse, avec un
projet, la requête ne rendait QUE ses documents et excluait le corpus public.

Ce que ces tests exigent (critère AS-06) :
  - deux tenants A et B ; A ingère un document par la VRAIE route d'upload ;
    la recherche RAG de B et la recherche globale ne rendent aucun fragment
    de A — à tous les niveaux d'appel (`query_collection`, `query_rag`,
    `get_salesforce_context`, `get_code_context`) et sur les cinq collections ;
  - contrôle négatif : la recherche du projet de A rend bien son fragment
    (le test ne passe pas « à vide ») ;
  - le corpus public marqué reste visible de tous, avec ou sans projet ;
  - une ingestion privée sans projet/document est refusée ;
  - une collection dont des chunks n'ont pas de visibilité n'est pas servie
    en silence : l'appel est signalé comme panne RAG (GL-10) ;
  - l'outil de classement des chunks existants ne classe PAS automatiquement
    public un chunk sans métadonnée (Astra : « backfill prudent »).

Embeddings : `tests.vague2_a_outils.embedding_bouchon`, déterministe, sans
réseau. Chroma : répertoire temporaire, jamais /opt/digital-humans/rag.
"""
import pytest

from app.main import app
from app.services import rag_service
from tests.vague2_a_outils import (
    client_sans_lifespan,
    creer_tenant,
    embedding_bouchon,
    installer_chroma_temporaire,
)

SENTINELLE_A = "SENTINELLE-SEC04-TENANT-A-4c9e1b7a"
TEXTE_PUBLIC = "DOC-PUBLIQUE-SEC04-ed21f0"
QUESTION = "quelles sont les regles de partage"
# Assez grand pour que chaque requête rende TOUT le contenu de la collection
# temporaire : un fragment absent l'est par filtrage, pas par distance.
N = 50


@pytest.fixture
def chroma(tmp_path, monkeypatch):
    client = installer_chroma_temporaire(tmp_path / "chroma_sec04", monkeypatch)
    for cle, info in rag_service.COLLECTIONS.items():
        client.get_collection(info["name"]).add(
            ids=[f"public-{cle}"],
            documents=[f"{TEXTE_PUBLIC} — documentation Salesforce ({cle})"],
            embeddings=[embedding_bouchon(cle)],
            metadatas=[{"source": "doc_publique.txt", "visibility": "public"}],
        )
    return client


@pytest.fixture
def deux_tenants(db_session, chroma, tmp_path, monkeypatch):
    from app.api.routes import documents as documents_routes

    monkeypatch.setattr(documents_routes, "DOCUMENTS_DIR", tmp_path / "docs")
    client = client_sans_lifespan(app, db_session)
    a = creer_tenant(db_session, "alice-sec04@example.test")
    b = creer_tenant(db_session, "bob-sec04@example.test")

    reponse = client.post(
        f"/api/projects/{a['project'].id}/documents",
        files={
            "file": (
                "cahier_a.txt",
                (f"{SENTINELLE_A} clause confidentielle du client A. " * 40).encode(),
                "text/plain",
            )
        },
        headers=a["headers"],
    )
    assert reponse.status_code == 200, reponse.text
    assert reponse.json()["status"] == "ready", reponse.text
    assert reponse.json()["chunk_count"] >= 1
    yield {"a": a, "b": b, "client": client}
    app.dependency_overrides.clear()


def _textes(docs):
    return "\n".join(docs)


def test_le_document_prive_de_a_ne_sort_ni_pour_b_ni_en_recherche_globale(deux_tenants):
    a, b = deux_tenants["a"], deux_tenants["b"]
    pid_a, pid_b = a["project"].id, b["project"].id

    # Contrôle négatif : le fragment de A existe bien et sort pour A.
    docs_a, metas_a = rag_service.query_collection("technical", QUESTION, N, project_id=pid_a)
    assert SENTINELLE_A in _textes(docs_a), "le document de A n'a pas été ingéré : le test ne prouverait rien"

    fuites = []
    for cle in rag_service.COLLECTIONS:
        for libelle, pid in (("B", pid_b), ("global", None)):
            docs, _ = rag_service.query_collection(cle, QUESTION, N, project_id=pid)
            if SENTINELLE_A in _textes(docs):
                fuites.append(f"query_collection({cle}, project_id={libelle})")

    for libelle, pid in (("B", pid_b), ("global", None)):
        for agent in ("default", "pm", "developer_apex"):
            res = rag_service.query_rag(QUESTION, n_results=N, agent_type=agent, project_id=pid, n_candidates=3 * N)
            if SENTINELLE_A in _textes(res["documents"]):
                fuites.append(f"query_rag(agent={agent}, project_id={libelle})")
        if SENTINELLE_A in rag_service.get_salesforce_context(QUESTION, n_results=N, project_id=pid):
            fuites.append(f"get_salesforce_context(project_id={libelle})")
        for langage in ("apex", "lwc"):
            if SENTINELLE_A in rag_service.get_code_context(QUESTION, langage, N, project_id=pid):
                fuites.append(f"get_code_context({langage}, project_id={libelle})")

    assert fuites == [], f"le document privé de A sort ailleurs que pour A : {fuites}"


def test_le_corpus_public_reste_visible_avec_et_sans_projet(deux_tenants):
    a, b = deux_tenants["a"], deux_tenants["b"]
    for libelle, pid in (("A", a["project"].id), ("B", b["project"].id), ("global", None)):
        docs, _ = rag_service.query_collection("technical", QUESTION, N, project_id=pid)
        assert TEXTE_PUBLIC in _textes(docs), (
            f"le corpus public n'est pas rendu pour {libelle} : avec un projet, "
            f"la requête doit rendre public OU projet autorisé (Astra SEC-04)"
        )
    docs_a, _ = rag_service.query_collection("technical", QUESTION, N, project_id=a["project"].id)
    assert SENTINELLE_A in _textes(docs_a)


def test_ingestion_privee_sans_projet_ou_sans_document_refusee(chroma):
    collection = chroma.get_collection(rag_service.COLLECTIONS["technical"]["name"])
    avant = collection.count()
    for kwargs in ({"project_id": None, "document_id": 12}, {"project_id": 7, "document_id": None}, {}):
        with pytest.raises(ValueError):
            rag_service.ingest_document("technical", ["texte privé orphelin"], metadata={"source": "x"}, **kwargs)
    assert collection.count() == avant, "un chunk sans projet ou sans document a été ingéré"


def test_ingestion_privee_marque_chaque_chunk_prive_et_rattache(chroma):
    n = rag_service.ingest_document("technical", ["un", "deux"], metadata={"source": "x"}, project_id=7, document_id=3)
    assert n == 2
    lus = chroma.get_collection(rag_service.COLLECTIONS["technical"]["name"]).get(where={"document_id": "3"})
    assert len(lus["ids"]) == 2
    for meta in lus["metadatas"]:
        assert meta["visibility"] == "private"
        assert meta["project_id"] == "7"


def test_une_collection_non_classee_est_signalee_pas_servie_en_silence(chroma, monkeypatch):
    """Un chunk sans métadonnée `visibility` (corpus antérieur au correctif)
    n'est ni deviné public ni servi : la collection est signalée en panne."""
    chroma.get_collection(rag_service.COLLECTIONS["technical"]["name"]).add(
        ids=["ancien-0"],
        documents=["ANCIEN-CHUNK-SANS-VISIBILITE"],
        embeddings=[embedding_bouchon("ancien")],
        metadatas=[{"source": "ancien.txt"}],
    )
    signalements = []
    monkeypatch.setattr(rag_service, "signaler_rag_indisponible", lambda cle, err: signalements.append((cle, err)))

    docs, _ = rag_service.query_collection("technical", QUESTION, N, project_id=None)

    assert "ANCIEN-CHUNK-SANS-VISIBILITE" not in _textes(docs)
    assert docs == [], "une collection partiellement classée ne doit rien servir"
    assert [cle for cle, _ in signalements] == ["technical"], signalements
    assert "visibility" in str(signalements[0][1])

    # Contrôle négatif : une collection entièrement classée n'est pas signalée.
    signalements.clear()
    docs_ops, _ = rag_service.query_collection("operations", QUESTION, N, project_id=None)
    assert TEXTE_PUBLIC in _textes(docs_ops)
    assert signalements == []


# ---------------------------------------------------------------------------
# Classement des chunks existants (backfill prudent)
# ---------------------------------------------------------------------------

def _peupler_anciens(chroma):
    coll = chroma.get_collection(rag_service.COLLECTIONS["business"]["name"])
    coll.add(
        ids=["doc-sf-0", "proj5_doc9_0", "uuid-orphelin"],
        documents=["ANCIEN-PUBLIC", "ANCIEN-PRIVE-PAR-ID", "ANCIEN-PRIVE-PAR-META"],
        embeddings=[embedding_bouchon("p"), embedding_bouchon("q"), embedding_bouchon("r")],
        metadatas=[{"source": "sf_docs.txt"}, {"source": "client.txt"}, {"source": "c.txt", "project_id": "5", "document_id": "11"}],
    )
    return coll


def test_classement_a_blanc_ne_modifie_rien_et_compte(chroma):
    from app.services import rag_visibilite

    coll = _peupler_anciens(chroma)
    rapport = rag_visibilite.classer_collections(appliquer=False)

    business = rapport["business"]
    assert business["prives_a_marquer"] == 2
    assert business["sans_projet_non_classes"] == 1
    assert business["modifies"] == 0
    lus = coll.get(ids=["doc-sf-0", "proj5_doc9_0", "uuid-orphelin"])
    assert all("visibility" not in m for m in lus["metadatas"])


def test_classement_ne_rend_pas_public_un_chunk_sans_metadonnee_sans_decision(chroma, monkeypatch):
    from app.services import rag_visibilite

    coll = _peupler_anciens(chroma)
    rag_visibilite.classer_collections(appliquer=True)

    par_id = dict(zip(*[coll.get(ids=["doc-sf-0", "proj5_doc9_0", "uuid-orphelin"])[k] for k in ("ids", "metadatas")]))
    assert par_id["proj5_doc9_0"]["visibility"] == "private"
    assert par_id["proj5_doc9_0"]["project_id"] == "5"
    assert par_id["uuid-orphelin"]["visibility"] == "private"
    assert "visibility" not in par_id["doc-sf-0"], "classé public sans décision explicite"

    # Toujours non classée : la collection reste signalée.
    signalements = []
    monkeypatch.setattr(rag_service, "signaler_rag_indisponible", lambda cle, err: signalements.append(cle))
    rag_service.query_collection("business", QUESTION, N, project_id=None)
    assert signalements == ["business"]


def test_classement_public_explicite_puis_idempotent(chroma):
    from app.services import rag_visibilite

    coll = _peupler_anciens(chroma)
    premier = rag_visibilite.classer_collections(appliquer=True, public_sans_projet=True)
    assert premier["business"]["modifies"] == 3

    docs, _ = rag_service.query_collection("business", QUESTION, N, project_id=None)
    assert "ANCIEN-PUBLIC" in _textes(docs)
    assert "ANCIEN-PRIVE" not in _textes(docs)
    docs_5, _ = rag_service.query_collection("business", QUESTION, N, project_id=5)
    assert "ANCIEN-PRIVE-PAR-ID" in _textes(docs_5) and "ANCIEN-PRIVE-PAR-META" in _textes(docs_5)

    second = rag_visibilite.classer_collections(appliquer=True, public_sans_projet=True)
    assert all(r["modifies"] == 0 for r in second.values()), second
    assert coll.count() == 4
