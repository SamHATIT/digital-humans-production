#!/bin/bash
#
# ROLLBACK SCRIPT - Retour à OpenAI (avant migration Claude)
# Date: 27 novembre 2025
# 
# Usage: ./scripts/rollback_to_openai.sh
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="$PROJECT_DIR/backups/pre_claude_migration_27nov2025"

echo "🔄 ROLLBACK - Retour à la version OpenAI"
echo "========================================"
echo ""

cd "$PROJECT_DIR"

# Vérifier que le backup existe
if [ ! -d "$BACKUP_DIR" ]; then
    echo "❌ Backup directory not found: $BACKUP_DIR"
    echo "   Trying git tag rollback..."
    git checkout backup-pre-claude-migration-27nov2025 -- backend/
    echo "✅ Rolled back using git tag"
    exit 0
fi

echo "📁 Backup found: $BACKUP_DIR"
echo ""

# Rollback via fichiers backup
echo "1️⃣ Restoring agent files from backup..."

# Restore agents
for agent in salesforce_business_analyst salesforce_solution_architect salesforce_developer_apex \
             salesforce_developer_lwc salesforce_admin salesforce_qa_tester salesforce_trainer \
             salesforce_devops salesforce_data_migration; do
    if [ -f "$BACKUP_DIR/${agent}.py" ]; then
        cp "$BACKUP_DIR/${agent}.py" "$PROJECT_DIR/backend/agents/roles/${agent}.py"
        echo "   ✓ Restored ${agent}.py"
    fi
done

echo ""
echo "2️⃣ Restarting backend container..."
docker restart digital-humans-backend

echo ""
echo "3️⃣ Waiting for backend to be ready..."
sleep 5

# Vérifier le statut
if docker ps | grep -q digital-humans-backend; then
    echo "✅ Backend is running"
else
    echo "❌ Backend failed to start!"
    docker logs digital-humans-backend --tail 50
    exit 1
fi

echo ""
echo "========================================"
echo "✅ ROLLBACK COMPLETED"
echo ""
echo "Le système utilise maintenant OpenAI GPT-4."
echo "Pour vérifier: docker logs digital-humans-backend --tail 20"
