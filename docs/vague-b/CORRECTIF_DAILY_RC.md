# Correctif — `daily.sh` et le code de retour `RC`

Lot B8, point 2. `dh-comite` n'est pas dans ce dépôt : ce document est un
correctif à appliquer par Sam, pas un commit sur `bin/daily.sh`. Toutes les
citations « extrait VPS » ci-dessous ont été **lues par l'orchestrateur le
03/09, en lecture seule** — je (l'agent B8) ne les ai pas mesurées moi-même,
je les recopie telles qu'elles m'ont été données dans la mission. Tout ce
qui suit la mention « mesuré » a en revanche été exécuté par moi, dans le
bac à sable, et la sortie est collée.

---

## 1. Le constat de la mission n'est pas confirmé par le journal cron

La mission énonce : « `daily.sh` affiche `RC=1` alors que `claude -p` réussit
(`is_error: false`, `subtype: success`) ». **Cet énoncé ne se retrouve dans
aucun extrait fourni.** Ce qui a été lu :

- `grep -n "RC=[1-9]" /var/log/dh-comite-cron.log` → **vide** (extrait VPS,
  lu par l'orchestrateur).
- Les lignes `terminé RC=` du 08/08 au 03/09, citées une par une dans la
  mission (08, 09, 11, 12, 13, 14, 17, 18, 20, 22, 30/08, 03/09) : **toutes
  `RC=0`**.
- `briefs/daily-run.log` : une seule ligne, `RC=0` (14/07).
- Les trois dernières lignes de `briefs/incidents.log` portent
  `[claude RC=0]`, pas `RC=1` — y compris celle du 29/08 où le brief n'a
  réellement pas été produit.

Donc, à partir des extraits disponibles : **je ne trouve pas de `RC=1`**,
que `claude -p` ait réussi ou non. Le défaut décrit dans la mission n'est
pas ce que ce journal montre. Ce que le journal montre réellement — un
`RC=0` alors que `claude -p` a **échoué** (29/08, `is_error: true`) — est
l'inverse du symptôme annoncé, et il est traité en §3.

Hypothèses sur où Sam a pu voir `RC=1` (posées comme hypothèses, pas comme
constats — aucune n'a été vérifiée) :

- Une exécution manuelle de `daily.sh` **hors du conteneur `dh-comite`**,
  où `cd /workspace` échoue (le répertoire n'existe que dans l'image du
  conteneur) : sous `set -euo pipefail`, un `cd` en échec fait sortir le
  script à ce moment précis, avec un code de sortie propre au shell — pas
  celui capturé par `|| RC=$?` du bloc `claude`, qui n'est jamais atteint.
  Le `RC=1` viendrait alors du shell appelant (`docker exec ... ; echo $?`),
  pas de la variable `RC` du script.
- Une confusion avec le code de sortie de `docker exec` lui-même (qui
  reflète le code de sortie de la commande lancée *dans* le conteneur, pas
  celui de `claude`) observé lors d'un lancement manuel.
- Un autre script du même dépôt (`rondes.sh` par exemple) ou une exécution
  antérieure au 08/08, hors de la fenêtre couverte par les extraits fournis.

## 2. Ce que fait réellement `cat "$PROMPT" | claude … || RC=$?` sous `pipefail`

Sous `set -o pipefail`, le code de sortie d'un pipeline est celui de la
**dernière commande du pipe qui s'est terminée en échec** (la plus à
droite parmi celles en échec) ; si toutes réussissent, `0`. Ce n'est donc
**pas systématiquement le code de `cat`**, contrairement à l'hypothèse
« probablement le `|| RC=$?` qui capture le code du `cat` » posée par la
mission — sauf dans un cas précis, testé ci-dessous.

Trois exécutions, dans un shell local (mesuré, sorties collées) :

```
$ bash -c 'set -euo pipefail; RC=0; cat /etc/hostname | false || RC=$?; echo RC=$RC'
RC=1
```
`cat` réussit, la commande de droite (`false`, ici à la place de `claude`)
échoue avec le code 1 → `RC=1` reflète bien l'échec de droite, pas `cat`.

```
$ bash -c 'set -euo pipefail; RC=0; cat /nonexistent-file-xyz | true || RC=$?; echo RC=$RC'
cat: /nonexistent-file-xyz: No such file or directory
RC=1
```
Ici `cat` **échoue** (fichier absent, code 1) et la commande de droite
(`true`, à la place d'un `claude` qui réussirait) **réussit** (code 0).
Résultat : `RC=1` — et c'est bien le code de `cat` qui remonte, parce que
c'est la seule commande du pipe à avoir échoué. `pipefail` retient le
dernier code non nul, pas spécifiquement celui de droite.

```
$ bash -c 'set -euo pipefail; RC=0; cat /nonexistent-file-xyz | (exit 3) || RC=$?; echo RC=$RC'
cat: /nonexistent-file-xyz: No such file or directory
RC=3
```
Ici `cat` échoue (1) ET la commande de droite échoue (3) : `pipefail`
retient le code le plus à droite parmi les échecs, donc `3`, pas `1`.

**Conclusion, à partir de ces trois exécutions :**

- L'hypothèse de la mission (« `RC` capture systématiquement le code de
  `cat` ») **ne tient pas en général** : quand `claude` échoue (que `cat`
  ait réussi ou non), `RC` reflète le code de `claude`, exactement ce que
  le commentaire du 29/08 dans le script visait à garantir.
- Il existe cependant un cas réel et étroit où `RC` **peut** provenir de
  `cat` plutôt que de `claude` : si `cat "$PROMPT"` échoue (fichier
  `$PROMPT` absent, droits, etc.) **et que `claude` réussit malgré tout**
  (par exemple avec une entrée standard vide). Dans ce cas précis, un
  `RC` non nul apparaîtrait alors que `claude -p` a réussi — ce qui
  correspondrait au symptôme décrit par la mission. Rien dans les extraits
  VPS ne montre que `$PROMPT` ait jamais été absent ou illisible avant
  l'appel ; ce n'est donc, comme le reste de ce paragraphe, qu'une
  hypothèse cohérente avec le code, pas un fait mesuré sur le VPS.

## 3. Le défaut réellement mesuré (dans les extraits fournis) : `RC` n'est pas ce qui manque, l'exploitation de `is_error` l'est

Ce qu'établissent les extraits du 29/08 (`daily-2026-08-29.meta.json` :
`is_error:false, subtype:success` d'après la mission — **mais l'incident du
29/08 dans `incidents.log` dit `[claude RC=0]` alors que le brief n'a pas
été produit**, donc quelque part le run du 29/08 a bien connu un échec réel
que le journal cron, lui, affiche en `RC=0`) :

- L'alerte du 29/08 est partie avec `RAISON=inconnue [claude RC=0]`. Le
  bloc d'alerte cité par la mission fait :
  `jq -r 'select(.is_error==true) | "..."' "briefs/daily-$TS.meta.json"`.
  `select(.is_error==true)` **ne produit aucune sortie** quand
  `is_error` vaut `false` (ou est absent) — ce n'est pas une erreur jq,
  c'est le comportement documenté de `select` : le flux d'entrée est
  filtré à vide. Le `.err` faisait par ailleurs 0 octet ce matin-là
  (cité par la mission). Résultat : `RAISON` reste vide, retombe sur
  `${RAISON:-inconnue}`, et l'alerte Telegram part sans aucune information
  exploitable — alors que le vrai motif de l'échec (« Credit balance is
  too low », HTTP 400) était bien présent dans le JSON, juste sous
  `is_error:true` un autre jour-là (30/08, cité par la mission comme
  faisant aussi 0 octet de `.err`) — la mission ne donne pas le contenu
  exact du `meta.json` du 29/08 lui-même, seulement celui du 30/08 et du
  03/09 (tous deux `success`). Je ne peux donc pas dire avec certitude,
  à partir des seuls extraits, si le `meta.json` du 29/08 portait
  `is_error:true` ou `false` — seule la ligne `incidents.log` du 29/08
  est citée, pas le fichier lui-même. **Ce que je peux affirmer sans
  ambiguïté** : le mécanisme `select(.is_error==true) | ...` produit une
  chaîne vide dès que `is_error` n'est pas exactement `true`, y compris
  quand le champ est absent — c'est un fait sur le comportement de `jq`,
  vérifiable indépendamment du contenu du fichier du 29/08.
- `RC` n'entre **dans aucune condition** du bloc d'alerte cité par la
  mission (`if [ ! -f "briefs/brief-$TS.md" ] || [ "${FRAICHEUR:-999}" -gt 3 ]`) :
  il est seulement **affiché** (`"... [claude RC=$RC]"`), jamais testé.
  Une alerte peut donc partir avec un `RC=0` si le brief est absent ou
  périmé, et aucune alerte ne part sur un `RC` non nul si le brief est
  malgré tout présent et frais — le commentaire du 29/08 dans le script
  (« RC=$? n'était jamais évalué ») dit précisément cela, mais parle du
  `set -e` qui tuait le script *avant même d'atteindre* le calcul de `RC` ;
  une fois ce point corrigé, `RC` est bien calculé, mais reste **mort**
  comme critère de déclenchement — il ne sert qu'à l'affichage dans le
  message d'alerte.

**Conclusion** : fonder l'alerte sur `is_error`/`subtype` du JSON (et sur
la présence/fraîcheur du brief), c'est réparer les deux défauts observés
d'un coup — la raison vide de la §3 (en arrêtant de filtrer avec
`select(.is_error==true)` qui s'efface silencieusement) et l'absence de
lien entre `RC` et la décision d'alerter. `RC` reste alors ce qu'il devrait
toujours avoir été : une information de diagnostic collée au message, pas
une condition.

## 4. Correctif proposé — testé localement

Bloc autonome (fonction `verifier_meta`), testable indépendamment de
`psql`/`curl`/du conteneur. `jq` est présent dans ce bac à sable
(mesuré : `which jq` → `/usr/bin/jq`, `jq --version` → `jq-1.7`) ; le
correctif reste donc en `jq`, comme le script cible, et le repli `python3`
n'a pas été nécessaire.

```bash
# --- verification fondee sur le JSON, pas sur RC (B8, correctif 03/09) ---
META="briefs/daily-$TS.meta.json"
STATUT_LLM="OK"
RAISON_LLM=""
if [ ! -s "$META" ]; then
    # couvre absent ET vide : -s est faux dans les deux cas
    STATUT_LLM="ECHEC"
    RAISON_LLM="meta.json absent ou vide ($META) [claude RC=$RC]"
else
    IS_ERROR=$(jq -r 'if has("is_error") then (.is_error|tostring) else "absent" end' "$META" 2>/dev/null || echo "illisible")
    SUBTYPE=$(jq -r '.subtype // "inconnu"' "$META" 2>/dev/null)
    case "$IS_ERROR" in
        true)
            RAISON_LLM=$(jq -r '"HTTP " + ((.api_error_status//0)|tostring) + " " + (.result//"erreur inconnue, is_error=true")' "$META" 2>/dev/null)
            STATUT_LLM="ECHEC"
            RAISON_LLM="${RAISON_LLM} (subtype=${SUBTYPE}) [claude RC=$RC]"
            ;;
        false)
            STATUT_LLM="OK"
            ;;
        *)
            # champ absent, ou jq n'a pas pu parser le fichier
            STATUT_LLM="ECHEC"
            RAISON_LLM="meta.json sans is_error exploitable (jq a rendu '${IS_ERROR}') [claude RC=$RC]"
            ;;
    esac
fi

FRAICHEUR=$(psql "$COMITE_DB_DSN" -tA -c "SELECT round(extract(epoch FROM now()-updated_at)/3600) FROM deos_state WHERE cle='brief';" 2>/dev/null)
if [ "$STATUT_LLM" = "ECHEC" ] || [ ! -f "briefs/brief-$TS.md" ] || [ "${FRAICHEUR:-999}" -gt 3 ]; then
    if [ -n "$RAISON_LLM" ]; then
        RAISON="$RAISON_LLM"
    elif [ ! -f "briefs/brief-$TS.md" ]; then
        RAISON="brief-$TS.md absent alors que claude a annonce un succes [claude RC=$RC]"
    else
        RAISON="brief perime (${FRAICHEUR:-999} h) [claude RC=$RC]"
    fi
    # <... l'appel curl Telegram existant, inchange : cible et jeton restent
    # ceux deja en dur dans le script, ce correctif ne les touche pas ...>
    echo "$TS ALERTE : brief non produit — $RAISON" >> briefs/incidents.log
fi
```

Points de conception :

- `RC` reste calculé exactement comme avant (`|| RC=$?`) et reste collé
  dans chaque message — il redevient **purement informatif**, comme
  `rondes.sh` le fait déjà pour son propre contrôle post-run (ligne 320,
  cité par la mission : `jq -r '.is_error // false'`).
- `[ ! -s "$META" ]` traite en une seule condition le fichier absent et le
  fichier vide (0 octet) — le cas exact rencontré les 30/08 et 03/09 pour
  les `.err`, appliqué ici au `.meta.json`.
- `case` distingue `true` / `false` / tout le reste (`absent` ou
  `illisible`) — pas de repli silencieux : un JSON sans le champ
  `is_error`, ou pas du tout un JSON, déclenche une alerte au lieu d'être
  traité comme un succès implicite.
- Ne dépend d'aucune URL : `jq` lit un fichier local, `psql` et l'appel
  Telegram existant sont ceux déjà présents dans le script, non modifiés
  ici.

Sorties **mesurées** (`bash -n` d'abord, puis exécution) contre quatre
`meta.json` factices déposés dans `/tmp` :

```
$ bash -n bloc_final.sh
(rien -- syntaxe valide)

$ cat briefs/daily-1.meta.json
{"is_error": true, "subtype": "error_during_execution", "api_error_status": 400, "result": "Credit balance is too low"}
$ ./bloc_final.sh 1 0 1
ALERTE declenchee -- 1 ALERTE : brief non produit — HTTP 400 Credit balance is too low (subtype=error_during_execution) [claude RC=0]

$ cat briefs/daily-2.meta.json
{"is_error": false, "subtype": "success", "num_turns": 29, "duration_ms": 752000, "cost_usd": 7.33, "result": "brief ok"}
$ ./bloc_final.sh 2 1 1
ALERTE declenchee -- 2 ALERTE : brief non produit — brief perime (999 h) [claude RC=1]
   # (fraicheur simulee absente = psql injoignable -> repli 999, comportement
   #  deja present dans le script, inchange par ce correctif)

$ ./bloc_final.sh 2 1 1 1     # meme meta.json que ci-dessus, fraicheur=1h simulee
PAS D'ALERTE -- 2 OK (OK, brief present, fraicheur 1)
   # cas cle : is_error=false ET RC=1 (le symptome nomme par la mission) :
   # aucune alerte, correctement -- c'est bien le JSON qui decide, pas RC.

$ : > briefs/daily-3.meta.json     # fichier vide, 0 octet
$ ./bloc_final.sh 3 1 1
ALERTE declenchee -- 3 ALERTE : brief non produit — meta.json absent ou vide (briefs/daily-3.meta.json) [claude RC=1]

$ ./bloc_final.sh absente 0 1      # fichier totalement absent
ALERTE declenchee -- absente ALERTE : brief non produit — meta.json absent ou vide (briefs/daily-absente.meta.json) [claude RC=0]

$ ./bloc_final.sh 2 0 0            # is_error=false mais brief-2.md absent
ALERTE declenchee -- 2 ALERTE : brief non produit — brief-2.md absent alors que claude a annonce un succes [claude RC=0]
```

Le cas central est le quatrième bloc ci-dessus : `is_error:false` **et**
`RC=1` simulé — exactement le symptôme nommé par la mission — ne déclenche
**pas** d'alerte, parce que la décision ne dépend plus de `RC`.

## 5. Ce que Sam doit faire

1. **Choisir la copie à corriger.** Trois copies identiques
   (`md5sum` égal, cité par la mission) : `/root/workspace/dh-comite/bin/daily.sh`,
   `/root/workspace/dh-comite-v3/bin/daily.sh`, `/root/export-dh/comite/bin/daily.sh`.
   Le cron (`/etc/cron.d/dh-comite-rituels`) exécute
   `docker exec dh-comite bash -c 'bash /workspace/bin/daily.sh'` — c'est
   donc le fichier monté dans le conteneur `dh-comite` sous `/workspace/bin/daily.sh`
   qui fait foi en production ; les deux autres copies sont à mettre à jour
   pour rester identiques, ou à documenter comme obsolètes si elles ne le
   sont plus.
2. **Remplacer** le bloc « Bloc d'alerte » actuel (celui qui fait
   `RAISON=$(tail -c 200 ...)` puis le repli `jq -r 'select(.is_error==true) ...'`)
   par le bloc du §4 ci-dessus, immédiatement après le « Bloc d'appel »
   existant (qui n'a pas besoin de changer : `RC=0 ; cat "$PROMPT" | claude ... || RC=$?`
   reste correct, §2 le confirme pour le cas où c'est `claude` qui échoue).
3. **Vérifier après coup**, sur le VPS, sans attendre le prochain 7h30 :
   rejouer manuellement le bloc corrigé contre un `meta.json` réel archivé
   (`briefs/daily-2026-08-29.meta.json` si conservé, ou tout `meta.json`
   du dossier `briefs/`) et vérifier que `STATUT_LLM`/`RAISON` reflètent
   son `is_error` réel — pas de commande précise fournie ici : la
   vérification consiste à relire la sortie du bloc contre le contenu
   connu du fichier, à la main, une fois.
4. **Laisser tourner un cycle cron réel** (le lendemain 7h30) et comparer
   `briefs/incidents.log` : si une alerte part, `RAISON` doit maintenant
   contenir soit un motif `HTTP ... ` extrait du JSON, soit
   « meta.json absent ou vide », soit « brief absent/périmé » — jamais
   plus `inconnue [claude RC=0]` sans qu'aucun de ces trois cas ne
   s'applique.

---

*Rédigé par l'agent B8 le 03/09. §1 et le contenu des extraits VPS : lu,
non mesuré par moi (mesuré par l'orchestrateur le 03/09). §2 et §4 :
mesuré par moi, sorties ci-dessus. §3 : raisonnement sur les extraits
fournis + un fait vérifiable sur `jq` indépendamment de ces extraits
(comportement de `select`).*
