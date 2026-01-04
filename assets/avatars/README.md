# Avatars Digital Humans

## Sources officielles des avatars

| Agent | Fichier | Source originale | Date |
|-------|---------|------------------|------|
| Emma | emma-research.jpeg | "Emma - 4_48PM.jpeg" (ChatGPT génération) | 2025-01-04 |

## Utilisation

Les avatars sont déployés sur le site en format PNG :
- **Website** : `/var/www/digital-humans.fr/avatars/`
- **Nommage** : `{prenom}-{role}.png`

### Pour mettre à jour un avatar :

```bash
# 1. Copier le source dans ce dossier
cp /path/to/new-avatar.jpeg /root/workspace/digital-humans-production/assets/avatars/{agent}.jpeg

# 2. Convertir et déployer
convert /root/workspace/digital-humans-production/assets/avatars/{agent}.jpeg /var/www/digital-humans.fr/avatars/{agent}-{role}.png
```

## Historique

- **2025-01-04** : Correction avatar Emma (était une copie d'Olivia)
