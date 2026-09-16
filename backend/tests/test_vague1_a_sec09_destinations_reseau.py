"""Vague 1 / file A — SEC-09 (rapport Astra L173).

Le wizard accepte une URL d'instance Salesforce arbitraire et y envoie un
bearer ; un faux jeton suffit donc a faire emettre au serveur une requete
vers une destination choisie (SSRF), et le chemin OAuth y envoie un vrai
jeton. Cote Git, `git ls-remote` acceptait des URLs et des protocoles non
bornes.

Les destinations sont desormais validees **avant** toute connexion : schema,
hote, port, et resolution IP — loopback, reseaux prives, lien-local et
adresses reservees sont refuses.

Le reseau sortant est bloque par le bootstrap hermetique : les tests portent
sur la validation, pas sur un appel reel.
"""
import pytest


# ==========================================================================
# 1. La primitive de validation
# ==========================================================================

DESTINATIONS_REFUSEES = [
    "http://169.254.169.254/latest/meta-data/",   # metadonnees d'instance
    "https://127.0.0.1/services/oauth2/userinfo",
    "https://localhost/services/data",
    "https://10.0.0.5/services/data",
    "https://192.168.1.10/services/data",
    "https://172.16.3.4/services/data",
    "https://[::1]/services/data",
    "file:///etc/passwd",
    "gopher://evil.test/x",
    "ssh://git@evil.test/depot.git",
    "http://evil.test/",                           # http en clair
    "https://acme.my.salesforce.com:22/",          # port hors liste
]


@pytest.mark.parametrize("url", DESTINATIONS_REFUSEES)
def test_les_destinations_dangereuses_sont_refusees(url):
    from app.utils.url_guard import DestinationInterdite, valider_url_sortante

    with pytest.raises(DestinationInterdite):
        valider_url_sortante(url)


def test_controle_negatif_une_destination_publique_est_acceptee(monkeypatch):
    """Sans ce controle, un validateur qui refuse TOUT passerait les tests
    precedents. La resolution DNS est simulee : le bac a sable n'a pas de
    reseau sortant."""
    from app.utils import url_guard

    monkeypatch.setattr(url_guard, "_resoudre", lambda hote: ["93.184.216.34"])
    url_guard.valider_url_sortante("https://acme.my.salesforce.com/services/oauth2/userinfo")
    url_guard.valider_url_sortante("https://github.com/acme/projet.git")


def test_un_nom_qui_resout_en_prive_est_refuse(monkeypatch):
    """La defense ne peut pas etre lexicale : `interne.acme.test` peut
    resoudre en 10.x. On valide la resolution, pas seulement le nom."""
    from app.utils import url_guard

    monkeypatch.setattr(url_guard, "_resoudre", lambda hote: ["10.1.2.3"])
    with pytest.raises(url_guard.DestinationInterdite):
        url_guard.valider_url_sortante("https://interne.acme.test/services/data")


def test_un_nom_irresoluble_est_refuse_explicitement(monkeypatch):
    """Regle 6 : inconnu = refus, pas « on tente quand meme »."""
    from app.utils import url_guard

    def _echoue(hote):
        raise OSError("resolution impossible")

    monkeypatch.setattr(url_guard, "_resoudre", _echoue)
    with pytest.raises(url_guard.DestinationInterdite):
        url_guard.valider_url_sortante("https://inconnu.test/")


def test_une_url_git_hors_fournisseurs_supportes_est_refusee(monkeypatch):
    from app.utils import url_guard

    monkeypatch.setattr(url_guard, "_resoudre", lambda hote: ["93.184.216.34"])
    with pytest.raises(url_guard.DestinationInterdite):
        url_guard.valider_url_git("https://depot-inconnu.test/acme/projet.git")
    with pytest.raises(url_guard.DestinationInterdite):
        url_guard.valider_url_git("git@github.com:acme/projet.git")


def test_controle_negatif_les_fournisseurs_git_supportes_passent(monkeypatch):
    from app.utils import url_guard

    monkeypatch.setattr(url_guard, "_resoudre", lambda hote: ["93.184.216.34"])
    for url in (
        "https://github.com/acme/projet.git",
        "https://gitlab.com/acme/projet.git",
        "https://bitbucket.org/acme/projet.git",
    ):
        url_guard.valider_url_git(url)


# ==========================================================================
# 2. Les deux appelants reels
# ==========================================================================

def test_le_test_de_connexion_salesforce_ne_joint_pas_une_url_interne(monkeypatch):
    """Un bearer ne doit pas partir vers une destination choisie par
    l'appelant. Le transport est espionne : il ne doit jamais etre atteint."""
    from app.services.connection_validator import ConnectionValidatorService

    appels = []

    def _faux_get(*args, **kwargs):  # pragma: no cover — ne doit pas courir
        appels.append(args)
        raise AssertionError("une requete est partie malgre la garde")

    import requests

    monkeypatch.setattr(requests, "get", _faux_get)

    resultat = ConnectionValidatorService().test_salesforce_connection(
        instance_url="http://169.254.169.254/",
        access_token="faux-jeton",
    )
    assert resultat.success is False
    assert appels == []
    assert "destination" in (resultat.message or "").lower() or \
           "destination" in (resultat.error or "").lower()


def test_le_test_de_connexion_git_ne_lance_pas_ls_remote_sur_une_url_arbitraire(monkeypatch):
    from app.services import connection_validator as module

    def _interdit(*args, **kwargs):  # pragma: no cover
        raise AssertionError("git ls-remote a ete lance malgre la garde")

    monkeypatch.setattr(module.subprocess, "run", _interdit)

    resultat = module.ConnectionValidatorService().test_git_connection(
        repo_url="ssh://git@127.0.0.1/depot.git",
        token="faux-jeton",
    )
    assert resultat.success is False


def test_controle_negatif_une_instance_salesforce_publique_est_bien_jointe(monkeypatch):
    """Sans ce controle, un validateur qui refuserait tout passerait les deux
    tests precedents."""
    from app.services import connection_validator as module
    from app.utils import url_guard

    monkeypatch.setattr(url_guard, "_resoudre", lambda hote: ["93.184.216.34"])

    class _Reponse:
        status_code = 200

        @staticmethod
        def json():
            return {
                "organization_id": "00D000000000001EAA",
                "user_id": "005",
                "preferred_username": "admin@acme.test",
                "name": "Admin",
            }

    appels = []

    def _faux_get(url, **kwargs):
        appels.append(url)
        return _Reponse()

    # `requests` est importe DANS la methode : on substitue sur le module
    # `requests` lui-meme, pas sur un attribut du service.
    import requests

    monkeypatch.setattr(requests, "get", _faux_get)

    resultat = module.ConnectionValidatorService().test_salesforce_connection(
        instance_url="https://acme.my.salesforce.com",
        access_token="jeton",
    )
    assert resultat.success is True, resultat.message
    assert appels and appels[0].startswith("https://acme.my.salesforce.com")
