"""
Vague 2 / file A — RGPD-03 : un effacement partiel devenait définitif, sans
reprise fiable (audit Astra du 06/09, L870).

Défauts visés :
  - `AccountService._purger_chroma` avalait une erreur Chroma (et
    `rag_service.delete_project_document_chunks` la transformait déjà en
    « 0 chunk supprimé ») ; les lignes SQL qui désignaient les chunks étaient
    ensuite détruites : les chunks restants n'étaient plus retrouvables ;
  - aucune trace durable de l'effacement en cours ; le compte n'était pas
    désactivé d'abord ;
  - `DELETE /projects/{id}/documents/{doc}` supprimait la ligne même quand la
    purge Chroma échouait, et ne purgeait pas un document en erreur porteur de
    chunks partiels ;
  - `DELETE /pm-orchestrator/projects/{id}` (CRUD) ne nettoyait ni Chroma ni
    les fichiers ; un effacement de compte ultérieur ne les retrouvait plus.

Critère (AS-06) : un effacement est complet ou rejouable, jamais partiel et
définitif. Test : effacement interrompu au milieu (exception injectée) → état
cohérent, puis reprise idempotente.

Chroma : répertoire temporaire ; embeddings bouchons déterministes. Les
alertes admin sont capturées (aucun envoi réel).
"""
import uuid
from pathlib import Path

import pytest
from chromadb.api.models.Collection import Collection

from app.config import settings
from app.main import app
from app.models.project import Project
from app.models.project_document import ProjectDocument
from app.models.sds_version import SDSVersion
from app.models.user import User
from app.services import rag_service
from app.services.account_service import AccountService
from tests.vague2_a_outils import client_sans_lifespan, creer_tenant, installer_chroma_temporaire


# ---------------------------------------------------------------------------
# Outillage
# ---------------------------------------------------------------------------

def _compte(db, email, nb_docs):
    t = creer_tenant(db, email)
    pid = t["project"].id
    dossier_docs = Path(settings.UPLOAD_DIR) / "project_documents" / str(pid)
    dossier_docs.mkdir(parents=True, exist_ok=True)
    t["docs"], t["fichiers"] = [], []
    for i in range(nb_docs):
        chemin = dossier_docs / f"{uuid.uuid4().hex}.txt"
        chemin.write_text(f"contenu {email} {i}")
        doc = ProjectDocument(project_id=pid, filename=f"doc{i}.txt", file_path=str(chemin),
                              file_size=10, collection_name="technical", status="ready")
        db.add(doc)
        db.commit()
        db.refresh(doc)
        doc.chunk_count = rag_service.ingest_document(
            "technical", [f"{email} fragment {i}-0", f"{email} fragment {i}-1"],
            metadata={"source": doc.filename}, project_id=pid, document_id=doc.id,
        )
        db.commit()
        t["docs"].append(doc)
        t["fichiers"].append(chemin)
    dossier_sds = Path(settings.OUTPUT_DIR) / "projects" / str(pid)
    dossier_sds.mkdir(parents=True, exist_ok=True)
    sds = dossier_sds / f"{uuid.uuid4().hex}_SDS_v1.html"
    sds.write_text("<html>SDS confidentiel</html>")
    db.add(SDSVersion(project_id=pid, version_number=1, file_path=str(sds), file_name=sds.name))
    db.commit()
    t["fichiers"].append(sds)
    return t


def _chunks_du_projet(chroma, pid):
    total = []
    for info in rag_service.COLLECTIONS.values():
        total += chroma.get_collection(info["name"]).get(where={"project_id": str(pid)})["ids"]
    return total


@pytest.fixture
def env(db_session, tmp_path, monkeypatch):
    chroma = installer_chroma_temporaire(tmp_path / "chroma_rgpd03", monkeypatch)
    alertes = []
    from app.services import admin_alert_service
    monkeypatch.setattr(admin_alert_service, "alerter_admin",
                        lambda sujet, corps, **kw: alertes.append((sujet, corps, kw)) or False)
    a = _compte(db_session, "alice-rgpd03@example.test", 2)
    b = _compte(db_session, "bob-rgpd03@example.test", 1)
    yield {"db": db_session, "chroma": chroma, "a": a, "b": b, "alertes": alertes, "monkeypatch": monkeypatch}
    app.dependency_overrides.clear()


def _injecter_panne_chroma(monkeypatch, prefixe=None):
    """`Collection.delete` lève pour les ids qui commencent par `prefixe`
    (tous si None). Rend une fonction qui retire l'injection."""
    original = Collection.delete
    etat = {"active": True}

    def delete(self, ids=None, *args, **kwargs):
        if etat["active"] and (prefixe is None or any(str(i).startswith(prefixe) for i in (ids or []))):
            raise RuntimeError("Chroma injoignable (panne injectee)")
        return original(self, ids, *args, **kwargs)

    monkeypatch.setattr(Collection, "delete", delete)
    return lambda: etat.update(active=False)


def _b_intact(env):
    db, chroma, b = env["db"], env["chroma"], env["b"]
    db.expire_all()
    assert len(_chunks_du_projet(chroma, b["project"].id)) == 2
    assert all(f.exists() for f in b["fichiers"])
    assert db.query(Project).filter_by(id=b["project"].id).count() == 1
    assert db.query(User).get(b["user"].id).is_active


# ---------------------------------------------------------------------------
# Effacement de compte interrompu, puis repris
# ---------------------------------------------------------------------------

def test_effacement_interrompu_par_une_panne_chroma_puis_repris_idempotent(env):
    db, chroma, a = env["db"], env["chroma"], env["a"]
    pid, doc2 = a["project"].id, a["docs"][1]
    retirer = _injecter_panne_chroma(env["monkeypatch"], prefixe=f"proj{pid}_doc{doc2.id}_")

    rapport, leve = None, None
    try:
        rapport = AccountService(db).supprimer(a["user"])
    except Exception as exc:  # noqa: BLE001 — on examine ce qui est levé
        leve = exc
    assert leve is not None, f"effacement déclaré réussi malgré la panne Chroma : {rapport}"
    assert type(leve).__name__ == "EffacementIncomplet", repr(leve)

    # État cohérent après l'interruption.
    db.rollback()
    db.expire_all()
    utilisateur = db.query(User).get(a["user"].id)
    assert utilisateur.is_active is False, "le compte doit être bloqué dès le début de l'effacement"
    assert not utilisateur.email.endswith("anonymised.invalid"), "anonymisé alors que l'effacement est partiel"
    assert db.query(ProjectDocument).filter_by(project_id=pid).count() == 2, (
        "les références SQL des chunks restants ont été détruites : effacement partiel définitif"
    )
    restants = _chunks_du_projet(chroma, pid)
    assert restants and all(i.startswith(f"proj{pid}_doc{doc2.id}_") for i in restants), restants

    from app.models.effacement_compte import EffacementCompte
    effacement = db.query(EffacementCompte).filter_by(user_id=a["user"].id).one()
    assert effacement.statut == "partiel"
    assert effacement.erreurs and "panne injectee" in str(effacement.erreurs)
    assert env["alertes"], "un effacement partiel doit alerter l'exploitant"
    _b_intact(env)

    # Reprise, panne levée.
    retirer()
    rapport = AccountService(db).reprendre(effacement.id)
    db.expire_all()
    assert rapport["statut"] == "compte supprimé"
    assert _chunks_du_projet(chroma, pid) == []
    assert not any(f.exists() for f in a["fichiers"]), [str(f) for f in a["fichiers"] if f.exists()]
    assert db.query(Project).filter_by(user_id=a["user"].id).count() == 0
    assert db.query(User).get(a["user"].id).email.endswith("anonymised.invalid")
    effacement = db.query(EffacementCompte).get(effacement.id)
    assert effacement.statut == "termine" and effacement.termine_le is not None
    assert str(a["fichiers"][0]) not in str(effacement.perimetre), "chemins conservés après effacement terminé"
    _b_intact(env)

    # Idempotence : rejouer ne lève rien et ne change rien.
    deuxieme = AccountService(db).reprendre(effacement.id)
    assert deuxieme["statut"] == "compte supprimé"
    AccountService(db).supprimer(db.query(User).get(a["user"].id))
    db.expire_all()
    assert db.query(EffacementCompte).filter_by(user_id=a["user"].id).count() == 1
    assert db.query(EffacementCompte).get(effacement.id).statut == "termine"
    _b_intact(env)


def test_effacement_interrompu_pendant_l_etape_base_puis_repris(env, monkeypatch):
    db, chroma, a = env["db"], env["chroma"], env["a"]

    original = AccountService._supprimer_chat_logs

    def en_panne(self, utilisateur):
        raise RuntimeError("base indisponible (panne injectee)")

    monkeypatch.setattr(AccountService, "_supprimer_chat_logs", en_panne)
    leve = None
    try:
        AccountService(db).supprimer(a["user"])
    except Exception as exc:  # noqa: BLE001
        leve = exc
    assert type(leve).__name__ == "EffacementIncomplet", repr(leve)

    db.rollback()
    db.expire_all()
    assert db.query(User).get(a["user"].id).is_active is False
    assert db.query(Project).filter_by(user_id=a["user"].id).count() == 1, "transaction SQL non atomique"
    from app.models.effacement_compte import EffacementCompte
    effacement = db.query(EffacementCompte).filter_by(user_id=a["user"].id).one()
    assert effacement.statut == "partiel"

    # Panne levée (seule cette injection : Chroma temporaire et bouchon
    # d'alerte restent en place).
    monkeypatch.setattr(AccountService, "_supprimer_chat_logs", original)
    from app.services import account_service as module_service
    n = module_service.reprendre_effacements_en_attente(db)
    assert n == [effacement.id]
    db.expire_all()
    assert db.query(Project).filter_by(user_id=a["user"].id).count() == 0
    assert db.query(EffacementCompte).get(effacement.id).statut == "termine"
    assert module_service.reprendre_effacements_en_attente(db) == []


def test_route_effacement_en_echec_repond_503_puis_reprise_par_le_meme_jeton(env):
    db, chroma, a = env["db"], env["chroma"], env["a"]
    client = client_sans_lifespan(app, db)
    pid = a["project"].id
    retirer = _injecter_panne_chroma(env["monkeypatch"])

    r = client.delete("/api/account", headers=a["headers"])
    assert r.status_code == 503, r.text
    assert "effacement" in r.json()["detail"].lower()
    db.expire_all()
    assert db.query(User).get(a["user"].id).is_active is False

    retirer()
    r2 = client.delete("/api/account", headers=a["headers"])
    assert r2.status_code == 200, r2.text
    assert _chunks_du_projet(chroma, pid) == []
    _b_intact(env)


# ---------------------------------------------------------------------------
# Un échec Chroma reste un échec, pas zéro
# ---------------------------------------------------------------------------

def test_echec_de_purge_chroma_n_est_pas_compte_zero(env):
    a = env["a"]
    _injecter_panne_chroma(env["monkeypatch"])
    with pytest.raises(Exception):
        rag_service.delete_project_document_chunks("technical", a["docs"][0].id)


# ---------------------------------------------------------------------------
# Suppression d'un document, d'un projet
# ---------------------------------------------------------------------------

def test_suppression_document_en_echec_chroma_conserve_ligne_et_fichier(env):
    db, chroma, a = env["db"], env["chroma"], env["a"]
    client = client_sans_lifespan(app, db)
    doc = a["docs"][0]
    retirer = _injecter_panne_chroma(env["monkeypatch"])

    r = client.delete(f"/api/projects/{a['project'].id}/documents/{doc.id}", headers=a["headers"])
    assert r.status_code == 502, r.text
    db.expire_all()
    assert db.query(ProjectDocument).get(doc.id) is not None
    assert Path(doc.file_path).exists()

    retirer()
    r2 = client.delete(f"/api/projects/{a['project'].id}/documents/{doc.id}", headers=a["headers"])
    assert r2.status_code == 200, r2.text
    assert not any(i.startswith(f"proj{a['project'].id}_doc{doc.id}_") for i in _chunks_du_projet(chroma, a["project"].id))


def test_suppression_d_un_document_en_erreur_purge_ses_chunks_partiels(env):
    db, chroma, a = env["db"], env["chroma"], env["a"]
    client = client_sans_lifespan(app, db)
    doc = a["docs"][0]
    doc.status, doc.chunk_count = "error", 0  # ingestion interrompue : chunks partiels
    db.commit()

    r = client.delete(f"/api/projects/{a['project'].id}/documents/{doc.id}", headers=a["headers"])
    assert r.status_code == 200, r.text
    assert not any(i.startswith(f"proj{a['project'].id}_doc{doc.id}_") for i in _chunks_du_projet(chroma, a["project"].id))


def test_suppression_d_un_projet_par_le_crud_purge_chroma_et_fichiers(env):
    db, chroma, a = env["db"], env["chroma"], env["a"]
    client = client_sans_lifespan(app, db)
    pid = a["project"].id

    r = client.delete(f"/api/pm-orchestrator/projects/{pid}", headers=a["headers"])
    assert r.status_code == 204, r.text
    assert _chunks_du_projet(chroma, pid) == [], "chunks orphelins après suppression du projet"
    assert not any(f.exists() for f in a["fichiers"]), "fichiers orphelins après suppression du projet"
    _b_intact(env)


def test_suppression_d_un_projet_en_echec_chroma_conserve_le_projet(env):
    db, chroma, a = env["db"], env["chroma"], env["a"]
    client = client_sans_lifespan(app, db)
    pid = a["project"].id
    _injecter_panne_chroma(env["monkeypatch"])

    r = client.delete(f"/api/pm-orchestrator/projects/{pid}", headers=a["headers"])
    assert r.status_code == 502, r.text
    db.expire_all()
    assert db.query(Project).filter_by(id=pid).count() == 1
    assert db.query(ProjectDocument).filter_by(project_id=pid).count() == 2


# ---------------------------------------------------------------------------
# Reprises après revue 1 (testeur-A)
# ---------------------------------------------------------------------------

def test_un_effacement_orphelin_n_arrete_pas_la_reprise_des_autres(env):
    """Reprise 2 : `reprendre_effacements_en_attente` ne captait que
    `EffacementIncomplet` ; un effacement dont le compte a disparu
    (`user_id` NULL par `ondelete=SET NULL`) levait `LookupError` et arrêtait
    la boucle (sonde C : « statut du second : en_cours »)."""
    from app.models.effacement_compte import EffacementCompte
    from app.services import account_service as module_service

    db, a = env["db"], env["a"]
    orphelin = EffacementCompte(user_id=None, statut="partiel", perimetre={}, etapes={}, erreurs=[], tentatives=1)
    db.add(orphelin)
    db.commit()
    valide = AccountService(db)._ouvrir_effacement(a["user"])
    assert orphelin.id < valide.id  # l'orphelin passe en premier dans la boucle

    leve, termines = None, None
    try:
        termines = module_service.reprendre_effacements_en_attente(db)
    except Exception as exc:  # noqa: BLE001
        leve = exc
    assert leve is None, f"la boucle de reprise s'arrête sur l'orphelin : {leve!r}"
    assert termines == [valide.id]

    db.expire_all()
    relu = db.query(EffacementCompte).get(orphelin.id)
    assert relu.statut == "bloque", relu.statut
    assert "introuvable" in str(relu.erreurs)
    assert any(str(orphelin.id) in corps for _, corps, _ in env["alertes"]), env["alertes"]
    assert db.query(EffacementCompte).get(valide.id).statut == "termine"
    # Un orphelin bloqué n'est pas repris en boucle à chaque passage.
    assert module_service.reprendre_effacements_en_attente(db) == []

