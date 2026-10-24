"""
Vague 2 / file A — PROD-09 : upload non borné avant lecture, collisions,
ingestion disproportionnée (audit Astra du 06/09, L510).

Défauts visés (`api/routes/documents.py::upload_document`) :
  1. la limite de 20 Mo était contrôlée APRÈS lecture intégrale du corps
     (`file.file.read()`, et avant cela l'analyse multipart complète faite par
     FastAPI pour remplir `UploadFile`) ;
  2. deux uploads de même nom désignaient le même fichier disque : le second
     écrasait le premier, et supprimer l'un supprimait le fichier de l'autre ;
  3. un parseur PDF/DOCX absent faisait lire le binaire comme du texte, ingéré
     comme valide (mesuré le 24/10 : PyMuPDF/`fitz` n'est installé ni dans le
     venv de production ni dans celui des tests) ;
  4. aucune borne sur le texte extrait, donc sur le nombre de chunks et
     d'appels d'embedding ; un seul `upsert` géant ;
  5. aucun quota de stockage par projet.

Mesure « avant lecture du corps » : l'application est appelée directement en
ASGI. Deux compteurs :
  - `octets_lus_par_l_application` : octets rendus par `Request.stream()`,
    seule voie par laquelle FastAPI (analyse du formulaire) ou la route lisent
    le corps. C'est lui qui est vérifié ;
  - `octets_recus_avant_reponse` : octets tirés du `receive` brut avant le
    début de la réponse, donné pour information. Il NE mesure PAS la lecture
    par la route : `BaseHTTPMiddleware` (Starlette 0.27, trois middlewares
    dans app.main) écoute la déconnexion du client en appelant `receive`
    pendant qu'il transmet la réponse, et vide ainsi le reste du corps, sans
    le conserver (mesuré : il vaut le corps entier même après correctif, alors
    que le pic mémoire reste < 1,5 Mo).
La mémoire Python allouée pendant la requête est mesurée par `tracemalloc`
(pic). Aucun réseau ; embeddings bouchons
(`tests.vague2_a_outils.embedding_bouchon`).
"""
import asyncio
import io
import sys
import tracemalloc
import zipfile

import pytest

from app.main import app
from app.models.project_document import ProjectDocument
from app.services import rag_service
from tests.vague2_a_outils import client_sans_lifespan, creer_tenant, installer_chroma_temporaire

MIO = 1024 * 1024
MORCEAU = 64 * 1024
FRONTIERE = b"frontiereVAGUE2A"


@pytest.fixture
def env(db_session, tmp_path, monkeypatch):
    from app.api.routes import documents as documents_routes

    chroma = installer_chroma_temporaire(tmp_path / "chroma_prod09", monkeypatch)
    monkeypatch.setattr(documents_routes, "DOCUMENTS_DIR", tmp_path / "docs")
    client = client_sans_lifespan(app, db_session)
    a = creer_tenant(db_session, "alice-prod09@example.test")
    yield {"client": client, "a": a, "chroma": chroma, "routes": documents_routes, "db": db_session, "docs": tmp_path / "docs"}
    app.dependency_overrides.clear()


# Valeurs des bornes introduites par le correctif. Le test les lit dans le
# module ; à défaut (commit parent, avant correctif), il prend les mêmes
# valeurs littérales pour que le test rouge échoue sur le COMPORTEMENT et non
# sur un attribut absent.
_BORNES_PAR_DEFAUT = {
    "MARGE_MULTIPART": 64 * 1024,
    "MAX_OCTETS_DECOMPRESSES": 100 * MIO,
    "MAX_CARACTERES_EXTRAITS": 2_000_000,
    "MAX_OCTETS_PAR_PROJET": 200 * MIO,
    "MAX_DOCUMENTS_PAR_PROJET": 50,
}


def _borne(env, nom):
    return getattr(env["routes"], nom, _BORNES_PAR_DEFAUT[nom])


def _chunks_du_projet(chroma, project_id):
    coll = chroma.get_collection(rag_service.COLLECTIONS["technical"]["name"])
    return coll.get(where={"project_id": str(project_id)})


# ---------------------------------------------------------------------------
# 1. Borne avant lecture du corps — mesurée
# ---------------------------------------------------------------------------

def _appel_asgi_multipart(project_id, jeton, taille_fichier, annoncer_longueur=True):
    """POST multipart en ASGI direct. Rend (statut, octets lus avant réponse,
    pic tracemalloc en octets, corps de réponse).

    Fusion vague 2 (24/10) : « octets lus » = octets TIRÉS DU CLIENT par
    `receive` avant le début de la réponse. L'ancien compteur instrumentait
    `Request.stream` : depuis Starlette 1.x (montée de la file B), chaque
    `BaseHTTPMiddleware` (audit, contexte, BUILD) fait transiter le corps par
    son propre `Request.stream` — mesuré : 21 037 170 octets lus par la route,
    comptés 4 fois = 84 148 680. Le receive brut compte chaque octet une fois."""
    entete = (
        b"--" + FRONTIERE + b"\r\n"
        b'Content-Disposition: form-data; name="file"; filename="gros.txt"\r\n'
        b"Content-Type: text/plain\r\n\r\n"
    )
    pied = b"\r\n--" + FRONTIERE + b"--\r\n"
    plein = b"a" * MORCEAU  # un seul objet réutilisé : le client n'alloue rien
    morceaux = [entete]
    reste = taille_fichier
    while reste > 0:
        n = min(MORCEAU, reste)
        morceaux.append(plein if n == MORCEAU else b"a" * n)
        reste -= n
    morceaux.append(pied)
    total = sum(len(m) for m in morceaux)

    entetes = [
        (b"host", b"testserver"),
        (b"authorization", jeton.encode()),
        (b"content-type", b"multipart/form-data; boundary=" + FRONTIERE),
    ]
    if annoncer_longueur:
        entetes.append((b"content-length", str(total).encode()))
    scope = {
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
        "method": "POST", "scheme": "http",
        "path": f"/api/projects/{project_id}/documents",
        "raw_path": f"/api/projects/{project_id}/documents".encode(),
        "query_string": b"collection_name=technical", "root_path": "",
        "headers": entetes, "client": ("127.0.0.1", 50000), "server": ("testserver", 80),
    }
    etat = {"i": 0, "lus_avant_reponse": 0, "statut": None, "corps": b"", "repondu": False}

    async def receive():
        if etat["i"] >= len(morceaux):
            await asyncio.sleep(0)
            return {"type": "http.disconnect"}
        m = morceaux[etat["i"]]
        etat["i"] += 1
        if not etat["repondu"]:
            etat["lus_avant_reponse"] += len(m)
        return {"type": "http.request", "body": m, "more_body": etat["i"] < len(morceaux)}

    async def send(message):
        if message["type"] == "http.response.start":
            etat["repondu"] = True
            etat["statut"] = message["status"]
        elif message["type"] == "http.response.body":
            etat["corps"] += message.get("body", b"")

    from starlette.requests import Request

    stream_original = Request.stream
    lus_par_l_application = {"octets": 0}

    async def stream_compte(self):
        async for morceau in stream_original(self):
            lus_par_l_application["octets"] += len(morceau)
            yield morceau

    Request.stream = stream_compte
    # Mise en route (fusion vague 2, 24/10) : le premier appel de l'application
    # paie ~3 Mo d'initialisation paresseuse (FastAPI 0.162 / Starlette 1.x),
    # quel que soit le test lancé en premier — mesuré : refus à froid 3 165 950
    # octets, à chaud 122 577. On mesure le traitement du corps, pas l'amorçage :
    # un appel refusé sur l'en-tête, sans corps, est joué avant la mesure.
    scope_amorce = dict(scope, headers=[h for h in entetes if h[0] != b"content-length"]
                        + [(b"content-length", str(10 ** 12).encode())])

    async def receive_vide():
        return {"type": "http.disconnect"}

    async def send_ignore(message):
        pass

    try:
        asyncio.run(app(scope_amorce, receive_vide, send_ignore))
    except Exception:  # noqa: BLE001 — l'amorce ne juge rien ; les assertions jugent
        pass
    tracemalloc.start()
    try:
        asyncio.run(app(scope, receive, send))
        _, pic = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
        Request.stream = stream_original
    print(f"[MESURE PROD-09] octets_recus_avant_reponse (receive brut, information)={etat['lus_avant_reponse']}")
    print(f"[MESURE PROD-09] Request.stream cumule sur toutes les couches (information)={lus_par_l_application['octets']}")
    return etat["statut"], etat["lus_avant_reponse"], pic, etat["corps"], total


def test_upload_au_dela_du_plafond_refuse_avant_lecture_du_corps(env):
    plafond = env["routes"].MAX_FILE_SIZE
    taille = plafond + 4 * MIO
    statut, lus, pic, corps, total = _appel_asgi_multipart(
        env["a"]["project"].id, env["a"]["headers"]["Authorization"], taille
    )
    print(f"[MESURE PROD-09 longueur annoncee] corps={total} statut={statut} "
          f"octets_lus_par_l_application={lus} pic_tracemalloc={pic}")
    assert statut == 413, corps[:300]
    assert lus == 0, f"{lus} octets du corps lus avant de refuser (corps de {total})"
    assert pic < 2 * MIO, f"pic mémoire {pic} octets pendant un refus de {total} octets"
    assert not list(env["docs"].rglob("*")) or all(p.is_dir() for p in env["docs"].rglob("*"))


def test_upload_sans_longueur_annoncee_coupe_au_plafond(env):
    """Corps en flux sans Content-Length : la lecture s'arrête au plafond."""
    plafond = env["routes"].MAX_FILE_SIZE
    marge = _borne(env, "MARGE_MULTIPART")
    taille = plafond + 8 * MIO
    statut, lus, pic, corps, total = _appel_asgi_multipart(
        env["a"]["project"].id, env["a"]["headers"]["Authorization"], taille, annoncer_longueur=False
    )
    print(f"[MESURE PROD-09 flux sans longueur] corps={total} statut={statut} "
          f"octets_lus_par_l_application={lus} pic_tracemalloc={pic}")
    assert statut == 413, corps[:300]
    assert lus <= plafond + marge + MORCEAU, f"{lus} octets lus pour un plafond de {plafond}"
    assert pic < 4 * MIO, f"pic mémoire {pic} octets"
    assert env["db"].query(ProjectDocument).count() == 0


def test_fichier_d_un_octet_de_trop_refuse_meme_sous_la_marge_multipart(env):
    """Le plafond porte sur le FICHIER, pas seulement sur le corps."""
    plafond = env["routes"].MAX_FILE_SIZE
    statut, _, _, corps, _ = _appel_asgi_multipart(
        env["a"]["project"].id, env["a"]["headers"]["Authorization"], plafond + 1
    )
    assert statut == 413, corps[:300]
    assert env["db"].query(ProjectDocument).count() == 0


def test_controle_negatif_un_petit_fichier_passe(env):
    r = env["client"].post(
        f"/api/projects/{env['a']['project'].id}/documents",
        files={"file": ("petit.txt", b"Exigence : partage par territoire. " * 20, "text/plain")},
        headers=env["a"]["headers"],
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "ready"
    assert len(_chunks_du_projet(env["chroma"], env["a"]["project"].id)["ids"]) == r.json()["chunk_count"] >= 1


# ---------------------------------------------------------------------------
# 2. Collisions de nom
# ---------------------------------------------------------------------------

def test_deux_uploads_de_meme_nom_ne_partagent_pas_le_fichier(env):
    client, a = env["client"], env["a"]
    url = f"/api/projects/{a['project'].id}/documents"
    r1 = client.post(url, files={"file": ("notes.txt", b"PREMIER contenu " * 10, "text/plain")}, headers=a["headers"])
    r2 = client.post(url, files={"file": ("notes.txt", b"SECOND contenu " * 10, "text/plain")}, headers=a["headers"])
    assert r1.status_code == r2.status_code == 200, (r1.text, r2.text)

    db = env["db"]
    d1 = db.query(ProjectDocument).get(r1.json()["id"])
    d2 = db.query(ProjectDocument).get(r2.json()["id"])
    assert d1.filename == d2.filename == "notes.txt"
    assert d1.file_path != d2.file_path, "deux documents pointent le même fichier disque"

    rd = client.delete(f"{url}/{d1.id}", headers=a["headers"])
    assert rd.status_code == 200, rd.text
    from pathlib import Path
    assert Path(d2.file_path).exists(), "supprimer le premier a supprimé le fichier du second"
    assert Path(d2.file_path).read_bytes().startswith(b"SECOND")


# ---------------------------------------------------------------------------
# 3. Parseur absent : refus explicite, pas de binaire lu comme du texte
# ---------------------------------------------------------------------------

def _pdf_minimal(texte: str) -> bytes:
    flux = f"BT /F1 12 Tf 72 712 Td ({texte}) Tj ET".encode()
    objets = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(flux) + flux + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    sortie = b"%PDF-1.4\n"
    positions = []
    for i, objet in enumerate(objets, 1):
        positions.append(len(sortie))
        sortie += b"%d 0 obj\n" % i + objet + b"\nendobj\n"
    xref = len(sortie)
    sortie += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objets) + 1)
    for p in positions:
        sortie += b"%010d 00000 n \n" % p
    sortie += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objets) + 1, xref)
    return sortie


def test_pdf_lu_par_un_vrai_parseur_pas_comme_du_binaire(env):
    a = env["a"]
    r = env["client"].post(
        f"/api/projects/{a['project'].id}/documents",
        files={"file": ("spec.pdf", _pdf_minimal("SENTINELLE PDF PROD09"), "application/pdf")},
        headers=a["headers"],
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "ready", r.text
    textes = " ".join(_chunks_du_projet(env["chroma"], a["project"].id)["documents"])
    assert "SENTINELLE PDF PROD09" in textes
    assert "endobj" not in textes and "%PDF" not in textes, f"binaire PDF ingéré comme texte : {textes[:200]!r}"


def test_parseur_pdf_absent_refus_explicite_rien_ingere(env, monkeypatch):
    for module in ("fitz", "PyPDF2", "pypdf"):
        monkeypatch.setitem(sys.modules, module, None)  # import -> ImportError
    a = env["a"]
    r = env["client"].post(
        f"/api/projects/{a['project'].id}/documents",
        files={"file": ("spec.pdf", _pdf_minimal("NE DOIT PAS ENTRER"), "application/pdf")},
        headers=a["headers"],
    )
    assert r.status_code == 503, r.text
    assert "PDF" in r.json()["detail"]
    assert _chunks_du_projet(env["chroma"], a["project"].id)["ids"] == []
    assert env["db"].query(ProjectDocument).count() == 0
    assert [p for p in env["docs"].rglob("*") if p.is_file()] == []


def test_docx_dont_le_contenu_decompresse_depasse_la_borne_refuse(env):
    """Bombe de décompression : petit .docx, énorme une fois décompressé."""
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w", zipfile.ZIP_DEFLATED) as zf:
        with zf.open("word/document.xml", "w") as f:
            zero = b"\0" * MIO
            for _ in range(_borne(env, "MAX_OCTETS_DECOMPRESSES") // MIO + 1):
                f.write(zero)
    contenu = tampon.getvalue()
    assert len(contenu) < 2 * MIO
    a = env["a"]
    r = env["client"].post(
        f"/api/projects/{a['project'].id}/documents",
        files={"file": ("bombe.docx", contenu, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        headers=a["headers"],
    )
    assert r.status_code == 422, r.text
    assert env["db"].query(ProjectDocument).count() == 0


# ---------------------------------------------------------------------------
# 4. Ingestion proportionnée : texte borné, lots bornés
# ---------------------------------------------------------------------------

def test_texte_extrait_au_dela_de_la_borne_refuse_sans_aucun_embedding(env, monkeypatch):
    appels = []
    monkeypatch.setattr(rag_service, "get_openai_embedding", lambda t: appels.append(1) or [0.0] * 8)
    borne = _borne(env, "MAX_CARACTERES_EXTRAITS")
    a = env["a"]
    r = env["client"].post(
        f"/api/projects/{a['project'].id}/documents",
        files={"file": ("long.txt", b"x" * (borne + 1), "text/plain")},
        headers=a["headers"],
    )
    assert r.status_code == 422, r.text[:300]
    assert appels == [], f"{len(appels)} embeddings calculés pour un document refusé"
    assert env["db"].query(ProjectDocument).count() == 0


def test_ingestion_par_lots_bornes(env, monkeypatch):
    from chromadb.api.models.Collection import Collection

    tailles = []
    original = Collection.upsert

    def espion(self, *args, **kwargs):
        tailles.append(len(kwargs.get("ids") or args[0]))
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Collection, "upsert", espion)
    a = env["a"]
    texte = "".join(f"paragraphe {i:05d} " for i in range(30000)).encode()  # ~ 540 000 caractères
    r = env["client"].post(
        f"/api/projects/{a['project'].id}/documents",
        files={"file": ("moyen.txt", texte, "text/plain")},
        headers=a["headers"],
    )
    assert r.status_code == 200, r.text[:300]
    n = r.json()["chunk_count"]
    assert n > getattr(rag_service, "TAILLE_LOT_INGESTION", 100)
    assert sum(tailles) == n
    assert max(tailles) <= getattr(rag_service, "TAILLE_LOT_INGESTION", 100), f"upsert de {max(tailles)} chunks d'un coup"


def test_ingestion_en_echec_au_milieu_ne_laisse_aucun_chunk(env, monkeypatch):
    """Avec des lots, un échec au milieu laisserait des lots déjà écrits :
    ils sont retirés, le document est en erreur."""
    compteur = {"n": 0}

    def embedding_qui_casse(texte):
        compteur["n"] += 1
        if compteur["n"] > getattr(rag_service, "TAILLE_LOT_INGESTION", 100) + 5:
            raise RuntimeError("429 credit_balance_exhausted (injecte)")
        return [0.1] * 8

    monkeypatch.setattr(rag_service, "get_openai_embedding", embedding_qui_casse)
    a = env["a"]
    texte = "".join(f"ligne {i:05d} " for i in range(30000)).encode()
    r = env["client"].post(
        f"/api/projects/{a['project'].id}/documents",
        files={"file": ("casse.txt", texte, "text/plain")},
        headers=a["headers"],
    )
    assert r.json()["status"] == "error", r.text[:300]
    assert _chunks_du_projet(env["chroma"], a["project"].id)["ids"] == []


# ---------------------------------------------------------------------------
# 5. Quota de stockage par projet, indépendant des jetons
# ---------------------------------------------------------------------------

def test_quota_d_octets_du_projet_refuse_l_upload_suivant(env):
    db, a, routes = env["db"], env["a"], env["routes"]
    db.add(ProjectDocument(project_id=a["project"].id, filename="deja.pdf", file_path="/nulle/part",
                           file_size=_borne(env, "MAX_OCTETS_PAR_PROJET") - 10, status="ready"))
    db.commit()
    r = env["client"].post(
        f"/api/projects/{a['project'].id}/documents",
        files={"file": ("encore.txt", b"y" * 100, "text/plain")},
        headers=a["headers"],
    )
    assert r.status_code == 413, r.text
    assert "quota" in r.json()["detail"].lower()
    assert db.query(ProjectDocument).count() == 1


def test_quota_de_documents_du_projet(env):
    db, a, routes = env["db"], env["a"], env["routes"]
    for i in range(_borne(env, "MAX_DOCUMENTS_PAR_PROJET")):
        db.add(ProjectDocument(project_id=a["project"].id, filename=f"d{i}.txt", file_path="/nulle/part",
                               file_size=1, status="ready"))
    db.commit()
    r = env["client"].post(
        f"/api/projects/{a['project'].id}/documents",
        files={"file": ("un_de_plus.txt", b"z" * 100, "text/plain")},
        headers=a["headers"],
    )
    assert r.status_code == 413, r.text
    assert "quota" in r.json()["detail"].lower()
