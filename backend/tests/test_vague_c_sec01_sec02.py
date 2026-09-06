"""Vague C — fermetures immediates de l audit du 06/09 (GPT-6 Astra).

SEC-02 : le routeur agent_tester ne doit plus etre monte (tout compte
authentifie pouvait lancer une execution imputee au compte 2).
SEC-01 : plus aucune cle Ghost en clair dans scripts/, et les deux pages de
test publiques (admin@… prerempli) ont disparu du frontend.
"""
import re
from pathlib import Path

from app.main import app

RACINE = Path(__file__).resolve().parents[2]


def test_sec02_agent_tester_n_est_plus_monte():
    chemins = {getattr(r, "path", "") for r in app.routes}
    fuites = [c for c in chemins if "agent-tester" in c or "agent_tester" in c]
    assert fuites == [], fuites


def test_sec02_controle_negatif_les_autres_routeurs_restent():
    """Sans ce controle, un test qui demonte TOUT passerait aussi."""
    chemins = {getattr(r, "path", "") for r in app.routes}
    assert any("/api/auth/login" in c for c in chemins)
    assert any("/api/subscription/tiers" in c for c in chemins)


def test_sec01_aucune_cle_ghost_en_clair_dans_scripts():
    motif = re.compile(r"[0-9a-f]{24}:[0-9a-f]{64}")
    trouves = [str(p) for p in (RACINE / "scripts").rglob("*.py") if motif.search(p.read_text(encoding="utf-8", errors="ignore"))]
    assert trouves == [], trouves


def test_sec01_pages_de_test_publiques_supprimees():
    for nom in ("test.html", "login-test.html"):
        assert not (RACINE / "frontend" / "public" / nom).exists(), nom
