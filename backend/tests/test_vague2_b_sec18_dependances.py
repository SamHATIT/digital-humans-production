"""Vague 2 / file B — SEC-18 : dependances sur des versions vulnerables.

Audit execute (pip-audit 2.10.1 sur le gel du venv de test, commit 388299a ;
sortie dans docs/missions/RAPPORT_VAGUE2_B.md) : 57 avis, dont
python-multipart 0.0.6 (CVE-2024-24762, CVE-2024-53981, ... jusqu'a
CVE-2026-53540), starlette 0.27.0 (CVE-2024-47874, CVE-2025-54121, ...),
fastapi 0.104.1, python-jose 3.3.0 (dont deux avis SANS version corrigee :
CVE-2024-29370, CVE-2026-85394), python-dotenv 1.0.0, PyPDF2 3.0.1 (paquet
abandonne ; correctif publie dans `pypdf`).

Ces tests lisent `requirements.txt` (ce qui sera installe en production) et
le code applicatif ; la preuve que la montee de version ne casse rien est la
suite complete avant/apres, mesuree dans le rapport.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

RACINE_BACKEND = Path(__file__).resolve().parents[1]
REQUIREMENTS = RACINE_BACKEND / "requirements.txt"

# Jetons emis le 24/10/2026 par python-jose 3.3.0 (l'ancienne bibliotheque)
# avec la SECRET_KEY factice de .env.test. Des sessions ouvertes avant le
# deploiement doivent rester valides apres la bascule vers PyJWT.
JETON_JOSE_VALIDE = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI0MiIsImVtYWlsIjoiam9zZUBleGVtcGxlLnRlc3Q"
    "iLCJleHAiOjQwNzA5MDg4MDB9.cc2a9K4DPWFlbPN8ofXOVay-fOV-q4oRkxUqVwCPjhM"
)
JETON_JOSE_EXPIRE = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI0MiIsImV4cCI6MTAwMDAwMDAwMH0."
    "vXildtsCb5LHgVSyWWtykNVR-XrmM8OwhrInff1Abog"
)


def _pins():
    pins = {}
    for ligne in REQUIREMENTS.read_text().splitlines():
        ligne = ligne.split("#", 1)[0].strip()
        if not ligne:
            continue
        m = re.match(r"^([A-Za-z0-9_.\-]+)(\[[^\]]*\])?\s*(.*)$", ligne)
        if m:
            pins.setdefault(m.group(1).lower(), []).append(m.group(3))
    return pins


def _version(texte):
    return tuple(int(x) for x in re.findall(r"\d+", texte)[:3])


def _borne_basse(contraintes):
    """Plus petite version admise par `==x` ou `>=x` (None si non bornee)."""
    bornes = []
    for c in contraintes:
        for op, v in re.findall(r"(==|>=)\s*([0-9][0-9.]*)", c):
            bornes.append(_version(v))
    return max(bornes) if bornes else None


@pytest.mark.parametrize("paquet,minimum", [
    ("python-multipart", "0.0.31"),   # CVE-2026-53540 corrige en 0.0.31
    ("starlette", "1.3.1"),           # CVE-2026-54283 corrige en 1.3.1
    ("fastapi", "0.109.1"),           # CVE-2024-24762
    ("python-dotenv", "1.2.2"),       # CVE-2026-28684
])
def test_versions_minimales_declarees(paquet, minimum):
    pins = _pins()
    assert paquet in pins, f"{paquet} absent de requirements.txt (version non maitrisee)"
    borne = _borne_basse(pins[paquet])
    assert borne is not None and borne >= _version(minimum), (paquet, pins[paquet])


@pytest.mark.parametrize("paquet", ["python-jose", "pypdf2"])
def test_paquets_sans_correctif_retires(paquet):
    assert paquet not in _pins()


def test_le_code_n_importe_plus_jose_ni_pypdf2():
    fautifs = []
    for fichier in (RACINE_BACKEND / "app").rglob("*.py"):
        texte = fichier.read_text(errors="replace")
        if re.search(r"^\s*(from|import)\s+(jose|PyPDF2)\b", texte, re.M):
            fautifs.append(str(fichier.relative_to(RACINE_BACKEND)))
    assert fautifs == []


def test_un_jeton_emis_par_l_ancienne_bibliotheque_reste_valide():
    from app.utils.auth import decode_access_token

    charge = decode_access_token(JETON_JOSE_VALIDE)
    assert charge is not None and charge["sub"] == "42"


def test_un_jeton_expire_est_refuse():
    from app.utils.auth import decode_access_token

    assert decode_access_token(JETON_JOSE_EXPIRE) is None


def test_un_jeton_alg_none_est_refuse():
    import base64
    import json

    from app.utils.auth import decode_access_token

    def b64(d):
        return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()

    jeton = f"{b64({'alg': 'none', 'typ': 'JWT'})}.{b64({'sub': '42', 'exp': 4070908800})}."
    assert decode_access_token(jeton) is None


def test_un_jeton_emis_puis_relu_par_l_application():
    from app.utils.auth import create_access_token, decode_access_token

    assert decode_access_token(create_access_token({"sub": "7"}))["sub"] == "7"


def test_chemins_montes_voit_un_routeur_inclus():
    """Controle de l'outil de test : depuis fastapi 0.162, `app.routes` ne
    deplie plus les routeurs inclus ; `chemins_montes` doit les voir, sinon
    les tests « routeur demonte » (blog, agent-tester, download) seraient
    vrais sans rien verifier."""
    from fastapi import APIRouter, FastAPI

    from tests.routes_montees import chemins_montes

    routeur = APIRouter(prefix="/blog")

    @routeur.post("/generate-batch")
    def _g():  # pragma: no cover
        return {}

    app = FastAPI()
    app.include_router(routeur, prefix="/api")
    assert "/api/blog/generate-batch" in chemins_montes(app)


def test_chemins_montes_voit_les_websockets():
    """Reprise 5 (revue 1) : la premiere version ne depliait que les routes
    HTTP ; la route websocket du suivi d'execution manquait."""
    from fastapi import APIRouter, FastAPI, WebSocket

    from app.main import app as application
    from tests.routes_montees import chemins_montes

    assert "/api/pm-orchestrator/ws/{execution_id}" in chemins_montes(application)

    interne = APIRouter(prefix="/flux")

    @interne.websocket("/ws/{ident}")
    async def _w(websocket: WebSocket, ident: str):  # pragma: no cover
        await websocket.close()

    externe = APIRouter()
    externe.include_router(interne, prefix="/v2")
    app = FastAPI()
    app.include_router(externe, prefix="/api")
    assert "/api/v2/flux/ws/{ident}" in chemins_montes(app)
