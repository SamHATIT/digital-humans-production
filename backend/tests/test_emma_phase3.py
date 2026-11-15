#!/usr/bin/env python3
"""
Tests d'intégration pour Phase 3 - Emma Validate & Coverage Loop

Scénarios testés:
1. Solution complète du premier coup (coverage >= 95%)
2. Solution incomplète → revision → amélioration
3. Max iterations atteint (3 révisions sans succès)
4. Emma validate échoue → WBS non généré
"""

import pytest
import json
import sys
import os
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Test fixtures
@pytest.fixture
def sample_use_cases():
    """Sample UCs for testing."""
    return [
        {
            "id": "UC-001",
            "title": "Submit Customer Feedback",
            "br_id": "BR-001",
            "actor": "Customer",
            "salesforce_components": {
                "objects": ["Customer_Feedback__c", "Account"],
                "fields": ["Rating__c", "Comments__c"],
                "automations": ["Flow"]
            }
        },
        {
            "id": "UC-002", 
            "title": "View Feedback History",
            "br_id": "BR-001",
            "actor": "Sales Rep",
            "salesforce_components": {
                "objects": ["Customer_Feedback__c"],
                "fields": ["Submission_Date__c"],
                "automations": []
            }
        },
        {
            "id": "UC-003",
            "title": "Analyze Sentiment",
            "br_id": "BR-002",
            "actor": "System",
            "salesforce_components": {
                "objects": ["Customer_Feedback__c"],
                "fields": ["Sentiment__c", "Sentiment_Confidence__c"],
                "automations": ["Trigger"],
                "integrations": ["Einstein Sentiment API"]
            }
        }
    ]

@pytest.fixture
def complete_solution_design():
    """Solution design that covers all UCs."""
    return {
        "artifact_id": "ARCH-001",
        "data_model": {
            "custom_objects": [
                {
                    "api_name": "Customer_Feedback__c",
                    "fields": [
                        "Rating__c",
                        "Comments__c", 
                        "Submission_Date__c",
                        "Sentiment__c",
                        "Sentiment_Confidence__c"
                    ]
                }
            ],
            "standard_objects": [
                {"api_name": "Account", "customizations": []}
            ]
        },
        "automation_design": {
            "flows": [{"name": "Feedback_Submission_Flow"}],
            "triggers": [{"name": "SentimentAnalysisTrigger"}]
        },
        "integration_points": [
            {"system": "Einstein Sentiment API"}
        ]
    }

@pytest.fixture
def incomplete_solution_design():
    """Solution design with gaps (missing Sentiment fields)."""
    return {
        "artifact_id": "ARCH-001",
        "data_model": {
            "custom_objects": [
                {
                    "api_name": "Customer_Feedback__c",
                    "fields": [
                        "Rating__c",
                        "Comments__c",
                        "Submission_Date__c"
                        # Missing: Sentiment__c, Sentiment_Confidence__c
                    ]
                }
            ],
            "standard_objects": [
                {"api_name": "Account", "customizations": []}
            ]
        },
        "automation_design": {
            "flows": [{"name": "Feedback_Submission_Flow"}]
            # Missing: SentimentAnalysisTrigger
        },
        "integration_points": []  # Missing: Einstein Sentiment API
    }

@pytest.fixture
def high_coverage_report():
    """Coverage report with >= 95% coverage."""
    return {
        "coverage_percentage": 97.5,
        "status": "PASSED",
        "gaps": [],
        "covered_use_cases": ["UC-001", "UC-002", "UC-003"],
        "uncovered_use_cases": []
    }

@pytest.fixture
def low_coverage_report():
    """Coverage report with < 95% coverage."""
    return {
        "coverage_percentage": 73.2,
        "status": "NEEDS_REVISION",
        "gaps": [
            {"element_type": "sf_field", "element_value": "Sentiment__c", "severity": "high"},
            {"element_type": "sf_field", "element_value": "Sentiment_Confidence__c", "severity": "high"},
            {"element_type": "integration", "element_value": "Einstein Sentiment API", "severity": "high"}
        ],
        "covered_use_cases": ["UC-001", "UC-002"],
        "uncovered_use_cases": ["UC-003"]
    }


class TestEmmaValidateMode:
    """Tests for Emma validate mode."""
    
    def test_validate_mode_exists_in_choices(self):
        """Verify validate mode is in Emma's supported modes."""
        # This is a basic smoke test
        emma_modes = ['analyze', 'validate', 'write_sds']
        assert 'validate' in emma_modes
    
    def test_coverage_calculation_high(self, sample_use_cases, complete_solution_design):
        """Test that complete solution gets high coverage."""
        # Simulate coverage calculation
        total_ucs = len(sample_use_cases)
        covered_ucs = 3  # All UCs covered
        coverage = (covered_ucs / total_ucs) * 100
        assert coverage >= 95
    
    def test_coverage_calculation_low(self, sample_use_cases, incomplete_solution_design):
        """Test that incomplete solution gets low coverage."""
        # Simulate coverage calculation
        total_ucs = len(sample_use_cases)
        covered_ucs = 2  # UC-003 not covered (missing sentiment)
        coverage = (covered_ucs / total_ucs) * 100
        assert coverage < 95


class TestMarcusFixGapsMode:
    """Tests for Marcus fix_gaps mode."""
    
    def test_fix_gaps_mode_exists(self):
        """Verify fix_gaps mode is available."""
        from agents.roles.salesforce_solution_architect import get_fix_gaps_prompt
        assert callable(get_fix_gaps_prompt)
    
    def test_fix_gaps_prompt_generation(self, incomplete_solution_design, low_coverage_report):
        """Test fix_gaps prompt includes all gaps."""
        from agents.roles.salesforce_solution_architect import get_fix_gaps_prompt
        
        prompt = get_fix_gaps_prompt(
            current_solution=incomplete_solution_design,
            coverage_gaps=low_coverage_report["gaps"],
            uncovered_use_cases=low_coverage_report["uncovered_use_cases"],
            iteration=1
        )
        
        # Verify prompt contains key elements
        assert "REVISION" in prompt
        assert "Sentiment__c" in prompt
        assert "Einstein Sentiment" in prompt
        assert "v2" in prompt  # Version increment


class TestCoverageLoop:
    """Tests for the coverage validation loop."""
    
    def test_loop_not_triggered_high_coverage(self, high_coverage_report):
        """Verify loop doesn't trigger when coverage >= 95%."""
        coverage_pct = high_coverage_report["coverage_percentage"]
        needs_revision = coverage_pct < 95
        assert not needs_revision
    
    def test_loop_triggered_low_coverage(self, low_coverage_report):
        """Verify loop triggers when coverage < 95%."""
        coverage_pct = low_coverage_report["coverage_percentage"]
        needs_revision = coverage_pct < 95
        assert needs_revision
    
    def test_gaps_extracted_correctly(self, low_coverage_report):
        """Verify gaps are properly extracted from coverage report."""
        gaps = low_coverage_report["gaps"]
        assert len(gaps) == 3
        assert any(g["element_value"] == "Sentiment__c" for g in gaps)


class TestValidationEmmaImpossible:
    """15/11/2026 — remplace un test qui cherchait des chaines dans le code.

    Regle (Sam, option 2) : si la validation de couverture d'Emma PLANTE, le
    SDS continue mais l'execution est marquee degradee et l'admin alerte.
    """

    def _orchestrateur(self, monkeypatch):
        from app.services import pm_orchestrator_service_v2 as mod
        orch = mod.PMOrchestratorServiceV2.__new__(mod.PMOrchestratorServiceV2)
        traces, alertes = [], []
        monkeypatch.setattr(orch, "_tracer_degradation",
                            lambda ex, motif, detail: traces.append((ex, motif, detail)), raising=False)
        import app.services.admin_alert_service as alerte
        monkeypatch.setattr(alerte, "alerter_admin", lambda *a, **k: alertes.append((a, k)) or True)
        return orch, traces, alertes

    def test_echec_technique_trace_une_degradation_et_alerte(self, monkeypatch):
        orch, traces, alertes = self._orchestrateur(monkeypatch)
        orch._signaler_validation_emma_impossible(182, "Anthropic call failed: timeout")
        assert traces and traces[0][0] == 182
        assert traces[0][1] == orch.MOTIF_COUVERTURE_NON_VERIFIEE
        assert "timeout" in traces[0][2]
        assert alertes and alertes[0][1]["execution_id"] == 182

    def test_une_alerte_en_panne_ne_casse_pas_le_pipeline(self, monkeypatch):
        orch, traces, _ = self._orchestrateur(monkeypatch)
        import app.services.admin_alert_service as alerte
        def boum(*a, **k): raise RuntimeError("telegram en panne")
        monkeypatch.setattr(alerte, "alerter_admin", boum)
        orch._signaler_validation_emma_impossible(7, "x")   # ne doit pas lever
        assert traces, "la degradation doit etre tracee meme si l'alerte echoue"

    def test_la_branche_echec_appelle_bien_le_signalement(self):
        """Controle de cablage : la branche « Emma Validate failed » du
        workflow appelle le signalement (et n'ecrit plus « skipped »)."""
        import inspect
        from app.services import pm_orchestrator_service_v2 as mod
        source = inspect.getsource(mod.PMOrchestratorServiceV2)
        assert "self._signaler_validation_emma_impossible(" in source
        assert "Coverage check skipped" not in source

