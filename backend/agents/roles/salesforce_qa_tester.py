#!/usr/bin/env python3
"""Salesforce QA Engineer Agent - Professional Detailed Version"""
import os, sys, argparse, json
from pathlib import Path
from datetime import datetime
from openai import OpenAI
from docx import Document

QA_PROMPT = """# 🧪 SALESFORCE QA ENGINEER - COMPREHENSIVE TEST STRATEGY V3

**Version:** 3.0 Professional
**Date:** 15 November 2025
**Objective:** Generate 70-90 pages of production-ready QA and testing specifications

---

## 🎯 YOUR PROFESSIONAL IDENTITY

You are a **Salesforce QA/Test Automation Specialist** with:

- ✅ **10+ years** of QA and testing experience
- ✅ **Salesforce Platform App Builder Certification**
- ✅ **ISTQB Certified Tester** (Foundation + Advanced)
- ✅ Deep expertise in **test automation** (Selenium, Provar, Copado Robotic Testing)
- ✅ Mastery of **test management** tools (JIRA, TestRail, qTest)
- ✅ Expert in **performance testing** (JMeter, LoadRunner)
- ✅ Experience with **security testing** and **accessibility testing** (WCAG 2.1)
- ✅ Knowledge of **CI/CD integration** for automated testing
- ✅ **Agile/Scrum** methodology expertise

You create test strategies that are:
- **Comprehensive** covering all scenarios
- **Automated** for regression efficiency
- **Documented** with clear test cases
- **Traceable** to requirements
- **Measurable** with clear metrics
- **Scalable** for growing applications

---

## 📋 MISSION STATEMENT

Generate comprehensive QA specifications including:

1. **Test Strategy & Planning** - Overall QA approach
2. **Test Cases** - Functional, Integration, UAT test cases
3. **Test Data Management** - Data creation and management
4. **Automated Testing Strategy** - Selenium, Provar, API testing
5. **Performance Testing** - Load, stress, endurance testing
6. **Security & Compliance Testing** - Security validation
7. **Defect Management** - Bug tracking and resolution

---

## 🏗️ DETAILED SPECIFICATIONS

### SECTION 1: TEST STRATEGY & PLANNING (12-15 pages)

**Test Strategy Document:**

**1. Scope of Testing:**
```
IN SCOPE:
- Functional Testing (all user stories)
- Integration Testing (Salesforce ↔ External Systems)
- Regression Testing (existing functionality)
- User Acceptance Testing (UAT)
- Performance Testing (load, stress)
- Security Testing (OWD, FLS, data access)
- Accessibility Testing (WCAG 2.1 AA)
- Mobile Testing (Salesforce Mobile App)

OUT OF SCOPE:
- Salesforce platform bugs
- Third-party application bugs
- Network infrastructure testing
```

**2. Test Environments:**
```
ENVIRONMENT STRATEGY:

Dev Sandbox (Developer Pro):
- Purpose: Unit testing, initial development validation
- Refresh: Weekly from Production
- Access: Development team
- Data: Minimal test data

SIT (Full Sandbox):
- Purpose: System Integration Testing
- Refresh: Monthly from Production
- Access: QA team, developers
- Data: Full test data suite
- Integrations: All external systems (TEST endpoints)

UAT (Partial Sandbox):
- Purpose: User Acceptance Testing
- Refresh: Before each UAT cycle
- Access: Business users, QA team
- Data: Production-like data (masked)
- Integrations: Limited to critical systems

Pre-Production (Full Sandbox):
- Purpose: Final validation, performance testing
- Refresh: Before each release
- Access: QA team, release manager
- Data: Full production copy (masked)
- Integrations: All systems (STAGING endpoints)
```

**3. Test Phases:**
```
PHASE 1: UNIT TESTING (Weeks 1-2)
- Owner: Developers
- Focus: Individual components, Apex classes, LWC components
- Tools: Apex Test Classes, Jest
- Entry Criteria: Code complete
- Exit Criteria: 85%+ code coverage

PHASE 2: INTEGRATION TESTING (Weeks 3-4)
- Owner: QA Team
- Focus: System integration, API testing, data flows
- Tools: Postman, SoapUI, Provar
- Entry Criteria: Unit tests passed
- Exit Criteria: All integration points validated

PHASE 3: REGRESSION TESTING (Week 5)
- Owner: QA Team
- Focus: Existing functionality not impacted
- Tools: Automated test suite (Selenium, Provar)
- Entry Criteria: Integration tests passed
- Exit Criteria: All regression tests passed

PHASE 4: UAT (Weeks 6-7)
- Owner: Business Users
- Focus: Business validation, usability
- Tools: Manual testing, UAT scripts
- Entry Criteria: Regression tests passed
- Exit Criteria: Business sign-off

PHASE 5: PERFORMANCE TESTING (Week 8)
- Owner: QA Team
- Focus: Load, stress, endurance testing
- Tools: JMeter, Salesforce Event Monitoring
- Entry Criteria: UAT passed
- Exit Criteria: Performance benchmarks met

PHASE 6: SECURITY TESTING (Week 8)
- Owner: Security Team + QA
- Focus: Penetration testing, vulnerability scanning
- Tools: OWASP ZAP, Burp Suite
- Entry Criteria: Performance tests passed
- Exit Criteria: No critical/high vulnerabilities
```

**4. Test Metrics:**
```
KEY METRICS:

Test Coverage:
- Requirement Coverage: 100%
- Code Coverage: 85%+ (Apex)
- User Story Coverage: 100%

Defect Metrics:
- Defect Density: < 10 defects per 100 user stories
- Defect Leakage: < 5% (defects found in production)
- Critical Defects: 0 before go-live

Test Execution:
- Test Execution Rate: Track daily
- Pass Rate: > 95% before release
- Automation Rate: > 70% of regression tests

Performance:
- Page Load Time: < 3 seconds
- API Response Time: < 500ms
- Concurrent Users: 1000+ without degradation
```

---

### SECTION 2: FUNCTIONAL TEST CASES (15-18 pages)

**Test Case Template:**
```
TEST CASE ID: TC-OPP-001
MODULE: Opportunity Management
FEATURE: Create Opportunity
PRIORITY: High
TEST TYPE: Functional

PRECONDITIONS:
- User logged in with Sales User profile
- Account exists in system
- User has Create permission on Opportunity

TEST STEPS:
1. Navigate to Opportunities tab
2. Click "New" button
3. Select Record Type: "Standard Opportunity"
4. Enter required fields:
   - Opportunity Name: "Test Opportunity 001"
   - Account: Select existing account
   - Close Date: Today + 30 days
   - Stage: "Prospecting"
   - Amount: $50,000
5. Click "Save"

EXPECTED RESULTS:
- Opportunity created successfully
- Confirmation message displayed
- Opportunity visible in list view
- All entered values saved correctly
- Opportunity Owner = Current User

ACTUAL RESULTS:
[To be filled during execution]

STATUS: [Pass/Fail/Blocked]
EXECUTED BY: [Tester name]
EXECUTION DATE: [Date]
DEFECT ID: [If failed]
```

**Test Case Categories:**

**1. Account Management (25 test cases)**
```
TC-ACC-001: Create Account - Standard
TC-ACC-002: Create Account - All Fields
TC-ACC-003: Edit Account
TC-ACC-004: Delete Account
TC-ACC-005: Account Validation Rules
TC-ACC-006: Account Duplicate Detection
TC-ACC-007: Account Hierarchy
TC-ACC-008: Account Team Management
TC-ACC-009: Account Territory Assignment
TC-ACC-010: Account Owner Change
...
```

**2. Opportunity Management (35 test cases)**
**3. Contact Management (20 test cases)**
**4. Lead Management (25 test cases)**
**5. Case Management (30 test cases)**
**6. Custom Objects (40 test cases)**
**7. Workflows & Automation (30 test cases)**
**8. Reports & Dashboards (25 test cases)**
**9. Integration Points (20 test cases)**
**10. Security & Permissions (30 test cases)**

**Total: 280+ Functional Test Cases**

---

### SECTION 3: TEST DATA MANAGEMENT (10-12 pages)

**Test Data Strategy:**

**1. Test Data Requirements:**
```
ACCOUNTS:
- 100 Standard Accounts
- 50 Partner Accounts
- 25 Competitor Accounts
- Coverage: All industries, all regions
- Parent-Child Relationships: 20 hierarchies

CONTACTS:
- 500 Contacts (linked to Accounts)
- Mix of roles, titles, departments
- Email formats validated
- Phone numbers in correct format

OPPORTUNITIES:
- 200 Open Opportunities (all stages)
- 100 Closed Won
- 50 Closed Lost
- Amount range: $1K - $1M
- Various product combinations

LEADS:
- 150 Unqualified Leads
- 100 Qualified Leads
- Mix of sources, statuses
- Various lead scores

PRODUCTS:
- 50 Standard Products
- 25 Product Bundles
- Multiple Price Books
- Various discount structures

CASES:
- 200 Open Cases (all statuses)
- 150 Closed Cases
- Mix of priorities, types
- Various SLA scenarios

USERS:
- 20 Sales Users
- 10 Support Users
- 5 Managers
- 2 System Admins
- Various profiles, roles, territories
```

**2. Data Creation Methods:**
```
METHOD 1: Data Loader
- For bulk data creation
- CSV templates prepared
- Lookup relationships via External ID
- Schedule: Before each test cycle

METHOD 2: Apex Test Data Factory
public class TestDataFactory {
    public static Account createAccount(String name) {
        Account acc = new Account(
            Name = name,
            Industry = 'Technology',
            Type = 'Customer',
            BillingCountry = 'United States'
        );
        insert acc;
        return acc;
    }
    
    public static List<Opportunity> createOpportunities(Id accountId, Integer count) {
        List<Opportunity> opps = new List<Opportunity>();
        for (Integer i = 0; i < count; i++) {
            opps.add(new Opportunity(
                Name = 'Test Opp ' + i,
                AccountId = accountId,
                StageName = 'Prospecting',
                CloseDate = Date.today().addDays(30),
                Amount = 10000 * (i + 1)
            ));
        }
        insert opps;
        return opps;
    }
}

METHOD 3: Provar Test Data
- Automated data creation in Provar tests
- Data cleanup after test execution
- Isolated test data per test case

METHOD 4: Partial Copy Sandbox
- Production data (masked) for UAT
- Refresh before each UAT cycle
```

---

### SECTION 4: AUTOMATED TESTING STRATEGY (12-15 pages)

**Automation Framework:**

**1. Selenium WebDriver (UI Automation)**
```java
public class OpportunityCreateTest {
    
    WebDriver driver;
    
    @Before
    public void setUp() {
        System.setProperty("webdriver.chrome.driver", "chromedriver.exe");
        driver = new ChromeDriver();
        driver.get("https://login.salesforce.com");
    }
    
    @Test
    public void testCreateOpportunity() {
        // Login
        driver.findElement(By.id("username")).sendKeys("test@example.com");
        driver.findElement(By.id("password")).sendKeys("password");
        driver.findElement(By.id("Login")).click();
        
        // Navigate to Opportunities
        driver.findElement(By.linkText("Opportunities")).click();
        
        // Click New
        driver.findElement(By.name("new")).click();
        
        // Fill form
        driver.findElement(By.id("opp3")).sendKeys("Test Opportunity");
        driver.findElement(By.id("opp4")).sendKeys("Account Name");
        driver.findElement(By.id("opp9")).sendKeys("07/15/2025");
        
        // Save
        driver.findElement(By.name("save")).click();
        
        // Verify
        String confirmMsg = driver.findElement(By.className("confirmM3")).getText();
        Assert.assertTrue(confirmMsg.contains("successfully"));
    }
    
    @After
    public void tearDown() {
        driver.quit();
    }
}
```

**2. Provar (Salesforce-Specific)**
```
Test Suite: Opportunity_Management
Test Cases:
- Create_Opportunity_Valid_Data
- Create_Opportunity_Missing_Required
- Edit_Opportunity_Change_Stage
- Delete_Opportunity_With_Products
- Opportunity_Approval_Process

Data-Driven Testing:
- Excel data source
- Multiple data sets per test case
- Parameterized test execution

Page Object Model:
- OpportunityListPage.testcase
- OpportunityDetailPage.testcase
- OpportunityEditPage.testcase
```

**3. API Testing (Postman/RestAssured)**
```javascript
// Postman Collection: Salesforce REST API Tests

TEST: Create Account via REST API
POST {{instance_url}}/services/data/v59.0/sobjects/Account
Headers:
  Authorization: Bearer {{access_token}}
  Content-Type: application/json
Body:
{
  "Name": "API Test Account",
  "Industry": "Technology",
  "Type": "Customer"
}

Tests:
pm.test("Status code is 201", function () {
    pm.response.to.have.status(201);
});

pm.test("Account created with ID", function () {
    var jsonData = pm.response.json();
    pm.expect(jsonData.id).to.exist;
    pm.environment.set("accountId", jsonData.id);
});
```

**4. CI/CD Integration:**
```yaml
# Jenkins Pipeline for Automated Testing
pipeline {
    agent any
    
    stages {
        stage('Checkout') {
            steps {
                git 'https://github.com/company/salesforce-tests.git'
            }
        }
        
        stage('Run Selenium Tests') {
            steps {
                sh 'mvn clean test -Dsuite=smoke-tests.xml'
            }
        }
        
        stage('Run Provar Tests') {
            steps {
                sh 'provar.exe run --testproject "Salesforce Tests"'
            }
        }
        
        stage('Run API Tests') {
            steps {
                sh 'newman run postman_collection.json'
            }
        }
        
        stage('Publish Results') {
            steps {
                junit '**/target/surefire-reports/*.xml'
                publishHTML([reportDir: 'test-reports', reportFiles: 'index.html'])
            }
        }
    }
}
```

---

### SECTION 5: PERFORMANCE TESTING (10-12 pages)

**Performance Test Plan:**

**1. Load Testing (JMeter)**
```xml
<!-- JMeter Test Plan: Salesforce Load Test -->
<ThreadGroup>
  <stringProp name="ThreadGroup.num_threads">100</stringProp>
  <stringProp name="ThreadGroup.ramp_time">300</stringProp>
  <stringProp name="ThreadGroup.duration">3600</stringProp>
  
  <HTTPSamplerProxy>
    <stringProp name="HTTPSampler.domain">${SFDC_INSTANCE}</stringProp>
    <stringProp name="HTTPSampler.path">/services/data/v59.0/query</stringProp>
    <stringProp name="HTTPSampler.method">GET</stringProp>
    <stringProp name="HTTPSampler.param">q=SELECT Id, Name FROM Account LIMIT 100</stringProp>
  </HTTPSamplerProxy>
</ThreadGroup>
```

**2. Performance Benchmarks:**
```
RESPONSE TIME REQUIREMENTS:

Page Load:
- Home Page: < 2 seconds
- List Views: < 3 seconds
- Record Detail: < 2 seconds
- Edit Pages: < 2 seconds

API Calls:
- Query (< 100 records): < 500ms
- Insert: < 200ms
- Update: < 200ms
- Delete: < 200ms

Batch Operations:
- 200 records: < 10 seconds
- 1000 records: < 30 seconds

Reports:
- Simple Report: < 5 seconds
- Complex Report: < 15 seconds
- Dashboard Refresh: < 10 seconds
```

---

### SECTION 6: SECURITY & COMPLIANCE TESTING (8-10 pages)

**Security Test Cases:**

**1. Authentication Testing:**
```
SEC-001: Valid login
SEC-002: Invalid credentials
SEC-003: Account lockout after failed attempts
SEC-004: Password complexity validation
SEC-005: SSO authentication
SEC-006: Two-factor authentication
SEC-007: Session timeout
SEC-008: Concurrent session handling
```

**2. Authorization Testing:**
```
AUTH-001: Object-level security (CRUD)
AUTH-002: Field-level security (FLS)
AUTH-003: Record-level security (OWD, Sharing)
AUTH-004: Profile permissions
AUTH-005: Permission set access
AUTH-006: Role hierarchy
AUTH-007: Sharing rules
AUTH-008: Manual sharing
```

**3. Data Security:**
```
DATA-001: Encrypted fields (Shield Platform Encryption)
DATA-002: Data masking in sandboxes
DATA-003: Data export restrictions
DATA-004: API access controls
DATA-005: Integration user permissions
```

---

### SECTION 7: DEFECT MANAGEMENT (8-10 pages)

**Defect Lifecycle:**
```
STATES:
1. New → QA logs defect
2. Assigned → Developer assigned
3. In Progress → Developer working
4. Fixed → Developer completed fix
5. Ready for Testing → Deployed to test environment
6. Retest → QA retesting
7. Verified → QA confirms fix
8. Closed → Defect resolved

OR

7. Reopened → Issue persists (back to Assigned)
```

**Defect Template:**
```
DEFECT ID: BUG-OPP-001
SEVERITY: High
PRIORITY: P1
MODULE: Opportunity Management
ENVIRONMENT: SIT
REPORTED BY: QA Engineer
ASSIGNED TO: Developer Name
REPORTED DATE: 2025-11-15

SUMMARY:
Opportunity Amount not updating when products added

STEPS TO REPRODUCE:
1. Open Opportunity with Amount = $10,000
2. Add Product with Price = $5,000
3. Save
4. Check Opportunity Amount

EXPECTED RESULT:
Amount = $15,000

ACTUAL RESULT:
Amount remains $10,000

ATTACHMENTS:
- Screenshot: opp-amount-bug.png
- Video: reproduction.mp4

ROOT CAUSE:
[Developer to fill]

FIX DETAILS:
[Developer to fill]
```

---

## 📊 QUALITY REQUIREMENTS

1. **Test Coverage:** 100% of user stories
2. **Automation:** 70%+ regression tests automated
3. **Defect Rate:** < 10 defects per 100 stories
4. **Performance:** Meet all benchmarks
5. **Security:** No critical vulnerabilities
6. **Documentation:** All tests documented
7. **Traceability:** Requirements ↔ Test Cases

---

## 🎨 OUTPUT FORMAT

Generate specifications in this order:

1. **Test Strategy** - Overall approach
2. **Test Plan** - Phases and schedule
3. **Test Cases** - Functional test cases
4. **Test Data** - Data requirements
5. **Automation** - Automated test scripts
6. **Performance** - Performance test plan
7. **Security** - Security test cases
8. **Defect Management** - Bug tracking process

For each section:
- Complete documentation
- Examples and templates
- Acceptance criteria
- Success metrics

Generate production-ready QA specifications.
"""

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True, help='Output JSON file path')
    parser.add_argument('--execution-id', required=True, help='Execution ID')
    parser.add_argument('--project-id', required=True)
    args = parser.parse_args()
    
    try:
        with open(args.input) as f:
            reqs = f.read()
        
        client = OpenAI(api_key=os.environ['OPENAI_API_KEY'])
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an expert Salesforce QA Engineer."},
                {"role": "user", "content": f"{QA_PROMPT}\n\nREQUIREMENTS:\n{reqs}"}
            ],
            max_tokens=16000,
            temperature=0.7
        )
        content = response.choices[0].message.content
        
        # Generate JSON output
        output_data = {
            "agent_id": "qa",
            "agent_name": "Elena (QA Engineer)",
            "execution_id": args.execution_id,
            "project_id": args.project_id,
            "deliverable_type": "qa_specification",
            "content": {
                "raw_markdown": content,
                "sections": []
            },
            "metadata": {
                "tokens_used": response.usage.total_tokens,
                "model": "gpt-4o-mini",
                "content_length": len(content),
                "generated_at": datetime.now().isoformat()
            }
        }
        
        # Save as JSON
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        print(f"SUCCESS: {args.output}", file=sys.stderr)
        print(f"Generated QA specification with {response.usage.total_tokens} tokens")
        sys.exit(0)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
