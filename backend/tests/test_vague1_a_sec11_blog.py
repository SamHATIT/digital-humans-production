"""Vague 1 / file A — SEC-11 (rapport Astra L203).

Le routeur blog etait monte dans le SaaS public **sans authentification** :
`POST /api/blog/generate-batch` lancait `scripts/blog_generator.py` (appels
Anthropic/Gemini, ecritures Ghost) pour n'importe quel identifiant de sujet,
et un titre egal a `--publish` devenait une option argparse. L'API autonome
`scripts/blog_api.py` distribuait en plus des JWT Ghost Admin sur
`/ghost-token`, sans authentification.

Aucun appelant dans le depot (frontend, scripts, docs de contrat) : la
fermeture est un demontage, pas un filtrage.
"""
import asyncio
import importlib.util
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.main import app

RACINE = Path(__file__).resolve().parents[2]


def _chemins():
    return {getattr(r, "path", "") for r in app.routes}


def test_sec11_le_routeur_blog_n_est_plus_monte():
    fuites = sorted(c for c in _chemins() if "/blog" in c)
    assert fuites == [], fuites


def test_sec11_controle_negatif_les_routeurs_voisins_restent():
    """`leads` et `journal_webhook` sont montes juste a cote du blog dans
    main.py : un demontage trop large les emporterait."""
    chemins = _chemins()
    assert any(c.startswith("/api/leads") for c in chemins), sorted(chemins)
    assert any("journal" in c for c in chemins), sorted(chemins)
    assert any("/api/auth/login" in c for c in chemins)


def test_sec11_generate_batch_repond_404_sans_lancer_de_generation(client):
    from app.api.routes import blog

    with patch.object(blog.asyncio, "create_subprocess_exec", new=AsyncMock()) as sp, \
            patch.object(blog, "get_db_connection", new=AsyncMock()) as db_conn:
        reponse = client.post(
            "/api/blog/generate-batch",
            json={"topics": [{"id": 1, "title": "--publish", "agent": "diego-martinez"}]},
        )
    assert reponse.status_code == 404, reponse.text
    assert sp.await_count == 0, "un sous-processus a ete lance depuis une route anonyme"
    assert db_conn.await_count == 0, "la base a ete touchee depuis une route anonyme"


def test_sec11_pending_et_approved_topics_repondent_404(client):
    from app.api.routes import blog

    with patch.object(blog, "get_db_connection", new=AsyncMock()) as db_conn:
        for chemin in ("/api/blog/pending-topics", "/api/blog/approved-topics"):
            assert client.get(chemin).status_code == 404, chemin
    assert db_conn.await_count == 0


def test_sec11_le_titre_est_une_donnee_jamais_une_option_cli():
    """Meme demonte, le module reste importable (le bootstrap hermetique lit
    son DATABASE_URL). Si quelqu'un le remonte, un titre commencant par `-`
    doit rester un argument positionnel : le separateur `--` doit preceder
    le titre dans argv."""
    from app.api.routes import blog

    class _Proc:
        returncode = 1

        async def communicate(self):
            return b"", b"refuse"

    fake = AsyncMock(return_value=_Proc())
    with patch.object(blog.asyncio, "create_subprocess_exec", new=fake):
        asyncio.run(
            blog.generate_single_article(
                blog.TopicRequest(id=1, title="--publish", agent="diego-martinez")
            )
        )
    assert fake.await_count == 1
    argv = list(fake.await_args.args)
    assert "--" in argv, argv
    assert argv.index("--") < argv.index("--publish"), argv
    # Les options du script sont posees AVANT le separateur, la donnee apres.
    assert argv.index("--agent") < argv.index("--"), argv


def _charger_blog_api():
    chemin = RACINE / "scripts" / "blog_api.py"
    spec = importlib.util.spec_from_file_location("dh_scripts_blog_api", chemin)
    module = importlib.util.module_from_spec(spec)
    sys.modules.pop("dh_scripts_blog_api", None)
    spec.loader.exec_module(module)
    return module


def test_sec11_blog_api_ne_distribue_plus_de_jeton_ghost():
    module = _charger_blog_api()
    chemins = {getattr(r, "path", "") for r in module.app.routes}
    assert "/ghost-token" not in chemins, sorted(chemins)


def test_sec11_controle_negatif_blog_api_garde_sa_sonde():
    module = _charger_blog_api()
    chemins = {getattr(r, "path", "") for r in module.app.routes}
    assert "/health" in chemins, sorted(chemins)
