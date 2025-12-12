# INVENTAIRE DES ÉLÉMENTS MANQUANTS - Digital Humans

## A. Informations Client (à collecter à la création du projet)

### A1. Identité
| Élément | Requis | Actuellement | Usage |
|---------|--------|--------------|-------|
| Nom de la société | ✅ | ❌ Manquant | SDS header, naming conventions |
| Contact principal | ✅ | ❌ Manquant | Communication, validation |
| Email contact | ✅ | ❌ Manquant | Notifications |
| Logo client | ⚪ Optionnel | ❌ Manquant | SDS branding |

### A2. Organisation Salesforce
| Élément | Requis | Actuellement | Usage |
|---------|--------|--------------|-------|
| Org ID (Production) | ✅ | ❌ Manquant | Référence, déploiement |
| Instance URL | ✅ | ❌ Manquant | Connexion API |
| Edition (Enterprise, Unlimited...) | ✅ | ❌ Manquant | Limites, features disponibles |
| Sandbox disponibles | ✅ | ❌ Manquant | Environnements de dev/test |

## B. Environnements SFDX (à configurer par projet)

### B1. Connexions
| Élément | Requis | Actuellement | Usage |
|---------|--------|--------------|-------|
| Dev Sandbox URL | ✅ | ❌ Manquant | Développement |
| Dev Sandbox Alias | ✅ | ❌ Manquant | Commandes SFDX |
| QA Sandbox URL | ✅ | ❌ Manquant | Tests Elena |
| UAT Sandbox URL | ✅ | ❌ Manquant | Validation client |
| Prod Org URL | ✅ | ❌ Manquant | Déploiement final |

### B2. Authentification
| Élément | Requis | Actuellement | Usage |
|---------|--------|--------------|-------|
| Connected App Client ID | ✅ | ❌ Manquant | OAuth SFDX |
| Connected App Client Secret | ✅ | ❌ Manquant | OAuth SFDX |
| Refresh Token (par env) | ✅ | ❌ Manquant | Connexion persistante |
| OU Username + Security Token | ✅ | ❌ Manquant | Alternative auth |

### B3. Permissions
| Élément | Requis | Actuellement | Usage |
|---------|--------|--------------|-------|
| User avec droits déploiement | ✅ | ❌ Manquant | SFDX deploy |
| API Enabled | ✅ | ❌ Manquant | Toutes opérations |
| Modify All Data | ✅ | ❌ Manquant | Data operations |

## C. Repository Git (par projet)

| Élément | Requis | Actuellement | Usage |
|---------|--------|--------------|-------|
| Repo URL | ✅ | ❌ Manquant | Version control |
| Branch strategy | ✅ | ❌ Manquant | Workflow dev |
| Access token | ✅ | ❌ Manquant | Push/Pull |
| Default branch | ✅ | ❌ Manquant | Main/Master |

## D. Configuration Projet Digital Humans

### D1. Paramètres actuels (dans DB)
| Élément | Présent | Utilisé |
|---------|---------|---------|
| project.name | ✅ | ✅ |
| project.description | ✅ | ✅ |
| project.business_requirements | ✅ | ✅ |
| project.sfdx_project_path | ✅ | ⚠️ Partiellement |
| project.architecture_notes | ✅ | ⚠️ Partiellement |
| project.compliance_requirements | ✅ | ⚠️ Partiellement |

### D2. Paramètres manquants à ajouter
| Élément | Priorité | Usage |
|---------|----------|-------|
| client_name | HAUTE | SDS, communications |
| client_contact_email | HAUTE | Notifications |
| org_id | HAUTE | Référence Salesforce |
| dev_sandbox_alias | HAUTE | SFDX commands |
| dev_sandbox_url | HAUTE | Connexion |
| qa_sandbox_alias | MOYENNE | Tests |
| uat_sandbox_alias | MOYENNE | UAT |
| prod_org_alias | HAUTE | Déploiement |
| git_repo_url | HAUTE | Version control |
| git_branch | MOYENNE | Default branch |
| sfdx_auth_method | HAUTE | jwt / password / web |
| sfdx_client_id | HAUTE | Si JWT |
| sfdx_username | HAUTE | Connexion |
| project_language | MOYENNE | FR/EN pour SDS |
| sds_template_id | MOYENNE | Template à utiliser |

## E. Pour chaque tâche WBS

### E1. Éléments requis pour exécution
| Type tâche | Prérequis |
|------------|-----------|
| SETUP env | Sandbox URL, credentials, SFDX auth |
| Data Model | Dev sandbox connected |
| Apex Dev | Dev sandbox, test classes template |
| LWC Dev | Dev sandbox, component library |
| Flow Dev | Dev sandbox |
| Deploy | Target sandbox, package.xml |
| QA Test | QA sandbox, test data |

### E2. Critères de validation par type
| Type tâche | Validation automatique possible ? |
|------------|-----------------------------------|
| SETUP env | ✅ Oui - sfdx org:display |
| Data Model | ✅ Oui - sfdx force:source:push + describe |
| Apex Dev | ✅ Oui - tests unitaires |
| LWC Dev | ⚠️ Partiel - lint, mais pas UI tests |
| Flow Dev | ⚠️ Partiel - deploy success |
| Deploy | ✅ Oui - deployment status |
| QA Test | ❌ Non - Elena valide manuellement |

## F. Actions requises

### Court terme (bloquant pour BUILD)
1. [ ] Ajouter champs client/org dans table `projects`
2. [ ] Créer UI de configuration projet avec tous les prérequis
3. [ ] Implémenter stockage sécurisé des credentials (vault?)
4. [ ] Ajouter validation des connexions SFDX à la création projet

### Moyen terme (qualité)
5. [ ] Template SDS configurable avec infos client
6. [ ] Gestion multi-environnements dans UI
7. [ ] Dashboard état des connexions

### Long terme (scalabilité)
8. [ ] Multi-tenant avec isolation credentials
9. [ ] Rotation automatique des tokens
10. [ ] Audit log des accès

