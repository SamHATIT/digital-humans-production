# DIGITAL HUMANS - CRITICAL FIXES SESSION

## 📍 CURRENT STATE (Nov 25, 2025)

### ✅ What's Done
- Repository created: https://github.com/SamHATIT/digital-humans-production
- Clean production structure established
- Backend: 9/9 agents operational (validated Execution #22)
- Frontend: Gemini version with avatars
- Git: 155 files, 2 commits, pushed to main branch
- Location: /root/workspace/digital-humans-production

### 🔴 What Needs Fixing (Priority Order)

## 🎯 PRIORITY 1: SSE Progress Updates (403 Forbidden) - 30 MIN

**Problem:** Real-time progress monitoring not working
- EventSource cannot send Authorization headers
- Backend SSE endpoint requires auth
- Result: 403 Forbidden on /execute/{execution_id}/progress

**Fix Strategy:**
```
File: backend/app/api/routes/pm_orchestrator.py
Line: ~150-180 (SSE endpoint)

BEFORE:
@router.get("/execute/{execution_id}/progress")
async def stream_progress(
    execution_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
)

AFTER:
@router.get("/execute/{execution_id}/progress")
async def stream_progress(
    execution_id: int,
    token: str = Query(..., description="JWT token for auth"),
    db: Session = Depends(get_db)
):
    # Validate token manually
    from app.utils.auth import verify_token
    user = verify_token(token, db)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
```

**Frontend Change:**
```typescript
File: frontend/src/hooks/useExecutionProgress.ts
Line: ~20-30

BEFORE:
const eventSource = new EventSource(`${API_BASE_URL}/pm-orchestrator/execute/${executionId}/progress`);

AFTER:
const token = localStorage.getItem('token');
const eventSource = new EventSource(
  `${API_BASE_URL}/pm-orchestrator/execute/${executionId}/progress?token=${token}`
);
```

**Testing:**
1. Start an execution
2. Check browser DevTools Network tab
3. Verify SSE connection opens (200 status)
4. Confirm real-time updates appear in UI

---

## 🎯 PRIORITY 2: Status Display Issues - 15 MIN

**Problem:** Shows "Completed" when status is "FAILED"

**Fix Strategy:**
```
File: frontend/src/pages/ExecutionMonitoringPage.tsx or ExecutionPage.tsx
Search for: status rendering logic

BEFORE:
const statusText = execution.status === 'completed' ? 'Completed' : 'Running';

AFTER:
const statusMap = {
  'pending': 'Pending',
  'running': 'Running',
  'completed': 'Completed',
  'failed': 'Failed'
};
const statusText = statusMap[execution.status] || execution.status;

// Add color coding
const statusColor = {
  'pending': 'text-yellow-600',
  'running': 'text-blue-600',
  'completed': 'text-green-600',
  'failed': 'text-red-600'
};
```

**Testing:**
1. Create execution that fails (wrong agent ID)
2. Verify status shows "Failed" not "Completed"
3. Check color coding matches status

---

## 🎯 PRIORITY 3: Download Button Visibility - 10 MIN

**Problem:** Download button shows even when no SDS document exists

**Fix Strategy:**
```
File: frontend/src/pages/ExecutionMonitoringPage.tsx
Search for: download button rendering

BEFORE:
<button onClick={handleDownload}>Download SDS</button>

AFTER:
{execution.sds_document_path && (
  <button onClick={handleDownload}>
    Download SDS
  </button>
)}

// OR check if file actually exists
{execution.status === 'completed' && execution.sds_document_path && (
  <a 
    href={`${API_BASE_URL}/pm-orchestrator/download/${execution.id}`}
    download
    className="..."
  >
    Download SDS
  </a>
)}
```

**Testing:**
1. View execution with no SDS (failed or running)
2. Verify no download button
3. View completed execution with SDS
4. Verify download button appears and works

---

## 🎯 PRIORITY 4: Gemini Auth Corrections - 1 HOUR

**Problem:** Token injection not always working, intermittent auth failures

**Reference:** Gemini corrections already exist in /root/workspace/digital-humans-gemini/

**Files to Check:**
1. frontend/src/services/api.ts - Axios interceptor
2. frontend/src/pages/LoginPage.tsx - Token storage
3. All API calls - Token retrieval

**Fix Strategy:**
```typescript
File: frontend/src/services/api.ts

Ensure proper interceptor:
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Add response interceptor for 401
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);
```

**Testing:**
1. Login and verify token stored
2. Make API calls, verify Authorization header
3. Test with expired token
4. Verify automatic redirect to login

---

## 🎯 PRIORITY 5: Token/Cost Tracking - 1-2 HOURS

**Problem:** total_tokens_used = 0 in database

**Fix Strategy:**

**Backend Changes:**
```python
File: backend/app/services/agent_integration.py
Function: execute_agent()

After each OpenAI call, capture usage:
response = openai_client.chat.completions.create(...)

# Capture token usage
tokens_used = response.usage.total_tokens
prompt_tokens = response.usage.prompt_tokens
completion_tokens = response.usage.completion_tokens

# Update execution record
execution.total_tokens_used += tokens_used
execution.estimated_cost += calculate_cost(tokens_used, model)
db.commit()
```

**Add Cost Calculation:**
```python
File: backend/app/utils/cost_calculator.py (create new)

def calculate_cost(tokens: int, model: str = "gpt-4") -> float:
    """Calculate cost based on OpenAI pricing"""
    pricing = {
        "gpt-4": {
            "prompt": 0.03 / 1000,      # $0.03 per 1K prompt tokens
            "completion": 0.06 / 1000    # $0.06 per 1K completion tokens
        }
    }
    # Simplified: use average
    return tokens * 0.045 / 1000
```

**Database:**
```python
Verify columns exist in execution table:
- total_tokens_used (Integer)
- estimated_cost (Float)
- tokens_by_agent (JSON) - optional for detailed tracking
```

**Testing:**
1. Run execution
2. Check database: SELECT total_tokens_used, estimated_cost FROM executions
3. Verify non-zero values
4. Compare with OpenAI dashboard

---

## 📋 EXECUTION CHECKLIST

### Before Starting:
- [ ] Current directory: /root/workspace/digital-humans-production
- [ ] Git status clean: `git status`
- [ ] Backend running: Check port 8002
- [ ] Frontend running: Check port 3000 (or can start fresh)

### For Each Fix:
- [ ] Create feature branch: `git checkout -b fix/issue-name`
- [ ] Make changes
- [ ] Test locally
- [ ] Commit: `git commit -m "fix: description"`
- [ ] Merge to main: `git checkout main && git merge fix/issue-name`
- [ ] Push: `git push origin main`

### After All Fixes:
- [ ] Run complete end-to-end test
- [ ] Verify all issues resolved
- [ ] Document changes
- [ ] Tag release: `git tag v1.0.1 -m "Critical fixes applied"`

---

## 🧪 COMPREHENSIVE TESTING PLAN

After all fixes, run this complete test:

```bash
# 1. Start services
cd /root/workspace/digital-humans-production
docker-compose down
docker-compose up -d

# 2. Check logs
docker-compose logs -f backend

# 3. Test authentication
curl -X POST http://localhost:8002/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'

# 4. Create test project
# Use frontend UI or API

# 5. Start execution with 2-3 agents
# Monitor SSE progress
# Verify status updates
# Check download button
# Download SDS document

# 6. Verify database
docker-compose exec db psql -U digital_humans -d digital_humans_db
SELECT id, status, total_tokens_used, estimated_cost FROM executions ORDER BY id DESC LIMIT 5;

# 7. Check logs for any errors
docker-compose logs backend | grep -i error
```

---

## 📂 KEY FILES TO MODIFY

**Backend:**
1. `/root/workspace/digital-humans-production/backend/app/api/routes/pm_orchestrator.py`
2. `/root/workspace/digital-humans-production/backend/app/services/agent_integration.py`
3. `/root/workspace/digital-humans-production/backend/app/utils/cost_calculator.py` (new)

**Frontend:**
1. `/root/workspace/digital-humans-production/frontend/src/hooks/useExecutionProgress.ts`
2. `/root/workspace/digital-humans-production/frontend/src/pages/ExecutionMonitoringPage.tsx`
3. `/root/workspace/digital-humans-production/frontend/src/pages/ExecutionPage.tsx`
4. `/root/workspace/digital-humans-production/frontend/src/services/api.ts`

---

## 🎯 SUCCESS CRITERIA

### Must Work:
- ✅ Login and authentication
- ✅ Create new project
- ✅ Start execution with agent selection
- ✅ Real-time SSE progress updates (no 403)
- ✅ Correct status display (Failed shows as Failed)
- ✅ Download button only when SDS exists
- ✅ Download SDS document successfully
- ✅ Token usage tracked in database
- ✅ Estimated cost calculated

### Nice to Have:
- Cost display in UI
- Token breakdown by agent
- Progress percentage accuracy
- Error handling improvements

---

## 💾 BACKUP BEFORE STARTING

```bash
cd /root/workspace
tar -czf digital-humans-backup-$(date +%Y%m%d-%H%M%S).tar.gz digital-humans-production/
echo "Backup created"
```

---

## 🚀 QUICK START COMMAND FOR NEXT SESSION

```bash
cd /root/workspace/digital-humans-production
git status
git log --oneline -n 5
echo "Ready to start fixes!"
```

---

## 📞 CONTEXT FOR CLAUDE

**Project:** Digital Humans - AI Salesforce Implementation System
**Repository:** https://github.com/SamHATIT/digital-humans-production
**Location:** /root/workspace/digital-humans-production (VPS: srv1064321.hstgr.cloud)
**Status:** 95% complete, 5 critical issues to fix
**Goal:** Get to 100% functional before simplification/improvements
**Stack:** FastAPI backend, React/TypeScript frontend, PostgreSQL, Docker
**Agents:** 9 operational (Olivia, Marcus, Diego, Zara, Raj, Elena, Jordan, Aisha, Lucas) + Sophie PM

**Last Test:** Execution #22 (Nov 19)
- Duration: 12 min 8 sec
- Agents: 9/9 successful
- Output: 283 KB, SDS: 47.8 KB
- Quality: Fortune 500-level ✅

**Current Issues:** SSE 403, Status display wrong, Download button always visible, No token tracking, Gemini auth partial

**Approach:** Fix issues one by one, test each, commit, then comprehensive end-to-end test.

---

## 📝 NOTES

- Backend .env already configured (check /root/workspace/front-end-digital-humans/backend/.env)
- Database already populated with test data
- Admin user exists: admin/admin123
- OpenAI API key configured
- Port 8002 (backend), 3000 (frontend), 5432 (postgres)

**Expected Timeline:**
- Priority 1 (SSE): 30 min
- Priority 2 (Status): 15 min  
- Priority 3 (Download): 10 min
- Priority 4 (Auth): 1 hour
- Priority 5 (Tokens): 1-2 hours
- Testing: 30 min
**Total: 3-4 hours to 100% functional**

---

END OF TODO - START NEXT CONVERSATION WITH THIS CONTEXT
