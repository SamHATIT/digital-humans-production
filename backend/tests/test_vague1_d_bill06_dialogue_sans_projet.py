"""VAGUE 1 / file D — BILL-06 : le Free n'avait aucun parcours de dialogue.

Constat d'Astra (06/09, L717), re-mesure le 16/09 sur `f78e8ad` :

  - `POST /api/projects/{id}/chat` (project_chat.py) exige un projet, et
    verifie qu'il appartient a l'appelant ;
  - `POST /api/pm-orchestrator/executions/{id}/chat` (hitl_routes.py) exige
    une execution ;
  - la matrice serveur donne au Free `chat_sophie: True`, `chat_olivia: True`
    et `max_projects: 0`.

Le palier Free vend donc un dialogue avec Sophie et Olivia, et les deux seules
portes vers ce dialogue exigent un objet que le Free n'a pas le droit de
creer. Le concierge public ne remplace pas ce service : il ne debite pas les
credits du compte et passe par un autre parcours (`sans_compte=True` dans
`sophie_concierge_service`).

Ce fichier exige une porte authentifiee hors projet, et ses garde-fous :
l'appelant est facture comme n'importe quel appel d'agent (decision D10), le
palier est resolu **cote serveur** (jamais lu dans la requete), et le Free
n'atteint que Sophie et Olivia.
"""
from __future__ import annotations

import uuid

import pytest

from app.models.credit import (
    TRANSACTION_TYPE_CHARGE,
    CreditBalance,
    CreditTransaction,
)
from app.models.user import User
from app.utils.auth import create_access_token

# Meme socle tarifaire et meme transport simule que le lot B1 : les reimporter
# evite d'en tenir deux copies divergentes.
from tests.test_vague_b_b1_credits import (  # noqa: F401
    CREDITS_PAR_APPEL,
    socle_credits,
    transport_llm_simule,
)

ROUTE = "/api/studio/chat"


def _creer_compte_sans_projet(db_session, palier: str) -> User:
    """Un compte du palier demande, **sans aucun projet ni execution**.

    C'est tout l'objet de BILL-06 : le Free ne peut pas creer de projet
    (`max_projects: 0`), donc le dialogue qu'on lui vend doit fonctionner
    sans.
    """
    suffixe = uuid.uuid4().hex[:8]
    utilisateur = User(
        email=f"bill06-{suffixe}@exemple.test",
        hashed_password="x",
        name=f"Compte BILL-06 {suffixe}",
        subscription_tier=palier,
    )
    db_session.add(utilisateur)
    db_session.commit()
    db_session.refresh(utilisateur)

    # Le solde vient du palier, comme en production : le Free est plafonne au
    # jour par `tier_config.daily_credits_cap` (son `included_credits` vaut 0),
    # un palier payant porte son alloue mensuel.
    from app.models.credit import TierConfig

    ligne = (
        db_session.query(TierConfig).filter(TierConfig.tier_name == palier).first()
    )
    db_session.add(
        CreditBalance(
            user_id=utilisateur.id,
            included_credits=(ligne.monthly_credits if ligne else 0),
            used_credits=0,
        )
    )
    db_session.commit()
    return utilisateur


@pytest.fixture
def compte_free_sans_projet(db_session, socle_credits):
    return _creer_compte_sans_projet(db_session, "free")


@pytest.fixture
def compte_pro_sans_projet(db_session, socle_credits):
    return _creer_compte_sans_projet(db_session, "pro")


def _entetes(utilisateur: User) -> dict:
    return {
        "Authorization": f"Bearer {create_access_token({'sub': str(utilisateur.id)})}"
    }


def _lignes_de_credit(db_session, user_id: int):
    db_session.expire_all()
    return (
        db_session.query(CreditTransaction)
        .filter(
            CreditTransaction.user_id == user_id,
            CreditTransaction.transaction_type == TRANSACTION_TYPE_CHARGE,
        )
        .all()
    )


# ─────────────────────────────────────────────────────────────────────
# 1. Le parcours vendu au Free existe
# ─────────────────────────────────────────────────────────────────────


def test_un_compte_free_sans_aucun_projet_peut_parler_a_sophie(
    db_session, client, compte_free_sans_projet, transport_llm_simule
):
    from app.models.project import Project

    assert (
        db_session.query(Project)
        .filter(Project.user_id == compte_free_sans_projet.id)
        .count()
        == 0
    ), "la fixture doit prouver le cas « sans projet »"

    reponse = client.post(
        ROUTE,
        json={"message": "Bonjour Sophie, je voudrais parler de mon projet.", "agent_id": "sophie"},
        headers=_entetes(compte_free_sans_projet),
    )

    assert reponse.status_code == 200, reponse.text
    corps = reponse.json()
    assert corps["agent_id"] == "sophie"
    assert corps["response"], "reponse vide"
    assert transport_llm_simule, "le transport LLM n'a jamais ete atteint"


def test_le_dialogue_hors_projet_est_facture_a_l_appelant(
    db_session, client, compte_free_sans_projet, transport_llm_simule
):
    """Le concierge public ne debite rien ; ce parcours-ci doit debiter, sinon
    il n'est pas le service vendu mais une seconde vitrine gratuite."""
    reponse = client.post(
        ROUTE,
        json={"message": "Peux-tu m'aider a cadrer un besoin ?", "agent_id": "sophie"},
        headers=_entetes(compte_free_sans_projet),
    )
    assert reponse.status_code == 200, reponse.text

    lignes = _lignes_de_credit(db_session, compte_free_sans_projet.id)
    assert len(lignes) == len(transport_llm_simule), (
        f"{len(transport_llm_simule)} appel(s) LLM mais {len(lignes)} ligne(s) "
        f"credit_transactions : le dialogue hors projet n'est pas facture"
    )
    assert lignes[0].credits_consumed == CREDITS_PAR_APPEL


def test_olivia_est_joignable_par_le_free(
    client, compte_free_sans_projet, transport_llm_simule
):
    reponse = client.post(
        ROUTE,
        json={"message": "Olivia, peux-tu decouper ce besoin ?", "agent_id": "olivia"},
        headers=_entetes(compte_free_sans_projet),
    )
    assert reponse.status_code == 200, reponse.text
    assert reponse.json()["agent_id"] == "olivia"


# ─────────────────────────────────────────────────────────────────────
# 2. Controles negatifs — la porte discrimine bien deux cas
# ─────────────────────────────────────────────────────────────────────


def test_le_free_n_atteint_pas_le_reste_de_l_ensemble(
    client, compte_free_sans_projet, transport_llm_simule
):
    """Sans ce controle, une porte qui laisserait tout passer satisferait les
    tests ci-dessus : le Free obtiendrait l'equipe complete (`chat_full_team`),
    que sa matrice lui refuse."""
    reponse = client.post(
        ROUTE,
        json={"message": "Marcus, dessine-moi une architecture.", "agent_id": "marcus"},
        headers=_entetes(compte_free_sans_projet),
    )
    assert reponse.status_code == 403, reponse.text
    detail = reponse.json()["detail"]
    assert detail["error"] == "feature_not_available"
    assert detail["feature"] == "chat_full_team"
    assert not transport_llm_simule, "un appel LLM a ete paye pour un refus"


def test_un_compte_pro_atteint_l_ensemble_complet(
    client, compte_pro_sans_projet, transport_llm_simule
):
    """Controle positif du precedent : le refus vient bien du palier, pas
    d'une liste d'agents fermee pour tout le monde."""
    reponse = client.post(
        ROUTE,
        json={"message": "Marcus, dessine-moi une architecture.", "agent_id": "marcus"},
        headers=_entetes(compte_pro_sans_projet),
    )
    assert reponse.status_code == 200, reponse.text
    assert reponse.json()["agent_id"] == "marcus"


def test_sans_jeton_la_porte_est_fermee(client, transport_llm_simule):
    reponse = client.post(ROUTE, json={"message": "Bonjour", "agent_id": "sophie"})
    assert reponse.status_code in (401, 403), reponse.text
    assert not transport_llm_simule


def test_le_palier_envoye_par_le_client_est_ignore(
    client, compte_free_sans_projet, transport_llm_simule
):
    """Le palier se resout cote serveur. Un corps de requete qui pretend
    « team » ne doit rien ouvrir."""
    reponse = client.post(
        ROUTE,
        json={
            "message": "Marcus, une architecture.",
            "agent_id": "marcus",
            "subscription_tier": "team",
            "tier": "team",
        },
        headers=_entetes(compte_free_sans_projet),
    )
    assert reponse.status_code == 403, reponse.text


def test_un_agent_inconnu_est_refuse_sans_appel_llm(
    client, compte_free_sans_projet, transport_llm_simule
):
    reponse = client.post(
        ROUTE,
        json={"message": "Bonjour", "agent_id": "agent_qui_n_existe_pas"},
        headers=_entetes(compte_free_sans_projet),
    )
    assert reponse.status_code == 400, reponse.text
    assert not transport_llm_simule


# ─────────────────────────────────────────────────────────────────────
# 3. Memoire : conforme a ce que le palier annonce
# ─────────────────────────────────────────────────────────────────────


def test_le_free_n_a_pas_de_memoire_persistante(
    db_session, client, compte_free_sans_projet, transport_llm_simule
):
    """`persistent_memory: False` cote serveur. La reponse doit le dire, et
    rien ne doit etre ecrit en base pour ce dialogue."""
    from app.models.project_conversation import ProjectConversation

    avant = db_session.query(ProjectConversation).count()
    reponse = client.post(
        ROUTE,
        json={"message": "Retiens que mon client s'appelle Untel.", "agent_id": "sophie"},
        headers=_entetes(compte_free_sans_projet),
    )
    assert reponse.status_code == 200, reponse.text
    assert reponse.json()["memory"] == "session"
    db_session.expire_all()
    assert db_session.query(ProjectConversation).count() == avant


def test_l_historique_fourni_est_borne(
    client, compte_free_sans_projet, transport_llm_simule
):
    """Le dialogue est sans etat serveur : l'historique vient du client. Il
    doit donc etre borne, sinon un appelant choisit la taille du prompt qu'il
    nous fait payer."""
    historique = [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"tour {i}"}
        for i in range(60)
    ]
    reponse = client.post(
        ROUTE,
        json={"message": "Et donc ?", "agent_id": "sophie", "history": historique},
        headers=_entetes(compte_free_sans_projet),
    )
    assert reponse.status_code == 200, reponse.text

    assert transport_llm_simule, "aucun appel LLM"
    prompt = transport_llm_simule[-1].prompt
    assert "tour 0" not in prompt, "l'historique n'est pas borne"
    assert "tour 59" in prompt, "les tours recents doivent etre conserves"
