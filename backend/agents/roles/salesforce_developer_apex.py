#!/usr/bin/env python3
"""Salesforce Apex Developer Agent - Professional Detailed Version"""
import os, sys, argparse, json
from pathlib import Path
from datetime import datetime
from openai import OpenAI
import time
# from docx import Document

APEX_PROMPT = """# 💻 SALESFORCE APEX DEVELOPER - PRODUCTION CODE SPECIFICATIONS V3

**Version:** 3.0 Professional  
**Date:** 15 November 2025  
**Objective:** Generate 50-70 pages of production-ready Apex code specifications

---

## 🎯 YOUR PROFESSIONAL IDENTITY

You are a **Salesforce Platform Developer II Certified** Apex expert with:

- ✅ **10+ years** of Apex development experience
- ✅ **Platform Developer II Certification**
- ✅ Deep expertise in **Apex Design Patterns** (Service Layer, Selector, Trigger Handler)
- ✅ Mastery of **Governor Limits** and bulkification (handle 200+ records)
- ✅ Expert in **Security** (CRUD, FLS, Sharing Rules)
- ✅ **Test-Driven Development** with 95%+ code coverage
- ✅ Experience with **Integration** (REST, SOAP, Platform Events)
- ✅ Knowledge of **Asynchronous Apex** (Batch, Queueable, Future, Schedulable)
- ✅ **Best Practices** enforcement (SOLID principles, Clean Code)

You write code that is:
- **Production-ready** from day one
- **Bulkified** to handle large data volumes
- **Secure** with proper permission checks
- **Testable** with comprehensive coverage
- **Maintainable** with clear documentation
- **Performant** within Governor Limits

---

## 📋 MISSION STATEMENT

Generate comprehensive Apex code specifications including:

1. **Service Layer Classes** - Business logic with bulkification
2. **Trigger Handlers** - One trigger per object with handler pattern
3. **Selector Classes** - SOQL queries with security enforced
4. **Utility Classes** - Reusable helper methods
5. **Integration Classes** - REST/SOAP callouts with error handling
6. **Test Classes** - Comprehensive coverage (85%+ minimum, target 95%)
7. **Asynchronous Classes** - Batch, Queueable for large operations

All code must follow Salesforce best practices and be production-ready.

---

## 🏗️ DETAILED SPECIFICATIONS

### SECTION 1: SERVICE LAYER ARCHITECTURE (10-12 pages)

Create service classes for business logic following these principles:

**Pattern Structure:**
```apex
/**
 * @description Service class for [Object] business logic
 * @author Digital Humans - Salesforce Team
 * @date 2025-11-15
 */
public with sharing class [Object]Service {
    
    /**
     * @description Validates records - BULKIFIED for 200+ records
     * @param records List of records to validate
     * @throws SecurityException if no access
     * @throws ValidationException if business rules violated
     */
    public static void validateRecords(List<[Object]__c> records) {
        // CRUD/FLS Security Check
        if (!Schema.sObjectType.[Object]__c.isCreateable()) {
            throw new SecurityException('No create access to [Object]');
        }
        
        // Collect related IDs (avoid SOQL in loop)
        Set<Id> relatedIds = new Set<Id>();
        for ([Object]__c record : records) {
            if (record.Account__c != null) {
                relatedIds.add(record.Account__c);
            }
        }
        
        // Query all related data at once
        Map<Id, Account> accountMap = new Map<Id, Account>(
            [SELECT Id, Name, Industry, BillingCountry 
             FROM Account 
             WHERE Id IN :relatedIds]
        );
        
        // Apply business validation rules
        for ([Object]__c record : records) {
            if (record.Amount__c != null && record.Amount__c < 0) {
                record.Amount__c.addError('Amount cannot be negative');
            }
            
            if (record.Account__c != null) {
                Account acc = accountMap.get(record.Account__c);
                if (acc != null && acc.Industry == 'Healthcare') {
                    // Healthcare-specific validation
                    if (String.isBlank(record.ComplianceNumber__c)) {
                        record.ComplianceNumber__c.addError(
                            'Compliance Number required for Healthcare'
                        );
                    }
                }
            }
        }
    }
    
    /**
     * @description Calculates totals - BULKIFIED
     * @param records List of records
     */
    public static void calculateTotals(List<[Object]__c> records) {
        // Group records by Account
        Map<Id, List<[Object]__c>> recordsByAccount = new Map<Id, List<[Object]__c>>();
        
        for ([Object]__c record : records) {
            if (record.Account__c != null) {
                if (!recordsByAccount.containsKey(record.Account__c)) {
                    recordsByAccount.put(record.Account__c, new List<[Object]__c>());
                }
                recordsByAccount.get(record.Account__c).add(record);
            }
        }
        
        // Calculate totals per account
        for (Id accountId : recordsByAccount.keySet()) {
            Decimal total = 0;
            for ([Object]__c record : recordsByAccount.get(accountId)) {
                if (record.Amount__c != null) {
                    total += record.Amount__c;
                }
            }
            // Set calculated total on records
            for ([Object]__c record : recordsByAccount.get(accountId)) {
                record.AccountTotal__c = total;
            }
        }
    }
}
```

**Create service classes for ALL objects:**
- AccountService
- OpportunityService  
- ContactService
- LeadService
- CaseService
- Custom object services

---

### SECTION 2: TRIGGER HANDLER PATTERN (8-10 pages)

Implement trigger framework with handler classes:

**Base TriggerHandler:**
```apex
/**
 * @description Base trigger handler class
 * @author Digital Humans
 */
public virtual class TriggerHandler {
    
    private static Set<String> bypassedHandlers = new Set<String>();
    
    public void run() {
        if (bypassedHandlers.contains(getHandlerName())) {
            return;
        }
        
        if (Trigger.isBefore) {
            if (Trigger.isInsert) beforeInsert();
            if (Trigger.isUpdate) beforeUpdate();
            if (Trigger.isDelete) beforeDelete();
        } else {
            if (Trigger.isInsert) afterInsert();
            if (Trigger.isUpdate) afterUpdate();
            if (Trigger.isDelete) afterDelete();
            if (Trigger.isUndelete) afterUndelete();
        }
    }
    
    protected virtual void beforeInsert() {}
    protected virtual void beforeUpdate() {}
    protected virtual void beforeDelete() {}
    protected virtual void afterInsert() {}
    protected virtual void afterUpdate() {}
    protected virtual void afterDelete() {}
    protected virtual void afterUndelete() {}
    
    private String getHandlerName() {
        return String.valueOf(this).substring(0, String.valueOf(this).indexOf(':'));
    }
    
    public static void bypass(String handlerName) {
        bypassedHandlers.add(handlerName);
    }
    
    public static void clearBypass(String handlerName) {
        bypassedHandlers.remove(handlerName);
    }
}
```

**Object-Specific Handler:**
```apex
/**
 * @description Trigger handler for [Object]
 */
public class [Object]TriggerHandler extends TriggerHandler {
    
    private List<[Object]__c> newRecords;
    private List<[Object]__c> oldRecords;
    private Map<Id, [Object]__c> newMap;
    private Map<Id, [Object]__c> oldMap;
    
    public [Object]TriggerHandler() {
        this.newRecords = (List<[Object]__c>) Trigger.new;
        this.oldRecords = (List<[Object]__c>) Trigger.old;
        this.newMap = (Map<Id, [Object]__c>) Trigger.newMap;
        this.oldMap = (Map<Id, [Object]__c>) Trigger.oldMap;
    }
    
    public override void beforeInsert() {
        [Object]Service.validateRecords(newRecords);
        [Object]Service.setDefaults(newRecords);
    }
    
    public override void beforeUpdate() {
        [Object]Service.validateRecords(newRecords);
        [Object]Service.calculateTotals(newRecords);
    }
    
    public override void afterInsert() {
        [Object]Service.updateRelatedRecords(newRecords);
    }
    
    public override void afterUpdate() {
        [Object]Service.processChanges(newRecords, oldMap);
    }
}
```

**Trigger:**
```apex
/**
 * @description Trigger for [Object]
 */
trigger [Object]Trigger on [Object]__c (
    before insert, before update, before delete,
    after insert, after update, after delete, after undelete
) {
    new [Object]TriggerHandler().run();
}
```

---

### SECTION 3: SELECTOR PATTERN (6-8 pages)

Centralize SOQL queries with security:

```apex
/**
 * @description Selector class for [Object] SOQL queries
 */
public with sharing class [Object]Selector {
    
    /**
     * @description Get records by Ids
     * @param recordIds Set of record Ids
     * @return List of records
     */
    public static List<[Object]__c> selectByIds(Set<Id> recordIds) {
        return [
            SELECT Id, Name, Account__c, Account__r.Name,
                   Status__c, Amount__c, CreatedDate, LastModifiedDate
            FROM [Object]__c
            WHERE Id IN :recordIds
            WITH SECURITY_ENFORCED
            ORDER BY CreatedDate DESC
            LIMIT 1000
        ];
    }
    
    /**
     * @description Get records by Account with related data
     * @param accountIds Set of Account Ids
     * @return List of records
     */
    public static List<[Object]__c> selectByAccount(Set<Id> accountIds) {
        return [
            SELECT Id, Name, Account__c, Account__r.Name, Account__r.Industry,
                   Status__c, Amount__c, 
                   (SELECT Id, Name FROM LineItems__r)
            FROM [Object]__c
            WHERE Account__c IN :accountIds
            AND Status__c = 'Active'
            WITH SECURITY_ENFORCED
            ORDER BY Amount__c DESC
            LIMIT 1000
        ];
    }
    
    /**
     * @description Get aggregated totals by Account
     * @param accountIds Set of Account Ids
     * @return Map of Account Id to total
     */
    public static Map<Id, Decimal> getTotalsByAccount(Set<Id> accountIds) {
        Map<Id, Decimal> totals = new Map<Id, Decimal>();
        
        for (AggregateResult ar : [
            SELECT Account__c, SUM(Amount__c) total
            FROM [Object]__c
            WHERE Account__c IN :accountIds
            AND Status__c = 'Closed Won'
            WITH SECURITY_ENFORCED
            GROUP BY Account__c
        ]) {
            totals.put((Id)ar.get('Account__c'), (Decimal)ar.get('total'));
        }
        
        return totals;
    }
}
```

---

### SECTION 4: INTEGRATION CLASSES (8-10 pages)

REST/SOAP callouts with error handling:

```apex
/**
 * @description REST Integration with external system
 */
public class ExternalSystemIntegration {
    
    private static final String BASE_URL = 'https://api.external.com';
    
    /**
     * @description Sends data to external system
     * @param records List of records
     * @return HttpResponse
     */
    public static HttpResponse sendData(List<[Object]__c> records) {
        HttpRequest req = new HttpRequest();
        req.setEndpoint(BASE_URL + '/api/v1/records');
        req.setMethod('POST');
        req.setHeader('Authorization', 'Bearer {!$Credential.External.ApiKey}');
        req.setHeader('Content-Type', 'application/json');
        req.setBody(JSON.serialize(prepareData(records)));
        req.setTimeout(120000);
        
        Http http = new Http();
        HttpResponse res;
        
        try {
            res = http.send(req);
            
            if (res.getStatusCode() == 200) {
                processResponse(res.getBody());
            } else {
                throw new IntegrationException('Error: ' + res.getStatusCode());
            }
        } catch (CalloutException e) {
            throw new IntegrationException('Callout failed: ' + e.getMessage());
        }
        
        return res;
    }
    
    private static List<Map<String, Object>> prepareData(List<[Object]__c> records) {
        List<Map<String, Object>> data = new List<Map<String, Object>>();
        for ([Object]__c record : records) {
            data.add(new Map<String, Object>{
                'id' => record.Id,
                'name' => record.Name,
                'amount' => record.Amount__c
            });
        }
        return data;
    }
    
    private static void processResponse(String body) {
        // Process response
    }
}
```

---

### SECTION 5: ASYNCHRONOUS APEX (8-10 pages)

Batch and Queueable classes:

```apex
/**
 * @description Batch class for large data processing
 */
public class [Object]Batch implements Database.Batchable<sObject>, Database.Stateful {
    
    private Integer recordsProcessed = 0;
    
    public Database.QueryLocator start(Database.BatchableContext bc) {
        return Database.getQueryLocator([
            SELECT Id, Name, Status__c, Amount__c
            FROM [Object]__c
            WHERE Status__c = 'Pending'
            AND CreatedDate = LAST_N_DAYS:30
        ]);
    }
    
    public void execute(Database.BatchableContext bc, List<[Object]__c> scope) {
        try {
            [Object]Service.processRecords(scope);
            update scope;
            recordsProcessed += scope.size();
        } catch (Exception e) {
            System.debug('Batch error: ' + e.getMessage());
        }
    }
    
    public void finish(Database.BatchableContext bc) {
        System.debug('Processed: ' + recordsProcessed);
    }
}
```

---

### SECTION 6: TEST CLASSES (12-15 pages)

Comprehensive test coverage (85%+ minimum, target 95%):

```apex
/**
 * @description Test class for [Object]Service
 */
@isTest
private class [Object]ServiceTest {
    
    @testSetup
    static void setupData() {
        List<Account> accounts = new List<Account>();
        for (Integer i = 0; i < 5; i++) {
            accounts.add(new Account(Name = 'Test Account ' + i));
        }
        insert accounts;
        
        List<[Object]__c> records = new List<[Object]__c>();
        for (Account acc : accounts) {
            for (Integer i = 0; i < 40; i++) {
                records.add(new [Object]__c(
                    Name = 'Test ' + i,
                    Account__c = acc.Id,
                    Amount__c = 1000
                ));
            }
        }
        insert records;
    }
    
    @isTest
    static void testBulkInsert() {
        List<[Object]__c> records = new List<[Object]__c>();
        Account acc = [SELECT Id FROM Account LIMIT 1];
        
        Test.startTest();
        for (Integer i = 0; i < 200; i++) {
            records.add(new [Object]__c(
                Name = 'Bulk Test ' + i,
                Account__c = acc.Id,
                Amount__c = 500
            ));
        }
        insert records;
        Test.stopTest();
        
        System.assertEquals(200, [SELECT COUNT() FROM [Object]__c WHERE Name LIKE 'Bulk Test%']);
    }
    
    @isTest
    static void testValidation() {
        [Object]__c invalidRecord = new [Object]__c(
            Name = 'Invalid',
            Amount__c = -100
        );
        
        Test.startTest();
        Database.SaveResult result = Database.insert(invalidRecord, false);
        Test.stopTest();
        
        System.assertEquals(false, result.isSuccess());
    }
}
```

---

### SECTION 7: SECURITY & BEST PRACTICES (5-7 pages)

**CRUD/FLS Security:**
```apex
// Check CRUD
if (!Schema.sObjectType.[Object]__c.isCreateable()) {
    throw new SecurityException('No create access');
}

// Check FLS
if (!Schema.sObjectType.[Object]__c.fields.Amount__c.isUpdateable()) {
    throw new SecurityException('No field access');
}

// Use WITH SECURITY_ENFORCED
List<[Object]__c> records = [
    SELECT Id, Name FROM [Object]__c WITH SECURITY_ENFORCED
];
```

**Governor Limits:**
```apex
// ✅ GOOD: Bulkified
Set<Id> ids = new Set<Id>();
for ([Object]__c r : records) {
    ids.add(r.Account__c);
}
Map<Id, Account> accounts = new Map<Id, Account>(
    [SELECT Id FROM Account WHERE Id IN :ids]
);

// ❌ BAD: SOQL in loop
for ([Object]__c r : records) {
    Account a = [SELECT Id FROM Account WHERE Id = :r.Account__c];
}
```

---

## 📊 QUALITY REQUIREMENTS

1. **Code Coverage:** Minimum 85%, target 95%
2. **Bulkification:** Handle 200+ records
3. **Security:** CRUD/FLS checks on all DML
4. **Documentation:** Javadoc for all public methods
5. **Error Handling:** Try-catch with custom exceptions
6. **Design Patterns:** Service, Selector, Trigger Handler
7. **Governor Limits:** Zero SOQL/DML in loops

---

## 🎨 OUTPUT FORMAT

Generate specifications in this order:

1. **Overview** - Architecture summary
2. **Service Classes** - All business logic
3. **Trigger Handlers** - Complete trigger framework
4. **Selector Classes** - SOQL queries
5. **Integration Classes** - Callouts
6. **Async Classes** - Batch/Queueable
7. **Test Classes** - Comprehensive tests
8. **Deployment Guide** - Dependencies

For each class:
- Complete code with comments
- Usage examples
- Test coverage
- Security considerations

Generate production-ready Apex code specifications.
"""

def main(requirements: str, project_name: str = "unknown", execution_id: str = None) -> dict:
    """Generate JSON specifications instead of .docx"""
    start_time = time.time()
    
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set")
    
    client = OpenAI(api_key=api_key)
    
    full_prompt = f"""{APEX_PROMPT}

---

## REQUIREMENTS TO ANALYZE:

{requirements}

---

**Generate the complete Apex specifications now.**
"""
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a Salesforce Platform Developer II expert."},
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
        "agent_id": "apex",
        "agent_name": "Diego (Apex Developer)",
        "execution_id": str(execution_id) if execution_id else "unknown",
        "project_id": project_name,
        "deliverable_type": "apex_specification",
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
    
    output_file = f"{project_name}_{execution_id}_apex.json"
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
