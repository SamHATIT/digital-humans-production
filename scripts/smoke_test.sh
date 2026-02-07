#!/bin/bash
# scripts/smoke_test.sh — Exécuter après chaque merge
PASS=0; FAIL=0

test_endpoint() {
    local name="$1" url="$2" expected="$3"
    response=$(curl -s -o /dev/null -w "%{http_code}" "$url")
    if [ "$response" = "$expected" ]; then
        echo "✅ PASS: $name ($response)"
        ((PASS++))
    else
        echo "❌ FAIL: $name (got $response, expected $expected)"
        ((FAIL++))
    fi
}

echo "=== Smoke Test Digital Humans ==="
test_endpoint "Health" "http://localhost:8002/health" "200"
test_endpoint "API Docs" "http://localhost:8002/docs" "200"
test_endpoint "Frontend" "http://localhost:3000" "200"
test_endpoint "Projects" "http://localhost:8002/api/pm-orchestrator/projects" "200"
test_endpoint "Dashboard" "http://localhost:8002/api/pm-orchestrator/dashboard/stats" "200"

echo ""
echo "=== Résultat: $PASS passed, $FAIL failed ==="
[ $FAIL -eq 0 ] && exit 0 || exit 1
