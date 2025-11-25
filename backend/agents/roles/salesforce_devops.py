#!/usr/bin/env python3
"""Salesforce DevOps Engineer Agent - Professional Version"""
import os, sys, argparse, json
from pathlib import Path
from datetime import datetime
from openai import OpenAI
import time
# from docx import Document

DEVOPS_PROMPT = """# 🚀 SALESFORCE DEVOPS ENGINEER V3 PROFESSIONAL

You are an **expert Salesforce DevOps Engineer** with deep expertise in CI/CD pipelines, deployment automation, and infrastructure management. Generate comprehensive, production-ready DevOps strategies.

## PRIMARY OBJECTIVE
Create a **complete DevOps package** (80-120 pages) covering CI/CD pipeline architecture, environment strategy, deployment automation, monitoring, backup/disaster recovery, release management, and security.

## DELIVERABLES REQUIRED

### 1. CI/CD PIPELINE (20 pages)
Include complete GitHub Actions workflow YAML (100+ lines), pipeline architecture diagram, build/test/deploy stages, automated testing strategy, code quality gates, and artifact management.

### 2. ENVIRONMENT STRATEGY (15 pages)
Detail all environments (Dev, SIT, UAT, Pre-Prod, Production) with org types, refresh schedules, data volumes, user counts, and environment promotion flow with Mermaid diagrams.

### 3. DEPLOYMENT AUTOMATION (15 pages)
Provide COMPLETE executable bash scripts (200+ lines each):
- Master deployment script with validation, backup, rollback
- Backup script for metadata and data
- Rollback script for disaster recovery
- Pre/post deployment verification scripts

### 4. MONITORING & ALERTING (15 pages)
Define monitoring layers (Infrastructure, Application, Business, Integration), key metrics with thresholds, alert configurations (Critical/Warning/Info), and monitoring dashboard design with Platform Events.

### 5. BACKUP & DISASTER RECOVERY (12 pages)
Document backup strategy (metadata, data, config), backup schedules with retention policies, disaster recovery runbook with RTO/RPO targets (4 hours/24 hours), and complete recovery procedures.

### 6. RELEASE MANAGEMENT (10 pages)
Include release types (Major/Minor/Patch/Hotfix) with frequencies, comprehensive release checklist (2 weeks before, 1 week, day-of, post-release), rollback decision matrix, and CAB approval process.

### 7. VERSION CONTROL (8 pages)
Define Git branching model (main/develop/feature/release/hotfix) with Mermaid diagram, branch policies and protection rules, commit message conventions, and merge strategies.

### 8. SECURITY IN DEVOPS (10 pages)
Cover DevSecOps practices, security scanning in pipeline (SAST, dependency checks, secrets scanning), OWASP Top 10 for Salesforce, security checklist for deployments, and compliance requirements.

### 9. PERFORMANCE OPTIMIZATION (8 pages)
Define performance KPIs, optimization strategies for database/code/integrations, monitoring and profiling tools, and scalability planning.

## REQUIRED DIAGRAMS (Mermaid)
1. CI/CD Pipeline Flow
2. Environment Architecture
3. Deployment Process
4. Monitoring Architecture  
5. Branching Strategy
6. Disaster Recovery Flow
Minimum: 6 comprehensive diagrams

## SCRIPT REQUIREMENTS
- All scripts must be COMPLETE and EXECUTABLE (no placeholders)
- Include error handling, logging, and validation
- Production-ready with safety checks
- Document all parameters and usage

## QUALITY STANDARDS
✅ Production-ready (not theoretical)
✅ Complete executable scripts
✅ Specific to requirements provided
✅ Salesforce DX best practices
✅ Security-first approach
✅ 80-120 pages comprehensive documentation

## CONTEXT
{context}

Generate this DevOps package for: {current_date}
"""

def main(requirements: str, project_name: str = "unknown", execution_id: str = None) -> dict:
    """Generate JSON specifications instead of .docx"""
    start_time = time.time()
    
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set")
    
    client = OpenAI(api_key=api_key)
    
    full_prompt = f"""{DEVOPS_PROMPT}

---

## REQUIREMENTS TO ANALYZE:

{requirements}

---

**Generate the complete specifications now.**
"""
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": DEVOPS_PROMPT},
            {"role": "user", "content": full_prompt}
        ],
        max_tokens=16000,
        temperature=0.3
    )
    
    specifications = response.choices[0].message.content
    tokens_used = response.usage.total_tokens
    
    sections = []
    current_section = None
    
    for line in specifications.split('\n'):
        if line.startswith('#'):
            level = len(line) - len(line.lstrip('#'))
            title = line.lstrip('#').strip()
            current_section = {
                "title": title,
                "level": level,
                "content": ""
            }
            sections.append(current_section)
        elif current_section:
            current_section["content"] += line + "\n"
    
    execution_time = time.time() - start_time
    
    output = {
        "agent_id": "devops",
        "agent_name": "Jordan (DevOps Engineer)",
        "execution_id": str(execution_id) if execution_id else "unknown",
        "project_id": project_name,
        "deliverable_type": "devops_specification",
        "content": {
            "raw_markdown": specifications,
            "sections": sections
        },
        "metadata": {
            "tokens_used": tokens_used,
            "model": "gpt-4o-mini",
            "execution_time_seconds": round(execution_time, 2),
            "content_length": len(specifications),
            "sections_count": len(sections),
            "generated_at": datetime.now().isoformat()
        }
    }
    
    output_dir = Path(__file__).parent.parent.parent / "outputs"
    output_dir.mkdir(exist_ok=True)
    
    output_file = f"{project_name}_{execution_id}_devops.json"
    output_path = output_dir / output_file
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"✅ JSON generated: {output_file}")
    print(f"📊 Tokens: {tokens_used}, Time: {execution_time:.2f}s")
    
    return output



if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True, help='Input requirements file')
    parser.add_argument('--output', required=True, help='Output JSON file path')
    parser.add_argument('--execution-id', required=True, help='Execution ID')
    parser.add_argument('--project-id', default='unknown', help='Project ID')
    args = parser.parse_args()
    
    with open(args.input, 'r') as f:
        requirements = f.read()
    
    result = main(requirements, args.project_id, args.execution_id)
    print(f"✅ Generated: {result['metadata']['content_length']} chars")
