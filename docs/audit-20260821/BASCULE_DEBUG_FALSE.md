# Bascule `DEBUG=False` — séquence préparée, **non exécutée**

**VAGUE 2 / LOT 4 — audit croisé du 21/08/2026.**
Rédigé le 23/08. **Ce document ne s'exécute pas tout seul et n'a pas été
exécuté.** La bascule est une décision de Sam ; ce qui suit est la marche à
suivre, dans l'ordre, avec ce qui casse si on la prend à l'envers.

---

## 1. Ce qui est cassé aujourd'hui, et pourquoi ça ne se voit pas

`backend/app/config.py` :

```python
@model_validator(mode="after")
def validate_encryption_key(self):
    if self.CREDENTIALS_ENCRYPTION_KEY or self.DEBUG:
        return self
    raise ValueError("CREDENTIALS_ENCRYPTION_KEY is required in production mode …")
```

Le garde-fou de LOT-E n'exige la clé **que si `DEBUG=False`**.

Sur le VPS : `DEBUG=True` (défaut de `config.py:31`, et valeur livrée par
`.env.example`), `CREDENTIALS_ENCRYPTION_KEY` absente. **Le garde-fou ne
s'oppose donc à rien.** `app/utils/encryption.py` retombe sur une clé dérivée
de `SECRET_KEY` — comportement documenté, prévu, et censé être réservé au
développement.

Deux conséquences concrètes :

- **Le secret qui signe les JWT chiffre aussi les credentials.** Une rotation
  de `SECRET_KEY` — geste banal, prévu par la documentation en cas de fuite de
  jeton — rend d'un seul coup **illisibles tous les credentials Salesforce et
  Git de tous les projets**. Pas une corruption : un `InvalidToken` à chaque
  lecture, donc un arrêt net de tout déploiement.
- **Le rapport disait le contraire.** LOT-E annonçait le garde-fou posé. Il
  l'est, dans le code. Il est inerte, sur la machine.

Depuis la vague 2, le backend **le dit à chaque démarrage** : un log `CRITICAL`
émis par `app/schema_bootstrap.py:encryption_posture`. Il ne bascule rien —
dire n'est pas réparer — mais l'écart cesse d'être invisible.

> **Ne pas exécuter cette séquence sans avoir décidé de la mener jusqu'au
> bout.** Posée à moitié, elle laisse la base dans un état pire qu'avant :
> credentials rechiffrés avec une clé que `.env` ne porte pas encore.

---

## 2. Pourquoi `DEBUG=False` ne peut pas être basculé seul

En l'état, `DEBUG=False` fait **échouer le démarrage** :

```
ValueError: CREDENTIALS_ENCRYPTION_KEY is required in production mode (DEBUG=False).
```

C'est le comportement voulu. Mais il signifie que la bascule est la **dernière**
étape, pas la première.

Et l'inverse est pire : poser `CREDENTIALS_ENCRYPTION_KEY` **avant** d'avoir
rechiffré rend toutes les credentials existantes illisibles, puisqu'elles sont
chiffrées avec la clé dérivée de `SECRET_KEY` et qu'on vient de dire au
processus d'en utiliser une autre.

**L'ordre est impératif : rotation → clé dans `.env` → redémarrage →
`DEBUG=False`.**

---

## 3. La séquence

### Étape 0 — Sauvegarde de la table des credentials

Non négociable : les étapes 2 et 3 réécrivent `project_credentials`.

```bash
sudo -u postgres pg_dump -d digital_humans_db -t project_credentials \
  > /root/backups/project_credentials-$(date +%Y%m%d-%H%M).sql
```

Vérifier que le fichier n'est pas vide avant de continuer.

### Étape 1 — Générer la clé

```bash
cd /root/workspace/digital-humans-production/backend
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

La garder de côté. **Ne pas encore la poser dans `.env`.**

### Étape 2 — Migrer les jetons encore en clair

Idempotent, à faire avant la rotation : un jeton en clair n'est pas
déchiffrable par l'ancienne clé, la rotation le sauterait.

```bash
python scripts/rotate_encryption_key.py --encrypt-plaintext          # à blanc
python scripts/rotate_encryption_key.py --encrypt-plaintext --apply
```

### Étape 3 — Rotation : clé dérivée → clé dédiée

```bash
python scripts/rotate_encryption_key.py \
  --old-secret-key-derived --new-key <clé de l'étape 1>            # à blanc
python scripts/rotate_encryption_key.py \
  --old-secret-key-derived --new-key <clé de l'étape 1> --apply
```

Le script vérifie que **chaque ligne** repasse par la nouvelle clé avant de
valider la transaction, et annule tout sinon.

### Étape 4 — Poser la clé, puis redémarrer

```bash
# backend/.env
CREDENTIALS_ENCRYPTION_KEY=<clé de l'étape 1>
```

```bash
systemctl restart digital-humans-backend
sleep 5
curl -s http://127.0.0.1:8002/health | python3 -m json.tool
```

Attendu : `200`, et les trois sondes `up` (`database`, `redis`, `chroma` —
voir LOT 3). Dans les journaux, le `CRITICAL` du §1 doit avoir **disparu**,
remplacé par « cle dediee (CREDENTIALS_ENCRYPTION_KEY) en place ».

### Étape 5 — Vérifier une lecture réelle avant de basculer

Le `/health` ne lit aucune credential. Il faut une vraie lecture :

```bash
python scripts/rotate_encryption_key.py --verify-only
```

Chaque ligne doit se déchiffrer. **Une seule ligne en échec ⇒ ne pas
basculer** : revenir en arrière consiste à retirer
`CREDENTIALS_ENCRYPTION_KEY` de `.env` et à redémarrer, ce qui redonne la clé
dérivée — ce repli n'existe plus une fois `DEBUG=False` posé.

### Étape 6 — Alors seulement, `DEBUG=False`

```bash
# backend/.env
DEBUG=False
```

```bash
systemctl restart digital-humans-backend
sleep 5
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8002/health   # 200
```

Si le service refuse de démarrer, le message le dit : la clé n'est pas lue.
Repli : remettre `DEBUG=True`, redémarrer, reprendre à l'étape 4.

---

## 4. Ce que la bascule change **en plus** du chiffrement

`DEBUG=False` n'est pas un interrupteur à une seule fonction. À vérifier avant :

| Ce qui change | Où | Effet |
|---|---|---|
| `SECRET_KEY` devient obligatoire | `config.py:143` | démarrage refusé si absente — la poser d'abord |
| `CREDENTIALS_ENCRYPTION_KEY` devient obligatoire | `config.py:172` | l'objet de ce document |
| `FastAPI(debug=…)` | `main.py` | les traces d'erreur ne partent plus au client — c'est voulu |
| `uvicorn --reload` | `main.py` bloc `__main__` | sans effet : le service est lancé par systemd |

**`create_all` n'est plus dans cette liste.** Il en faisait partie avant la
vague 2 : la création du schéma était conditionnée à `DEBUG`, si bien que la
production — en `DEBUG=True` — exécutait `create_all` à chaque démarrage,
malgré le critère de fin de LOT-G. Elle dépend désormais de
`AUTO_CREATE_SCHEMA`, non posée, donc désactivée quel que soit `DEBUG`. La
bascule n'y change plus rien, et c'est le but : les deux décisions étaient
liées par accident.

---

## 5. Après la bascule

`EXECUTION.md` §6.4 reste à faire, indépendamment : sur une base créée par
l'ancien `create_all`, `alembic_version` est vide et le premier
`alembic upgrade head` échouera. Il faut un `alembic stamp <rev>` d'abord.
C'est exactement l'incident annoncé par PROD-05, et la vague 2 ne l'a pas
traité — elle a seulement cessé d'en créer de nouvelles occurrences.
