"""
LOT-C — Injections et execution de commandes.

Constats couverts : gem:SEC-01, gem:SEC-02, kim:SEC-01 (volet agent_tester),
kim:SEC-02, kim:SEC-03 (traversee de repertoire).

Le critere de fin du lot tient en deux phrases :

  * `grep -rn "shell=True" backend/app` ne renvoie rien ;
  * `/api/agent-tester/org/query` -> 401 sans jeton, 200 avec.

Les deux sont verifies ici, plus la preuve qui compte vraiment : une charge
utile qui detruisait un fichier temoin quand la commande etait construite par
interpolation ne le detruit plus, et arrive a `sf` comme UNE case d'`argv`.

Le test de non-injection est monte sur un faux executable `sf` place en tete
de PATH : rien ne sort du repertoire temporaire de pytest, aucune org
Salesforce n'est jointe, et la charge utile ne vise qu'un fichier temoin cree
pour l'occasion.

`pm_orchestrator_service_v2` n'est pas importable dans cet environnement
(`python-docx` absent, defaut prealable a ce lot) : il est verifie par lecture
de son arbre syntaxique, ce qui suffit pour la propriete recherchee.
"""
import ast
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from app.models.user import User
from app.utils.auth import create_access_token, get_password_hash


BACKEND_APP = Path(__file__).resolve().parent.parent / "app"
QUERY_URL = "/api/agent-tester/org/query"

# Charges utiles destructrices : la commande shell qu'elles contiennent efface
# le fichier temoin. Elles ne visent que ce fichier, dans le tmp_path du test.
#
# La premiere sort des guillemets de la commande d'avant le correctif
# (`--query "{soql}"`) avant d'enchainer sur `;` — c'est l'exploitation decrite
# par gem:SEC-01. Elle commence par `SELECT ... FROM ...`, donc elle franchit
# aussi le filtre SOQL : ce qui la neutralise est bien l'absence de shell, pas
# le filtre. La seconde reste dans les guillemets, ou `$(...)` et les backticks
# sont interpretes malgre tout.
DESTRUCTIVE_SOQL = 'SELECT Id FROM Account" ; rm -rf {witness} ; echo "'
SUBSTITUTION_SOQL = "SELECT Id FROM Contact WHERE Name = '$(rm -f {witness})`rm -f {witness}`'"


# --------------------------------------------------------------- fixtures

@pytest.fixture
def auth_headers(db_session):
    """Un utilisateur actif et son en-tete Authorization."""
    user = User(
        email="lot-c@example.test",
        hashed_password=get_password_hash("motdepasse-de-test"),
        name="lot-c",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return {"Authorization": f"Bearer {create_access_token({'sub': str(user.id)})}"}


@pytest.fixture
def fake_sf(tmp_path, monkeypatch):
    """
    Un faux CLI `sf` en tete de PATH.

    Il note son `argv` dans un fichier et repond un JSON valide. Il permet de
    voir exactement ce que le backend transmet, sans joindre d'org reelle.
    """
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    argv_file = tmp_path / "argv.json"
    sf = bin_dir / "sf"
    sf.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys\n"
        f"open({str(argv_file)!r}, 'w').write(json.dumps(sys.argv[1:]))\n"
        "print(json.dumps({'status': 0, 'result': {'records': [], 'totalSize': 0}}))\n"
    )
    sf.chmod(sf.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    return {"bin_dir": bin_dir, "argv_file": argv_file}


@pytest.fixture
def configured_org(monkeypatch):
    """Une org par defaut configuree (LOT-E bis : sinon org_alias vaut None)."""
    from app.salesforce_config import salesforce_config
    monkeypatch.setattr(salesforce_config, "org_alias", "org-de-test", raising=False)
    monkeypatch.setattr(salesforce_config, "username", "u@test", raising=False)
    monkeypatch.setattr(salesforce_config, "org_id", "00Dtest", raising=False)
    monkeypatch.setattr(salesforce_config, "instance_url", "https://test.my.salesforce.com", raising=False)
    return salesforce_config


def _witness(tmp_path) -> Path:
    w = tmp_path / "preuve.txt"
    w.write_text("ce fichier doit survivre")
    return w


# ============================================================ critere de fin
# « grep -rn "shell=True" backend/app ne renvoie rien »

def test_aucun_shell_true_dans_backend_app():
    """Aucun appel subprocess de app/ ne passe par un shell.

    Verifie sur l'arbre syntaxique, pas sur le texte : un `shell=True` ecrit
    autrement (variable, `**kwargs`, valeur non litterale) serait invisible a
    un grep et reste une execution de commande interpretee.
    """
    coupables = []
    for f in sorted(BACKEND_APP.rglob("*.py")):
        tree = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            for kw in node.keywords:
                if kw.arg != "shell":
                    continue
                # Seul `shell=False` litteral est acceptable.
                if not (isinstance(kw.value, ast.Constant) and kw.value.value is False):
                    coupables.append(f"{f.relative_to(BACKEND_APP.parent.parent)}:{node.lineno}")
    assert coupables == [], f"shell actif ou non litteral : {coupables}"


def test_grep_litteral_shell_true_ne_renvoie_rien():
    """Le critere de fin tel qu'il est ecrit dans le plan, joue litteralement."""
    r = subprocess.run(
        ["grep", "-rn", "shell=True", "app"],
        cwd=str(BACKEND_APP.parent), capture_output=True, text=True,
    )
    assert r.returncode == 1, f"grep a trouve :\n{r.stdout}"
    assert r.stdout == ""


# ============================================================ critere de fin
# « route -> 401 sans jeton, 200 avec »

def test_org_query_sans_jeton_renvoie_401(client):
    """gem:SEC-02 / kim:SEC-01 : la route etait anonyme et joignable d'Internet."""
    r = client.get(QUERY_URL, params={"soql": "SELECT Id FROM Account"})
    assert r.status_code == 401, r.text


def test_org_query_avec_jeton_renvoie_200(client, auth_headers, fake_sf, configured_org):
    r = client.get(QUERY_URL, params={"soql": "SELECT Id FROM Account"}, headers=auth_headers)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == 0


def test_jeton_invalide_renvoie_401(client):
    r = client.get(
        QUERY_URL,
        params={"soql": "SELECT Id FROM Account"},
        headers={"Authorization": "Bearer pas-un-jeton"},
    )
    assert r.status_code == 401


@pytest.mark.parametrize("url", [
    "/api/agent-tester/agents",
    "/api/agent-tester/agents/olivia",
    "/api/agent-tester/workspace/files",
    "/api/agent-tester/llm/status",
    "/api/agent-tester/logs",
])
def test_tout_le_routeur_exige_une_authentification(client, url):
    """L'auth est posee au niveau du routeur : elle vaut pour chaque route."""
    assert client.get(url).status_code == 401, url


def test_test_agent_stream_sans_jeton_renvoie_401(client):
    """La route la plus couteuse du routeur : elle declenche des appels LLM."""
    r = client.post(
        "/api/agent-tester/test/olivia/stream",
        json={"task_description": "x", "deploy_to_org": False, "use_rag": False},
    )
    assert r.status_code == 401


# ==================================================== preuve de non-injection

def test_charge_destructrice_traitee_comme_donnee(client, auth_headers, fake_sf, configured_org, tmp_path):
    """
    gem:SEC-01 / kim:SEC-02 — le coeur du lot.

    Une charge contenant `; rm -rf <temoin> ;` passe par la route corrigee :
    le fichier temoin survit, et la charge arrive a `sf` comme UN seul
    element d'`argv`, apres `--query`.
    """
    witness = _witness(tmp_path)
    soql = DESTRUCTIVE_SOQL.format(witness=witness)

    r = client.get(QUERY_URL, params={"soql": soql}, headers=auth_headers)
    assert r.status_code == 200, r.text

    assert witness.exists(), "le fichier temoin a ete detruit : la charge a ete executee"
    assert witness.read_text() == "ce fichier doit survivre"

    argv = json.loads(fake_sf["argv_file"].read_text())
    assert argv == ["data", "query", "--query", soql, "--target-org", "org-de-test", "--json"]
    # La charge occupe une case et une seule : elle n'a pas ete decoupee.
    assert argv.count(soql) == 1


def test_substitution_de_commande_traitee_comme_donnee(client, auth_headers, fake_sf, configured_org, tmp_path):
    """`$(...)` et les backticks n'ont plus d'interprete pour les lire."""
    witness = _witness(tmp_path)
    soql = SUBSTITUTION_SOQL.format(witness=witness)

    r = client.get(QUERY_URL, params={"soql": soql}, headers=auth_headers)
    assert r.status_code == 200, r.text
    assert witness.exists(), "le fichier temoin a ete detruit : substitution executee"

    argv = json.loads(fake_sf["argv_file"].read_text())
    assert argv[3] == soql


@pytest.mark.parametrize("gabarit", [DESTRUCTIVE_SOQL, SUBSTITUTION_SOQL])
def test_la_meme_charge_etait_bien_destructrice_avant_le_correctif(fake_sf, tmp_path, gabarit):
    """
    Contre-epreuve : sans elle, les deux tests precedents ne prouvent rien.

    On rejoue ICI, hors de l'application, la construction de commande d'avant
    le correctif (interpolation + shell). Le fichier temoin disparait. C'est
    la demonstration que la charge utilisee est reellement dangereuse et que
    ce sont bien `shell=False` et la liste d'arguments qui la neutralisent.
    """
    witness = _witness(tmp_path)
    soql = gabarit.format(witness=witness)

    # Forme vulnerable, telle qu'elle etait en production le 21/08 :
    #   f'sf data query --query "{soql}" --target-org {alias} --json', shell=True
    subprocess.run(
        f'sf data query --query "{soql}" --target-org org-de-test --json',
        shell=True, capture_output=True, text=True, timeout=30,
    )
    assert not witness.exists(), (
        "le temoin a survecu a la forme vulnerable : la charge de test ne "
        "prouve rien, il faut la revoir"
    )


def test_injection_soql_refusee_avant_le_cli(client, auth_headers, fake_sf, configured_org):
    """`' OR 1=1 --` n'est pas une requete de lecture : refus en 400."""
    r = client.get(QUERY_URL, params={"soql": "' OR 1=1 --"}, headers=auth_headers)
    assert r.status_code == 400, r.text
    assert not fake_sf["argv_file"].exists(), "le CLI a ete appele malgre le refus"


@pytest.mark.parametrize("soql", [
    "",
    "   ",
    "--version",                              # se ferait passer pour une option de `sf`
    "-r",
    "DELETE FROM Account",
    "UPDATE Account SET Name = 'x'",
    "sf org display",
    "SELECT Id FROM Account\x00",
])
def test_soql_refuse(client, auth_headers, fake_sf, configured_org, soql):
    r = client.get(QUERY_URL, params={"soql": soql}, headers=auth_headers)
    assert r.status_code == 400, f"{soql!r} accepte : {r.text}"
    assert not fake_sf["argv_file"].exists()


def test_soql_trop_long_refuse(client, auth_headers, fake_sf, configured_org):
    from app.api.routes.agent_tester import SOQL_MAX_LENGTH
    soql = "SELECT Id FROM Account WHERE Name = '" + "a" * SOQL_MAX_LENGTH + "'"
    r = client.get(QUERY_URL, params={"soql": soql}, headers=auth_headers)
    assert r.status_code == 400


# ============================================ LOT-E bis : org non configuree

def test_sans_org_configuree_message_clair_et_pas_de_cli(client, auth_headers, fake_sf, monkeypatch):
    """
    LOT-E bis a retire les identites codees en dur : `org_alias` peut valoir
    None. Sans garde, la route enverrait `--target-org None` au CLI. Elle
    repond 503 avec un message exploitable, et n'appelle pas `sf`.
    """
    from app.salesforce_config import salesforce_config
    monkeypatch.setattr(salesforce_config, "org_alias", None, raising=False)

    r = client.get(QUERY_URL, params={"soql": "SELECT Id FROM Account"}, headers=auth_headers)
    assert r.status_code == 503, r.text
    assert "org_alias" in r.json()["detail"]
    assert not fake_sf["argv_file"].exists()


def test_agents_n_annonce_plus_une_org_connectee_en_dur(client, auth_headers, monkeypatch):
    """`connected` etait la constante True, meme sans org configuree."""
    from app.salesforce_config import salesforce_config
    monkeypatch.setattr(salesforce_config, "org_alias", None, raising=False)

    body = client.get("/api/agent-tester/agents", headers=auth_headers).json()
    assert body["salesforce_org"]["connected"] is False
    assert "org_alias" in body["salesforce_org"]["missing"]


# ============================================== kim:SEC-03 — traversee (lecture)

@pytest.mark.parametrize("brut, attendu", [
    ("../../../etc/passwd", "passwd"),
    ("..%2F..%2F..%2Fetc%2Fpasswd", "passwd"),
    ("/etc/passwd", "passwd"),
    ("/etc/shadow", "shadow"),
    ("..\\..\\windows\\win.ini", "..\\..\\windows\\win.ini"),
    ("test-2026-08-21.json", "test-2026-08-21.json"),
])
def test_safe_log_id_ne_laisse_passer_aucun_chemin(brut, attendu):
    """
    Le verrou lui-meme, teste directement.

    `%2F` est decode par Starlette dans un parametre de chemin ; la valeur
    arrivait ensuite telle quelle dans `LOGS_DIR / filename`. `Path(...).name`
    ne conserve que le dernier segment.
    """
    from app.api.routes.agent_tester import _safe_log_id
    obtenu = _safe_log_id(brut.replace("%2F", "/"))
    assert obtenu == attendu
    assert "/" not in obtenu
    assert not Path(obtenu).is_absolute()


@pytest.mark.parametrize("brut", ["", "   /   ", "..", "../", "/"])
def test_safe_log_id_refuse_les_identifiants_vides(brut):
    from app.api.routes.agent_tester import _safe_log_id
    with pytest.raises(Exception) as exc:
        _safe_log_id(brut)
    assert getattr(exc.value, "status_code", None) == 400


@pytest.mark.parametrize("test_id", [
    "../../../etc/passwd",
    "..%2F..%2F..%2Fetc%2Fpasswd",
    "/etc/passwd",
    "..",
])
def test_logs_ne_sort_pas_du_repertoire_de_logs(client, auth_headers, test_id, monkeypatch):
    """
    `AgentTestLogger.get_log_by_filename()` fait `LOGS_DIR / filename` sans
    controle. Le parametre d'URL lui arrivait tel quel. On verifie que le nom
    transmis ne comporte plus de composante de chemin.
    """
    vus = []
    from app.services import agent_test_logger

    monkeypatch.setattr(
        agent_test_logger.AgentTestLogger, "get_log",
        classmethod(lambda cls, tid: vus.append(tid) or None),
    )
    monkeypatch.setattr(
        agent_test_logger.AgentTestLogger, "get_log_by_filename",
        classmethod(lambda cls, fn: vus.append(fn) or None),
    )

    r = client.get(f"/api/agent-tester/logs/{test_id}", headers=auth_headers)
    assert r.status_code in (400, 404), r.text
    for vu in vus:
        assert "/" not in vu and ".." not in vu, f"nom de fichier non assaini : {vu!r}"

    # Le montage est bien celui qu'on croit : un identifiant anodin, lui,
    # atteint le logger. Sans ce controle, les assertions ci-dessus pourraient
    # passer a vide (404 de routage avant le handler).
    vus.clear()
    client.get("/api/agent-tester/logs/anodin.json", headers=auth_headers)
    assert vus == ["anodin.json", "anodin.json"], vus


def test_documents_upload_assaini_par_lot_b():
    """
    kim:SEC-03, volet ecriture : deja traite par LOT-B dans documents.py.
    Ce test est un garde-fou de non-regression, pas un correctif du LOT-C.
    """
    src = (BACKEND_APP / "api" / "routes" / "documents.py").read_text(encoding="utf-8")
    # Le nom brut ne sert plus a construire le chemin d'ecriture (la chaine
    # subsiste dans un commentaire de LOT-B : on teste le code, pas le texte).
    assert "file_path = project_dir / file.filename" not in src
    assert "file_path = project_dir / safe_filename" in src
    assert 'Path(file.filename or "").name' in src


# ================================ agent_executor / pm_orchestrator : proprietes

def _call_kwargs(path: Path, func_name: str):
    """Les appels a subprocess.run situes dans une fonction donnee."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    out = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func_name:
            for sub in ast.walk(node):
                if (isinstance(sub, ast.Call)
                        and isinstance(sub.func, ast.Attribute)
                        and sub.func.attr == "run"):
                    out.append(sub)
    return out


@pytest.mark.parametrize("func", ["_check_salesforce_connection", "_deploy_to_salesforce"])
def test_agent_executor_commandes_en_liste(func):
    """kim:SEC-02 : les deux sites de agent_executor passent une liste d'arguments."""
    path = BACKEND_APP / "services" / "agent_executor.py"
    calls = _call_kwargs(path, func)
    assert calls, f"aucun subprocess.run trouve dans {func}"
    for call in calls:
        assert call.args, f"{func}: subprocess.run sans argument positionnel"
        assert isinstance(call.args[0], ast.List), (
            f"{func}:{call.lineno} la commande n'est pas une liste d'arguments"
        )
        shell = [k for k in call.keywords if k.arg == "shell"]
        assert shell and shell[0].value.value is False, f"{func}: shell non desactive"


@pytest.mark.parametrize("func", ["_check_salesforce_connection", "_deploy_to_salesforce"])
def test_agent_executor_exige_une_org_avant_la_commande(func):
    """LOT-E bis : `require()` avant de construire la commande."""
    path = BACKEND_APP / "services" / "agent_executor.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func:
            src = ast.dump(node)
            assert "'require'" in src or '"require"' in src, f"{func} n'appelle pas require()"
            return
    pytest.fail(f"{func} introuvable")


def test_agent_executor_check_connection_sans_org(monkeypatch):
    """Sans org, message clair au lieu d'une erreur du CLI `sf`."""
    from app.services.agent_executor import AgentExecutor
    from app.salesforce_config import salesforce_config
    monkeypatch.setattr(salesforce_config, "org_alias", None, raising=False)

    res = AgentExecutor._check_salesforce_connection(object())
    assert res["connected"] is False
    assert "org_alias" in res.get("error", "")


def test_pm_orchestrator_run_sfdx_async_sans_shell():
    """
    pm_orchestrator_service_v2 n'est pas importable ici (python-docx absent,
    defaut prealable au lot) : verification par arbre syntaxique.

    On exige que `_run_sfdx_async` prenne une liste (`args`), desactive le
    shell, et que chacun de ses appelants lui passe une liste litterale.
    """
    path = BACKEND_APP / "services" / "pm_orchestrator_service_v2.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))

    helper = next(
        (n for n in ast.walk(tree)
         if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
         and n.name == "_run_sfdx_async"),
        None,
    )
    assert helper is not None, "_run_sfdx_async introuvable"
    assert helper.args.args[0].arg == "args", "la signature accepte encore une chaine"

    shell_kw = [
        kw for node in ast.walk(helper) if isinstance(node, ast.Call)
        for kw in node.keywords if kw.arg == "shell"
    ]
    assert shell_kw, "aucun parametre shell explicite"
    assert all(k.value.value is False for k in shell_kw), "shell encore actif"

    # Chaque appelant passe une liste, jamais une f-string.
    appels = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == "_run_sfdx_async"
    ]
    assert len(appels) >= 6, f"{len(appels)} appelants trouves, 6 attendus au moins"
    noms_listes = {
        t.id
        for node in ast.walk(tree) if isinstance(node, ast.Assign)
        for t in node.targets if isinstance(t, ast.Name)
        if isinstance(node.value, ast.List)
    }
    for appel in appels:
        arg = appel.args[0]
        assert isinstance(arg, ast.List) or (
            isinstance(arg, ast.Name) and arg.id in noms_listes
        ), f"ligne {appel.lineno} : la commande n'est pas une liste d'arguments"

    assert "JoinedStr" not in ast.dump(helper), "f-string residuelle dans le helper"
