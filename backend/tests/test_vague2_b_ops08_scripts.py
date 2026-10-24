"""Vague 2 / file B — OPS-08 : scripts d'alerte, de rotation et d'export.

Constat Astra (L1020) : le watchdog enregistre l'etat « notifie » meme quand
Telegram a refuse l'envoi, et sort en succes sans identifiants ; le script de
rotation sonde `/api/health`, route absente du backend, et restaure l'ancienne
cle apres une rotation reussie ; l'export de journaux ecrase un export
exploitable par du vide quand `journalctl` echoue.

Aucun envoi reel : `curl`, `systemctl`, `journalctl` et `sleep` sont remplaces
par des bouchons places en tete de PATH. Le bouchon `curl` journalise chaque
appel (arguments, URL, donnees) dans un fichier que les tests relisent : on
assere sur ce qui AURAIT ete envoye (destinataire, texte), pas sur un envoi.

Les scripts lisent des chemins de production en dur (`.env` du comite qui
porte le vrai jeton Telegram, `/var/log/digital-humans`). Quand une version
du script ne connait pas la variable de surcharge, le test execute une COPIE
du script dont seule cette ligne est remplacee : le vrai fichier de secrets
n'est jamais lu, et aucun export de production n'est ecrase.
"""
from __future__ import annotations

import json
import os
import re
import stat
import subprocess
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[2]
WATCHDOG = RACINE / "scripts" / "dh-watchdog.sh"
ROTATION = RACINE / "scripts" / "rotate_anthropic_key.sh"
EXPORT = RACINE / "scripts" / "ops" / "export_logs_24h.sh"

ENV_COMITE_REEL = "/root/workspace/dh-comite/.env"
DEST_EXPORT_REEL = "/var/log/digital-humans"

# --------------------------------------------------------------------------
# Bouchons
# --------------------------------------------------------------------------

FAUX_CURL = r'''#!/usr/bin/env python3
"""Bouchon curl : journalise l'appel, repond selon FAKE_* ; jamais de reseau."""
import json, os, sys
args = sys.argv[1:]
url = next((a for a in args if a.startswith("http")), "")
sortie = None; fmt = None; donnees = []
i = 0
while i < len(args):
    a = args[i]
    if a == "-o": sortie = args[i + 1]; i += 2; continue
    if a == "-w": fmt = args[i + 1]; i += 2; continue
    if a in ("-d", "--data", "--data-urlencode"): donnees.append(args[i + 1]); i += 2; continue
    i += 1
with open(os.environ["FAKE_LOG"], "a") as f:
    f.write(json.dumps({"args": args, "url": url, "data": donnees}) + "\n")

def compteur(nom):
    chemin = os.environ["FAKE_LOG"] + "." + nom
    n = int(open(chemin).read()) + 1 if os.path.exists(chemin) else 1
    open(chemin, "w").write(str(n))
    return n

code, corps, rc = "200", "", 0
if "api.telegram.org" in url:
    mode = os.environ.get("FAKE_TELEGRAM", "ok")
    if mode == "ok": code, corps = "200", '{"ok":true,"result":{"message_id":1}}'
    elif mode == "ok_false": code, corps = "200", '{"ok":false,"description":"Bad Request: chat not found"}'
    elif mode == "http500": code, corps = "500", '{"ok":false,"description":"Internal Server Error"}'
    elif mode == "reseau": code, corps, rc = "000", "", 7
elif "api.anthropic.com" in url:
    code, corps = os.environ.get("FAKE_ANTHROPIC", "200"), '{"content":[]}'
elif url.endswith("/workers/health"):
    code, corps = os.environ.get("FAKE_WORKER", "200"), '{"worker":"up"}'
elif url.endswith("/api/health"):
    code, corps = "404", '{"detail":"Not Found"}'
elif url.endswith("/health"):
    n = compteur("health")
    pret = int(os.environ.get("FAKE_HEALTH_PRET_APRES", "0"))
    code = os.environ.get("FAKE_HEALTH", "200") if n > pret else "000"
    rc = 7 if code == "000" else 0
    corps = '{"status":"healthy"}'
elif "18084" in url:
    code, corps = os.environ.get("FAKE_SPARK", "200"), '{"data":[]}'
elif url.rstrip("/").endswith(":8002"):
    code, corps = os.environ.get("FAKE_ROOT", "200"), '{"status":"healthy"}'
if "-f" in args or "-sf" in args or "-fsS" in args:
    if not code.startswith("2"):
        rc = rc or 22
if sortie:
    open(sortie, "w").write(corps)
elif not ("-o" in args):
    sys.stdout.write(corps)
if fmt:
    # comme curl : `\n` dans -w est un saut de ligne
    sys.stdout.write(fmt.replace("\\n", "\n").replace("%{http_code}", code))
sys.exit(rc)
'''

FAUX_SYSTEMCTL = r'''#!/bin/bash
echo "systemctl $*" >> "$FAKE_LOG.systemctl"
if [ "$1" = "is-active" ]; then
  for inactif in ${FAKE_INACTIFS:-}; do
    [ "$2" = "$inactif" ] && { echo inactive; exit 3; }
  done
  echo active; exit 0
fi
exit 0
'''

FAUX_SLEEP = "#!/bin/bash\nexit 0\n"

FAUX_JOURNALCTL = r'''#!/bin/bash
echo "journalctl $*" >> "$FAKE_LOG.journalctl"
if [ "${FAKE_JOURNALCTL:-ok}" = "echec" ]; then
  echo "Failed to open journal: Permission denied" >&2
  exit 1
fi
echo "2026-10-24T10:00:00+00:00 srv dh[1]: ligne une"
echo "2026-10-24T10:01:00+00:00 srv dh[1]: ligne deux"
'''


def _ecrire_executable(chemin: Path, contenu: str) -> None:
    chemin.write_text(contenu)
    chemin.chmod(chemin.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


@pytest.fixture
def bouchons(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _ecrire_executable(bin_dir / "curl", FAUX_CURL)
    _ecrire_executable(bin_dir / "systemctl", FAUX_SYSTEMCTL)
    _ecrire_executable(bin_dir / "sleep", FAUX_SLEEP)
    _ecrire_executable(bin_dir / "journalctl", FAUX_JOURNALCTL)
    log = tmp_path / "appels.jsonl"
    log.write_text("")
    env = {
        "PATH": f"{bin_dir}:/usr/bin:/bin",
        "HOME": str(tmp_path),
        "FAKE_LOG": str(log),
        "LANG": "C.UTF-8",
    }
    return env, log, tmp_path


def _appels(log: Path):
    return [json.loads(l) for l in log.read_text().splitlines() if l.strip()]


def _appels_telegram(log: Path):
    return [a for a in _appels(log) if "api.telegram.org" in a["url"]]


# --------------------------------------------------------------------------
# Watchdog
# --------------------------------------------------------------------------

def _script_watchdog(tmp_path: Path) -> Path:
    """Le script tel quel s'il accepte DH_WATCHDOG_ENV, sinon une copie dont
    seule la ligne du fichier de secrets est remplacee (jamais le vrai)."""
    source = WATCHDOG.read_text()
    if "DH_WATCHDOG_ENV" in source:
        return WATCHDOG
    assert f"ENV={ENV_COMITE_REEL}" in source, "ligne ENV introuvable : test a revoir"
    copie = tmp_path / "dh-watchdog-copie.sh"
    copie.write_text(source.replace(f"ENV={ENV_COMITE_REEL}", 'ENV="$DH_WATCHDOG_ENV"'))
    copie.chmod(0o755)
    return copie


def _lancer_watchdog(bouchons, *, identifiants=True, **fake):
    env, log, tmp_path = bouchons
    fichier_env = tmp_path / "comite.env"
    if identifiants:
        fichier_env.write_text("TELEGRAM_BOT_TOKEN=jeton-bouchon\nTELEGRAM_CHAT_ID=4242\n")
    else:
        fichier_env.write_text("AUTRE=1\n")
    env = dict(env)
    env.update({
        "DH_WATCHDOG_ENV": str(fichier_env),
        "STATE": str(tmp_path / "watchdog.state"),
    })
    env.update({k: str(v) for k, v in fake.items()})
    script = _script_watchdog(tmp_path)
    r = subprocess.run(["bash", str(script)], env=env, capture_output=True, text=True, timeout=60)
    return r, tmp_path / "watchdog.state"


def test_watchdog_lit_le_fichier_de_secrets_surchargeable():
    """Sans surcharge, aucun test ne peut lancer le watchdog sans lire le vrai
    jeton Telegram du comite."""
    assert "DH_WATCHDOG_ENV" in WATCHDOG.read_text()


def test_watchdog_alerte_envoyee_au_bon_destinataire_et_etat_enregistre(bouchons):
    r, state = _lancer_watchdog(bouchons, FAKE_HEALTH=503)
    assert r.returncode == 0, r.stderr
    envois = _appels_telegram(bouchons[1])
    assert len(envois) == 1
    assert "botjeton-bouchon/sendMessage" in envois[0]["url"]
    assert "chat_id=4242" in envois[0]["data"]
    texte = [d for d in envois[0]["data"] if d.startswith("text=")][0]
    assert "DH ALERTE" in texte and "backend /health = 503" in texte
    assert state.read_text().strip() == "backend /health = 503"


@pytest.mark.parametrize("mode", ["http500", "ok_false", "reseau"])
def test_watchdog_echec_telegram_n_enregistre_pas_l_etat(bouchons, mode):
    """Un envoi refuse (HTTP 500, `ok:false`, reseau) ne doit pas marquer
    l'etat comme notifie : la tentative suivante doit pouvoir renvoyer."""
    r, state = _lancer_watchdog(bouchons, FAKE_HEALTH=503, FAKE_TELEGRAM=mode)
    assert len(_appels_telegram(bouchons[1])) == 1
    assert not state.exists() or state.read_text().strip() == "", (
        f"etat enregistre malgre l'echec d'envoi ({mode}) : {state.read_text()!r}"
    )
    assert r.returncode != 0
    assert "telegram" in r.stderr.lower()


def test_watchdog_echec_puis_succes_renvoie_l_alerte(bouchons):
    _lancer_watchdog(bouchons, FAKE_HEALTH=503, FAKE_TELEGRAM="http500")
    r, state = _lancer_watchdog(bouchons, FAKE_HEALTH=503, FAKE_TELEGRAM="ok")
    assert r.returncode == 0
    assert len(_appels_telegram(bouchons[1])) == 2
    assert state.read_text().strip() == "backend /health = 503"


def test_watchdog_pas_de_doublon_pour_le_meme_etat(bouchons):
    """Controle : deux passages consecutifs, meme panne -> un seul envoi."""
    _lancer_watchdog(bouchons, FAKE_HEALTH=503)
    r, _ = _lancer_watchdog(bouchons, FAKE_HEALTH=503)
    assert r.returncode == 0
    assert len(_appels_telegram(bouchons[1])) == 1


def test_watchdog_retablissement_signale_une_fois(bouchons):
    _lancer_watchdog(bouchons, FAKE_HEALTH=503)
    r, state = _lancer_watchdog(bouchons)
    assert r.returncode == 0
    envois = _appels_telegram(bouchons[1])
    assert len(envois) == 2
    assert any("rétabli" in d for d in envois[1]["data"])
    assert state.read_text().strip() == ""
    _lancer_watchdog(bouchons)
    assert len(_appels_telegram(bouchons[1])) == 2


def test_watchdog_sans_identifiants_sort_en_erreur_et_le_dit(bouchons):
    """Sans jeton ni destinataire, le watchdog sortait 0 en silence : un
    dispositif d'alerte inerte doit le dire et echouer."""
    r, _ = _lancer_watchdog(bouchons, identifiants=False, FAKE_HEALTH=503)
    assert r.returncode != 0
    assert "TELEGRAM" in r.stderr
    assert _appels_telegram(bouchons[1]) == []


def test_watchdog_sonde_le_worker(bouchons):
    """Astra OPS-02 : le watchdog ne sondait pas le worker. Un battement ARQ
    absent (sonde 503) et un service worker inactif doivent alerter."""
    r, state = _lancer_watchdog(
        bouchons, FAKE_WORKER=503, FAKE_INACTIFS="digital-humans-worker"
    )
    assert r.returncode == 0, r.stderr
    etat = state.read_text()
    assert "worker" in etat
    assert "digital-humans-worker down" in etat
    urls = [a["url"] for a in _appels(bouchons[1])]
    assert any(u.endswith("/api/pm-orchestrator/workers/health") for u in urls)


# --------------------------------------------------------------------------
# Rotation de la cle Anthropic
# --------------------------------------------------------------------------

NOUVELLE_CLE = "sk-ant-api03-" + "n" * 60
ANCIENNE_CLE = "sk-ant-api03-" + "a" * 60


def _lancer_rotation(bouchons, **fake):
    env, log, tmp_path = bouchons
    fichier_env = tmp_path / "backend.env"
    fichier_env.write_text(f"DEBUG=False\nANTHROPIC_API_KEY={ANCIENNE_CLE}\n")
    env = dict(env)
    env.update({
        # DH_ENV_FILE est AUSSI la variable de la suite hermetique (qui pointe
        # .env.test) : on la pose explicitement, sinon le script reecrirait
        # backend/.env.test.
        "DH_ENV_FILE": str(fichier_env),
        "DH_SERVICE_NAME": "dh-test-faux-service",
        "DH_ROOT_URL": "http://localhost:8002/",
    })
    env.pop("DH_HEALTH_URL", None)
    env.update({k: str(v) for k, v in fake.items()})
    r = subprocess.run(
        ["bash", str(ROTATION), NOUVELLE_CLE], env=env, capture_output=True,
        text=True, timeout=120,
    )
    return r, fichier_env


@pytest.mark.skipif(os.geteuid() != 0, reason="le script exige root (il le verifie)")
def test_rotation_reussie_n_est_pas_annulee(bouchons):
    """Backend sain sur /health, /api/health absent (comme le vrai backend) :
    la rotation doit aboutir, pas restaurer l'ancienne cle."""
    r, fichier_env = _lancer_rotation(bouchons)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "ROLLBACK" not in r.stdout + r.stderr
    assert f"ANTHROPIC_API_KEY={NOUVELLE_CLE}" in fichier_env.read_text()
    urls = [a["url"] for a in _appels(bouchons[1])]
    assert "http://localhost:8002/health" in urls
    assert not any(u.endswith("/api/health") for u in urls)


@pytest.mark.skipif(os.geteuid() != 0, reason="le script exige root (il le verifie)")
def test_rotation_attend_un_demarrage_de_deux_minutes(bouchons):
    """Le backend met ~2 min a repondre apres redemarrage (mesure du 23/10) :
    une attente de 30 s annule une rotation reussie."""
    r, fichier_env = _lancer_rotation(bouchons, FAKE_HEALTH_PRET_APRES=90)
    assert r.returncode == 0, r.stdout + r.stderr
    assert f"ANTHROPIC_API_KEY={NOUVELLE_CLE}" in fichier_env.read_text()


@pytest.mark.skipif(os.geteuid() != 0, reason="le script exige root (il le verifie)")
def test_rotation_backend_mort_restaure_l_ancienne_cle(bouchons):
    """Controle negatif : backend jamais sain -> rollback, code non nul."""
    r, fichier_env = _lancer_rotation(bouchons, FAKE_HEALTH="503")
    assert r.returncode != 0
    assert "ROLLBACK" in r.stdout + r.stderr
    assert f"ANTHROPIC_API_KEY={ANCIENNE_CLE}" in fichier_env.read_text()


@pytest.mark.skipif(os.geteuid() != 0, reason="le script exige root (il le verifie)")
def test_rotation_tous_les_curl_ont_un_delai(bouchons):
    _lancer_rotation(bouchons)
    sans_delai = [a for a in _appels(bouchons[1]) if "--max-time" not in a["args"]]
    assert sans_delai == [], f"curl sans --max-time : {[a['url'] for a in sans_delai]}"


# --------------------------------------------------------------------------
# Export des journaux
# --------------------------------------------------------------------------

def _script_export(tmp_path: Path) -> Path:
    source = EXPORT.read_text()
    if "DH_LOG_EXPORT_DIR" in source:
        return EXPORT
    ligne = f'DEST_DIR="{DEST_EXPORT_REEL}"'
    assert ligne in source, "ligne DEST_DIR introuvable : test a revoir"
    copie = tmp_path / "export-copie.sh"
    copie.write_text(source.replace(ligne, 'DEST_DIR="$DH_LOG_EXPORT_DIR"'))
    copie.chmod(0o755)
    return copie


def _lancer_export(bouchons, **fake):
    env, log, tmp_path = bouchons
    dest = tmp_path / "exports"
    dest.mkdir(exist_ok=True)
    env = dict(env)
    env["DH_LOG_EXPORT_DIR"] = str(dest)
    env.update({k: str(v) for k, v in fake.items()})
    r = subprocess.run(
        ["bash", str(_script_export(tmp_path))], env=env, capture_output=True,
        text=True, timeout=60,
    )
    return r, dest


def test_export_nominal_ecrit_les_deux_fichiers(bouchons):
    r, dest = _lancer_export(bouchons)
    assert r.returncode == 0, r.stderr
    contenu = (dest / "backend-24h.log").read_text()
    assert "# Lignes exportees     : 2" in contenu
    assert "ligne deux" in contenu
    assert (dest / "worker-24h.log").exists()


def test_export_journalctl_en_echec_conserve_l_export_precedent(bouchons):
    """`journalctl` en echec : l'ancien export exploitable reste en place, le
    script le dit et sort en erreur."""
    r, dest = _lancer_export(bouchons)
    assert r.returncode == 0
    avant = (dest / "backend-24h.log").read_text()
    r, dest = _lancer_export(bouchons, FAKE_JOURNALCTL="echec")
    assert (dest / "backend-24h.log").read_text() == avant, "export precedent ecrase"
    assert r.returncode != 0
    assert "journalctl" in r.stderr
