"""Vague 1 / file A — SEC-03 (rapport Astra L53).

Les noms et chemins issus des sorties LLM servaient de chemins d'ecriture.
Le modele n'est pas une frontiere de confiance : une sortie orientee par un
brief peut viser `../../etc/`, un chemin absolu, ou — dans un depot git —
`.git/config` et les hooks, qui s'executent.

Quatre points d'ecriture nommes par Astra :

* `AgentExecutor._save_to_workspace` — `os.path.join(folder, filename)` ;
* `GitService.commit_files` — `os.path.join(self.repo_path, path)` ;
* `JordanDeployService.deploy_source_code` — ecriture dans un tmpdir ;
* `PhaseAggregator._normalize_path` — « normalisation » qui ne refusait ni
  `..` ni tous les chemins absolus.

Tous passent desormais par une primitive commune, testee ici d'abord seule
puis a chacun de ses points d'appel.
"""
import asyncio
import os
from pathlib import Path

import pytest

CHEMINS_REFUSES = [
    "../evasion.cls",
    "../../etc/passwd",
    "/etc/passwd",
    "classes/../../../evasion.cls",
    ".git/config",
    ".git/hooks/pre-commit",
    "force-app/main/default/../../../../evasion.cls",
    "",
    ".",
    "..",
]


# ==========================================================================
# 1. La primitive
# ==========================================================================

@pytest.mark.parametrize("chemin", CHEMINS_REFUSES)
def test_les_chemins_hors_racine_sont_refuses(tmp_path, chemin):
    from app.utils.path_guard import CheminInterdit, resoudre_sous_racine

    with pytest.raises(CheminInterdit):
        resoudre_sous_racine(tmp_path, chemin)


def test_controle_negatif_un_chemin_normal_est_accepte(tmp_path):
    """Sans ce controle, une primitive qui refuse TOUT passerait les tests
    precedents."""
    from app.utils.path_guard import resoudre_sous_racine

    cible = resoudre_sous_racine(tmp_path, "force-app/main/default/classes/Compte.cls")
    assert str(cible).startswith(str(tmp_path.resolve()))
    assert cible.name == "Compte.cls"


def test_un_lien_symbolique_ne_fait_pas_sortir_de_la_racine(tmp_path):
    """`resolve()` seul ne suffit pas si un repertoire de la racine est un
    lien : on verifie la cible reelle."""
    from app.utils.path_guard import CheminInterdit, resoudre_sous_racine

    dehors = tmp_path / "dehors"
    dehors.mkdir()
    racine = tmp_path / "racine"
    racine.mkdir()
    os.symlink(dehors, racine / "lien")

    with pytest.raises(CheminInterdit):
        resoudre_sous_racine(racine, "lien/evasion.cls")


def test_une_extension_hors_liste_est_refusee(tmp_path):
    from app.utils.path_guard import CheminInterdit, resoudre_sous_racine

    with pytest.raises(CheminInterdit):
        resoudre_sous_racine(tmp_path, "classes/charge.sh", extensions=(".cls", ".xml"))


def test_controle_negatif_une_extension_de_la_liste_passe(tmp_path):
    from app.utils.path_guard import resoudre_sous_racine

    cible = resoudre_sous_racine(tmp_path, "classes/Compte.cls", extensions=(".cls", ".xml"))
    assert cible.suffix == ".cls"


# ==========================================================================
# 2. Les points d'ecriture reels
# ==========================================================================

def test_l_executeur_d_agents_n_ecrit_pas_hors_du_workspace(tmp_path, monkeypatch):
    import app.services.agent_executor as module
    from app.utils.path_guard import CheminInterdit

    workspace = tmp_path / "force-app"
    workspace.mkdir()
    monkeypatch.setattr(
        module.salesforce_config, "force_app_path", str(workspace), raising=False
    )

    executeur = module.AgentExecutor.__new__(module.AgentExecutor)
    with pytest.raises(CheminInterdit):
        executeur._save_to_workspace({"../../evasion.cls": "corps"}, "diego")

    assert not (tmp_path.parent / "evasion.cls").exists()


def test_controle_negatif_l_executeur_ecrit_bien_un_fichier_normal(tmp_path, monkeypatch):
    import app.services.agent_executor as module

    workspace = tmp_path / "force-app"
    workspace.mkdir()
    monkeypatch.setattr(
        module.salesforce_config, "force_app_path", str(workspace), raising=False
    )

    executeur = module.AgentExecutor.__new__(module.AgentExecutor)
    enregistres = executeur._save_to_workspace({"Compte.cls": "public class Compte {}"}, "diego")

    assert enregistres, "aucun fichier ecrit"
    assert (workspace / "classes" / "Compte.cls").read_text() == "public class Compte {}"


def test_git_commit_files_refuse_un_chemin_traversant(tmp_path):
    from app.services.git_service import GitService
    from app.utils.path_guard import CheminInterdit

    depot = tmp_path / "depot"
    (depot / ".git").mkdir(parents=True)
    service = GitService("https://github.com/acme/projet.git", token=None)
    service.repo_path = str(depot)

    with pytest.raises(CheminInterdit):
        asyncio.run(service.commit_files({"../../evasion.txt": "charge"}, "msg"))
    assert not (tmp_path.parent / "evasion.txt").exists()


def test_git_commit_files_refuse_d_ecrire_dans_dot_git(tmp_path):
    """Un chemin peut rester DANS le depot et rester dangereux : `.git/config`
    et les hooks s'executent."""
    from app.services.git_service import GitService
    from app.utils.path_guard import CheminInterdit

    depot = tmp_path / "depot"
    (depot / ".git" / "hooks").mkdir(parents=True)
    service = GitService("https://github.com/acme/projet.git", token=None)
    service.repo_path = str(depot)

    for chemin in (".git/config", ".git/hooks/pre-commit"):
        with pytest.raises(CheminInterdit):
            asyncio.run(service.commit_files({chemin: "charge"}, "msg"))
    assert (depot / ".git" / "config").exists() is False


def test_controle_negatif_git_commit_files_ecrit_un_chemin_normal(tmp_path):
    from app.services.git_service import GitService

    depot = tmp_path / "depot"
    (depot / ".git").mkdir(parents=True)
    service = GitService("https://github.com/acme/projet.git", token=None)
    service.repo_path = str(depot)

    async def _faux_run(args, cwd=None, timeout=120):
        return True, "abc123", ""

    service._run_git = _faux_run

    async def _faux_push():
        return {"success": True}

    service.push = _faux_push

    resultat = asyncio.run(
        service.commit_files({"force-app/classes/Compte.cls": "public class Compte {}"}, "msg")
    )
    assert resultat["success"] is True, resultat
    assert (depot / "force-app" / "classes" / "Compte.cls").exists()


def test_le_normaliseur_de_phase_refuse_les_chemins_traversants():
    from app.services.phase_aggregator import PhaseAggregator
    from app.utils.path_guard import CheminInterdit

    agregateur = PhaseAggregator.__new__(PhaseAggregator)
    for chemin in ("../../evasion.cls", "/etc/passwd", "classes/../../evasion.cls"):
        with pytest.raises(CheminInterdit):
            agregateur._normalize_path(chemin)


def test_controle_negatif_le_normaliseur_prefixe_toujours_force_app():
    from app.services.phase_aggregator import PhaseAggregator

    agregateur = PhaseAggregator.__new__(PhaseAggregator)
    assert agregateur._normalize_path("classes/Compte.cls") == \
        "force-app/main/default/classes/Compte.cls"
    assert agregateur._normalize_path("// FILE: force-app/main/default/lwc/x/x.js") == \
        "force-app/main/default/lwc/x/x.js"
