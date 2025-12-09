"""
TEST DU FLUX COMPLET - ÉTAPE PAR ÉTAPE
======================================
Simule chaque étape du flux Digital Humans sans exécuter les agents LLM
pour valider que toute la mécanique fonctionne.

Étapes testées:
1. Création projet
2. Démarrage exécution SDS  
3. Récupération WBS
4. Création tâches BUILD
5. Exécution tâche BUILD (simulation)
6. Validation et completion
"""

import sys
import json
from pathlib import Path
from datetime import datetime, timezone

# Setup path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session

def test_step_by_step():
    """Test complet du flux étape par étape"""
    
    print("=" * 70)
    print("TEST DU FLUX DIGITAL HUMANS - ÉTAPE PAR ÉTAPE")
    print("=" * 70)
    print()
    
    # Import après setup du path
    from app.database import SessionLocal, engine
    from app.models.project import Project, ProjectStatus
    from app.models.execution import Execution, ExecutionStatus
    from app.models.task_execution import TaskExecution, TaskStatus
    from app.models.agent_deliverable import AgentDeliverable
    from app.models.user import User
    
    db = SessionLocal()
    errors = []
    
    try:
        # ============================================================
        # ÉTAPE 1: Vérifier qu'on peut créer un projet
        # ============================================================
        print("ÉTAPE 1: Création projet de test...")
        
        # Trouver un user existant
        user = db.query(User).first()
        if not user:
            errors.append("ÉTAPE 1: Aucun utilisateur en base")
            print(f"   ❌ {errors[-1]}")
        else:
            # Créer un projet de test
            test_project = Project(
                user_id=user.id,
                name=f"TEST_FLOW_{datetime.now().strftime('%H%M%S')}",
                description="Projet de test automatique",
                salesforce_product="Sales Cloud",
                organization_type="Test",
                status=ProjectStatus.READY
            )
            db.add(test_project)
            db.commit()
            db.refresh(test_project)
            
            print(f"   ✅ Projet créé: ID={test_project.id}, Name={test_project.name}")
        
        # ============================================================
        # ÉTAPE 2: Créer une exécution
        # ============================================================
        print()
        print("ÉTAPE 2: Création exécution...")
        
        execution = Execution(
            project_id=test_project.id,
            user_id=user.id,
            status=ExecutionStatus.RUNNING,
            progress=0,
            selected_agents=["pm", "ba", "architect"],
            agent_execution_status={}
        )
        db.add(execution)
        db.commit()
        db.refresh(execution)
        
        print(f"   ✅ Exécution créée: ID={execution.id}, Status={execution.status.value}")
        
        # ============================================================
        # ÉTAPE 3: Simuler un WBS de Marcus
        # ============================================================
        print()
        print("ÉTAPE 3: Simulation WBS de Marcus...")
        
        # WBS content must be a JSON string (Text column, not JSONB)
        wbs_data = {
            "phases": [
                {
                    "id": "PHASE-01",
                    "name": "Test Phase",
                    "tasks": [
                        {
                            "id": "TASK-001",
                            "name": "Test Task Admin",
                            "description": "Tache de test pour Raj",
                            "assigned_agent": "Raj",
                            "dependencies": []
                        },
                        {
                            "id": "TASK-002", 
                            "name": "Test Task Apex",
                            "description": "Tache de test pour Diego",
                            "assigned_agent": "Diego",
                            "dependencies": ["TASK-001"]
                        }
                    ]
                }
            ]
        }
        
        # Content is stored as JSON string in Text column
        wbs_content = json.dumps({
            "agent_id": "architect",
            "deliverable_type": "architect_wbs",
            "content": {
                "raw": json.dumps(wbs_data)
            }
        })
        
        wbs_deliverable = AgentDeliverable(
            execution_id=execution.id,
            agent_id=None,  # FK Integer - set to None, agent name is in deliverable_type
            deliverable_type="architect_wbs",  # Type includes agent name
            content=wbs_content  # String, not dict
        )
        db.add(wbs_deliverable)
        db.commit()
        
        print(f"   ✅ WBS créé avec 2 tâches")
        
        # ============================================================
        # ÉTAPE 4: Parser le WBS et créer les TaskExecution
        # ============================================================
        print()
        print("ÉTAPE 4: Parsing WBS et création TaskExecution...")
        
        # Simuler le parsing comme le fait pm_orchestrator.py
        # Note: wbs_content is already a dict from the test setup above
        wbs_data_parsed = json.loads(wbs_content) if isinstance(wbs_content, str) else wbs_content
        inner_content = wbs_data_parsed.get("content", {})
        wbs_raw = inner_content.get("raw", "{}")
        wbs_data = json.loads(wbs_raw)
        
        agent_mapping = {
            "raj": "admin", "diego": "apex", "zara": "lwc", 
            "elena": "qa", "jordan": "devops", "aisha": "data"
        }
        
        tasks_created = 0
        for phase in wbs_data.get("phases", []):
            phase_name = phase.get("name", "Unknown")
            for task in phase.get("tasks", []):
                assigned = task.get("assigned_agent", "").lower()
                agent_id = agent_mapping.get(assigned, assigned)
                
                task_exec = TaskExecution(
                    execution_id=execution.id,
                    task_id=task.get("id"),
                    task_name=task.get("name"),
                    phase_name=phase_name,
                    assigned_agent=agent_id,
                    status=TaskStatus.PENDING,
                    depends_on=task.get("dependencies", [])
                )
                db.add(task_exec)
                tasks_created += 1
        
        db.commit()
        
        print(f"   ✅ {tasks_created} TaskExecution créées")
        
        # ============================================================
        # ÉTAPE 5: Vérifier qu'on peut récupérer la prochaine tâche
        # ============================================================
        print()
        print("ÉTAPE 5: Récupération prochaine tâche...")
        
        # Simuler get_next_task de IncrementalExecutor
        pending_tasks = db.query(TaskExecution).filter(
            TaskExecution.execution_id == execution.id,
            TaskExecution.status == TaskStatus.PENDING
        ).all()
        
        # Trouver une tâche sans dépendances non résolues
        next_task = None
        for task in pending_tasks:
            deps = task.depends_on or []
            if not deps:
                next_task = task
                break
            # Vérifier si toutes les dépendances sont complétées
            all_deps_done = True
            for dep in deps:
                dep_task = db.query(TaskExecution).filter(
                    TaskExecution.execution_id == execution.id,
                    TaskExecution.task_id == dep
                ).first()
                if not dep_task or dep_task.status != TaskStatus.COMPLETED:
                    all_deps_done = False
                    break
            if all_deps_done:
                next_task = task
                break
        
        if next_task:
            print(f"   ✅ Prochaine tâche: {next_task.task_id} - {next_task.task_name} (Agent: {next_task.assigned_agent})")
        else:
            errors.append("ÉTAPE 5: Aucune tâche disponible")
            print(f"   ❌ {errors[-1]}")
        
        # ============================================================
        # ÉTAPE 6: Simuler l'exécution d'une tâche
        # ============================================================
        print()
        print("ÉTAPE 6: Simulation exécution tâche...")
        
        if next_task:
            next_task.status = TaskStatus.RUNNING
            next_task.started_at = datetime.now(timezone.utc)
            next_task.attempt_count = 1
            db.commit()
            
            # Simuler génération de code
            next_task.generated_files = {
                "files": [
                    {"path": "force-app/main/default/classes/TestClass.cls", "type": "ApexClass"}
                ]
            }
            
            # Simuler succès
            next_task.status = TaskStatus.COMPLETED
            next_task.completed_at = datetime.now(timezone.utc)
            next_task.deploy_result = {"success": True}
            next_task.test_result = {"verdict": "PASS"}
            db.commit()
            
            print(f"   ✅ Tâche {next_task.task_id} complétée")
        
        # ============================================================
        # ÉTAPE 7: Vérifier le calcul de progression
        # ============================================================
        print()
        print("ÉTAPE 7: Calcul progression...")
        
        all_tasks = db.query(TaskExecution).filter(
            TaskExecution.execution_id == execution.id
        ).all()
        
        completed = sum(1 for t in all_tasks if t.status == TaskStatus.COMPLETED)
        total = len(all_tasks)
        progress = int((completed / total) * 100) if total > 0 else 0
        
        print(f"   ✅ Progression: {completed}/{total} tâches = {progress}%")
        
        # ============================================================
        # CLEANUP
        # ============================================================
        print()
        print("CLEANUP: Suppression données de test...")
        
        db.query(TaskExecution).filter(TaskExecution.execution_id == execution.id).delete()
        db.query(AgentDeliverable).filter(AgentDeliverable.execution_id == execution.id).delete()
        db.query(Execution).filter(Execution.id == execution.id).delete()
        db.query(Project).filter(Project.id == test_project.id).delete()
        db.commit()
        
        print("   ✅ Données de test supprimées")
        
    except Exception as e:
        import traceback
        errors.append(f"Exception: {e}")
        traceback.print_exc()
    finally:
        db.close()
    
    # ============================================================
    # RÉSULTAT
    # ============================================================
    print()
    print("=" * 70)
    if errors:
        print(f"❌ TEST ÉCHOUÉ - {len(errors)} erreur(s):")
        for e in errors:
            print(f"   - {e}")
        return False
    else:
        print("✅ TOUS LES TESTS PASSENT")
        return True


if __name__ == "__main__":
    success = test_step_by_step()
    sys.exit(0 if success else 1)
