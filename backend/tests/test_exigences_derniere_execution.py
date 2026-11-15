"""Exigences : seul le jeu de la derniere execution est montre et valide (15/11/2026).

Smoke du 05/11 (projet 122) : chaque relance recreait un jeu complet ; la
liste affichait 35 lignes pour 17 exigences et « tout valider » validait aussi
les exigences des executions abandonnees.
"""
import pytest

from app.main import app
from app.models.business_requirement import BRSource, BRStatus, BusinessRequirement
from app.models.execution import Execution, ExecutionStatus
from app.models.project import Project
from app.models.user import User
from app.utils.dependencies import get_current_user, get_current_user_from_token_or_header


@pytest.fixture
def projet(db_session):
    u = User(email="br@example.com", name="BR", hashed_password="x", subscription_tier="pro")
    db_session.add(u); db_session.commit()
    p = Project(user_id=u.id, name="Relances"); db_session.add(p); db_session.commit()
    ex = []
    for _ in range(2):
        e = Execution(project_id=p.id, user_id=u.id, selected_agents=["pm"], agent_execution_status={},
                      status=ExecutionStatus.WAITING_BR_VALIDATION)
        db_session.add(e); db_session.commit(); ex.append(e)
    for e in ex:
        for i in range(3):
            db_session.add(BusinessRequirement(execution_id=e.id, project_id=p.id, br_id=f"BR-00{i+1}",
                           category="General", requirement=f"exec {e.id} exigence {i+1}",
                           source=BRSource.EXTRACTED, status=BRStatus.PENDING, order_index=i))
    db_session.commit()
    for dep in (get_current_user, get_current_user_from_token_or_header):
        app.dependency_overrides[dep] = lambda u=u: u
    yield p, ex
    app.dependency_overrides.clear()


def test_la_liste_ne_montre_que_la_derniere_execution(client, projet):
    p, ex = projet
    r = client.get(f"/api/br/{p.id}")
    assert r.status_code == 200, r.text
    corps = r.json()
    assert corps["total"] == 3 and corps["pending"] == 3
    assert all(f"exec {ex[1].id}" in b["requirement"] for b in corps["brs"])


def test_tout_valider_ne_touche_pas_les_executions_abandonnees(client, projet, db_session):
    p, ex = projet
    r = client.post(f"/api/br/{p.id}/validate-all")
    assert r.status_code == 200, r.text
    assert r.json()["validated_count"] == 3
    anciennes = db_session.query(BusinessRequirement).filter_by(execution_id=ex[0].id).all()
    assert all(b.status == BRStatus.PENDING for b in anciennes)


def test_exigence_ajoutee_a_la_main_rattachee_a_l_execution_courante(client, projet, db_session):
    p, ex = projet
    r = client.post(f"/api/br/{p.id}", json={"requirement": "Exigence manuelle", "category": "General", "priority": "should"})
    assert r.status_code == 201, r.text
    br = db_session.query(BusinessRequirement).filter_by(requirement="Exigence manuelle").one()
    assert br.execution_id == ex[1].id
