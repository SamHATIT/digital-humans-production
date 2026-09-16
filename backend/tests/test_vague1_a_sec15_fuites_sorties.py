"""Vague 1 / file A — SEC-15 (rapport Astra L269).

Trois fuites par les sorties :

1. `app/main.py` : le gestionnaire d'erreurs de validation renvoyait le
   **corps complet** de la requete (`"body": body`) et les erreurs Pydantic
   brutes, qui portent `input` — donc le mot de passe d'un formulaire mal
   rempli, dans la reponse ET dans le journal.
2. `GitService._run_git` journalisait tous les arguments, URL authentifiee
   comprise, et le clone laissait le jeton dans l'URL passee en argv (donc
   visible de `ps`) puis dans le remote du depot clone.
3. `PMOrchestratorServiceV2._get_salesforce_metadata` copie integralement
   `org_data["result"]`, qui contient `accessToken`, et le stocke comme
   livrable puis l'envoie dans le contexte d'analyse. Ce fichier appartient
   a une autre file : la liste blanche vit ici (`app/utils/redaction.py`),
   son application est livree en diff dans le rapport.
"""
import logging

import pytest

SECRET = "ghp_0123456789abcdefghijklmnopqrstuvwxyzAB"
MOT_DE_PASSE = "Motdepasse-tres-secret-42"


# ==========================================================================
# 1. La reponse de validation ne doit rendre ni corps ni valeur fautive
# ==========================================================================

def test_une_erreur_de_validation_ne_renvoie_pas_le_corps(client):
    reponse = client.post(
        "/api/auth/login",
        json={"email": 42, "password": MOT_DE_PASSE},
    )
    assert reponse.status_code == 422, reponse.text
    assert MOT_DE_PASSE not in reponse.text, reponse.text
    charge = reponse.json()
    assert "body" not in charge, charge


def test_une_erreur_de_validation_ne_renvoie_que_loc_type_msg(client):
    reponse = client.post("/api/auth/login", json={"password": MOT_DE_PASSE})
    assert reponse.status_code == 422
    for erreur in reponse.json()["detail"]:
        assert set(erreur) <= {"loc", "type", "msg"}, erreur


def test_le_journal_de_validation_ne_porte_pas_la_valeur_fautive(client, caplog):
    with caplog.at_level(logging.DEBUG):
        client.post("/api/auth/login", json={"password": MOT_DE_PASSE})
    assert MOT_DE_PASSE not in caplog.text, caplog.text[:2000]


def test_controle_negatif_l_erreur_reste_exploitable(client):
    """Sans ce controle, renvoyer `{}` passerait les tests precedents."""
    reponse = client.post("/api/auth/login", json={"password": MOT_DE_PASSE})
    detail = reponse.json()["detail"]
    assert detail, reponse.text
    assert any("email" in str(e.get("loc", "")) for e in detail), detail
    assert all(e.get("msg") for e in detail), detail


# ==========================================================================
# 2. Git : ni jeton dans argv, ni jeton dans le journal, remote propre
# ==========================================================================

@pytest.fixture
def git_service():
    from app.services.git_service import GitService

    return GitService("https://github.com/acme/projet.git", branch="main", token=SECRET)


def test_le_journal_git_ne_porte_pas_le_jeton(git_service, caplog):
    import asyncio
    from unittest.mock import patch

    class _Proc:
        returncode = 0

        async def communicate(self):
            return b"", b""

    with caplog.at_level(logging.DEBUG), \
            patch("asyncio.create_subprocess_exec", return_value=_Proc()):
        asyncio.run(git_service._run_git(["clone", git_service._get_auth_url(), "/tmp/x"]))

    assert SECRET not in caplog.text, caplog.text[:2000]


def test_le_clone_ne_met_pas_le_jeton_dans_argv(git_service):
    import asyncio
    from unittest.mock import AsyncMock, patch

    appels = []

    async def _faux_run(args, cwd=None, timeout=120):
        appels.append(list(args))
        return True, "", ""

    with patch.object(git_service, "_run_git", new=_faux_run), \
            patch("os.path.exists", return_value=False):
        asyncio.run(git_service.clone())

    assert appels, "aucune commande git n'a ete construite"
    for args in appels:
        for element in args:
            assert SECRET not in str(element), (args, "jeton visible dans argv (ps)")


def test_le_remote_du_clone_ne_porte_pas_le_jeton(git_service):
    import asyncio
    from unittest.mock import patch

    appels = []

    async def _faux_run(args, cwd=None, timeout=120):
        appels.append(list(args))
        return True, "", ""

    with patch.object(git_service, "_run_git", new=_faux_run), \
            patch("os.path.exists", return_value=False):
        asyncio.run(git_service.clone())

    remotes = [a for a in appels if a[:1] == ["remote"] or "set-url" in a]
    assert remotes, f"aucun nettoyage de remote apres clone : {appels}"
    for args in remotes:
        assert all(SECRET not in str(e) for e in args), args


def test_controle_negatif_le_clone_reste_fonctionnel(git_service):
    """Le clone doit toujours viser le depot et la bonne branche."""
    import asyncio
    from unittest.mock import patch

    appels = []

    async def _faux_run(args, cwd=None, timeout=120):
        appels.append(list(args))
        return True, "", ""

    with patch.object(git_service, "_run_git", new=_faux_run), \
            patch("os.path.exists", return_value=False):
        resultat = asyncio.run(git_service.clone())

    # `clone` n'est plus en tete d'argv : la commande est precedee de
    # `-c credential.helper=store --file=<tmp>` (SEC-15).
    clone = next(a for a in appels if "clone" in a)
    assert "-b" in clone and "main" in clone, clone
    assert any("github.com/acme/projet" in str(e) for e in clone), clone
    assert resultat["success"] is True


# ==========================================================================
# 3. Liste blanche des champs d'org Salesforce
# ==========================================================================

def test_le_resultat_d_org_est_filtre_par_liste_blanche():
    from app.utils.redaction import filtrer_resultat_org_salesforce

    brut = {
        "accessToken": "00D000000000000!AQ4AQ...",
        "refreshToken": "5Aep861...",
        "clientId": "3MVG9...",
        "password": "motdepasse",
        "username": "admin@acme.sandbox",
        "id": "00D000000000001EAA",
        "instanceUrl": "https://acme--preprod.sandbox.my.salesforce.com",
        "alias": "acme-preprod",
        "isSandbox": True,
        "champInconnuDuJour": "valeur",
    }
    filtre = filtrer_resultat_org_salesforce(brut)

    assert "accessToken" not in filtre
    assert "refreshToken" not in filtre
    assert "clientId" not in filtre
    assert "password" not in filtre
    # Un champ inconnu est retire aussi : liste blanche, pas liste noire.
    assert "champInconnuDuJour" not in filtre
    assert filtre["username"] == "admin@acme.sandbox"
    assert filtre["id"] == "00D000000000001EAA"
    assert filtre["instanceUrl"].endswith("salesforce.com")
    assert filtre["isSandbox"] is True


def test_aucune_valeur_secrete_ne_survit_au_filtre():
    from app.utils.redaction import filtrer_resultat_org_salesforce

    brut = {"accessToken": "SECRET-ORG-42", "username": "u@acme.test"}
    assert "SECRET-ORG-42" not in str(filtrer_resultat_org_salesforce(brut))


def test_expurger_masque_un_jeton_dans_un_texte_libre():
    from app.utils.redaction import expurger

    texte = f"git clone https://{SECRET}@github.com/acme/projet.git"
    sortie = expurger(texte, secrets=[SECRET])
    assert SECRET not in sortie
    assert "github.com/acme/projet.git" in sortie


def test_expurger_masque_meme_un_secret_non_annonce():
    """Le jeton d'une URL authentifiee doit disparaitre meme si l'appelant
    n'a pas pense a le passer en parametre."""
    from app.utils.redaction import expurger

    sortie = expurger(f"remote: https://{SECRET}@github.com/acme/projet.git")
    assert SECRET not in sortie
