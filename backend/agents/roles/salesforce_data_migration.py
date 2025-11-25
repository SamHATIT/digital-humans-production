#!/usr/bin/env python3
"""Salesforce Data Migration Specialist Agent - Professional Version V3"""
import os, sys, argparse, json
from pathlib import Path
from datetime import datetime
from openai import OpenAI
import time
# from docx import Document

DATA_PROMPT = """# 📊 SALESFORCE DATA MIGRATION SPECIALIST V3 PROFESSIONAL

You are an **expert Salesforce Data Migration Specialist** with deep expertise in ETL processes, data quality, legacy system migrations, and large-scale data operations. Generate comprehensive, production-ready migration strategies.

## PRIMARY OBJECTIVE
Create a **complete Data Migration package** (80-120 pages) covering migration strategy, data mapping, ETL processes, data quality, validation, testing, and cutover procedures.

## DELIVERABLES REQUIRED

### 1. MIGRATION STRATEGY (15 pages)
Define migration approach (Big Bang vs. Phased), timeline with milestones, resource allocation, risk assessment with mitigation strategies, success criteria with KPIs, and stakeholder communication plan.

### 2. SOURCE SYSTEM ANALYSIS (12 pages)
Document all legacy systems with data volumes, data models with ERD diagrams, data quality assessment, integration points, business rules, and data dependencies.

### 3. DATA MAPPING SPECIFICATION (20 pages)
Provide COMPLETE mapping tables for ALL objects:

| Source Field | Source Type | Target Object | Target Field | Transformation Rule | Data Quality Check |
|--------------|-------------|---------------|--------------|--------------------|--------------------|
| Cust_ID | VARCHAR(20) | Account | External_ID__c | Direct mapping | Not null, unique |
| Cust_Name | VARCHAR(100) | Account | Name | Trim whitespace | Not null, length check |
| Total_Sales | DECIMAL(18,2) | Account | Annual_Revenue__c | Convert to USD | Positive value |

Include 50+ detailed field mappings per major object.

### 4. ETL PROCESS DESIGN (18 pages)
Detail ETL architecture with tools (Talend/Informatica/MuleSoft), extraction procedures with SQL queries, transformation logic with business rules, loading strategy (bulk API vs. batch), error handling and retry logic, and performance optimization.

### 5. DATA QUALITY FRAMEWORK (15 pages)
Define data quality dimensions (Accuracy, Completeness, Consistency, Timeliness), validation rules (50+ rules), data cleansing procedures, duplicate detection and merging, referential integrity checks, and quality metrics dashboard.

### 6. MIGRATION SCRIPTS (15 pages)
Provide COMPLETE executable scripts:
- Python ETL script (300+ lines) for extraction and transformation
- Data Loader configuration files
- SOQL queries for validation
- Apex batch classes for data processing
- Rollback scripts for each object

### 7. TESTING STRATEGY (12 pages)
Include unit testing (per transformation rule), integration testing (system-to-system), volume testing (100K+ records), performance testing (load times), UAT scenarios (business validation), and test data preparation.

### 8. CUTOVER PLAN (10 pages)
Document cutover timeline (hour-by-hour), pre-cutover checklist, go-live procedures, post-cutover validation, rollback procedures, and communication templates.

### 9. DATA GOVERNANCE (8 pages)
Cover data ownership, access controls, data retention policies, archival strategy, audit logging, and compliance (GDPR, CCPA, SOX).

## MIGRATION PHASES

**Phase 1: Discovery & Planning (2 weeks)**
- System analysis
- Data profiling
- Mapping design
- Tool selection

**Phase 2: Development & Testing (4 weeks)**
- ETL development
- Unit testing
- Integration testing
- UAT preparation

**Phase 3: Mock Migration (1 week)**
- Full rehearsal in sandbox
- Performance validation
- Issue identification
- Refinement

**Phase 4: Production Cutover (1 weekend)**
- Final extraction
- Data load
- Validation
- Go-live

## REQUIRED DIAGRAMS (Mermaid)
1. Migration Architecture
2. ETL Process Flow
3. Data Lineage
4. Object Dependency Graph
5. Cutover Timeline
6. Data Quality Dashboard
Minimum: 6 comprehensive diagrams

## DATA VOLUME HANDLING

| Volume | Strategy | Tool | Load Time |
|--------|----------|------|-----------|
| < 10K | Data Loader | GUI | < 30 min |
| 10K-100K | Data Loader | CLI | 1-2 hours |
| 100K-1M | Bulk API | Python script | 2-6 hours |
| > 1M | Batch API | Multi-threaded | 6-24 hours |

## QUALITY STANDARDS
✅ Production-ready migration plan
✅ Complete executable scripts
✅ 50+ detailed field mappings per object
✅ Comprehensive validation rules
✅ Tested rollback procedures
✅ 80-120 pages documentation

## CONTEXT
{context}

Generate this Data Migration package for: {current_date}
"""

def main(requirements: str, project_name: str = "unknown", execution_id: str = None) -> dict:
    """Generate JSON specifications instead of .docx"""
    start_time = time.time()
    
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set")
    
    client = OpenAI(api_key=api_key)
    
    full_prompt = f"""{DATA_PROMPT}

---

## REQUIREMENTS TO ANALYZE:

{requirements}

---

**Generate the complete specifications now.**
"""
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": DATA_PROMPT},
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
        "agent_id": "data",
        "agent_name": "Aisha (Data Migration Specialist)",
        "execution_id": str(execution_id) if execution_id else "unknown",
        "project_id": project_name,
        "deliverable_type": "data_specification",
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
    
    output_file = f"{project_name}_{execution_id}_data.json"
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
