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
from app.models.effacement_compte import (
    STATUT_EN_COURS,
    STATUT_PARTIEL,
    STATUT_TERMINE,
    STATUTS_OUVERTS,
    EffacementCompte,
)

logger = logging.getLogger(__name__)


class EffacementIncomplet(RuntimeError):
    """RGPD-03 : l'effacement n'a pas abouti. Le compte reste bloqué, la
    tâche `effacements_comptes` est `partiel` et se reprend."""

    def __init__(self, effacement_id: int, cause: str):
        super().__init__(f"Effacement RGPD {effacement_id} incomplet : {cause}")
        self.effacement_id = effacement_id
        self.cause = cause


class EchecPurgeHorsBase(RuntimeError):
    """Une purge hors base (Chroma, fichiers) a échoué pour au moins un
    élément ; tous les éléments ont été tentés."""

    def __init__(self, etape: str, echecs: List[str]):
        super().__init__(f"purge {etape} : {len(echecs)} échec(s) — " + " ; ".join(echecs[:5]))
        self.etape = etape
        self.echecs = echecs

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

        conversations_vitrine = self._chat_logs_du_compte(utilisateur)

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

        RGPD-03 (vague 2 / file A) — complet ou rejouable, jamais partiel et
        définitif :
          0. le compte est désactivé et le PÉRIMÈTRE de l'effacement
             (projets, exécutions, documents et collections, fichiers) est
             enregistré dans `effacements_comptes`, dans la même transaction ;
          1. purge Chroma puis fichiers — un échec reste un échec : la tâche
             passe `partiel`, l'exploitant est alerté, `EffacementIncomplet`
             est levée, et AUCUNE ligne SQL n'est détruite ;
          2. effacement/anonymisation en base et passage à `termine` dans une
             seule transaction (voir `_effacer_en_base` pour l'ordre).
        Rappeler `supprimer` (ou `reprendre`) rejoue toutes les étapes ; chacune
        est idempotente.
        """
        effacement = self._effacement_ouvert(utilisateur.id)
        if effacement is None:
            termine = (
                self.db.query(EffacementCompte)
                .filter(
                    EffacementCompte.user_id == utilisateur.id,
                    EffacementCompte.statut == STATUT_TERMINE,
                )
                .order_by(EffacementCompte.id.desc())
                .first()
            )
            if termine is not None and est_anonymise(utilisateur):
                return self._rapport_deja_termine(termine, utilisateur)
            effacement = self._ouvrir_effacement(utilisateur)
        return self._executer(effacement, utilisateur)

    def reprendre(self, effacement_id: int) -> Dict[str, Any]:
        """Rejoue un effacement `en_cours` ou `partiel` ; sans effet s'il est
        déjà terminé."""
        effacement = self.db.query(EffacementCompte).get(effacement_id)
        if effacement is None:
            raise LookupError(f"Effacement {effacement_id} inconnu")
        utilisateur = (
            self.db.query(User).get(effacement.user_id) if effacement.user_id else None
        )
        if effacement.statut == STATUT_TERMINE:
            return self._rapport_deja_termine(effacement, utilisateur)
        if utilisateur is None:
            raise LookupError(
                f"Effacement {effacement_id} : compte {effacement.user_id} introuvable"
            )
        return self._executer(effacement, utilisateur)

    def purger_hors_base_projet(self, projet: Project) -> Dict[str, Any]:
        """Chroma et fichiers d'UN projet, avant sa suppression par le CRUD.

        RGPD-03 : `DELETE /projects/{id}` supprimait les lignes sans nettoyer
        Chroma ni les fichiers ; un effacement de compte ultérieur ne les
        retrouvait plus. Lève `EchecPurgeHorsBase` : l'appelant ne supprime
        alors pas le projet, la suppression reste rejouable.
        """
        documents = self._par_projet(ProjectDocument, [projet.id])
        ids_executions = [
            ligne[0]
            for ligne in self.db.query(Execution.id)
            .filter(Execution.project_id == projet.id)
            .all()
        ]
        perimetre = self._perimetre([projet.id], ids_executions, documents)
        chunks = self._purger_chroma(perimetre)
        supprimes, ignores = self._purger_fichiers(perimetre["fichiers"])
        return {
            "chunks_chroma_supprimes": chunks,
            "fichiers_supprimes": supprimes,
            "fichiers_ignores": ignores,
        }

    # ------------------------------------------------------------------
    # Effacement durable (RGPD-03)
    # ------------------------------------------------------------------

    def _effacement_ouvert(self, user_id: int) -> Optional[EffacementCompte]:
        return (
            self.db.query(EffacementCompte)
            .filter(
                EffacementCompte.user_id == user_id,
                EffacementCompte.statut.in_(STATUTS_OUVERTS),
            )
            .order_by(EffacementCompte.id.desc())
            .first()
        )

    def _ids_projets_et_executions(self, utilisateur: User):
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
        return ids_projets, sorted(ids_executions)

    def _perimetre(self, ids_projets, ids_executions, documents) -> Dict[str, Any]:
        return {
            "projets": list(ids_projets),
            "executions": list(ids_executions),
            "documents": [
                {
                    "id": d.id,
                    "projet": d.project_id,
                    "collection": d.collection_name or "technical",
                }
                for d in documents
            ],
            "fichiers": self._chemins_de_fichiers(ids_projets, ids_executions, documents),
        }

    def _ouvrir_effacement(self, utilisateur: User) -> EffacementCompte:
        """Étape 0 : bloquer le compte et rendre le périmètre durable."""
        ids_projets, ids_executions = self._ids_projets_et_executions(utilisateur)
        documents = self._par_projet(ProjectDocument, ids_projets)
        effacement = EffacementCompte(
            user_id=utilisateur.id,
            statut=STATUT_EN_COURS,
            perimetre=self._perimetre(ids_projets, ids_executions, documents),
            etapes={},
            erreurs=[],
            tentatives=0,
        )
        # Plus aucune requête authentifiée ne passe (`get_current_user` refuse
        # un compte inactif) : aucun nouveau travail ne démarre pendant
        # l'effacement.
        utilisateur.is_active = False
        self.db.add(effacement)
        self.db.commit()
        self.db.refresh(effacement)
        logger.info(
            "RGPD art.17 : effacement %s ouvert pour le compte %s (compte bloqué)",
            effacement.id,
            utilisateur.id,
        )
        return effacement

    def _noter_etape(self, effacement: EffacementCompte, nom: str, detail: Any) -> None:
        etapes = dict(effacement.etapes or {})
        etapes[nom] = {"fait": True, "detail": detail, "a": datetime.utcnow().isoformat()}
        effacement.etapes = etapes
        self.db.commit()

    def _executer(self, effacement: EffacementCompte, utilisateur: User) -> Dict[str, Any]:
        effacement_id = effacement.id
        effacement.tentatives = (effacement.tentatives or 0) + 1
        effacement.statut = STATUT_EN_COURS
        self.db.commit()
        perimetre = dict(effacement.perimetre or {})

        try:
            # 1. Hors base, tant que les lignes qui les désignent existent.
            chunks_supprimes = self._purger_chroma(perimetre)
            self._noter_etape(effacement, "chroma", chunks_supprimes)
            fichiers_supprimes, fichiers_ignores = self._purger_fichiers(
                perimetre.get("fichiers") or []
            )
            self._noter_etape(
                effacement,
                "fichiers",
                {"supprimes": len(fichiers_supprimes), "ignores": fichiers_ignores},
            )

            # 2. Base : une seule transaction, avec le passage à `termine`.
            rapport = self._effacer_en_base(utilisateur)
            etapes = dict(effacement.etapes or {})
            etapes["base"] = {"fait": True, "a": datetime.utcnow().isoformat()}
            effacement.etapes = etapes
            effacement.statut = STATUT_TERMINE
            effacement.termine_le = datetime.utcnow()
            # Minimisation : une fois terminé, plus de chemins ni d'identifiants.
            effacement.perimetre = {
                "resume": {
                    "projets": len(perimetre.get("projets") or []),
                    "executions": len(perimetre.get("executions") or []),
                    "documents": len(perimetre.get("documents") or []),
                    "fichiers": len(perimetre.get("fichiers") or []),
                }
            }
            self.db.commit()
        except Exception as exc:  # noqa: BLE001 — noté, alerté, relevé
            self.db.rollback()
            cause = f"{type(exc).__name__}: {exc}"
            effacement = self.db.query(EffacementCompte).get(effacement_id)
            effacement.statut = STATUT_PARTIEL
            effacement.erreurs = list(effacement.erreurs or []) + [
                {
                    "tentative": effacement.tentatives,
                    "a": datetime.utcnow().isoformat(),
                    "cause": cause[:2000],
                }
            ]
            self.db.commit()
            logger.error(
                "RGPD art.17 : effacement %s du compte %s INCOMPLET (tentative %s) : %s",
                effacement_id,
                utilisateur.id,
                effacement.tentatives,
                cause,
            )
            self._alerter_effacement_partiel(effacement, utilisateur, cause)
            raise EffacementIncomplet(effacement_id, cause) from exc

        rapport.update(
            {
                "effacement_id": effacement_id,
                "tentatives": effacement.tentatives,
                "chunks_chroma_supprimes": chunks_supprimes,
                "fichiers_supprimes": fichiers_supprimes,
                "fichiers_ignores": fichiers_ignores,
            }
        )
        return rapport

    @staticmethod
    def _alerter_effacement_partiel(effacement, utilisateur, cause: str) -> None:
        try:
            from app.services import admin_alert_service

            admin_alert_service.alerter_admin(
                "Effacement RGPD incomplet",
                (
                    f"Effacement {effacement.id} du compte {utilisateur.id} : "
                    f"tentative {effacement.tentatives} en échec.\n"
                    f"Cause : {cause}\n"
                    f"Le compte est bloqué ; aucune ligne SQL n'a été détruite. "
                    f"Reprendre : python -m app.services.account_service --reprendre"
                ),
                cle_deduplication=f"rgpd_effacement:{effacement.id}:{effacement.tentatives}",
                categorie="rgpd",
            )
        except Exception as e:  # noqa: BLE001 — l'alerte ne masque pas l'échec
            logger.error("RGPD art.17 : alerte d'effacement partiel impossible : %s", e)

    @staticmethod
    def _rapport_deja_termine(effacement, utilisateur) -> Dict[str, Any]:
        return {
            "statut": "compte supprimé",
            "base_legale": "RGPD art. 17 (droit à l'effacement)",
            "user_id": utilisateur.id if utilisateur is not None else effacement.user_id,
            "effacement_id": effacement.id,
            "deja_termine": True,
            "termine_le": _valeur_exportable(effacement.termine_le),
        }

    def _effacer_en_base(self, utilisateur: User) -> Dict[str, Any]:
        """Effacement/anonymisation en base, SANS commit (l'appelant le fait
        avec le passage de la tâche à `termine`).

        L'ordre compte :
          1. `task_executions` d'abord : sa clé étrangère vers `executions`
             n'a **pas** d'`ondelete` (app/models/task_execution.py:34), elle
             bloquerait la suppression en cascade des exécutions ;
          2. projets — la cascade emporte exécutions, livrables, exigences,
             conversations, identifiants chiffrés et environnements ;
          3. anonymisation de `users`, du journal d'audit et détachement des
             gabarits de SDS.
        """
        ids_projets, ids_executions = self._ids_projets_et_executions(utilisateur)

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
        supprimes_chat = self._supprimer_chat_logs(utilisateur)

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
        }

    # ------------------------------------------------------------------
    # Outils internes
    # ------------------------------------------------------------------

    def _par_projet(self, modele, ids_projets: List[int]) -> List[Any]:
        if not ids_projets:
            return []
        return self.db.query(modele).filter(modele.project_id.in_(ids_projets)).all()

    def _sessions_reclamees(self, utilisateur: Optional[User]) -> List[str]:
        """UUID des sessions vitrine que ce compte a REVENDIQUEES.

        SEC-12 (audit du 06/09, vague 1 / file A) : cette selection se faisait
        sur `ChatLog.email_collected == email`. Un visiteur peut saisir
        l'adresse d'un tiers dans le widget public ; creer ensuite le compte
        correspondant a cette adresse donnait acces a la conversation, en
        export comme en effacement. « Adresse citee » n'est pas « session
        possedee » : seule une revendication explicite, qui suppose de
        connaitre le `session_uuid` detenu par le navigateur du visiteur,
        rattache une session a un compte.
        """
        if utilisateur is None or not getattr(utilisateur, "id", None):
            return []
        lignes = (
            self.db.query(ChatLog.session_uuid)
            .filter(ChatLog.claimed_by_user_id == utilisateur.id)
            .distinct()
            .all()
        )
        return [ligne[0] for ligne in lignes]

    def _chat_logs_du_compte(self, utilisateur: Optional[User]) -> List[ChatLog]:
        sessions = self._sessions_reclamees(utilisateur)
        if not sessions:
            return []
        return (
            self.db.query(ChatLog)
            .filter(ChatLog.session_uuid.in_(sessions))
            .order_by(ChatLog.id)
            .all()
        )

    def _supprimer_chat_logs(self, utilisateur: Optional[User]) -> int:
        sessions = self._sessions_reclamees(utilisateur)
        if not sessions:
            return 0
        return (
            self.db.query(ChatLog)
            .filter(ChatLog.session_uuid.in_(sessions))
            .delete(synchronize_session=False)
        )

    def revendiquer_session(self, utilisateur: User, session_uuid: str) -> int:
        """Rattache une session vitrine au compte qui en presente l'UUID.

        Le `session_uuid` est genere cote client et conserve par le
        navigateur du visiteur : le presenter est la preuve de possession que
        l'adresse e-mail ne fournissait pas. Une session deja revendiquee par
        un autre compte n'est pas volee : la revendication est refusee.
        """
        if not session_uuid:
            raise ValueError("session_uuid manquant")

        lignes = self.db.query(ChatLog).filter(ChatLog.session_uuid == session_uuid).all()
        if not lignes:
            raise LookupError("Session inconnue")

        deja = {
            ligne.claimed_by_user_id
            for ligne in lignes
            if ligne.claimed_by_user_id is not None
        }
        if deja - {utilisateur.id}:
            raise PermissionError("Session deja revendiquee par un autre compte")

        for ligne in lignes:
            ligne.claimed_by_user_id = utilisateur.id
        self.db.commit()
        return len(lignes)

    def _purger_chroma(self, perimetre: Dict[str, Any]) -> int:
        """Supprime les chunks du périmètre ; lève `EchecPurgeHorsBase`.

        Les collections ChromaDB ne sont **pas** nommées par projet : elles
        sont cinq, globales, et l'isolation se fait par les métadonnées
        `document_id` / `project_id` du chunk. Deux passes : par document
        (collection connue), puis par projet dans les cinq collections (un
        chunk dont la ligne `project_documents` aurait disparu).

        RGPD-03 : une erreur était journalisée puis l'effacement continuait,
        lignes SQL comprises ; les chunks restants devenaient introuvables.
        Toutes les suppressions sont tentées, puis les échecs sont levés.
        """
        documents = perimetre.get("documents") or []
        projets = perimetre.get("projets") or []
        if not documents and not projets:
            return 0
        from app.services import rag_service

        total = 0
        echecs: List[str] = []
        for document in documents:
            try:
                total += rag_service.delete_project_document_chunks(
                    document["collection"], document["id"]
                )
            except Exception as exc:  # noqa: BLE001 — collecté puis levé
                echecs.append(
                    f"document {document['id']} ({document['collection']}) : "
                    f"{type(exc).__name__}: {exc}"
                )
        for projet_id in projets:
            try:
                total += rag_service.delete_project_chunks(projet_id)
            except Exception as exc:  # noqa: BLE001
                echecs.append(f"projet {projet_id} : {type(exc).__name__}: {exc}")
        if echecs:
            raise EchecPurgeHorsBase("Chroma", echecs)
        return total

    def _chemins_de_fichiers(
        self,
        ids_projets: List[int],
        ids_executions: List[int],
        documents: List[ProjectDocument],
    ) -> List[str]:
        """Fichiers désignés par le compte (ou le projet), dédoublonnés."""
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
        return list(dict.fromkeys(chemins))  # dédoublonne en gardant l'ordre

    def _purger_fichiers(self, chemins: List[str]):
        """Efface les fichiers situés sous une racine configurée.

        Rend (supprimés, ignorés). Un chemin hors racines est ignoré (règle
        10), un fichier déjà absent n'est pas une erreur (reprise). Un échec
        d'effacement (OSError) n'est plus rangé parmi les « ignorés » : il fait
        lever `EchecPurgeHorsBase` après avoir tenté tous les fichiers.
        """
        racines = _racines_de_fichiers()
        supprimes: List[str] = []
        ignores: List[str] = []
        echecs: List[str] = []

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
                echecs.append(f"{chemin} : {exc}")

        if echecs:
            raise EchecPurgeHorsBase("fichiers", echecs)
        return supprimes, ignores

    @staticmethod
    def _sous_racine(chemin: Path, racine: Path) -> bool:
        try:
            chemin.relative_to(racine)
            return True
        except ValueError:
            return False


def reprendre_effacements_en_attente(db: Session) -> List[int]:
    """Rejoue chaque effacement `en_cours` ou `partiel`. Rend les identifiants
    terminés ; un nouvel échec est noté, alerté, et n'arrête pas les autres."""
    termines: List[int] = []
    ids = [
        ligne[0]
        for ligne in db.query(EffacementCompte.id)
        .filter(EffacementCompte.statut.in_(STATUTS_OUVERTS))
        .order_by(EffacementCompte.id)
        .all()
    ]
    for effacement_id in ids:
        try:
            AccountService(db).reprendre(effacement_id)
            termines.append(effacement_id)
        except EffacementIncomplet:
            continue
    return termines


def main(argv=None) -> int:
    """`python -m app.services.account_service --reprendre` : rejoue les
    effacements en attente sur la base de `settings.DATABASE_URL`."""
    import argparse

    from app.database import SessionLocal

    parser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument("--reprendre", action="store_true", help="rejouer les effacements en attente")
    args = parser.parse_args(argv)
    if not args.reprendre:
        parser.print_help()
        return 2
    db = SessionLocal()
    try:
        termines = reprendre_effacements_en_attente(db)
        restants = (
            db.query(EffacementCompte)
            .filter(EffacementCompte.statut.in_(STATUTS_OUVERTS))
            .count()
        )
    finally:
        db.close()
    print(f"effacements terminés : {termines} ; encore en attente : {restants}")
    return 1 if restants else 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
