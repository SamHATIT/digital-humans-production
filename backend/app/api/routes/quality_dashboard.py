"""
Quality Dashboard API Routes
- BLD-07: Dashboard qualité code
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging
import re

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/quality", tags=["Quality"])


# ========== Quality Metrics Models ==========

class QualityMetrics(BaseModel):
    apex_score: float
    lwc_score: float
    overall_score: float
    errors_count: int
    warnings_count: int
    test_coverage_estimate: float
    best_practices_violations: int


class FileQuality(BaseModel):
    file_path: str
    file_type: str
    score: float
    issues: List[Dict[str, Any]]
    metrics: Dict[str, Any]


# ========== BLD-07: Quality Dashboard ==========

@router.get("/execution/{execution_id}")
async def get_execution_quality(execution_id: int):
    """
    Get quality metrics for all code generated in an execution.
    """
    from sqlalchemy import text
    from app.database import get_db_session
    
    try:
        with get_db_session() as session:
            # Get all generated files
            result = session.execute(text("""
                SELECT task_id, task_name, generated_files, validation_status, validation_errors
                FROM task_executions 
                WHERE execution_id = :exec_id 
                AND generated_files IS NOT NULL
            """), {"exec_id": execution_id})
            
            all_files = []
            total_errors = 0
            total_warnings = 0
            apex_scores = []
            lwc_scores = []
            
            for row in result:
                if row.generated_files:
                    for file_path, content in row.generated_files.items():
                        analysis = _analyze_code_quality(file_path, content)
                        all_files.append({
                            "task_id": row.task_id,
                            "file_path": file_path,
                            **analysis
                        })
                        
                        total_errors += analysis["errors_count"]
                        total_warnings += analysis["warnings_count"]
                        
                        if analysis["file_type"] == "apex":
                            apex_scores.append(analysis["score"])
                        elif analysis["file_type"] == "lwc":
                            lwc_scores.append(analysis["score"])
            
            # Calculate aggregates
            apex_score = sum(apex_scores) / len(apex_scores) if apex_scores else 0
            lwc_score = sum(lwc_scores) / len(lwc_scores) if lwc_scores else 0
            overall_score = (apex_score + lwc_score) / 2 if (apex_scores or lwc_scores) else 0
            
            # Estimate test coverage based on test files
            test_files = [f for f in all_files if "Test" in f["file_path"]]
            source_files = [f for f in all_files if "Test" not in f["file_path"] and f["file_type"] == "apex"]
            test_coverage = (len(test_files) / len(source_files) * 75) if source_files else 0
            
            return {
                "success": True,
                "execution_id": execution_id,
                "summary": {
                    "overall_score": round(overall_score, 1),
                    "apex_score": round(apex_score, 1),
                    "lwc_score": round(lwc_score, 1),
                    "total_files": len(all_files),
                    "errors_count": total_errors,
                    "warnings_count": total_warnings,
                    "test_coverage_estimate": round(test_coverage, 1),
                    "grade": _score_to_grade(overall_score)
                },
                "files": all_files,
                "generated_at": datetime.now().isoformat()
            }
            
    except Exception as e:
        logger.error(f"Quality analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/file")
async def analyze_file(file_path: str, content: str):
    """
    Analyze quality of a single file.
    """
    try:
        analysis = _analyze_code_quality(file_path, content)
        return {
            "success": True,
            "file_path": file_path,
            **analysis
        }
    except Exception as e:
        logger.error(f"File analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trends/{project_id}")
async def get_quality_trends(project_id: int, limit: int = 10):
    """
    Get quality score trends over recent executions.
    """
    from sqlalchemy import text
    from app.database import get_db_session
    
    try:
        with get_db_session() as session:
            result = session.execute(text("""
                SELECT e.id, e.created_at, COUNT(t.id) as task_count
                FROM executions e
                LEFT JOIN task_executions t ON e.id = t.execution_id
                WHERE e.project_id = :project_id
                GROUP BY e.id, e.created_at
                ORDER BY e.created_at DESC
                LIMIT :limit
            """), {"project_id": project_id, "limit": limit})
            
            trends = []
            for row in result:
                # Get quality for each execution
                quality = await get_execution_quality(row.id)
                trends.append({
                    "execution_id": row.id,
                    "date": row.created_at.isoformat() if row.created_at else None,
                    "score": quality.get("summary", {}).get("overall_score", 0),
                    "grade": quality.get("summary", {}).get("grade", "N/A")
                })
            
            return {
                "success": True,
                "project_id": project_id,
                "trends": trends
            }
            
    except Exception as e:
        logger.error(f"Trends error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rules")
async def get_quality_rules():
    """
    Get the quality rules being checked.
    """
    return {
        "apex_rules": [
            {"id": "APEX001", "severity": "error", "description": "SOQL/DML in loops"},
            {"id": "APEX002", "severity": "error", "description": "Hardcoded IDs"},
            {"id": "APEX003", "severity": "warning", "description": "Missing null checks"},
            {"id": "APEX004", "severity": "warning", "description": "Too many nested loops"},
            {"id": "APEX005", "severity": "error", "description": "Missing test methods"},
            {"id": "APEX006", "severity": "warning", "description": "Magic numbers"},
            {"id": "APEX007", "severity": "error", "description": "Hardcoded credentials"}
        ],
        "lwc_rules": [
            {"id": "LWC001", "severity": "error", "description": "Missing API decorator"},
            {"id": "LWC002", "severity": "warning", "description": "Missing error handling"},
            {"id": "LWC003", "severity": "warning", "description": "Inline styles"},
            {"id": "LWC004", "severity": "error", "description": "Direct DOM manipulation"},
            {"id": "LWC005", "severity": "warning", "description": "Missing accessibility attributes"}
        ],
        "metadata_rules": [
            {"id": "META001", "severity": "error", "description": "Invalid API version"},
            {"id": "META002", "severity": "warning", "description": "Missing description"},
            {"id": "META003", "severity": "error", "description": "Forbidden properties"}
        ]
    }


# ========== Helper Functions ==========

def _analyze_code_quality(file_path: str, content: str) -> Dict[str, Any]:
    """
    Analyze code quality and return metrics.
    """
    file_type = _detect_file_type(file_path)
    issues = []
    score = 100.0
    metrics = {
        "lines": len(content.split('\n')),
        "chars": len(content)
    }
    
    if file_type == "apex":
        issues, score, metrics = _analyze_apex(content, metrics)
    elif file_type == "lwc":
        issues, score, metrics = _analyze_lwc(content, metrics)
    elif file_type == "metadata":
        issues, score, metrics = _analyze_metadata(content, metrics)
    
    errors = [i for i in issues if i["severity"] == "error"]
    warnings = [i for i in issues if i["severity"] == "warning"]
    
    return {
        "file_type": file_type,
        "score": max(0, min(100, score)),
        "issues": issues,
        "metrics": metrics,
        "errors_count": len(errors),
        "warnings_count": len(warnings)
    }


def _detect_file_type(file_path: str) -> str:
    """Detect file type from path."""
    if file_path.endswith('.cls') or file_path.endswith('.trigger'):
        return "apex"
    elif file_path.endswith('.js') and '/lwc/' in file_path:
        return "lwc"
    elif file_path.endswith('.html') and '/lwc/' in file_path:
        return "lwc_template"
    elif file_path.endswith('.xml') or file_path.endswith('-meta.xml'):
        return "metadata"
    else:
        return "other"


def _analyze_apex(content: str, metrics: Dict) -> tuple:
    """Analyze Apex code quality."""
    issues = []
    score = 100.0
    
    # Count methods and complexity
    methods = re.findall(r'(public|private|global)\s+\w+\s+\w+\s*\(', content)
    metrics["methods_count"] = len(methods)
    
    # APEX001: SOQL/DML in loops
    loops = re.findall(r'for\s*\([^)]+\)\s*\{', content, re.IGNORECASE)
    for_content = content
    for loop in loops:
        if re.search(r'\[SELECT|INSERT|UPDATE|DELETE|Database\.', for_content, re.IGNORECASE):
            issues.append({"rule": "APEX001", "severity": "error", "message": "SOQL/DML detected inside loop"})
            score -= 15
            break
    
    # APEX002: Hardcoded IDs
    if re.search(r"'[a-zA-Z0-9]{15,18}'", content):
        issues.append({"rule": "APEX002", "severity": "error", "message": "Hardcoded Salesforce ID detected"})
        score -= 10
    
    # APEX003: Missing null checks before .size() or accessing properties
    if re.search(r'\w+\.size\(\)', content) and not re.search(r'!=\s*null.*\.size\(\)|\.isEmpty\(\)', content):
        issues.append({"rule": "APEX003", "severity": "warning", "message": "Potential null pointer - check before .size()"})
        score -= 5
    
    # APEX005: Test class without @isTest or testMethod
    if 'Test' in content and not re.search(r'@isTest|testMethod', content, re.IGNORECASE):
        issues.append({"rule": "APEX005", "severity": "warning", "message": "Test class missing @isTest annotation"})
        score -= 5
    
    # APEX007: Hardcoded credentials (from BUG-042)
    if re.search(r'password\s*=|api[_-]?key\s*=|secret\s*=|token\s*=', content, re.IGNORECASE):
        issues.append({"rule": "APEX007", "severity": "error", "message": "Potential hardcoded credentials detected"})
        score -= 20
    
    return issues, score, metrics


def _analyze_lwc(content: str, metrics: Dict) -> tuple:
    """Analyze LWC JavaScript quality."""
    issues = []
    score = 100.0
    
    # Count methods
    methods = re.findall(r'(async\s+)?\w+\s*\([^)]*\)\s*\{', content)
    metrics["methods_count"] = len(methods)
    
    # LWC001: Missing @api decorator for public properties
    if re.search(r'export\s+default\s+class', content) and not re.search(r'@api', content):
        if re.search(r'this\.\w+\s*=', content):
            issues.append({"rule": "LWC001", "severity": "warning", "message": "Consider using @api for public properties"})
            score -= 5
    
    # LWC002: Missing error handling in async methods
    if re.search(r'async\s+\w+', content) and not re.search(r'try\s*\{|catch\s*\(|\.catch\s*\(', content):
        issues.append({"rule": "LWC002", "severity": "warning", "message": "Missing error handling in async method"})
        score -= 5
    
    # LWC004: Direct DOM manipulation
    if re.search(r'document\.(getElementById|querySelector|createElement)', content):
        issues.append({"rule": "LWC004", "severity": "error", "message": "Direct DOM manipulation - use template refs instead"})
        score -= 15
    
    return issues, score, metrics


def _analyze_metadata(content: str, metrics: Dict) -> tuple:
    """Analyze metadata XML quality."""
    issues = []
    score = 100.0
    
    # META001: Invalid API version
    version_match = re.search(r'<apiVersion>(\d+\.\d+)</apiVersion>', content)
    if version_match:
        version = float(version_match.group(1))
        if version < 50.0:
            issues.append({"rule": "META001", "severity": "warning", "message": f"Old API version {version} - consider upgrading"})
            score -= 5
    
    # META002: Missing description
    if '<CustomObject' in content or '<CustomField' in content:
        if '<description>' not in content:
            issues.append({"rule": "META002", "severity": "warning", "message": "Missing description in metadata"})
            score -= 3
    
    # META003: Forbidden properties (from BLD-02)
    forbidden = ['enableChangeDataCapture', 'enableEnhancedLookup', 'enableHistory', 'enableBulkApi']
    for prop in forbidden:
        if prop in content:
            issues.append({"rule": "META003", "severity": "error", "message": f"Forbidden property: {prop}"})
            score -= 10
    
    return issues, score, metrics


def _score_to_grade(score: float) -> str:
    """Convert numeric score to letter grade."""
    if score >= 90:
        return "A"
    elif score >= 80:
        return "B"
    elif score >= 70:
        return "C"
    elif score >= 60:
        return "D"
    else:
        return "F"
