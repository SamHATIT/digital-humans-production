# Export des workflows N8N

Export automatique des 18 workflows, réalisé le 06/08/2026.

**Où vit réellement N8N** : service systemd `n8n.service` (pas un conteneur Docker),
base SQLite `/root/.n8n/database.sqlite`, interface sur `n8n.samhatit-consulting.cloud`.
Cette précision a son importance : chercher un conteneur Docker mène à conclure à tort
que N8N n'existe pas.

**Pourquoi cet export** : la base SQLite n'était sauvegardée nulle part hors du serveur.
18 workflows et 1 354 exécutions ne tenaient qu'à un disque.

**Régénérer l'export** :
```
n8n export:workflow --all --separate --output=n8n/export --pretty
```

**Restaurer** :
```
n8n import:workflow --separate --input=n8n/export
```

**Les cinq workflows dormants** — Lead Scoring, Email Outreach, Follow-up Relances,
LinkedIn Posts, Veille Concurrence — portent tous « Mistral Nemo » dans leur nom :
ils appellent le modèle local, désactivé faute de GPU. Il leur manque un repointage
vers un modèle disponible, rien de plus.

## Secrets

L'export du 06/08 contenait une **clé d'API Anthropic en clair** dans le workflow
« Blog - Veille Hebdo » — elle a été expurgée avant publication (GitHub l'avait
d'ailleurs bloquée automatiquement).

**À corriger dans N8N** : ce workflow porte la clé en dur dans un nœud au lieu de
passer par un identifiant N8N. Tant que ce n'est pas fait, chaque export devra être
expurgé à la main.

**Avant tout export public, vérifier** :
```
grep -rlE "sk-ant-|sk-[A-Za-z0-9]{20,}" n8n/export/
```
