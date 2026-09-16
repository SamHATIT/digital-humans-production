"""Aucun secret en dur dans le depot (GL-11, 16/09/2026).
Le mot de passe DH_SecurePass2025! a survecu a la rotation du 06/09 dans cinq fichiers et a casse la phase 5 pendant dix jours."""
import re, subprocess
from pathlib import Path

PATTERNS = [r"DH_SecurePass", r"postgresql://[^\s\"']+:[^\s\"'@:]{6,}@", r"sk-ant-api03-[A-Za-z0-9_-]{20,}", r"sk-[A-Za-z0-9]{32,}"]
ALLOW = {"tests/test_no_hardcoded_secrets.py"}
PLACEHOLDERS = {"password", "secret", "changeme", "xxx", "pass", "example", "test"}

def test_no_hardcoded_secrets():
    root = Path(__file__).resolve().parents[2]
    files = subprocess.run(["git", "ls-files", "*.py", "*.sh", "*.yaml", "*.yml", "*.json"], cwd=root, capture_output=True, text=True).stdout.split()
    hits = []
    for f in files:
        if f.replace("backend/", "", 1) in ALLOW or f in ALLOW: continue
        try: txt = (root / f).read_text(encoding="utf-8", errors="ignore")
        except Exception: continue
        for pat in PATTERNS:
            for m in re.finditer(pat, txt):
                if "os.getenv" in txt[max(0, m.start()-60):m.start()] and "DH_SecurePass" not in m.group(0): continue
                pw = re.search(r"://[^:]+:([^@]+)@", m.group(0))
                if pw and (pw.group(1).startswith("${") or pw.group(1).lower() in PLACEHOLDERS): continue  # gabarits, pas des secrets
                hits.append(f"{f}: {m.group(0)[:40]}")
    assert not hits, "Secrets en dur :\n" + "\n".join(hits)
