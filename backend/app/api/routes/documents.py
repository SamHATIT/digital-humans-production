"""
Document Upload API Routes — P3: RAG Project Isolation.

Allows users to upload PDF/DOCX/TXT files to a project's RAG context.
Documents are chunked and ingested into ChromaDB with project_id metadata
so that agents only see context from their own project.
"""
import logging
import shutil
import uuid
import zipfile
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile as StarletteUploadFile
from starlette.formparsers import MultiPartException, MultiPartParser

from app.database import get_db
from app.config import settings
from app.models.project import Project
from app.models.project_document import ProjectDocument
from app.models.user import User
from app.utils.feature_access import ensure_feature
from app.api.routes.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects", tags=["Documents"])

# Allowed file extensions and their MIME types
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md", ".csv"}

# ---------------------------------------------------------------------------
# VAGUE 2 / FILE A — PROD-09 (audit Astra du 06/09, L510) : bornes d'upload et
# d'ingestion. Chaque valeur est nommee ici ; celles qui ne viennent pas du code
# existant (20 Mo) sont a confirmer par Sam (rapport RAPPORT_VAGUE2_A.md).
# ---------------------------------------------------------------------------
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB — plafond du FICHIER (inchange)
# Enveloppe multipart (frontiere, en-tetes de partie) toleree au-dela du
# fichier pour le plafond du CORPS, controle avant toute lecture.
MARGE_MULTIPART = 64 * 1024
# Texte extrait maximal : borne le nombre de chunks (~2 500 a 1 000/200) et
# donc d'appels d'embedding par document.
MAX_CARACTERES_EXTRAITS = 2_000_000
MAX_PAGES_PDF = 500
# Taille decompressee maximale d'un .docx (archive zip) : bombe de decompression.
MAX_OCTETS_DECOMPRESSES = 100 * 1024 * 1024
# Quota de stockage par projet, independant des jetons de generation.
MAX_DOCUMENTS_PAR_PROJET = 50
MAX_OCTETS_PAR_PROJET = 200 * 1024 * 1024

# Upload directory: <UPLOAD_DIR>/project_documents/<project_id>/
DOCUMENTS_DIR = Path(settings.UPLOAD_DIR) / "project_documents"


class DocumentRefuse(Exception):
    """Refus explicite d'un document (parseur absent, borne depassee...)."""

    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class _CorpsTropVolumineux(MultiPartException):
    """Levee depuis le flux borne : le parseur multipart ferme alors ses
    fichiers temporaires (il ne le fait que pour MultiPartException)."""


def _refus_taille() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        detail=f"Fichier trop volumineux (max {MAX_FILE_SIZE // 1024 // 1024} Mo)",
    )


def _get_project_or_404(project_id: int, user: User, db: Session) -> Project:
    """Get project belonging to current user or raise 404."""
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == user.id,
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _verifier_quota(project_id: int, taille_entrante: int, db: Session) -> None:
    """Quota par projet (nombre de documents, octets stockes)."""
    nombre, octets = db.query(
        func.count(ProjectDocument.id), func.coalesce(func.sum(ProjectDocument.file_size), 0)
    ).filter(ProjectDocument.project_id == project_id).one()
    if nombre >= MAX_DOCUMENTS_PAR_PROJET:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Quota du projet atteint : {MAX_DOCUMENTS_PAR_PROJET} documents au plus",
        )
    if int(octets) + taille_entrante > MAX_OCTETS_PAR_PROJET:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=(
                f"Quota de stockage du projet atteint : "
                f"{MAX_OCTETS_PAR_PROJET // 1024 // 1024} Mo au plus"
            ),
        )


async def _lire_fichier_borne(request: Request) -> StarletteUploadFile:
    """Lit le corps multipart SANS jamais depasser le plafond.

    PROD-09 : l'ancienne route declarait `UploadFile = File(...)` ; FastAPI
    analysait alors tout le corps avant d'appeler la fonction, puis
    `file.file.read()` le chargeait en memoire, et la taille n'etait controlee
    qu'ensuite. Ici :
      - un Content-Length au-dela du plafond est refuse (413) avant de lire un
        seul octet du corps ;
      - sans Content-Length (flux), la lecture s'arrete des que le plafond est
        franchi ;
      - le parseur multipart deverse le fichier sur disque au-dela de 1 Mo.
    """
    limite = MAX_FILE_SIZE + MARGE_MULTIPART
    longueur = request.headers.get("content-length")
    if longueur is not None:
        try:
            annoncee = int(longueur)
        except ValueError:
            raise HTTPException(status_code=400, detail="En-tete Content-Length invalide")
        if annoncee > limite:
            raise _refus_taille()

    if not request.headers.get("content-type", "").lower().startswith("multipart/form-data"):
        raise HTTPException(
            status_code=400, detail="Corps attendu : multipart/form-data avec un champ 'file'"
        )

    async def flux_borne():
        recus = 0
        async for morceau in request.stream():
            recus += len(morceau)
            if recus > limite:
                raise _CorpsTropVolumineux("corps au-dela du plafond")
            yield morceau

    parseur = MultiPartParser(request.headers, flux_borne(), max_files=1, max_fields=10)
    try:
        formulaire = await parseur.parse()
    except _CorpsTropVolumineux:
        raise _refus_taille()
    except MultiPartException as exc:
        raise HTTPException(status_code=400, detail=f"Corps multipart invalide : {exc.message}")

    fichier = formulaire.get("file")
    if not isinstance(fichier, StarletteUploadFile):
        await formulaire.close()
        raise HTTPException(status_code=400, detail="Champ 'file' manquant")
    return fichier


def _chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
    """Split text into overlapping chunks."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
    return [c for c in chunks if c.strip()]


def _extraire_pdf(file_path: Path) -> str:
    # PROD-09 : PyMuPDF (`fitz`) etait le seul parseur essaye, et son absence
    # faisait lire le PDF binaire comme du texte, ingere comme valide. Mesure
    # du 24/10 : `fitz` n'est installe ni dans le venv de production ni dans
    # celui des tests. PyPDF2 est declare dans requirements.txt et installe
    # dans les deux. Absent : refus explicite, rien n'est ingere.
    try:
        from PyPDF2 import PdfReader
    except ImportError:
        raise DocumentRefuse(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Lecture des PDF indisponible sur ce serveur (PyPDF2 absent) : "
            "document refuse, rien n'a ete enregistre.",
        )
    with open(file_path, "rb") as flux:
        lecteur = PdfReader(flux)
        if len(lecteur.pages) > MAX_PAGES_PDF:
            raise DocumentRefuse(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"PDF trop long : {len(lecteur.pages)} pages (max {MAX_PAGES_PDF})",
            )
        morceaux, total = [], 0
        for page in lecteur.pages:
            texte = page.extract_text() or ""
            morceaux.append(texte)
            total += len(texte)
            if total > MAX_CARACTERES_EXTRAITS:
                break  # l'appelant refuse : inutile d'extraire la suite
    return "\n".join(morceaux)


def _extraire_docx(file_path: Path) -> str:
    try:
        from docx import Document as DocxDocument
    except ImportError:
        raise DocumentRefuse(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Lecture des DOCX indisponible sur ce serveur (python-docx absent) : "
            "document refuse, rien n'a ete enregistre.",
        )
    try:
        with zipfile.ZipFile(file_path) as archive:
            decompresse = sum(info.file_size for info in archive.infolist())
    except zipfile.BadZipFile:
        raise DocumentRefuse(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "Fichier .docx illisible (archive invalide)"
        )
    if decompresse > MAX_OCTETS_DECOMPRESSES:
        raise DocumentRefuse(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Fichier .docx refuse : {decompresse} octets une fois decompresse "
            f"(max {MAX_OCTETS_DECOMPRESSES // 1024 // 1024} Mo)",
        )
    doc = DocxDocument(str(file_path))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def _extract_text(file_path: Path, content_type: str = "") -> str:
    """Extract plain text from uploaded file.

    Lecture bornee a MAX_CARACTERES_EXTRAITS + 1 caracteres : au-dela, le
    document est refuse par l'appelant, pas tronque en silence.
    """
    suffix = file_path.suffix.lower()

    if suffix in (".txt", ".md", ".csv"):
        with open(file_path, encoding="utf-8", errors="replace") as flux:
            return flux.read(MAX_CARACTERES_EXTRAITS + 1)
    if suffix == ".pdf":
        return _extraire_pdf(file_path)
    if suffix == ".docx":
        return _extraire_docx(file_path)
    # Inatteignable tant que ALLOWED_EXTENSIONS est controle avant : refus
    # plutot que lecture binaire comme texte.
    raise DocumentRefuse(400, f"Type de fichier '{suffix}' non pris en charge")


# ========================================
# ENDPOINTS
# ========================================

@router.post("/{project_id}/documents")
async def upload_document(
    project_id: int,
    request: Request,
    collection_name: str = "technical",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload a document to a project's RAG context.

    The file is saved, chunked, and ingested into ChromaDB with
    project_id metadata for isolation.

    Corps : multipart/form-data, champ `file` (inchange pour le frontend).
    PROD-09 : la route ne declare plus `UploadFile = File(...)`, qui faisait
    lire tout le corps avant le moindre controle ; elle lit le corps elle-meme,
    borne, apres l'authentification, la propriete du projet et le quota.
    """
    # BILL-05 (vague 1 / file A) : ce chemin secondaire ne portait pas sa
    # porte Free — la capacite se verifiait ailleurs, pas ici.
    ensure_feature(current_user, "upload_documents")
    await run_in_threadpool(_get_project_or_404, project_id, current_user, db)

    # Validate collection name
    from app.services.rag_service import COLLECTIONS
    if collection_name not in COLLECTIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown collection '{collection_name}'. Available: {', '.join(COLLECTIONS.keys())}",
        )

    # Quota avant lecture : un projet deja plein ne lit pas le corps.
    await run_in_threadpool(_verifier_quota, project_id, 0, db)

    fichier = await _lire_fichier_borne(request)
    try:
        return await run_in_threadpool(
            _enregistrer_et_ingerer, project_id, fichier, collection_name, db
        )
    finally:
        await fichier.close()


def _enregistrer_et_ingerer(
    project_id: int, fichier: StarletteUploadFile, collection_name: str, db: Session
) -> dict:
    # LOT-B (kim:SEC-03, cote ecriture) : le nom de fichier vient du client.
    # `Path(...).name` ne garde que le dernier segment, sans composante de
    # chemin. PROD-09 : il n'est plus utilise comme nom DISQUE (deux uploads
    # homonymes partageaient le meme fichier) ; il reste le nom affiche.
    safe_filename = Path(fichier.filename or "").name
    if not safe_filename:
        raise HTTPException(status_code=400, detail="Invalid file name")

    # Validate file extension
    ext = Path(safe_filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{ext}' not allowed. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # Taille exacte du fichier (le corps etait deja borne).
    fichier.file.seek(0, 2)
    taille = fichier.file.tell()
    fichier.file.seek(0)
    if taille > MAX_FILE_SIZE:
        raise _refus_taille()
    _verifier_quota(project_id, taille, db)

    # Nom disque genere : jamais derive du nom client, jamais partage.
    project_dir = DOCUMENTS_DIR / str(project_id)
    project_dir.mkdir(parents=True, exist_ok=True)
    file_path = project_dir / f"{uuid.uuid4().hex}{ext}"
    with open(file_path, "xb") as sortie:
        shutil.copyfileobj(fichier.file, sortie, 1024 * 1024)

    # Extraction AVANT tout enregistrement : un refus (parseur absent, borne
    # depassee) ne laisse ni ligne, ni fichier, ni chunk.
    erreur_extraction = None
    text = ""
    try:
        text = _extract_text(file_path, fichier.content_type or "")
        if len(text) > MAX_CARACTERES_EXTRAITS:
            raise DocumentRefuse(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"Texte extrait trop long (plus de {MAX_CARACTERES_EXTRAITS} caracteres) : "
                f"document refuse, rien n'a ete ingere",
            )
    except DocumentRefuse as refus:
        file_path.unlink(missing_ok=True)
        raise HTTPException(status_code=refus.status_code, detail=refus.detail)
    except Exception as e:  # fichier corrompu : trace sur le document, comme avant
        logger.error(f"Error extracting text from '{safe_filename}': {e}")
        erreur_extraction = str(e)[:500]

    # Create DB record
    doc = ProjectDocument(
        project_id=project_id,
        filename=safe_filename,
        file_path=str(file_path),
        file_size=taille,
        content_type=fichier.content_type,
        collection_name=collection_name,
        status="processing",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    if erreur_extraction is not None or not text.strip():
        doc.status = "error"
        doc.error_message = erreur_extraction or "No text could be extracted from file"
        db.commit()
        return {
            "id": doc.id,
            "filename": doc.filename,
            "status": "error",
            "error": doc.error_message[:200],
        }

    chunks = _chunk_text(text)
    from app.services.rag_service import delete_project_document_chunks, ingest_document

    try:
        chunk_count = ingest_document(
            collection_name=collection_name,
            chunks=chunks,
            metadata={"source": safe_filename, "project_id": str(project_id)},
            project_id=project_id,
            document_id=doc.id,
        )
    except Exception as e:
        logger.error(f"Error ingesting document '{safe_filename}': {e}")
        message = str(e)[:500]
        # Ingestion par lots : des lots ont pu etre ecrits avant l'echec. On
        # les retire ; si le retrait echoue aussi, on le dit sur le document.
        try:
            delete_project_document_chunks(collection_name, doc.id)
        except Exception as e2:
            logger.error(f"Partial chunks of document {doc.id} could not be removed: {e2}")
            message = f"{message} | chunks partiels non retires : {e2}"[:500]
        doc.status = "error"
        doc.error_message = message
        db.commit()
        return {
            "id": doc.id,
            "filename": doc.filename,
            "status": "error",
            "error": str(e)[:200],
        }

    doc.chunk_count = chunk_count
    doc.status = "ready"
    db.commit()

    logger.info(f"Document '{safe_filename}' ingested: {chunk_count} chunks into {collection_name} for project {project_id}")

    return {
        "id": doc.id,
        "filename": doc.filename,
        "file_size": doc.file_size,
        "collection_name": collection_name,
        "chunk_count": chunk_count,
        "status": "ready",
    }


@router.get("/{project_id}/documents")
def list_documents(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all documents uploaded to a project."""
    _get_project_or_404(project_id, current_user, db)

    docs = (
        db.query(ProjectDocument)
        .filter(ProjectDocument.project_id == project_id)
        .order_by(ProjectDocument.created_at.desc())
        .all()
    )

    return [
        {
            "id": d.id,
            "filename": d.filename,
            "file_size": d.file_size,
            "collection_name": d.collection_name,
            "chunk_count": d.chunk_count,
            "status": d.status,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in docs
    ]


@router.delete("/{project_id}/documents/{document_id}")
def delete_document(
    project_id: int,
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a document and its chunks from ChromaDB."""
    _get_project_or_404(project_id, current_user, db)

    doc = db.query(ProjectDocument).filter(
        ProjectDocument.id == document_id,
        ProjectDocument.project_id == project_id,
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Remove chunks from ChromaDB
    deleted_chunks = 0
    if doc.status == "ready" and doc.chunk_count and doc.chunk_count > 0:
        try:
            from app.services.rag_service import delete_project_document_chunks
            deleted_chunks = delete_project_document_chunks(doc.collection_name, document_id)
        except Exception as e:
            logger.error(f"Error deleting chunks for document {document_id}: {e}")

    # Remove file from disk
    try:
        file_path = Path(doc.file_path)
        if file_path.exists():
            file_path.unlink()
    except Exception as e:
        logger.warning(f"Could not delete file {doc.file_path}: {e}")

    # Remove DB record
    db.delete(doc)
    db.commit()

    logger.info(f"Document '{doc.filename}' deleted: {deleted_chunks} chunks removed from {doc.collection_name}")

    return {
        "deleted": True,
        "filename": doc.filename,
        "chunks_removed": deleted_chunks,
    }
