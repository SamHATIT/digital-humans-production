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


@pytest.fixture(autouse=True)
def sans_sonde_spark(monkeypatch):
    """Le demarrage du TestClient sonde 127.0.0.1:18084 (tunnel vers le Spark
    reel). Autouse : pose avant la fixture `client` de chaque test."""
    monkeypatch.setattr(LLMRouterService, "verifier_fournisseurs_locaux", lambda self, *a, **k: [])


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


# --------------------------------------------------------------------------
# Reprise 2 (revue 1) : un envoi refuse ne marque pas la panne « alertee »
# --------------------------------------------------------------------------

class _HorlogeTest:
    def __init__(self):
        self.t = 5000.0

    def __call__(self):
        return self.t


def _DELAI():
    # Au commit parent la constante n'existe pas : 60 s, la valeur livree.
    return getattr(alertes_fournisseurs, "DELAI_NOUVELLE_TENTATIVE_S", 60)


def _classer(erreur, fournisseur):
    """`classer_erreur(erreur, fournisseur)` ; au commit parent la fonction ne
    prend que l'erreur : on l'appelle ainsi pour que le test y soit rouge
    pour la raison du constat (classement), pas pour une signature."""
    try:
        return alertes_fournisseurs.classer_erreur(erreur, fournisseur)
    except TypeError:
        return alertes_fournisseurs.classer_erreur(erreur)


REFUS = b'{"ok":false,"description":"Bad Request: chat not found"}'
ACCEPTE = b'{"ok":true,"result":{}}'


@pytest.fixture
def horloge(monkeypatch):
    h = _HorlogeTest()
    if alertes_fournisseurs is not None:
        monkeypatch.setattr(alertes_fournisseurs, "_horloge", h, raising=False)
    return h


def test_panne_refusee_par_telegram_est_retentee(telegram, horloge):
    envois, reglage = telegram
    reglage["corps"] = REFUS
    panne = lambda: alertes_fournisseurs.signaler_panne(  # noqa: E731
        "gpu_nemotron", "injoignable", "ConnectError", origine="test")

    panne()
    assert len(envois) == 1
    panne()  # aussitot : pas de rafale
    assert len(envois) == 1
    horloge.t += _DELAI() + 1
    panne()
    assert len(envois) == 2, "l'alerte refusee n'a jamais ete retentee"
    reglage["corps"] = ACCEPTE
    horloge.t += _DELAI() + 1
    panne()
    assert len(envois) == 3
    horloge.t += _DELAI() + 1
    panne()
    assert len(envois) == 3, "panne deja alertee avec succes : pas de doublon"


def test_retour_refuse_par_telegram_est_retente(telegram, horloge):
    envois, reglage = telegram
    alertes_fournisseurs.signaler_panne("anthropic", "solde_epuise", "credit", origine="test")
    assert len(envois) == 1
    reglage["corps"] = REFUS
    alertes_fournisseurs.signaler_retablissement("anthropic", origine="test")
    assert len(envois) == 2
    horloge.t += _DELAI() + 1
    reglage["corps"] = ACCEPTE
    alertes_fournisseurs.signaler_retablissement("anthropic", origine="test")
    assert len(envois) == 3, "le retour refuse n'a jamais ete retente"
    assert "rétabli" in envois[2]["texte"]
    horloge.t += _DELAI() + 1
    alertes_fournisseurs.signaler_retablissement("anthropic", origine="test")
    assert len(envois) == 3


def test_telegram_non_configure_pas_de_rafale(monkeypatch, horloge, caplog):
    """Controle : sans Telegram, l'alerte n'existe que dans le journal ; elle
    n'est pas re-ecrite a chaque occurrence (« non configure » n'est pas
    « refuse »)."""
    import logging

    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    monkeypatch.setattr(admin_alert_service, "_persister", lambda *a, **k: None)
    alertes_fournisseurs.reinitialiser()
    caplog.set_level(logging.ERROR)
    for _ in range(3):
        alertes_fournisseurs.signaler_panne("gpu_nemotron", "injoignable", "x", origine="test")
        horloge.t += 1000
    lignes = [r for r in caplog.records if "Fournisseur LLM gpu_nemotron" in r.getMessage()]
    assert len(lignes) == 1, [r.getMessage() for r in lignes]
    alertes_fournisseurs.reinitialiser()


# --------------------------------------------------------------------------
# Reprise 3 (revue 1) : classement sur de VRAIES erreurs de transport
# --------------------------------------------------------------------------
# Serveurs sur la boucle locale uniquement : port ferme (tunnel tombe),
# serveur qui accepte et ne repond jamais (Spark fige derriere un tunnel
# ouvert), serveur qui coupe la connexion. Les erreurs passent par le vrai
# `_call_gpu_local` du routeur (str(e)[:200], sans nom de classe).

import socket  # noqa: E402
import threading  # noqa: E402


def _port_libre():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class _Serveur:
    """Ecoute sur 127.0.0.1 ; `mode` = 'muet' (accepte, ne repond jamais) ou
    'coupe' (lit la requete puis ferme sans reponse)."""

    def __init__(self, mode):
        self.mode = mode
        self.sock = socket.socket()
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(8)
        self.port = self.sock.getsockname()[1]
        self.clients = []
        self.fin = threading.Event()
        threading.Thread(target=self._boucle, daemon=True).start()

    def _boucle(self):
        self.sock.settimeout(0.2)
        while not self.fin.is_set():
            try:
                c, _ = self.sock.accept()
            except OSError:
                continue
            if self.mode == "coupe":
                try:
                    c.recv(65536)
                finally:
                    c.close()
            else:
                self.clients.append(c)

    def arreter(self):
        self.fin.set()
        for c in self.clients:
            c.close()
        self.sock.close()


def _appel_local_reel(base_url, delai=0.5):
    """Le vrai `_call_gpu_local`, sur un fournisseur dont l'URL vise la boucle locale."""
    import asyncio

    from app.services.llm_router_service import LLMRequest

    routeur = LLMRouterService.__new__(LLMRouterService)
    routeur.providers = {"gpu_nemotron": {
        "type": routeur_mod.ProviderType.LOCAL, "base_url": base_url, "timeout": delai,
        "models": {"nemotron": {"model_id": "nemotron-lightning"}}}}
    requete = LLMRequest(prompt="Bonjour", agent_type="sophie", max_tokens=10)
    return asyncio.run(routeur._call_gpu_local(requete, "nemotron", "gpu_nemotron"))


@pytest.mark.parametrize("cas", ["port_ferme", "serveur_muet", "connexion_coupee"])
def test_vraie_panne_de_transport_locale_classee_injoignable(cas):
    serveur = None
    if cas == "port_ferme":
        url = f"http://127.0.0.1:{_port_libre()}/v1"
    else:
        serveur = _Serveur("muet" if cas == "serveur_muet" else "coupe")
        url = f"http://127.0.0.1:{serveur.port}/v1"
    try:
        reponse = _appel_local_reel(url)
    finally:
        if serveur:
            serveur.arreter()
    assert reponse.success is False
    assert _classer(reponse.error, reponse.provider) == "injoignable", (
        cas, repr(reponse.error))


@pytest.mark.parametrize("exc", [
    __import__("httpx").ConnectError("All connection attempts failed"),
    __import__("httpx").ConnectTimeout(""),
    __import__("httpx").ReadTimeout(""),
    __import__("httpx").RemoteProtocolError("Server disconnected without sending a response."),
])
def test_exceptions_httpx_d_un_fournisseur_local_classees_injoignable(exc):
    """Les classes httpx reelles, sous les deux formes que produit le routeur :
    `str(e)` (actuel) et `Type: message` (diff propose a la file C)."""
    assert _classer(str(exc)[:200], "gpu_nemotron") == "injoignable"
    assert _classer(f"{type(exc).__name__}: {exc}", "gpu_nemotron") == "injoignable"


def test_erreur_vide_d_un_fournisseur_cloud_n_est_pas_une_panne():
    """Controle : la regle « erreur vide = injoignable » ne vaut que pour un
    fournisseur local (httpx y rend str(e) vide sur delai depasse)."""
    assert _classer("", "anthropic") is None


def test_spark_fige_derriere_un_tunnel_ouvert_alerte_par_le_chemin_d_appel(
    client, db_session, socle, telegram, monkeypatch
):
    """Bout en bout : studio -> routeur -> vrai _call_gpu_local -> serveur muet
    (ReadTimeout, str vide). Avant : 503 sans alerte."""
    envois, _ = telegram
    serveur = _Serveur("muet")
    monkeypatch.setattr(LLMRouterService, "_select_provider", lambda self, r: "gpu_nemotron/nemotron")
    monkeypatch.setattr(LLMRouterService, "_get_model_id", lambda self, p: MODELE)
    monkeypatch.setattr(LLMRouterService, "verifier_fournisseurs_locaux", lambda self, *a, **k: [])
    monkeypatch.setattr(routeur_mod, "_router_instance", None, raising=False)
    routeur = routeur_mod.get_llm_router()
    routeur.providers["gpu_nemotron"] = {
        "type": routeur_mod.ProviderType.LOCAL, "base_url": f"http://127.0.0.1:{serveur.port}/v1",
        "timeout": 0.5, "models": {"nemotron": {"model_id": "nemotron-lightning"}}}
    try:
        r = _dire(client, _compte(db_session, "free"))
    finally:
        serveur.arreter()
    assert r.status_code == 503, r.text
    assert len(envois) == 1, envois
    assert "gpu_nemotron" in envois[0]["texte"] and "injoignable" in envois[0]["texte"]


def test_exception_hors_fournisseur_n_annonce_pas_une_panne_llm(
    client, db_session, socle, telegram, monkeypatch
):
    """La branche `except` du studio signalait sous le fournisseur « inconnu »
    toute exception dont le texte evoquait une connexion (ex. base injoignable),
    sans « retabli » possible."""
    def explose(*a, **k):
        raise RuntimeError("could not connect to server: Connection refused (base)")

    monkeypatch.setattr("app.services.llm_service.generate_llm_response", explose)
    envois, _ = telegram
    r = _dire(client, _compte(db_session, "pro"))
    assert r.status_code == 503, r.text
    assert "Connection refused" not in r.text
    assert envois == [], [e["texte"][:80] for e in envois]
    assert "inconnu" not in alertes_fournisseurs.etat()
