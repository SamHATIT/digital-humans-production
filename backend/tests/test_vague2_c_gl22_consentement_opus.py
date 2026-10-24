"""
Vague 2 / file C — GL-22 : consentement Opus au palier Pro.

Le site promet « Opus on opt-in, cost shown before each call ». Décision Sam
du 17/09 : on ajoute le recueil. Critère de sortie de la mission : « un
utilisateur Pro ne déclenche jamais Opus sans l'avoir accepté pour ce coût ».

Ce que ces tests exigent :

  - routeur : un appel routé vers un modèle `requires_opt_in` ne part sur ce
    modèle que si un consentement ACCEPTÉ existe pour CETTE exécution, et
    tant que le cumul mesuré + l'estimation de l'appel tient dans le montant
    accepté. Sinon : repli sur Sonnet, ANNONCÉ (marque `degraded` sur
    l'exécution, visible dans la progression), jamais silencieux ;
  - route de lancement : un Pro dont Marcus serait servi par Opus ne lance
    pas sans décision ; la décision est tracée (utilisateur, exécution, date,
    montant) ; un montant périmé est refusé ;
  - migration 023c : `claude-opus-5` repasse à `requires_opt_in = true`.

Aucun appel réseau : le transport du routeur est remplacé et capture le
fournisseur réellement appelé. `_select_provider` est le code de production
(profil `cloud`, palier `pro`).
"""
from __future__ import annotations

import asyncio
import importlib.util
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from app.main import app
from app.models.credit import (
    CreditBalance,
    CreditTransaction,
    ModelPricing,
    TierConfig,
)
from app.models.execution import Execution, ExecutionStatus
from app.models.project import Project
from app.models.user import User
from app.services import llm_router_service as routeur_mod
from app.services.llm_router_service import LLMRequest, LLMResponse, LLMRouterService
from app.utils.dependencies import get_current_user, get_current_user_from_token_or_header

BACKEND = Path(__file__).resolve().parent.parent
OPUS = "claude-opus-5"
SONNET = "claude-sonnet-5"
EXECUTE_URL = "/api/pm-orchestrator/execute"
ESTIMATE_URL = "/api/pm-orchestrator/execute/opus-estimate"

# Estimation d'un appel Marcus : max_tokens (32 000, llm_routing.yaml) en
# entrée ET en sortie, comme la réservation BILL-01.
#   Opus   : 32 × 5 + 32 × 25 = 960 crédits
#   Sonnet : 32 × 1 + 32 × 5  = 192 crédits
CREDITS_OPUS_PAR_APPEL = 960
CREDITS_SONNET_PAR_APPEL = 192


def _model_ids_du_yaml():
    conf = yaml.safe_load((BACKEND / "config" / "llm_routing.yaml").read_text())
    ids = {}
    for fournisseur, pconf in (conf.get("providers") or {}).items():
        for nom, mconf in ((pconf or {}).get("models") or {}).items():
            ids[f"{fournisseur}/{nom}"] = (mconf or {}).get("model_id", nom)
    return ids


@pytest.fixture
def socle(db_session):
    db_session.add_all([
        TierConfig(tier_name="pro", monthly_credits=15000, daily_credits_cap=None,
                   price_eur_monthly=79, description="pro"),
        ModelPricing(model_name=OPUS, credits_per_1k_input=5.0,
                     credits_per_1k_output=25.0, allowed_tiers="pro,team",
                     requires_opt_in=True, is_active=True),
        ModelPricing(model_name=SONNET, credits_per_1k_input=1.0,
                     credits_per_1k_output=5.0, allowed_tiers="pro,team",
                     requires_opt_in=False, is_active=True),
    ])
    db_session.commit()


def _compte(db_session, palier="pro", solde=15000):
    s = uuid.uuid4().hex[:8]
    u = User(email=f"gl22-{s}@exemple.test", hashed_password="x",
             name=f"GL-22 {s}", subscription_tier=palier)
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    db_session.add(CreditBalance(user_id=u.id, included_credits=solde, used_credits=0,
                                 overage_credits=0, last_reset_at=datetime.now(timezone.utc)))
    db_session.commit()
    return u


def _execution(db_session, user):
    p = Project(user_id=user.id, name="Projet GL-22")
    db_session.add(p)
    db_session.commit()
    e = Execution(project_id=p.id, user_id=user.id, status=ExecutionStatus.RUNNING)
    db_session.add(e)
    db_session.commit()
    db_session.refresh(e)
    return e


@pytest.fixture
def transport(monkeypatch):
    """Transport remplacé : capture le fournisseur appelé, rend 1 000 / 1 000
    jetons. `_get_model_id` lit le YAML (sans clé Anthropic dans l'environnement
    de test, le routeur de production rendrait l'alias au lieu du model_id)."""
    ids = _model_ids_du_yaml()
    appels = []

    async def _faux(self, request, provider_str):
        appels.append(provider_str)
        return LLMResponse(content="ok", provider=provider_str,
                           model_id=ids.get(provider_str, provider_str),
                           tokens_in=1000, tokens_out=1000, cost_usd=0.0,
                           latency_ms=1, success=True)

    monkeypatch.setattr(LLMRouterService, "_call_provider", _faux)
    monkeypatch.setattr(LLMRouterService, "_get_model_id",
                        lambda self, p: ids.get(p, p.split("/", 1)[-1]))
    monkeypatch.setattr(routeur_mod, "_router_instance", None, raising=False)
    monkeypatch.delenv("DH_DEPLOYMENT_PROFILE", raising=False)
    return appels


def _appel_marcus(user, execution, agent="architect"):
    routeur = LLMRouterService(profile="cloud")
    return asyncio.run(routeur.complete(LLMRequest(
        prompt="x", agent_type=agent, max_tokens=32000, user_id=user.id,
        execution_id=execution.id, subscription_tier="pro")))


def _consentir(db_session, user, execution, decision, credits):
    from app.models.consentement_opus import ConsentementOpus
    db_session.add(ConsentementOpus(user_id=user.id, execution_id=execution.id,
                                    model_name=OPUS, decision=decision,
                                    credits_estimes=credits, texte_version="test"))
    db_session.commit()


def _degrades(db_session, execution):
    db_session.expire_all()
    e = db_session.get(Execution, execution.id)
    return [d.get("motif") for d in (e.degraded or [])]


def _modeles_debites(db_session, user):
    db_session.expire_all()
    return [t.model_used for t in db_session.query(CreditTransaction)
            .filter_by(user_id=user.id).order_by(CreditTransaction.id)]


# ─────────────────────────────────────────────────────────────────────
# 1. Routeur
# ─────────────────────────────────────────────────────────────────────


def test_sans_consentement_marcus_passe_sur_sonnet_et_le_repli_est_annonce(
        db_session, socle, transport):
    u = _compte(db_session)
    e = _execution(db_session, u)

    r = _appel_marcus(u, e)

    assert r.success
    assert transport == ["anthropic/claude-sonnet"], (
        f"Marcus Pro sans consentement a été servi par {transport}")
    assert _modeles_debites(db_session, u) == [SONNET]
    assert "opus_repli_sonnet" in _degrades(db_session, e), (
        "le repli sur Sonnet n'est pas annoncé sur l'exécution : il serait silencieux")


def test_refus_enregistre_repli_annonce(db_session, socle, transport):
    u = _compte(db_session)
    e = _execution(db_session, u)
    _consentir(db_session, u, e, "refuse", 0)

    r = _appel_marcus(u, e)

    assert r.success
    assert transport == ["anthropic/claude-sonnet"]
    assert "opus_repli_sonnet" in _degrades(db_session, e)


def test_consentement_accepte_opus_sert_marcus(db_session, socle, transport):
    u = _compte(db_session)
    e = _execution(db_session, u)
    _consentir(db_session, u, e, "accepte", 7 * CREDITS_OPUS_PAR_APPEL)

    r = _appel_marcus(u, e)

    assert r.success
    assert transport == ["anthropic/claude-opus"]
    assert _modeles_debites(db_session, u) == [OPUS]
    assert _degrades(db_session, e) == []


def test_plafond_consenti_atteint_le_reste_passe_sur_sonnet_annonce(
        db_session, socle, transport):
    """Consentement pour UN appel : le premier est servi par Opus (mesuré
    1 000/1 000 → 30 crédits), le second ne tient plus (30 + 960 > 960)."""
    u = _compte(db_session)
    e = _execution(db_session, u)
    _consentir(db_session, u, e, "accepte", CREDITS_OPUS_PAR_APPEL)

    _appel_marcus(u, e)
    _appel_marcus(u, e)

    assert transport == ["anthropic/claude-opus", "anthropic/claude-sonnet"]
    assert "opus_repli_sonnet" in _degrades(db_session, e)


def test_consentement_d_une_autre_execution_ne_vaut_pas(db_session, socle, transport):
    u = _compte(db_session)
    e1 = _execution(db_session, u)
    e2 = _execution(db_session, u)
    _consentir(db_session, u, e1, "accepte", 7 * CREDITS_OPUS_PAR_APPEL)

    _appel_marcus(u, e2)

    assert transport == ["anthropic/claude-sonnet"]


def test_controle_negatif_un_modele_sans_opt_in_ne_demande_rien(
        db_session, socle, transport):
    """Sophie Pro est routée sur Sonnet (tier_overrides) : aucun consentement,
    aucune marque — le dispositif ne doit pas tout traiter comme Opus."""
    u = _compte(db_session)
    e = _execution(db_session, u)

    _appel_marcus(u, e, agent="pm")

    assert transport == ["anthropic/claude-sonnet"]
    assert _degrades(db_session, e) == []


def test_controle_negatif_opus_sans_opt_in_en_base_reste_servi(
        db_session, socle, transport):
    """Si la colonne dit `requires_opt_in = false`, le routeur ne doit pas
    inventer une exigence : Opus est servi, sans marque."""
    db_session.query(ModelPricing).filter_by(model_name=OPUS).update(
        {"requires_opt_in": False})
    db_session.commit()
    u = _compte(db_session)
    e = _execution(db_session, u)

    _appel_marcus(u, e)

    assert transport == ["anthropic/claude-opus"]
    assert _degrades(db_session, e) == []


# ─────────────────────────────────────────────────────────────────────
# 2. Route de lancement et estimation
# ─────────────────────────────────────────────────────────────────────


@pytest.fixture
def pool(monkeypatch):
    enfiles = []

    class _Job:
        def __init__(self, job_id):
            self.job_id = job_id

    class _Pool:
        async def enqueue_job(self, name, *a, **kw):
            enfiles.append(kw)
            return _Job(kw.get("_job_id") or "double")

    async def _get_pool():
        return _Pool()

    monkeypatch.setattr("app.api.routes.orchestrator.execution_routes.get_redis_pool",
                        _get_pool)
    monkeypatch.setattr(routeur_mod, "_router_instance", None, raising=False)
    monkeypatch.delenv("DH_DEPLOYMENT_PROFILE", raising=False)
    monkeypatch.setattr(LLMRouterService, "_get_model_id",
                        lambda self, p: _model_ids_du_yaml().get(p, p))
    return enfiles


def _authentifier(user):
    async def _o():
        return user
    app.dependency_overrides[get_current_user] = _o
    app.dependency_overrides[get_current_user_from_token_or_header] = _o


def _projet(db_session, user):
    p = Project(user_id=user.id, name="Projet GL-22 route")
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    return p


AGENTS = ["pm", "ba", "architect"]


def test_estimation_annonce_le_cout_en_credits(client, db_session, socle, pool):
    u = _compte(db_session)
    p = _projet(db_session, u)
    _authentifier(u)

    r = client.get(ESTIMATE_URL, params={"project_id": p.id})

    assert r.status_code == 200, r.text
    corps = r.json()
    assert corps["requis"] is True
    assert corps["modele"] == OPUS and corps["modele_repli"] == SONNET
    assert corps["credits_par_appel"] == CREDITS_OPUS_PAR_APPEL
    assert corps["credits_estimes"] == corps["appels_max"] * CREDITS_OPUS_PAR_APPEL
    assert corps["credits_repli_estimes"] == corps["appels_max"] * CREDITS_SONNET_PAR_APPEL


def test_lancement_pro_sans_decision_refuse_avant_creation(client, db_session, socle, pool):
    u = _compte(db_session)
    p = _projet(db_session, u)
    _authentifier(u)

    r = client.post(EXECUTE_URL, json={"project_id": p.id, "selected_agents": AGENTS})

    assert r.status_code == 409, r.text
    detail = r.json()["detail"]
    assert detail["code"] == "consentement_opus_requis"
    assert detail["estimation"]["credits_estimes"] > 0
    assert db_session.query(Execution).filter_by(project_id=p.id).count() == 0
    assert pool == [], "l'exécution a été enfilée sans décision"


def test_lancement_accepte_au_bon_montant_trace_le_consentement(
        client, db_session, socle, pool):
    from app.models.consentement_opus import ConsentementOpus
    u = _compte(db_session)
    p = _projet(db_session, u)
    _authentifier(u)
    montant = client.get(ESTIMATE_URL, params={"project_id": p.id}).json()["credits_estimes"]

    r = client.post(EXECUTE_URL, json={
        "project_id": p.id, "selected_agents": AGENTS,
        "consentement_opus": "accepte", "credits_opus_acceptes": montant})

    assert r.status_code == 202, r.text
    eid = r.json()["execution_id"]
    db_session.expire_all()
    trace = db_session.query(ConsentementOpus).filter_by(execution_id=eid).one()
    assert (trace.user_id, trace.decision, trace.credits_estimes, trace.model_name) == (
        u.id, "accepte", montant, OPUS)
    assert trace.created_at is not None
    assert trace.texte_version


def test_lancement_accepte_a_un_montant_perime_est_refuse(client, db_session, socle, pool):
    u = _compte(db_session)
    p = _projet(db_session, u)
    _authentifier(u)

    r = client.post(EXECUTE_URL, json={
        "project_id": p.id, "selected_agents": AGENTS,
        "consentement_opus": "accepte", "credits_opus_acceptes": 1})

    assert r.status_code == 409, r.text
    assert r.json()["detail"]["code"] == "consentement_opus_montant_perime"
    assert db_session.query(Execution).filter_by(project_id=p.id).count() == 0


def test_lancement_refuse_trace_et_annonce_le_repli(client, db_session, socle, pool):
    from app.models.consentement_opus import ConsentementOpus
    u = _compte(db_session)
    p = _projet(db_session, u)
    _authentifier(u)

    r = client.post(EXECUTE_URL, json={
        "project_id": p.id, "selected_agents": AGENTS, "consentement_opus": "refuse"})

    assert r.status_code == 202, r.text
    eid = r.json()["execution_id"]
    db_session.expire_all()
    trace = db_session.query(ConsentementOpus).filter_by(execution_id=eid).one()
    assert trace.decision == "refuse" and trace.user_id == u.id
    e = db_session.get(Execution, eid)
    assert "opus_repli_sonnet" in [d.get("motif") for d in (e.degraded or [])]


def test_controle_negatif_sans_opt_in_aucune_decision_demandee(
        client, db_session, socle, pool):
    db_session.query(ModelPricing).filter_by(model_name=OPUS).update(
        {"requires_opt_in": False})
    db_session.commit()
    u = _compte(db_session)
    p = _projet(db_session, u)
    _authentifier(u)

    assert client.get(ESTIMATE_URL, params={"project_id": p.id}).json()["requis"] is False
    r = client.post(EXECUTE_URL, json={"project_id": p.id, "selected_agents": AGENTS})
    assert r.status_code == 202, r.text


# ─────────────────────────────────────────────────────────────────────
# 3. Migration 023c
# ─────────────────────────────────────────────────────────────────────


def _migration():
    chemins = sorted((BACKEND / "alembic" / "versions").glob("023c_*.py"))
    assert len(chemins) == 1, f"migration 023c attendue, trouvé {chemins}"
    spec = importlib.util.spec_from_file_location("m023c", chemins[0])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_023c_part_de_la_tete_022():
    m = _migration()
    assert m.down_revision == "022_sec12_chat_logs_reclamation"
    assert m.revision.startswith("023c_")


def test_migration_023c_pose_l_opt_in_sur_opus_et_se_defait(db_session):
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    db_session.add(ModelPricing(model_name=OPUS, credits_per_1k_input=5.0,
                                credits_per_1k_output=25.0, allowed_tiers="pro,team",
                                requires_opt_in=False, is_active=True))
    db_session.commit()
    m = _migration()
    with db_session.get_bind().begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            m.upgrade()
    db_session.expire_all()
    assert db_session.get(ModelPricing, OPUS).requires_opt_in is True

    with db_session.get_bind().begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            m.downgrade()
    db_session.expire_all()
    assert db_session.get(ModelPricing, OPUS).requires_opt_in is False


# ─────────────────────────────────────────────────────────────────────
# 4. Hors exécution (dialogue Studio) : le repli est dit au client
# ─────────────────────────────────────────────────────────────────────


def test_dialogue_studio_avec_marcus_pro_repli_sonnet_dit_au_client(
        client, db_session, socle, transport):
    """Marcus Pro est routé sur Opus (agents_keep_orchestrator) ; hors
    exécution, aucun consentement n'est possible : Sonnet, et la réponse le
    dit (`avis_repli`) au lieu de le taire."""
    u = _compte(db_session)
    _authentifier(u)

    r = client.post("/api/studio/chat", json={"message": "Bonjour Marcus, ton rôle ?",
                                               "agent_id": "marcus"})

    assert r.status_code == 200, r.text
    assert transport == ["anthropic/claude-sonnet"]
    avis = r.json().get("avis_repli")
    assert avis and SONNET in avis and OPUS in avis, r.json()


def test_controle_negatif_dialogue_sans_opt_in_aucun_avis(
        client, db_session, socle, transport):
    u = _compte(db_session)
    _authentifier(u)

    r = client.post("/api/studio/chat", json={"message": "Bonjour Sophie, ton rôle ?",
                                               "agent_id": "sophie"})

    assert r.status_code == 200, r.text
    assert transport == ["anthropic/claude-sonnet"]
    assert r.json().get("avis_repli") is None
