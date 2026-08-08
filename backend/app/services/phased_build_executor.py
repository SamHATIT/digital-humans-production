"""
Phased Build Executor - BUILD v2
Orchestrateur principal du BUILD par phases.
"""
import logging
import json
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum

from app.services.phase_context_registry import PhaseContextRegistry
from app.services.phase_aggregator import PhaseAggregator
from app.services.jordan_deploy_service import JordanDeployService, PHASE_CONFIGS

logger = logging.getLogger(__name__)


class PhaseStatus(str, Enum):
    PENDING = "pending"
    GENERATING = "generating"
    AGGREGATING = "aggregating"
    REVIEWING = "reviewing"
    PR_CREATED = "pr_created"
    DEPLOYING = "deploying"
    RETRIEVING = "retrieving"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRY = "retry"


# Mapping task_type → phase
TASK_TYPE_TO_PHASE = {
    # ── FIX-PHASEMAP-001 (08/08/2026) ──────────────────────────────────────
    # Le WBS de Marcus a change de vocabulaire : il produit "dev_data_model",
    # "dev_apex", "dev_flow"... la ou cette table n'attendait que
    # "create_object", "apex_class", "flow". Aucun terme ne correspondait, tout
    # retombait sur le repli par agent — qui classe Diego en phase 2 et
    # n'atteint jamais Raj. Consequence observee sur l'execution 166 : les 7
    # taches de modele de donnees restaient PENDING pendant que Diego generait
    # de l'Apex contre des objets inexistants. Detecte par Sam a l'oeil nu.
    # Les deux vocabulaires sont desormais reconnus : les anciennes executions
    # restent lisibles, les nouvelles fonctionnent.
    "dev_data_model": 1,
    "setup_environment": 1,
    "setup_repository": 1,
    "devops_setup": 1,

    "dev_apex": 2,
    "test_unit": 2,
    "test_integration": 2,

    "config_layouts": 3,
    "config_apps": 3,

    "dev_flow": 4,
    "dev_validation": 4,

    "config_profiles": 5,
    "setup_permissions": 5,
    "config_sharing": 5,

    "config_reports": 6,
    "test_uat": 6,
    "doc_technical": 6,
    "doc_user": 6,
    "deploy_prepare": 6,
    "deploy_validate": 6,
    "deploy_execute": 6,

    # Phase 1: Data Model
    "create_object": 1,
    "create_field": 1,
    "record_type": 1,
    "list_view": 1,
    "simple_validation_rule": 1,
    "object_configuration": 1,
    "custom_object": 1,
    "custom_field": 1,
    
    # Phase 2: Business Logic
    "apex_class": 2,
    "apex_trigger": 2,
    "apex_test": 2,
    "apex_helper": 2,
    "apex_batch": 2,
    "apex_scheduler": 2,
    "apex_service": 2,
    "apex_controller": 2,
    
    # Phase 3: UI Components
    "lwc_component": 3,
    "aura_component": 3,
    "flexipage": 3,
    "custom_tab": 3,
    "lightning_page": 3,
    
    # Phase 4: Automation
    "flow": 4,
    "complex_validation_rule": 4,
    "approval_process": 4,
    "workflow_rule": 4,
    "process_builder": 4,
    
    # Phase 5: Security & Access
    "permission_set": 5,
    "profile": 5,
    "sharing_rule": 5,
    "page_layout": 5,
    "page_layout_assignment": 5,
    
    # Phase 6: Data Migration
    "data_migration": 6,
    "data_load": 6,
    "data_transform": 6,
    "data_validation": 6,
}


class PhasedBuildExecutor:
    """
    Orchestrateur principal du BUILD v2.
    Exécute les 6 phases séquentiellement avec sub-batching.
    """
    
    BUILD_PHASES = [
        {"phase": 1, "name": "data_model", "agent": "raj"},
        {"phase": 2, "name": "business_logic", "agent": "diego"},
        {"phase": 3, "name": "ui_components", "agent": "zara"},
        {"phase": 4, "name": "automation", "agent": "raj"},
        {"phase": 5, "name": "security", "agent": "raj"},
        {"phase": 6, "name": "data_migration", "agent": "aisha"},
    ]
    
    MAX_RETRIES = 3
    
    def __init__(self, project_id: int, execution_id: int, db):
        self.project_id = project_id
        self.execution_id = execution_id
        self.db = db
        
        self.context_registry = PhaseContextRegistry()
        self.aggregator = PhaseAggregator()
        self.jordan_service = None
        
        self.phase_results: Dict[int, Dict] = {}
        self.current_phase = 0
    
    async def initialize(self):
        """Initialise les services."""
        self.jordan_service = JordanDeployService(self.project_id, self.db)
        await self.jordan_service.initialize()
        logger.info(f"[PhasedBuild] Initialized for project {self.project_id}, execution {self.execution_id}")
    
    async def close(self):
        """Ferme les connexions."""
        if self.jordan_service:
            await self.jordan_service.close()
    
    # ═══════════════════════════════════════════════════════════════
    # MAIN EXECUTION
    # ═══════════════════════════════════════════════════════════════
    
    async def execute_build(self, wbs_tasks: List[Dict]) -> Dict[str, Any]:
        """
        Exécute le BUILD complet.
        
        Args:
            wbs_tasks: Liste des tâches WBS
            
        Returns:
            Résultat global du BUILD
        """
        logger.info(f"[PhasedBuild] Starting BUILD with {len(wbs_tasks)} tasks")
        
        result = {
            "success": True,
            "execution_id": self.execution_id,
            "phases_completed": 0,
            "phases_failed": 0,
            "phase_results": {},
            "total_time_seconds": 0,
            "deployed_components": [],
        }
        
        start_time = datetime.now()
        
        try:
            # Group tasks by phase
            tasks_by_phase = self.group_tasks_by_phase(wbs_tasks)
            logger.info(f"[PhasedBuild] Tasks grouped: {[(p, len(t)) for p, t in tasks_by_phase.items()]}")
            
            # Execute each phase sequentially
            for phase_config in self.BUILD_PHASES:
                phase_num = phase_config["phase"]
                phase_name = phase_config["name"]
                
                phase_tasks = tasks_by_phase.get(phase_num, [])
                if not phase_tasks:
                    logger.info(f"[PhasedBuild] Phase {phase_num} ({phase_name}): no tasks, skipping")
                    continue
                
                self.current_phase = phase_num
                logger.info(f"[PhasedBuild] Phase {phase_num} ({phase_name}): {len(phase_tasks)} tasks")
                
                # Update phase status in DB
                await self._update_phase_status(phase_num, phase_name, PhaseStatus.GENERATING)
                
                # Execute phase
                phase_result = await self.execute_phase(phase_config, phase_tasks)
                self.phase_results[phase_num] = phase_result
                result["phase_results"][phase_num] = phase_result
                
                if phase_result.get("success"):
                    result["phases_completed"] += 1
                    result["deployed_components"].extend(phase_result.get("deployed_components", []))
                    await self._update_phase_status(phase_num, phase_name, PhaseStatus.COMPLETED)
                else:
                    result["phases_failed"] += 1
                    result["success"] = False
                    await self._update_phase_status(phase_num, phase_name, PhaseStatus.FAILED, 
                                                    error=phase_result.get("error"))
                    # Stop on failure
                    logger.error(f"[PhasedBuild] Phase {phase_num} failed, stopping BUILD")
                    break
            
            # Final packaging if all phases succeeded
            if result["success"] and result["phases_completed"] > 0:
                package_result = await self.jordan_service.generate_final_package_xml(
                    list(self.phase_results.keys())
                )
                result["package"] = package_result
            
        except Exception as e:
            logger.exception("[PhasedBuild] BUILD failed with exception")
            result["success"] = False
            result["error"] = str(e)
        
        result["total_time_seconds"] = (datetime.now() - start_time).total_seconds()
        
        logger.info(f"[PhasedBuild] BUILD complete: {result['phases_completed']} phases, "
                   f"success={result['success']}, time={result['total_time_seconds']:.1f}s")
        
        return result
    
    async def execute_phase(self, phase_config: Dict, tasks: List[Dict]) -> Dict[str, Any]:
        """
        Exécute une phase complète.
        
        Flow:
        1. Generate batches (sub-batching)
        2. Aggregate outputs
        3. Elena review
        4. Jordan deploy
        """
        phase_num = phase_config["phase"]
        phase_name = phase_config["name"]
        agent = phase_config["agent"]
        
        result = {
            "phase": phase_num,
            "phase_name": phase_name,
            "agent": agent,
            "success": False,
            "batches": [],
            "deployed_components": [],
        }
        
        retry_count = 0
        retry_feedback = ""
        
        while retry_count < self.MAX_RETRIES:
            try:
                # Step 1: Generate batches
                await self._update_phase_status(phase_num, phase_name, PhaseStatus.GENERATING)
                
                batches = await self.generate_phase_batches(agent, tasks, phase_num, retry_feedback)
                result["batches"] = batches
                result["total_batches"] = len(batches)
                
                if not batches:
                    result["error"] = "No batches generated"
                    return result
                
                # Step 2: Aggregate
                await self._update_phase_status(phase_num, phase_name, PhaseStatus.AGGREGATING)
                
                aggregated = self.aggregator.aggregate(phase_num, batches)
                result["aggregated"] = {
                    "operations_count": len(aggregated.get("operations", [])),
                    "files_count": len(aggregated.get("files", {})),
                }
                
                # Register in context for subsequent phases
                self.context_registry.register_batch_output(phase_num, aggregated)
                
                # Step 3: Elena review
                await self._update_phase_status(phase_num, phase_name, PhaseStatus.REVIEWING)
                
                review_result = await self._elena_review(phase_num, aggregated)
                result["review"] = review_result
                
                if review_result.get("verdict") == "FAIL":
                    retry_count += 1
                    logger.warning(f"[PhasedBuild] Phase {phase_num} review FAIL, retry {retry_count}/{self.MAX_RETRIES}")
                    retry_feedback = review_result.get("feedback_for_developer", "") or ""
                    result["retry_feedback"] = retry_feedback
                    
                    if retry_count >= self.MAX_RETRIES:
                        result["error"] = f"Review failed after {self.MAX_RETRIES} retries"
                        return result
                    
                    # Retry with feedback
                    continue
                
                # Step 4: Create PR and deploy via Jordan
                await self._update_phase_status(phase_num, phase_name, PhaseStatus.DEPLOYING)
                
                # Create branch and PR
                branch_result = await self.jordan_service.create_phase_branch(phase_num, phase_name)
                branch_name = branch_result.get("branch_name", f"build/phase-{phase_num}")
                
                # Write files to branch
                files_to_commit = aggregated.get("files", {})
                if files_to_commit:
                    await self.jordan_service.commit_files(
                        files_to_commit,
                        f"feat(phase-{phase_num}): {phase_name} - {len(files_to_commit)} files"
                    )
                
                # Create PR
                pr_result = await self.jordan_service.create_phase_pr(
                    branch_name, phase_num, phase_name,
                    len(files_to_commit)
                )
                result["pr"] = pr_result
                
                # Deploy
                deploy_result = await self.jordan_service.deploy_phase(
                    phase_num,
                    aggregated,
                    branch_name,
                    pr_result.get("url")
                )
                result["deploy"] = deploy_result
                
                if deploy_result.get("success"):
                    result["success"] = True
                    result["deployed_components"] = deploy_result.get("deployed_components", [])
                    
                    # Mark tasks as completed
                    await self._mark_tasks_completed(tasks)
                    
                    logger.info(f"[PhasedBuild] Phase {phase_num} completed successfully")
                    return result
                else:
                    result["error"] = deploy_result.get("error", "Deploy failed")
                    return result
                
            except Exception as e:
                logger.exception(f"[PhasedBuild] Phase {phase_num} error")
                retry_count += 1
                result["error"] = str(e)
                
                if retry_count >= self.MAX_RETRIES:
                    return result
        
        return result
    
    # ═══════════════════════════════════════════════════════════════
    # BATCH GENERATION
    # ═══════════════════════════════════════════════════════════════
    
    def _publish_batch_progress(self, phase: int, done: int, total: int) -> None:
        """Publie l'avancement des lots en DB (lecture directe par l'interface)."""
        try:
            from sqlalchemy import text
            self.db.execute(text("""
                UPDATE build_phase_executions
                SET completed_batches = :done, total_batches = :total
                WHERE execution_id = :exec_id AND phase_number = :phase
            """), {"done": done, "total": total, "exec_id": self.execution_id, "phase": phase})
            self.db.commit()
        except Exception as e:
            logger.warning("[BATCHPROG] publication avancement echouee (non bloquant): %s", e)

    async def generate_phase_batches(
        self,
        agent: str,
        tasks: List[Dict],
        phase: int,
        retry_feedback: str = ""
    ) -> List[Dict]:
        """
        Génère les sous-lots pour une phase.
        
        Args:
            agent: Agent à utiliser (raj, diego, zara, aisha)
            tasks: Tâches de la phase
            phase: Numéro de phase
            
        Returns:
            Liste des outputs de lots
        """
        batches = []
        
        # Get context for this phase
        context = self.context_registry.get_context_for_batch(phase)
        
        # Group tasks into batches (1 object/class/component per batch)
        task_batches = self._create_task_batches(tasks, phase)
        
        logger.info(f"[PhasedBuild] Generating {len(task_batches)} batches for phase {phase}")
        # FIX-BATCHPROG-001 (02/08) : publier l'avancement lot par lot. Sans cela
        # l'interface affiche 0/0 pendant toute la phase (20-25 min) et parait figee.
        self._publish_batch_progress(phase, 0, len(task_batches))
        
        for i, batch_tasks in enumerate(task_batches):
            logger.debug(f"[PhasedBuild] Generating batch {i+1}/{len(task_batches)}")
            
            try:
                batch_result = await self._generate_single_batch(
                    agent, batch_tasks, phase, context, retry_feedback
                )
                
                if batch_result:
                    batches.append(batch_result)
                    self._publish_batch_progress(phase, len(batches), len(task_batches))
                    
                    # Update context with this batch's output
                    self.context_registry.register_batch_output(phase, batch_result)
                    context = self.context_registry.get_context_for_batch(phase)
                    
            except Exception as e:
                logger.error(f"[PhasedBuild] Batch {i+1} failed: {e}")
                # Continue with other batches
        
        return batches
    
    def _create_task_batches(self, tasks: List[Dict], phase: int) -> List[List[Dict]]:
        """
        Regroupe les tâches en lots selon la phase.
        
        Phase 1: 1 objet + ses champs par lot
        Phase 2: 1 classe + son test par lot
        Phase 3: 1 composant LWC par lot
        Phase 4: 1 flow ou groupe de VRs par lot
        Phase 5: 1 permission set par lot
        Phase 6: 1 objet cible par lot
        """
        if phase == 1:
            # Group by target object
            return self._group_by_object(tasks)
        elif phase == 2:
            # Group service class + test class
            return self._group_apex_classes(tasks)
        elif phase == 3:
            # One LWC component per batch
            return [[t] for t in tasks]
        elif phase == 4:
            # Group VRs by object, Flows individually
            return self._group_automations(tasks)
        elif phase in (5, 6):
            # One per batch
            return [[t] for t in tasks]
        else:
            return [[t] for t in tasks]
    
    def _group_by_object(self, tasks: List[Dict]) -> List[List[Dict]]:
        """Groupe les tâches Phase 1 par objet cible."""
        objects = {}
        for task in tasks:
            # Try to extract target object from task
            obj = task.get("target_object") or task.get("object_name") or "default"
            if obj not in objects:
                objects[obj] = []
            objects[obj].append(task)
        return list(objects.values())
    
    def _group_apex_classes(self, tasks: List[Dict]) -> List[List[Dict]]:
        """Groupe les classes Apex avec leurs tests."""
        batches = []
        tests = {}
        classes = []
        
        for task in tasks:
            # FIX-TASKTYPE-001 (05/08) : ligne exacte du crash de l'execution 165.
            # get(k, "") ne rend "" que si la cle est ABSENTE ; ici elle existait a
            # None (task_type non persiste en amont, corrige dans
            # pm_orchestrator_service_v2.prepare_build_phase). Meme idiome `or ""`
            # que group_tasks_by_phase. Conserve pour les 413 lignes deja NULL en
            # base, qui doivent pouvoir etre rejouees sans crash.
            task_type = (task.get("task_type") or "")
            name = (task.get("class_name") or task.get("name") or "")
            
            if "test" in task_type.lower() or "test" in name.lower():
                # This is a test, find its target
                target = name.replace("Test", "").replace("_Test", "")
                tests[target] = task
            else:
                classes.append(task)
        
        # Pair classes with their tests
        for cls_task in classes:
            name = cls_task.get("class_name") or cls_task.get("name", "")
            batch = [cls_task]
            if name in tests:
                batch.append(tests[name])
            batches.append(batch)
        
        return batches if batches else [[t] for t in tasks]
    
    def _group_automations(self, tasks: List[Dict]) -> List[List[Dict]]:
        """Groupe les automatisations Phase 4."""
        flows = []
        vrs_by_object = {}
        
        for task in tasks:
            # FIX-TASKTYPE-001 (05/08) : meme defaut latent qu'en phase 2, jamais
            # declenche car aucune execution n'a atteint la phase 4 a ce jour.
            task_type = (task.get("task_type") or "")
            if "flow" in task_type.lower():
                flows.append([task])
            else:
                obj = task.get("object") or task.get("target_object") or "default"
                if obj not in vrs_by_object:
                    vrs_by_object[obj] = []
                vrs_by_object[obj].append(task)
        
        return flows + list(vrs_by_object.values())
    
    async def _generate_single_batch(
        self,
        agent: str,
        tasks: List[Dict],
        phase: int,
        context: str,
        retry_feedback: str = ""
    ) -> Optional[Dict]:
        """Génère un seul lot via l'agent approprié."""
        # Import agent modules dynamically
        try:
            if agent == "raj":
                from agents.roles.salesforce_admin import generate_build_v2
                
                target = tasks[0].get("target_object") or tasks[0].get("name", "unknown")
                description = "\n".join([(t.get("description") or "") for t in tasks])
                
                result = generate_build_v2(
                    phase=phase,
                    target=target,
                    task_description=description,
                    context={"existing_context": context},
                    execution_id=str(self.execution_id),
                    previous_feedback=retry_feedback
                )
                return result if result.get("success") else None
                
            elif agent == "diego":
                from agents.roles.salesforce_developer_apex import generate_build
                
                task = tasks[0]  # Primary task
                result = generate_build(
                    task=task,
                    architecture_context=context,
                    execution_id=str(self.execution_id)
                )
                return {"files": result.get("content", {}).get("files", {})} if result.get("success") else None
                
            elif agent == "zara":
                from agents.roles.salesforce_developer_lwc import generate_build
                
                task = tasks[0]
                result = generate_build(
                    task=task,
                    architecture_context=context,
                    execution_id=str(self.execution_id)
                )
                return {"files": result.get("content", {}).get("files", {})} if result.get("success") else None
                
            elif agent == "aisha":
                from agents.roles.salesforce_data_migration import generate_build
                
                task = tasks[0]
                result = generate_build(
                    task=task,
                    architecture_context=context,
                    execution_id=str(self.execution_id)
                )
                return result.get("content", {}) if result.get("success") else None
                
        except Exception:
            logger.exception(f"[PhasedBuild] Agent {agent} failed")
            return None
        
        return None
    
    # ═══════════════════════════════════════════════════════════════
    # ELENA REVIEW
    # ═══════════════════════════════════════════════════════════════
    
    async def _elena_review(self, phase: int, aggregated: Dict) -> Dict:
        """Exécute la review Elena sur l'output agrégé."""
        try:
            from agents.roles.salesforce_qa_tester import structural_validation, review_phase_output
            
            # First: structural validation
            files = aggregated.get("files", {})
            if files:
                struct_result = structural_validation(files, phase)
                if not struct_result.get("valid"):
                    return {
                        "verdict": "FAIL",
                        "validation_type": "structural",
                        "issues": struct_result.get("issues", []),
                        "feedback_for_developer": "Erreurs structurelles détectées. " + 
                            str(struct_result.get("issues", []))[:500]
                    }
            
            # Then: LLM review
            context = {
                "data_model_context": self.context_registry.get_full_data_model(),
                "apex_context": self.context_registry.get_class_signatures(),
            }
            
            review_prep = await review_phase_output(
                phase, aggregated, context, str(self.execution_id)
            )
            
            if not review_prep.get("requires_llm_review"):
                return review_prep
            
            # Call Elena with the prepared prompt
            from agents.roles.salesforce_qa_tester import generate_test
            
            # Prepare input for generate_test
            code_files = aggregated.get("files", {})
            if not code_files and aggregated.get("operations"):
                code_files = {"plan.json": json.dumps(aggregated.get("operations"), indent=2)}
            
            result = generate_test(
                input_data={
                    "task": {"task_id": f"phase-{phase}-review", "name": f"Phase {phase} Review"},
                    "code_files": code_files,
                    "phase": phase,
                },
                execution_id=str(self.execution_id)
            )
            
            return {
                "verdict": result.get("verdict", "FAIL"),
                "issues": result.get("issues", []),
                "feedback_for_developer": result.get("feedback_for_developer", ""),
                "validation_type": "llm"
            }

        except Exception as e:
            logger.exception("[PhasedBuild] Elena review failed — failing phase visibly")
            # No fail-open: if Elena crashes we cannot assert the build is correct.
            # Return FAIL so the orchestrator can retry or surface the problem to HITL.
            return {
                "verdict": "FAIL",
                "validation_type": "error",
                "issues": [{"severity": "critical", "description": f"Elena review crashed: {e}"}],
                "feedback_for_developer": (
                    "Elena QA review raised an exception and could not validate the phase. "
                    "Investigate the executor logs (agent crash / LLM outage) before retrying."
                ),
                "error": str(e),
            }
    
    # ═══════════════════════════════════════════════════════════════
    # HELPERS
    # ═══════════════════════════════════════════════════════════════
    
    def group_tasks_by_phase(self, tasks: List[Dict]) -> Dict[int, List[Dict]]:
        """Regroupe les tâches WBS par phase."""
        grouped = {1: [], 2: [], 3: [], 4: [], 5: [], 6: []}
        
        for task in tasks:
            # Defensive: dict.get(k, default) returns the default only when k is
            # absent. If the key exists with None, get() returns None and .lower()
            # crashes. The `or ""` pattern handles both cases.
            task_type = (task.get("task_type") or "").lower()
            assigned_agent = (task.get("assigned_agent") or "").lower()
            
            # Try to determine phase from task_type
            phase = TASK_TYPE_TO_PHASE.get(task_type)
            
            if not phase:
                # Fallback: determine by agent
                if assigned_agent in ("raj", "admin"):
                    # Check if it's data model or automation
                    if any(kw in task_type for kw in ["object", "field", "record"]):
                        phase = 1
                    elif any(kw in task_type for kw in ["flow", "valid", "approval"]):
                        phase = 4
                    else:
                        phase = 5  # Default to security
                elif assigned_agent in ("diego", "apex"):
                    phase = 2
                elif assigned_agent in ("zara", "lwc"):
                    phase = 3
                elif assigned_agent in ("aisha", "data"):
                    phase = 6
                elif assigned_agent in ("jordan", "devops"):
                    # FIX-ROUTING-001 (02/08) : infrastructure, packaging, deploiement.
                    # Sans cette branche ces taches tombaient en phase 1 et Raj les
                    # modelisait en objets Salesforce (Depot_Git__c, Strategie_Branche__c...).
                    phase = 6
                elif assigned_agent in ("lucas", "trainer"):
                    # Documentation et supports de formation : jamais du modele de donnees.
                    phase = 6
                elif assigned_agent in ("elena", "qa", "qa_tester"):
                    # Tests et scenarios UAT : rattaches a la logique metier.
                    phase = 2
                else:
                    # FIX-ROUTING-001 : defaut = phase 6 (fin de chaine, documentaire)
                    # et NON phase 1. Un type de tache inconnu ne doit jamais devenir
                    # un objet de donnees par defaut.
                    logger.warning(
                        "[ROUTING] tache non classee (type=%r agent=%r) -> phase 6 par defaut",
                        task_type, assigned_agent,
                    )
                    phase = 6
            
            # Classify validation rules
            if "validation_rule" in task_type:
                phase = self.classify_validation_rule(task)
            
            grouped[phase].append(task)
            
            # Update task with phase
            task["build_phase"] = phase
        
        return grouped
    
    def classify_validation_rule(self, task: Dict) -> int:
        """
        Distingue simple_validation_rule (Phase 1) de complex (Phase 4).
        
        Simple = formule ne référence QUE des champs de l'objet
        Complex = VLOOKUP, référence cross-objet, ou dépendance Apex
        """
        formula = task.get("formula", "")
        dependencies = task.get("dependencies", [])
        
        # Check for cross-object indicators
        if "VLOOKUP" in formula.upper():
            return 4
        if "__r." in formula:  # Cross-object reference
            return 4
        if any("apex" in str(d).lower() for d in dependencies):
            return 4
        
        return 1  # Simple validation rule
    

    # FIX-TASKVIS-001 (02/08) : le BUILD v2 raisonne en 6 phases techniques alors
    # que task_executions est peuple depuis les groupes du WBS. Sans passerelle,
    # les taches restent PENDING pendant toute la phase et l'interface parait figee.
    PHASE_TASK_KEYWORDS = {
        1: ["modele de donnees", "donnees", "data model", "initialisation", "environnement", "depot"],
        2: ["apex", "trigger", "batch", "scheduler", "service"],
        3: ["interface", "lwc", "lightning", "reporting", "ui"],
        4: ["flow", "automatisation declarative", "process"],
        5: ["securite", "validation", "owd", "partage", "permission", "integration"],
        6: ["migration", "documentation", "deploiement", "test"],
    }

    def _sync_task_visibility(self, phase: int, status) -> None:
        """Reflete l'avancement des phases BUILD v2 sur task_executions (affichage)."""
        try:
            from sqlalchemy import text
            status_str = status.value if hasattr(status, "value") else str(status)
            if status_str in ("generating", "aggregating", "reviewing", "deploying"):
                target = "RUNNING"
            elif status_str == "completed":
                target = "COMPLETED"
            elif status_str == "failed":
                target = "FAILED"
            else:
                return
            kws = self.PHASE_TASK_KEYWORDS.get(phase, [])
            if not kws:
                return
            cond = " OR ".join([f"LOWER(COALESCE(phase_name,'')) LIKE :kw{i}" for i in range(len(kws))])
            params = {f"kw{i}": f"%{k}%" for i, k in enumerate(kws)}
            params["exec_id"] = self.execution_id
            params["target"] = target
            res = self.db.execute(text(f"""
                UPDATE task_executions SET status = CAST(:target AS taskstatus)
                WHERE execution_id = :exec_id AND ({cond})
                  AND status <> CAST(:target AS taskstatus)
            """), params)
            self.db.commit()
            if res.rowcount:
                logger.info("[TASKVIS] phase %s -> %s : %d taches mises a jour", phase, target, res.rowcount)
        except Exception as e:
            logger.warning("[TASKVIS] synchro affichage echouee (non bloquant): %s", e)

    async def _update_phase_status(
        self,
        phase: int,
        phase_name: str,
        status: PhaseStatus,
        error: str = None
    ):
        """Met à jour le statut d'une phase en DB."""
        try:
            from sqlalchemy import text
            
            query = text("""
                INSERT INTO build_phase_executions 
                (execution_id, phase_number, phase_name, status, agent_id, started_at, last_error)
                VALUES (:exec_id, :phase, :name, :status, :agent, NOW(), :error)
                ON CONFLICT (execution_id, phase_number) 
                DO UPDATE SET status = :status, last_error = :error,
                    completed_at = CASE WHEN :status IN ('completed', 'failed') THEN NOW() ELSE NULL END
            """)
            
            agent = PHASE_CONFIGS.get(phase, {})
            agent_id = agent.agent if hasattr(agent, 'agent') else "unknown"

            self._sync_task_visibility(phase, status)
            
            self.db.execute(query, {
                "exec_id": self.execution_id,
                "phase": phase,
                "name": phase_name,
                "status": status.value,
                "agent": agent_id,
                "error": error
            })
            self.db.commit()
            
        except Exception as e:
            logger.warning(f"[PhasedBuild] Failed to update phase status: {e}")
    
    async def _mark_tasks_completed(self, tasks: List[Dict]):
        """Marque les tâches comme complétées en DB."""
        try:
            from sqlalchemy import text
            
            for task in tasks:
                task_id = task.get("id") or task.get("task_id")
                if task_id:
                    self.db.execute(
                        text("UPDATE task_executions SET status = 'completed' WHERE id = :id"),
                        {"id": task_id}
                    )
            self.db.commit()
            
        except Exception as e:
            logger.warning(f"[PhasedBuild] Failed to mark tasks completed: {e}")


# ═══════════════════════════════════════════════════════════════
# FACTORY FUNCTION
# ═══════════════════════════════════════════════════════════════

async def create_phased_build_executor(
    project_id: int,
    execution_id: int,
    db
) -> PhasedBuildExecutor:
    """
    Crée et initialise un PhasedBuildExecutor.
    
    Args:
        project_id: ID du projet
        execution_id: ID de l'exécution
        db: Session SQLAlchemy
        
    Returns:
        PhasedBuildExecutor initialisé
    """
    executor = PhasedBuildExecutor(project_id, execution_id, db)
    await executor.initialize()
    return executor
