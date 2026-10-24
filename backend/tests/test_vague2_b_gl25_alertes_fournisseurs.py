"""Vague 2 / file B — GL-25 (solde fournisseur) et fournisseur local injoignable.

Attendu (backlog go-live §2, GL-25, et mission B) :
  - solde Anthropic / OpenAI epuise : alerte admin, et cote client un refus
    explicite « service momentanement indisponible », jamais un 502 brut
    portant le message du fournisseur ;
  - `gpu_nemotron` (le Free, tunnel vers le Spark) injoignable : alerte admin
    a la premiere indisponibilite ET au retour, message client explicite,
    aucun repli silencieux vers un modele payant ;
  - pas de doublon : une panne qui dure ne produit qu'une alerte.

Aucune alerte reelle : le transport Telegram (`urllib.request.urlopen` de
`admin_alert_service`) est remplace par un bouchon qui enregistre l'URL et le
corps de ce qui AURAIT ete envoye. Aucun appel LLM reel : `_call_provider`
du routeur est remplace (meme protocole que le lot B1) ; aucune requete vers
le Spark : la sonde recoit un `get` bouchonne.
"""
from __future__ import annotations

import urllib.parse
import uuid

import pytest
from fastapi.testclient import TestClient

from app.models.credit import CreditBalance, ModelPricing, TierConfig
from app.models.user import User
from app.services import admin_alert_service
from app.services import llm_router_service as routeur_mod
from app.services.llm_router_service import LLMResponse, LLMRouterService
from app.utils.auth import create_access_token

try:
    from app.services import alertes_fournisseurs
except ImportError:  # commit parent
    alertes_fournisseurs = None

ROUTE = "/api/studio/chat"
MODELE = "modele-fictif-gl25"
ERREUR_SOLDE_ANTHROPIC = (
    "Error code: 400 - {'type': 'error', 'error': {'type': 'invalid_request_error', "
    "'message': 'Your credit balance is too low to access the Anthropic API. Please go "
    "to Plans & Billing to upgrade or purchase credits.'}}"
)
ERREUR_SOLDE_OPENAI = (
    "Error code: 429 - {'error': {'message': 'You exceeded your current quota, please "
    "check your plan and billing details.', 'type': 'insufficient_quota', 'code': "
    "'insufficient_quota'}}"
)
ERREUR_SPARK = "ConnectError: [Errno 111] Connection refused"


# --------------------------------------------------------------------------
# Bouchon du canal d'envoi
# --------------------------------------------------------------------------

class _Reponse:
    def __init__(self, corps=b'{"ok":true,"result":{}}', status=200):
        self.status = status
        self._corps = corps

    def read(self):
        return self._corps

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@pytest.fixture
def telegram(monkeypatch):
    """Enregistre chaque envoi Telegram au lieu de l'emettre."""
    envois = []
    reglage = {"corps": b'{"ok":true,"result":{}}'}

    def faux_urlopen(url, donnees=None, timeout=None):
        champs = urllib.parse.parse_qs(donnees.decode()) if donnees else {}
        envois.append({
            "url": url,
            "chat_id": champs.get("chat_id", [None])[0],
            "texte": champs.get("text", [""])[0],
        })
        return _Reponse(reglage["corps"])

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "jeton-bouchon")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "4242")
    monkeypatch.setattr(admin_alert_service.urllib.request, "urlopen", faux_urlopen)
    admin_alert_service.reinitialiser_deduplication()
    if alertes_fournisseurs is not None:
        alertes_fournisseurs.reinitialiser()
    yield envois, reglage
    admin_alert_service.reinitialiser_deduplication()
    if alertes_fournisseurs is not None:
        alertes_fournisseurs.reinitialiser()


# --------------------------------------------------------------------------
# Routeur : transport simule, fournisseur choisi par le test
# --------------------------------------------------------------------------

@pytest.fixture
def transport(monkeypatch):
    """`_call_provider` simule : rend l'erreur ou la reponse decidee par le test,
    et journalise chaque fournisseur effectivement appele."""
    etat = {"fournisseur": "anthropic/claude-sonnet", "erreur": None, "appels": []}

    async def faux_appel(self, request, provider_str):
        etat["appels"].append(provider_str)
        if etat["erreur"]:
            return LLMResponse(
                content="", provider=provider_str, model_id=MODELE, tokens_in=0,
                tokens_out=0, cost_usd=0.0, latency_ms=1, success=False,
                error=etat["erreur"],
            )
        return LLMResponse(
            content="Bonjour, je suis la.", provider=provider_str, model_id=MODELE,
            tokens_in=100, tokens_out=50, cost_usd=0.0, latency_ms=1, success=True,
        )

    monkeypatch.setattr(LLMRouterService, "_call_provider", faux_appel)
    monkeypatch.setattr(LLMRouterService, "_select_provider", lambda self, r: etat["fournisseur"])
    monkeypatch.setattr(LLMRouterService, "_get_model_id", lambda self, p: MODELE)
    monkeypatch.setattr(routeur_mod, "_router_instance", None, raising=False)
    # Le demarrage du TestClient sonde les fournisseurs locaux (127.0.0.1:18084
    # = tunnel vers le Spark reel) : bouchonne ici.
    monkeypatch.setattr(LLMRouterService, "verifier_fournisseurs_locaux", lambda self, *a, **k: [])
    return etat


@pytest.fixture
def socle(db_session):
    db_session.add_all([
        TierConfig(tier_name="free", monthly_credits=0, daily_credits_cap=300,
                   price_eur_monthly=0, description="free"),
        TierConfig(tier_name="pro", monthly_credits=15000, daily_credits_cap=None,
                   price_eur_monthly=79, description="pro"),
        ModelPricing(model_name=MODELE, credits_per_1k_input=1.0, credits_per_1k_output=2.0,
                     allowed_tiers="free,pro,team", requires_opt_in=False, is_active=True),
    ])
    db_session.commit()


def _compte(db_session, palier):
    u = User(email=f"gl25-{uuid.uuid4().hex[:8]}@exemple.test", hashed_password="x",
             name="Compte GL-25", subscription_tier=palier)
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    db_session.add(CreditBalance(user_id=u.id,
                                 included_credits=15000 if palier == "pro" else 0,
                                 used_credits=0))
    db_session.commit()
    return u


def _dire(client, utilisateur, agent="sophie"):
    jeton = create_access_token({"sub": str(utilisateur.id)})
    return client.post(ROUTE, json={"message": "Bonjour", "agent_id": agent},
                       headers={"Authorization": f"Bearer {jeton}"})


# --------------------------------------------------------------------------
# 1. Classement des erreurs fournisseur
# --------------------------------------------------------------------------

@pytest.mark.parametrize("erreur,cause", [
    (ERREUR_SOLDE_ANTHROPIC, "solde_epuise"),
    (ERREUR_SOLDE_OPENAI, "solde_epuise"),
    ("Error code: 429 - credit_balance_exhausted", "solde_epuise"),
    (ERREUR_SPARK, "injoignable"),
    ("ConnectTimeout: timed out", "injoignable"),
    ("All connection attempts failed", "injoignable"),
    ("Error code: 400 - max_tokens: must be <= 64000", None),
    ("", None),
])
def test_classement_des_erreurs(erreur, cause):
    assert alertes_fournisseurs.classer_erreur(erreur) == cause


# --------------------------------------------------------------------------
# 2. Solde Anthropic epuise (palier Pro)
# --------------------------------------------------------------------------

def test_solde_anthropic_epuise_refus_explicite_et_alerte(
    client, db_session, socle, transport, telegram
):
    envois, _ = telegram
    transport["erreur"] = ERREUR_SOLDE_ANTHROPIC
    pro = _compte(db_session, "pro")

    r = _dire(client, pro)

    assert r.status_code == 503, r.text
    detail = r.json()["detail"]
    assert "momentanément indisponible" in detail
    assert "credit balance" not in r.text and "Anthropic" not in r.text, (
        "le message du fournisseur est remonte au client"
    )
    assert len(envois) == 1, envois
    assert envois[0]["chat_id"] == "4242"
    assert "botjeton-bouchon/sendMessage" in envois[0]["url"]
    texte = envois[0]["texte"]
    assert "anthropic" in texte and "solde" in texte.lower(), texte
    assert "credit balance is too low" in texte  # la cause exacte va a l'admin


def test_panne_qui_dure_une_seule_alerte_puis_retour_signale(
    client, db_session, socle, transport, telegram
):
    envois, _ = telegram
    transport["erreur"] = ERREUR_SOLDE_ANTHROPIC
    pro = _compte(db_session, "pro")
    for _ in range(3):
        assert _dire(client, pro).status_code == 503
    assert len(envois) == 1, [e["texte"][:60] for e in envois]

    transport["erreur"] = None
    assert _dire(client, pro).status_code == 200
    assert len(envois) == 2
    assert "rétabli" in envois[1]["texte"] and "anthropic" in envois[1]["texte"]

    assert _dire(client, pro).status_code == 200
    assert len(envois) == 2, "le retour a ete signale deux fois"


def test_erreur_inconnue_refus_explicite_sans_alerte(
    client, db_session, socle, transport, telegram
):
    """Controle negatif : une erreur qui n'est ni un solde ni une panne de
    transport ne declenche pas d'alerte de disponibilite — mais le client ne
    recoit toujours pas le message brut du fournisseur."""
    envois, _ = telegram
    transport["erreur"] = "Error code: 400 - max_tokens: must be <= 64000 (secret-interne)"
    pro = _compte(db_session, "pro")
    r = _dire(client, pro)
    assert r.status_code == 503, r.text
    assert "secret-interne" not in r.text
    assert envois == []


# --------------------------------------------------------------------------
# 3. gpu_nemotron injoignable (palier Free)
# --------------------------------------------------------------------------

def test_spark_injoignable_free_alerte_sans_repli_payant(
    client, db_session, socle, transport, telegram
):
    envois, _ = telegram
    transport["fournisseur"] = "gpu_nemotron/nemotron"
    transport["erreur"] = ERREUR_SPARK
    free = _compte(db_session, "free")

    r = _dire(client, free)

    assert r.status_code == 503, r.text
    assert "momentanément indisponible" in r.json()["detail"]
    assert "Connection refused" not in r.text
    assert transport["appels"] == ["gpu_nemotron/nemotron"], (
        f"repli vers un autre fournisseur : {transport['appels']}"
    )
    assert len(envois) == 1
    assert "gpu_nemotron" in envois[0]["texte"] and "injoignable" in envois[0]["texte"]


def test_credits_du_client_epuises_restent_un_402_explicite(
    client, db_session, socle, transport, telegram, monkeypatch
):
    """Controle : le quota du CLIENT n'est pas une panne fournisseur ; il ne
    doit ni alerter l'admin ni etre annonce comme une indisponibilite."""
    from app.services.credit_service import InsufficientCreditsError

    def refuse(*a, **k):
        raise InsufficientCreditsError(user_id=1, requested=10, available=0)

    monkeypatch.setattr("app.services.llm_service.generate_llm_response", refuse)
    envois, _ = telegram
    free = _compte(db_session, "free")
    r = _dire(client, free)
    assert r.status_code == 402, r.text
    assert r.json()["detail"]["error"] == "insufficient_credits"
    assert envois == []


# --------------------------------------------------------------------------
# 4. Sonde periodique des fournisseurs locaux servis
# --------------------------------------------------------------------------

class _RouteurFictif:
    profile = "cloud"
    config = {"profiles": {"cloud": {
        "orchestrator": "anthropic/claude-opus",
        "worker": "anthropic/claude-sonnet",
        "fallback_chain": {},
        "tier_overrides": {"free": {"orchestrator_default": "gpu_nemotron/nemotron",
                                    "worker_default": "gpu_nemotron/nemotron"}},
    }}}
    providers = {
        "gpu_nemotron": {"type": routeur_mod.ProviderType.LOCAL,
                         "base_url": "http://127.0.0.1:18084/v1",
                         "models": {"nemotron": {"model_id": "nemotron-lightning"}}},
        # declare mais non servi par le profil : ne doit ni etre sonde ni alerter
        "gpu_dsv4pro": {"type": routeur_mod.ProviderType.LOCAL,
                        "base_url": "http://127.0.0.1:18110/v1",
                        "models": {"dsv4pro": {"model_id": "deepseek"}}},
        "anthropic": {"type": routeur_mod.ProviderType.ANTHROPIC, "models": {}},
    }


class _ReponseHttp:
    def __init__(self, modeles):
        self._modeles = modeles

    def raise_for_status(self):
        return None

    def json(self):
        return {"data": [{"id": m} for m in self._modeles]}


def test_sonde_locale_premiere_panne_puis_retour_sans_doublon(telegram):
    envois, _ = telegram
    urls = []
    mode = {"etat": "panne"}

    def faux_get(url, timeout=None):
        urls.append(url)
        if mode["etat"] == "panne":
            raise ConnectionError("[Errno 111] Connection refused")
        if mode["etat"] == "modele_absent":
            return _ReponseHttp(["autre-modele"])
        return _ReponseHttp(["nemotron-lightning"])

    sonder = alertes_fournisseurs.sonder_fournisseurs_locaux_servis
    routeur = _RouteurFictif()

    sonder(routeur, get=faux_get)
    sonder(routeur, get=faux_get)
    assert len(envois) == 1, [e["texte"][:80] for e in envois]
    assert "gpu_nemotron" in envois[0]["texte"] and "injoignable" in envois[0]["texte"]
    assert all("18084" in u for u in urls), f"fournisseur non servi sonde : {urls}"

    mode["etat"] = "ok"
    sonder(routeur, get=faux_get)
    sonder(routeur, get=faux_get)
    assert len(envois) == 2
    assert "rétabli" in envois[1]["texte"]

    mode["etat"] = "modele_absent"
    sonder(routeur, get=faux_get)
    assert len(envois) == 3
    assert "nemotron-lightning" in envois[2]["texte"]


def test_sonde_locale_sain_des_le_depart_n_alerte_pas(telegram):
    """Controle negatif : un fournisseur sain au demarrage ne produit ni
    alerte de panne ni « retabli » fantome."""
    envois, _ = telegram
    alertes_fournisseurs.sonder_fournisseurs_locaux_servis(
        _RouteurFictif(), get=lambda url, timeout=None: _ReponseHttp(["nemotron-lightning"])
    )
    assert envois == []


def test_le_demarrage_arme_la_surveillance_et_l_arret_la_coupe(monkeypatch):
    class _RouteurMuet(_RouteurFictif):
        def verifier_fournisseurs_locaux(self, *a, **k):
            return []

    monkeypatch.setattr("app.services.llm_router_service.get_llm_router", lambda: _RouteurMuet())
    from app.main import app

    with TestClient(app):
        tache = getattr(app.state, "surveillance_fournisseurs_task", None)
        assert tache is not None and not tache.done()
    assert tache.done()


# --------------------------------------------------------------------------
# 5. Transport Telegram : accepte = HTTP 2xx ET ok:true (meme regle qu'OPS-08)
# --------------------------------------------------------------------------

def test_telegram_ok_false_n_est_pas_un_envoi_reussi(telegram):
    envois, reglage = telegram
    reglage["corps"] = b'{"ok":false,"description":"Bad Request: chat not found"}'
    envoye = admin_alert_service.alerter_admin("Sujet", "Corps")
    assert len(envois) == 1
    assert envoye is False
