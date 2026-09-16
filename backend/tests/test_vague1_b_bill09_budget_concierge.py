"""
Vague 1 / file B — BILL-09 (audit Astra du 06/09/2026, L777).

« Le budget public du concierge est calculé à zéro et peut être effacé. »

Trois mécanismes, mesurés avant correctif :

1. Le concierge force ``anthropic/claude-sonnet-4-6``. Le bloc ``pricing`` du
   YAML est indexé par ``anthropic/claude-sonnet`` : la clé forcée n'existe
   pas, ``_calculate_cost`` rend **0.0**, et le plafond de 20 USD/jour ne monte
   jamais. Mesuré le 16/09 :

       _calculate_cost('anthropic/claude-sonnet-4-6', 10 000, 2 000) = $0.0
       _calculate_cost('anthropic/claude-sonnet',     10 000, 2 000) = $0.06

2. Le budget est la somme de ``chat_logs.cost_usd``, et ``POST /forget``
   supprime ces lignes : le garde-fou de dépense dépend de données que le
   visiteur peut effacer lui-même.

3. Contrôle et dépense ne sont pas atomiques : N tours simultanés lisent le
   même total et passent tous.

Aucun appel réseau : le transport du routeur est remplacé.
"""
from __future__ import annotations

import threading
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

from app.models.chat_log import ChatLog
from app.models.concierge_budget import ConciergeBudgetJour


@pytest.fixture
def concierge(monkeypatch):
    from app.services import sophie_concierge_service as module
    monkeypatch.setattr(module, "IP_SALT", "sel-de-test-bill09")
    return module


def _total_jour(db_session) -> int:
    db_session.expire_all()
    ligne = db_session.query(ConciergeBudgetJour).filter_by(
        jour=datetime.now(timezone.utc).date()).first()
    return ligne.cout_micro_usd if ligne else 0


# ─────────────────────────────────────────────────────────────────────
# 1. Résolution tarifaire : plus de zéro par clé absente
# ─────────────────────────────────────────────────────────────────────


def test_le_tarif_du_fournisseur_du_concierge_est_resolu(concierge):
    """Le modèle que le concierge appelle doit avoir un tarif connu, sinon le
    plafond ne monte jamais."""
    from app.services.llm_router_service import get_llm_router

    routeur = get_llm_router()
    cout = routeur._calculate_cost(concierge.FOURNISSEUR_CONCIERGE, 10000, 2000)
    assert cout > 0, (
        f"{concierge.FOURNISSEUR_CONCIERGE} est facturé 0 : le plafond "
        f"journalier du concierge ne peut pas monter"
    )


def test_un_tarif_inconnu_est_refuse_et_non_tarife_a_zero(concierge):
    """Règle 6 : une valeur inconnue est refusée, pas devinée à zéro. Un zéro
    silencieux est exactement ce qui neutralisait le plafond."""
    from app.services.llm_router_service import UnknownProviderPricingError, get_llm_router

    routeur = get_llm_router()
    with pytest.raises(UnknownProviderPricingError):
        routeur._calculate_cost("fournisseur/modele-sans-tarif-bill09", 1000, 1000)


def test_un_modele_local_garde_un_cout_connu_et_nul(concierge):
    """Contrôle négatif : le refus ne doit pas frapper le local, dont le zéro
    est une vraie valeur."""
    from app.services.llm_router_service import get_llm_router

    routeur = get_llm_router()
    assert routeur._calculate_cost("gpu_nemotron/nemotron", 10000, 2000) == 0.0


# ─────────────────────────────────────────────────────────────────────
# 2. Le budget ne dépend plus de données effaçables
# ─────────────────────────────────────────────────────────────────────


def test_le_budget_survit_a_l_effacement_des_conversations(
    client, db_session, concierge
):
    """`/forget` efface les messages du visiteur — c'est son droit — mais pas
    le compteur de dépense."""
    concierge.reserver_budget(db_session, 5_000_000)   # 5 USD
    assert _total_jour(db_session) == 5_000_000

    session_uuid = str(uuid.uuid4())
    db_session.add(ChatLog(session_uuid=session_uuid, ip_hash="x" * 64,
                           visitor_language="fr", role="user", message="bonjour",
                           cost_usd=5_000_000))
    db_session.commit()

    reponse = client.post(f"/api/public/concierge/forget/{session_uuid}")
    assert reponse.status_code == 204, reponse.text

    db_session.expire_all()
    assert db_session.query(ChatLog).filter_by(session_uuid=session_uuid).count() == 0
    assert _total_jour(db_session) == 5_000_000, (
        "le visiteur a effacé le budget de sécurité en effaçant ses messages"
    )


def test_le_budget_du_jour_ignore_les_jours_precedents(db_session, concierge):
    """Contrôle : le plafond est journalier, il ne cumule pas indéfiniment."""
    hier = ConciergeBudgetJour(jour=date.today() - timedelta(days=1),
                               cout_micro_usd=19_000_000, requetes=100)
    db_session.add(hier)
    db_session.commit()
    assert concierge.budget_restant_micro(db_session) == int(
        concierge.DAILY_BUDGET_USD * 1_000_000)


# ─────────────────────────────────────────────────────────────────────
# 3. Réservation atomique du budget public
# ─────────────────────────────────────────────────────────────────────


def test_le_plafond_journalier_tient_sous_concurrence(db_session, concierge):
    """N réservations simultanées pour un budget qui n'en couvre que N-1 :
    exactement N-1 passent."""
    from sqlalchemy.orm import sessionmaker

    from app.services.sophie_concierge_service import BudgetConciergeDepasse

    plafond_micro = int(concierge.DAILY_BUDGET_USD * 1_000_000)
    n = 6
    part = plafond_micro // (n - 1)

    fabrique = sessionmaker(bind=db_session.get_bind(), autoflush=False,
                            autocommit=False, expire_on_commit=False)
    barriere = threading.Barrier(n)
    issues = [None] * n

    def travail(i):
        session = fabrique()
        try:
            barriere.wait(timeout=10)
            concierge.reserver_budget(session, part)
            issues[i] = "ok"
        except BudgetConciergeDepasse:
            issues[i] = "refus"
        except Exception as exc:  # noqa: BLE001
            issues[i] = f"erreur:{exc}"
        finally:
            session.close()

    fils = [threading.Thread(target=travail, args=(i,)) for i in range(n)]
    for f in fils:
        f.start()
    for f in fils:
        f.join(timeout=60)

    assert all(i is not None for i in issues), issues
    assert [i for i in issues if i and i.startswith("erreur")] == [], issues
    assert issues.count("ok") == n - 1, issues
    assert issues.count("refus") == 1
    assert _total_jour(db_session) <= plafond_micro


def test_une_reservation_liberee_rend_le_budget(db_session, concierge):
    concierge.reserver_budget(db_session, 3_000_000)
    concierge.liberer_budget(db_session, 3_000_000)
    assert _total_jour(db_session) == 0


def test_le_reglement_ajuste_la_reservation_au_cout_mesure(db_session, concierge):
    concierge.reserver_budget(db_session, 3_000_000)
    concierge.regler_budget(db_session, estimation_micro=3_000_000,
                            reel_micro=800_000)
    assert _total_jour(db_session) == 800_000


# ─────────────────────────────────────────────────────────────────────
# 4. Plafonds opérationnels, indépendants du coût monétaire
# ─────────────────────────────────────────────────────────────────────


def test_un_nombre_de_requetes_par_jour_borne_le_service(db_session, concierge, monkeypatch):
    """« un coût monétaire nul n'est pas une capacité infinie » : même à 0 USD,
    le nombre de tours par jour est borné."""
    from app.services.sophie_concierge_service import BudgetConciergeDepasse

    monkeypatch.setattr(concierge, "MAX_REQUETES_JOUR", 3)
    for _ in range(3):
        concierge.reserver_budget(db_session, 0)
    with pytest.raises(BudgetConciergeDepasse):
        concierge.reserver_budget(db_session, 0)
