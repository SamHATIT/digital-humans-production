#!/bin/bash
# scripts/smoke_test.sh — Suite de fumée à jouer contre un backend Digital
# Humans démarré et joignable (5 assertions, dans cet ordre exact).
#
# VAGUE A / lot A8 — réécriture. L'ancien script portait trois assertions
# fausses, mesurées sans backend puis avec :
#   - "/docs" attendait 200 : en production (DEBUG=False), main.py referme
#     docs_url/redoc_url/openapi_url (app/main.py:89-91) — la bonne attente
#     est 404.
#   - "Projects" et "Dashboard" interrogeaient des routes pm-orchestrator
#     SANS jeton en attendant 200, alors qu'elles exigent get_current_user
#     (401 attendu sans jeton, 200 seulement avec).
#   - "Frontend" (port 3000) n'a rien à faire dans un smoke test du backend.
#
# Assertions (exactement 5, dans cet ordre) :
#   1. GET  /health                    -> 200
#   2. GET  /docs                      -> 404 (DEBUG=False doit fermer /docs)
#   3. GET  $PROJECTS_PATH sans jeton  -> 401
#   4. POST /api/auth/login            -> 200 + access_token non vide
#   5. GET  $PROJECTS_PATH avec jeton  -> 200
#
# Note sur $PROJECTS_PATH : la mission A8 nomme "/api/projects". Vérifié par
# grep (backend/app/main.py, backend/app/api/routes/projects.py) : ce chemin
# n'existe pas comme route de LISTE dans ce dépôt — projects.py ne route que
# GET /api/projects/{project_id} (un projet précis, déjà protégé, mais qui
# exigerait de créer un projet au préalable pour tester le 200). La route de
# liste des projets, protégée par get_current_user, est
# /api/pm-orchestrator/projects (app/api/routes/orchestrator/project_routes.py
# ligne 54). C'est elle qui est testée ici : une liste vide reste un 200
# valide, et elle porte exactement le défaut que l'ancien script laissait
# passer (accessible sans jeton dans l'ancienne version).

set -u

BASE_URL="${BASE_URL:-http://localhost:8002}"
PROJECTS_PATH="/api/pm-orchestrator/projects"

# SMOKE_USER / SMOKE_PASS : obligatoires, jamais de valeur par défaut, jamais
# en dur dans ce fichier. Refus explicite et immédiat si absents.
if [ -z "${SMOKE_USER:-}" ] || [ -z "${SMOKE_PASS:-}" ]; then
    echo "ERREUR: SMOKE_USER et SMOKE_PASS doivent être exportés (identifiants" >&2
    echo "        d'un compte de test existant sur le backend visé). Reçu :" >&2
    echo "        SMOKE_USER=${SMOKE_USER:-<absent>} SMOKE_PASS=<absent ou vide, jamais affiché>." >&2
    echo "        Exemple : SMOKE_USER=test@example.com SMOKE_PASS='...' bash $0" >&2
    exit 1
fi

PASS=0
FAIL=0

pass() {
    echo "✅ PASS: $1"
    PASS=$((PASS + 1))
}

fail() {
    echo "❌ FAIL: $1"
    FAIL=$((FAIL + 1))
}

# Extrait access_token d'un fichier JSON sans dépendre de jq : python3 s'il
# est présent, sinon repli par sed sur le motif "access_token":"...".
extract_access_token() {
    body_file="$1"
    if command -v python3 >/dev/null 2>&1; then
        python3 -c '
import json, sys
try:
    with open(sys.argv[1]) as f:
        data = json.load(f)
    sys.stdout.write(str(data.get("access_token") or ""))
except Exception:
    pass
' "$body_file" 2>/dev/null
    else
        sed -n 's/.*"access_token"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$body_file" | head -1
    fi
}

echo "=== Smoke Test Digital Humans (BASE_URL=$BASE_URL) ==="

# 1. /health -> 200
code=$(curl -s -o /dev/null -w '%{http_code}' "$BASE_URL/health")
if [ "$code" = "200" ]; then
    pass "Health ($code)"
else
    fail "Health (obtenu $code, attendu 200)"
fi

# 2. /docs -> 404 (fermé quand DEBUG=False)
code=$(curl -s -o /dev/null -w '%{http_code}' "$BASE_URL/docs")
if [ "$code" = "404" ]; then
    pass "Docs fermés en production ($code)"
else
    fail "Docs (obtenu $code, attendu 404 — DEBUG=False doit fermer /docs)"
fi

# 3. Projects sans jeton -> 401
code=$(curl -s -o /dev/null -w '%{http_code}' "$BASE_URL$PROJECTS_PATH")
if [ "$code" = "401" ]; then
    pass "Projects sans jeton rejeté ($code)"
else
    fail "Projects sans jeton (obtenu $code, attendu 401)"
fi

# 4. Login -> 200 + access_token non vide (jamais imprimé)
LOGIN_BODY_FILE=$(mktemp)
login_code=$(curl -s -o "$LOGIN_BODY_FILE" -w '%{http_code}' -X POST \
    "$BASE_URL/api/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$SMOKE_USER\",\"password\":\"$SMOKE_PASS\"}")

TOKEN=""
if [ "$login_code" = "200" ]; then
    TOKEN=$(extract_access_token "$LOGIN_BODY_FILE")
fi
rm -f "$LOGIN_BODY_FILE"

if [ "$login_code" = "200" ] && [ -n "$TOKEN" ]; then
    pass "Login ($login_code, jeton reçu)"
else
    if [ -n "$TOKEN" ]; then jeton_etat="présent"; else jeton_etat="absent"; fi
    fail "Login (obtenu $login_code, attendu 200 ; jeton $jeton_etat)"
fi

# 5. Projects avec jeton -> 200 (seulement si un jeton a été obtenu)
if [ -n "$TOKEN" ]; then
    code=$(curl -s -o /dev/null -w '%{http_code}' \
        -H "Authorization: Bearer $TOKEN" \
        "$BASE_URL$PROJECTS_PATH")
else
    code="000"
fi
if [ "$code" = "200" ]; then
    pass "Projects avec jeton ($code)"
else
    fail "Projects avec jeton (obtenu $code, attendu 200)"
fi

echo ""
echo "=== Résultat: $PASS passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
