"""
Service des droits RGPD d'un compte — vague B, lot B4.

Trois droits couverts :
  - art. 15 (accès) et art. 20 (portabilité) : `exporter(user)` rend en JSON
    tout ce que la plateforme détient sur un compte ;
  - art. 17 (effacement) : `supprimer(user)` efface ce qui peut l'être et
    anonymise ce qui doit être conservé.

L'inventaire table par table qui commande ce service est dans
`docs/vague-b/INVENTAIRE_DONNEES_PERSONNELLES.md`.

Pourquoi une anonymisation et non un `DELETE FROM users`
--------------------------------------------------------
`credit_transactions.user_id` est `nullable=False` avec
`ForeignKey("users.id", ondelete="CASCADE")` (app/models/credit.py:78-82).
Supprimer la ligne `users` détruirait le grand livre des crédits, qui doit être
conservé au titre des obligations comptables (art. L123-22 du code de commerce,
base légale art. 6.1.c RGPD). Changer cette clé étrangère demanderait une
migration Alembic, hors périmètre du lot.

La ligne `users` est donc conservée, vidée de toute donnée identifiante :
e-mail réécrit en `compte-supprime-<id>@anonymised.invalid`, nom remplacé,
empreinte de mot de passe rendue inutilisable, compte désactivé. Le TLD
`.invalid` est réservé par la RFC 6761 : il ne résout jamais et ne désigne
aucun service (règle 9 de la mission).

Art. 22 : hors périmètre (décision D11 de Sam du 30/08).
"""
import logging
import secrets
from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Session

from app.config import settings
from app.models.audit import AuditLog
from app.models.business_requirement import BusinessRequirement
from app.models.change_request import ChangeRequest
from app.models.chat_log import ChatLog
from app.models.credit import CreditBalance, CreditTransaction
from app.models.execution import Execution
from app.models.output import Output
from app.models.project import Project
from app.models.project_conversation import ProjectConversation
from app.models.project_document import ProjectDocument
from app.models.sds_template import SDSTemplate
from app.models.sds_version import SDSVersion
from app.models.task_execution import TaskExecution
from app.models.user import User

logger = logging.getLogger(__name__)

# Marqueur d'anonymisation. `.invalid` est réservé par la RFC 6761.
DOMAINE_ANONYME = "anonymised.invalid"
NOM_ANONYME = "Compte supprimé"
ACTEUR_ANONYME = "compte-supprime"


def est_anonymise(utilisateur: User) -> bool:
    """Vrai si la ligne `users` a déjà été vidée par un effacement RGPD."""
    return bool(utilisateur.email) and utilisateur.email.endswith(f"@{DOMAINE_ANONYME}")


def _valeur_exportable(valeur: Any) -> Any:
    """Rend une valeur de colonne sérialisable en JSON."""
    if isinstance(valeur, (datetime, date)):
        return valeur.isoformat()
    if isinstance(valeur, Decimal):
        return float(valeur)
    if isinstance(valeur, Enum):
        return valeur.value
    return valeur


def _ligne_en_dict(ligne: Any) -> Dict[str, Any]:
    """Sérialise une ligne ORM, colonne par colonne, sans rien omettre."""
    return {
        colonne.key: _valeur_exportable(getattr(ligne, colonne.key))
        for colonne in sa_inspect(ligne).mapper.column_attrs
    }


def _racines_de_fichiers() -> List[Path]:
    """Racines sous lesquelles un fichier de compte peut être effacé.

    Règle 10 : un `file_path` stocké en base peut venir d'une autre
    installation. On n'efface que ce qui se trouve sous une racine
    effectivement configurée, jamais un chemin absolu arbitraire.
    """
    racines = []
    for brut in (
        settings.UPLOAD_DIR,
        settings.OUTPUT_DIR,
        settings.METADATA_DIR,
        settings.DELIVERABLES_DIR,
    ):
        try:
            racines.append(Path(str(brut)).resolve())
        except OSError:  # racine inaccessible : on ne l'utilise pas
            continue
    return racines


class AccountService:
    """Droits RGPD d'accès, de portabilité et d'effacement sur un compte."""

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # Art. 15 + 20 — export
    # ------------------------------------------------------------------

    def exporter(self, utilisateur: User) -> Dict[str, Any]:
        """Rend tout ce que la plateforme détient sur ce compte."""
        projets = (
            self.db.query(Project).filter(Project.user_id == utilisateur.id).all()
        )
        ids_projets = [p.id for p in projets]

        executions = (
            self.db.query(Execution).filter(Execution.user_id == utilisateur.id).all()
        )
        ids_executions = [e.id for e in executions]

        transactions = (
            self.db.query(CreditTransaction)
            .filter(CreditTransaction.user_id == utilisateur.id)
            .order_by(CreditTransaction.id)
            .all()
        )
        solde = (
            self.db.query(CreditBalance)
            .filter(CreditBalance.user_id == utilisateur.id)
            .first()
        )

        documents = self._par_projet(ProjectDocument, ids_projets)
        conversations_projet = self._par_projet(ProjectConversation, ids_projets)
        exigences = self._par_projet(BusinessRequirement, ids_projets)
        demandes_changement = self._par_projet(ChangeRequest, ids_projets)
        versions_sds = self._par_projet(SDSVersion, ids_projets)
        livrables = self._par_projet(Output, ids_projets)

        conversations_vitrine = self._chat_logs_du_compte(utilisateur.email)

        journal = (
            self.db.query(AuditLog)
            .filter(AuditLog.actor_id == str(utilisateur.id))
            .all()
        )

        return {
            "genere_le": datetime.utcnow().isoformat(),
            "base_legale": "RGPD art. 15 (accès) et art. 20 (portabilité)",
            "compte": {
                "id": utilisateur.id,
                "email": utilisateur.email,
                "nom": utilisateur.name,
                "actif": utilisateur.is_active,
                "tier": utilisateur.subscription_tier,
                "cree_le": _valeur_exportable(utilisateur.created_at),
                "abonnement_debute_le": _valeur_exportable(
                    utilisateur.subscription_started_at
                ),
                "abonnement_expire_le": _valeur_exportable(
                    utilisateur.subscription_expires_at
                ),
                "identifiant_client_stripe": utilisateur.stripe_customer_id,
            },
            "projets": [_ligne_en_dict(p) for p in projets],
            "executions": [_ligne_en_dict(e) for e in executions],
            "transactions_credits": [_ligne_en_dict(t) for t in transactions],
            "solde_credits": _ligne_en_dict(solde) if solde else None,
            "documents_projet": [_ligne_en_dict(d) for d in documents],
            "conversations_projet": [_ligne_en_dict(c) for c in conversations_projet],
            "exigences_metier": [_ligne_en_dict(b) for b in exigences],
            "demandes_de_changement": [_ligne_en_dict(c) for c in demandes_changement],
            "versions_sds": [_ligne_en_dict(v) for v in versions_sds],
            "livrables": [_ligne_en_dict(o) for o in livrables],
            "conversations_vitrine": [
                _ligne_en_dict(c) for c in conversations_vitrine
            ],
            "journal_audit": [_ligne_en_dict(a) for a in journal],
            "hors_base": {
                "chromadb": (
                    "Les chunks des documents du compte sont identifiés par la "
                    "métadonnée document_id dans les cinq collections globales "
                    "(technical, operations, business, apex, lwc). Ils sont "
                    "purgés à la suppression du compte."
                ),
                "stripe": (
                    "Les pièces de facturation détenues par Stripe ne sont pas "
                    "incluses : elles relèvent de Stripe, sous-traitant au sens "
                    "de l'art. 28."
                ),
            },
            "compteurs": {
                "projets": len(projets),
                "executions": len(ids_executions),
                "transactions_credits": len(transactions),
                "conversations_vitrine": len(conversations_vitrine),
            },
        }

    # ------------------------------------------------------------------
    # Art. 17 — effacement
    # ------------------------------------------------------------------

    def supprimer(self, utilisateur: User) -> Dict[str, Any]:
        """Efface le compte : suppression de ce qui peut l'être, anonymisation
        de ce qui doit être conservé.

        L'ordre compte :
          1. purge Chroma et fichiers — ils ne sont plus atteignables une fois
             les lignes parties ;
          2. `task_executions` d'abord : sa clé étrangère vers `executions`
             n'a **pas** d'`ondelete` (app/models/task_execution.py:34), elle
             bloquerait la suppression en cascade des exécutions ;
          3. projets — la cascade emporte exécutions, livrables, exigences,
             conversations, identifiants chiffrés et environnements ;
          4. anonymisation de `users`, du journal d'audit et détachement des
             gabarits de SDS.
        """
        projets = (
            self.db.query(Project).filter(Project.user_id == utilisateur.id).all()
        )
        ids_projets = [p.id for p in projets]

        # Deux chemins vers une exécution : elle porte `user_id`, et elle pend
        # d'un projet. On prend l'union des deux pour n'en oublier aucune.
        ids_executions = {
            ligne[0]
            for ligne in self.db.query(Execution.id)
            .filter(Execution.user_id == utilisateur.id)
            .all()
        }
        if ids_projets:
            ids_executions |= {
                ligne[0]
                for ligne in self.db.query(Execution.id)
                .filter(Execution.project_id.in_(ids_projets))
                .all()
            }
        ids_executions = sorted(ids_executions)

        documents = self._par_projet(ProjectDocument, ids_projets)

        # 1. Hors base, avant que les lignes qui les désignent ne disparaissent.
        chunks_supprimes = self._purger_chroma(documents)
        fichiers_supprimes, fichiers_ignores = self._purger_fichiers(
            ids_projets, ids_executions, documents
        )

        # 2. task_executions : pas d'ondelete, à supprimer explicitement.
        supprimes_taches = 0
        if ids_executions:
            supprimes_taches = (
                self.db.query(TaskExecution)
                .filter(TaskExecution.execution_id.in_(ids_executions))
                .delete(synchronize_session=False)
            )

        # 3. Projets, puis exécutions restantes. Les cascades de la base font
        #    le reste (voir l'inventaire, colonne « Rattachement »).
        supprimes_projets = (
            self.db.query(Project)
            .filter(Project.user_id == utilisateur.id)
            .delete(synchronize_session=False)
        )
        supprimes_executions = (
            self.db.query(Execution)
            .filter(Execution.user_id == utilisateur.id)
            .delete(synchronize_session=False)
        )

        # 4. Solde de crédits : état courant, pas pièce comptable.
        supprimes_soldes = (
            self.db.query(CreditBalance)
            .filter(CreditBalance.user_id == utilisateur.id)
            .delete(synchronize_session=False)
        )

        # 5. Conversations du site vitrine : la session entière, pas seulement
        #    le tour qui porte l'e-mail.
        supprimes_chat = self._supprimer_chat_logs(utilisateur.email)

        # 6. Journal d'audit : la trace reste, les champs identifiants partent.
        anonymises_audit = (
            self.db.query(AuditLog)
            .filter(AuditLog.actor_id == str(utilisateur.id))
            .update(
                {
                    AuditLog.actor_id: ACTEUR_ANONYME,
                    AuditLog.actor_name: None,
                    AuditLog.ip_address: None,
                    AuditLog.user_agent: None,
                },
                synchronize_session=False,
            )
        )

        # 7. Attributions restantes vers ce compte, dans des projets tiers.
        self.db.query(SDSTemplate).filter(
            SDSTemplate.created_by == utilisateur.id
        ).update({SDSTemplate.created_by: None}, synchronize_session=False)
        self.db.query(BusinessRequirement).filter(
            BusinessRequirement.validated_by == utilisateur.id
        ).update({BusinessRequirement.validated_by: None}, synchronize_session=False)
        self.db.query(ChangeRequest).filter(
            ChangeRequest.created_by == utilisateur.id
        ).update({ChangeRequest.created_by: None}, synchronize_session=False)

        # 8. Anonymisation de la ligne users.
        transactions_conservees = (
            self.db.query(CreditTransaction)
            .filter(CreditTransaction.user_id == utilisateur.id)
            .count()
        )
        utilisateur.email = f"compte-supprime-{utilisateur.id}@{DOMAINE_ANONYME}"
        utilisateur.name = NOM_ANONYME
        # Empreinte inutilisable : aucun mot de passe ne peut y correspondre.
        utilisateur.hashed_password = f"!compte-supprime!{secrets.token_hex(16)}"
        utilisateur.is_active = False

        self.db.commit()

        logger.info(
            "RGPD art.17 : compte %s effacé — %s projets, %s exécutions, "
            "%s conversations vitrine supprimées ; %s transactions conservées",
            utilisateur.id,
            supprimes_projets,
            supprimes_executions,
            supprimes_chat,
            transactions_conservees,
        )

        return {
            "statut": "compte supprimé",
            "base_legale": "RGPD art. 17 (droit à l'effacement)",
            "user_id": utilisateur.id,
            "supprime": {
                "projets": supprimes_projets,
                "executions": supprimes_executions,
                "taches_build": supprimes_taches,
                "soldes_credits": supprimes_soldes,
                "conversations_vitrine": supprimes_chat,
            },
            "anonymise": {
                "compte": True,
                "lignes_journal_audit": anonymises_audit,
            },
            "conserve": {
                "transactions_credits": transactions_conservees,
                "justification": (
                    "Pièces comptables — art. L123-22 du code de commerce, "
                    "base légale RGPD art. 6.1.c. Elles ne portent plus aucune "
                    "donnée identifiante une fois le compte anonymisé."
                ),
            },
            "chunks_chroma_supprimes": chunks_supprimes,
            "fichiers_supprimes": fichiers_supprimes,
            "fichiers_ignores": fichiers_ignores,
        }

    # ------------------------------------------------------------------
    # Outils internes
    # ------------------------------------------------------------------

    def _par_projet(self, modele, ids_projets: List[int]) -> List[Any]:
        if not ids_projets:
            return []
        return self.db.query(modele).filter(modele.project_id.in_(ids_projets)).all()

    def _sessions_vitrine(self, email: Optional[str]) -> List[str]:
        """UUID des sessions du site vitrine où ce compte a laissé son e-mail."""
        if not email:
            return []
        lignes = (
            self.db.query(ChatLog.session_uuid)
            .filter(ChatLog.email_collected == email)
            .distinct()
            .all()
        )
        return [ligne[0] for ligne in lignes]

    def _chat_logs_du_compte(self, email: Optional[str]) -> List[ChatLog]:
        sessions = self._sessions_vitrine(email)
        if not sessions:
            return []
        return (
            self.db.query(ChatLog)
            .filter(ChatLog.session_uuid.in_(sessions))
            .order_by(ChatLog.id)
            .all()
        )

    def _supprimer_chat_logs(self, email: Optional[str]) -> int:
        sessions = self._sessions_vitrine(email)
        if not sessions:
            return 0
        return (
            self.db.query(ChatLog)
            .filter(ChatLog.session_uuid.in_(sessions))
            .delete(synchronize_session=False)
        )

    def _purger_chroma(self, documents: List[ProjectDocument]) -> int:
        """Supprime les chunks des documents du compte.

        Les collections ChromaDB ne sont **pas** nommées par projet : elles
        sont cinq, globales, et l'isolation se fait par la métadonnée
        `document_id` du chunk (rag_service.py:47-53 et 418-425). La seule
        fonction de suppression disponible est
        `delete_project_document_chunks(collection, document_id)` ;
        `rag_service` est en lecture seule pour ce lot.
        """
        if not documents:
            return 0
        from app.services import rag_service

        total = 0
        for document in documents:
            collection = document.collection_name or "technical"
            try:
                total += rag_service.delete_project_document_chunks(
                    collection, document.id
                )
            except Exception as exc:  # noqa: BLE001
                # Pas de repli silencieux (règle 6) : on trace et on continue,
                # la suppression en base ne doit pas être bloquée par le RAG.
                logger.error(
                    "RGPD art.17 : purge Chroma impossible pour le document %s "
                    "dans la collection %s : %s",
                    document.id,
                    collection,
                    exc,
                )
        return total

    def _purger_fichiers(
        self,
        ids_projets: List[int],
        ids_executions: List[int],
        documents: List[ProjectDocument],
    ):
        """Efface les fichiers du compte situés sous une racine configurée."""
        chemins: List[str] = [d.file_path for d in documents if d.file_path]

        if ids_projets:
            for projet in (
                self.db.query(Project).filter(Project.id.in_(ids_projets)).all()
            ):
                if projet.requirements_file_path:
                    chemins.append(projet.requirements_file_path)
            for livrable in (
                self.db.query(Output).filter(Output.project_id.in_(ids_projets)).all()
            ):
                if livrable.file_path:
                    chemins.append(livrable.file_path)
            for version in (
                self.db.query(SDSVersion)
                .filter(SDSVersion.project_id.in_(ids_projets))
                .all()
            ):
                if version.file_path:
                    chemins.append(version.file_path)
        if ids_executions:
            for execution in (
                self.db.query(Execution)
                .filter(Execution.id.in_(ids_executions))
                .all()
            ):
                if execution.sds_document_path:
                    chemins.append(execution.sds_document_path)

        racines = _racines_de_fichiers()
        supprimes: List[str] = []
        ignores: List[str] = []

        for brut in dict.fromkeys(chemins):  # dédoublonne en gardant l'ordre
            try:
                chemin = Path(brut).resolve()
            except OSError:
                ignores.append(brut)
                continue
            if not any(self._sous_racine(chemin, racine) for racine in racines):
                # Règle 10 : un chemin hors des racines configurées vient d'une
                # autre installation. On le signale, on n'efface pas.
                logger.warning(
                    "RGPD art.17 : chemin hors des racines configurées, non "
                    "supprimé : %s",
                    brut,
                )
                ignores.append(brut)
                continue
            try:
                if chemin.is_file():
                    chemin.unlink()
                    supprimes.append(str(chemin))
            except OSError as exc:
                logger.error(
                    "RGPD art.17 : suppression du fichier %s impossible : %s",
                    chemin,
                    exc,
                )
                ignores.append(brut)

        return supprimes, ignores

    @staticmethod
    def _sous_racine(chemin: Path, racine: Path) -> bool:
        try:
            chemin.relative_to(racine)
            return True
        except ValueError:
            return False
