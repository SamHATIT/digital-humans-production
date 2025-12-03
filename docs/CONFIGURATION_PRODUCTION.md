# Configuration Production - Digital Humans

## Architecture Réseau

```
Internet → Nginx (port 80) → Frontend (port 3002)
                          → Backend (port 8002) via /api
```

## Accès

- **URL Production**: http://72.61.161.222 (port 80)
- **Login**: admin@samhatit.com / admin123

## Configuration Clés

### 1. Frontend (`frontend/src/services/api.ts`)
```javascript
const API_URL = import.meta.env.VITE_API_URL || '';
```
- Vide = chemins relatifs (/api/...)
- Nginx route /api vers le backend

### 2. Docker Compose (`docker-compose.yml`)
```yaml
frontend:
  environment:
    VITE_API_URL:  # Vide pour production
```

### 3. Backend CORS (`backend/app/main.py`)
```python
allow_origins=[
    "http://72.61.161.222:3002",
    "http://72.61.161.222:3000", 
    "http://srv1064321.hstgr.cloud:3000",
    "http://localhost:3000",
    "http://localhost:3002",
    "*"
]
```

### 4. Nginx (`/etc/nginx/sites-available/digital-humans-dev.conf`)
```nginx
server {
    listen 80;
    server_name 72.61.161.222 srv1064321.hstgr.cloud;
    
    location / {
        proxy_pass http://localhost:3002;
    }
    
    location /api {
        proxy_pass http://localhost:8002;
    }
}
```

### 5. Auth (`backend/app/utils/auth.py`)
- Utilise `bcrypt` directement (pas passlib)
- Évite les problèmes de compatibilité

## Ports

| Service    | Port | Accès Direct | Via Nginx |
|------------|------|--------------|-----------|
| Frontend   | 3002 | Non          | / (port 80) |
| Backend    | 8002 | Non          | /api (port 80) |
| PostgreSQL | 5432 | Local only   | Non |

## Commandes de Maintenance

```bash
# Redémarrer les services
docker restart digital-humans-backend
docker restart digital-humans-frontend

# Logs
docker logs digital-humans-backend --tail 50
docker logs digital-humans-frontend --tail 50

# Status nginx
systemctl status nginx
```

## NE PAS MODIFIER

1. `VITE_API_URL` - doit rester vide
2. Le fallback dans `api.ts` - doit rester `''`
3. La config nginx - route /api vers 8002

---
*Dernière mise à jour: 3 décembre 2025*
