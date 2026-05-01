"""
Contenu rédigé des 3 pages juridiques — FR + EN.
Boilerplate SaaS B2B FR à faire valider par juriste après go-live.
Date de rédaction : 1er mai 2026.
"""

LEGAL_FR = {
    "title": "Mentions légales",
    "updated": "Dernière mise à jour : 1er mai 2026",
    "sections": [
        {
            "h": "Éditeur du site",
            "p": [
                "Le site digital-humans.fr est édité par Sam Hatit, exerçant en qualité d'entrepreneur individuel sous le régime de la micro-entreprise.",
                "SIRET : [À COMPLÉTER]<br/>Adresse du siège : [À COMPLÉTER]<br/>Numéro de TVA intracommunautaire : non applicable (régime de la franchise en base).",
                "Directeur de la publication : Sam Hatit.",
                "Contact : <a href=\"mailto:hello@digital-humans.fr\">hello@digital-humans.fr</a>",
            ],
        },
        {
            "h": "Hébergement",
            "p": [
                "Le site est hébergé par Hostinger International Ltd.<br/>Adresse : 61 Lordou Vironos Street, 6023 Larnaca, Chypre.<br/>Téléphone : +370 5 205 5550.",
                "Les données traitées par la plateforme Digital·Humans (modèles de langage, base vectorielle) sont opérées via les fournisseurs Anthropic PBC (San Francisco, USA) et OpenAI Inc. (San Francisco, USA), dans le cadre des accords de traitement des données qu'ils proposent.",
            ],
        },
        {
            "h": "Propriété intellectuelle",
            "p": [
                "L'ensemble des éléments présents sur le site digital-humans.fr — textes, images, logos, identité graphique, code source — est la propriété de Sam Hatit, sauf mention contraire explicite. Toute reproduction, représentation ou diffusion, totale ou partielle, sans autorisation écrite préalable est interdite.",
                "Les noms et marques cités à titre illustratif (Salesforce, Apex, LWC, etc.) restent la propriété de leurs détenteurs respectifs.",
            ],
        },
        {
            "h": "Limites de responsabilité",
            "p": [
                "Les contenus publiés sur le site sont fournis à titre informatif. L'éditeur s'efforce d'assurer leur exactitude mais ne saurait être tenu pour responsable des erreurs, omissions ou indisponibilités temporaires du service.",
                "Les livrables produits par la plateforme Digital·Humans (SDS, design d'architecture, code généré) sont des aides à la décision destinées à des professionnels avertis. Ils doivent être systématiquement revus et validés par les équipes techniques du client avant tout usage en production.",
            ],
        },
        {
            "h": "Droit applicable",
            "p": [
                "Les présentes mentions sont régies par le droit français. Tout litige relèvera de la compétence exclusive des tribunaux de Paris, sous réserve des règles de droit impératif applicables au consommateur.",
            ],
        },
    ],
}

LEGAL_EN = {
    "title": "Legal Notice",
    "updated": "Last updated: May 1, 2026",
    "sections": [
        {
            "h": "Publisher",
            "p": [
                "The digital-humans.fr website is published by Sam Hatit, operating as a sole trader under the French micro-entrepreneur regime.",
                "Business registration (SIRET): [TO BE COMPLETED]<br/>Registered address: [TO BE COMPLETED]<br/>VAT registration: not applicable (small-business exemption).",
                "Editor in chief: Sam Hatit.",
                "Contact: <a href=\"mailto:hello@digital-humans.fr\">hello@digital-humans.fr</a>",
            ],
        },
        {
            "h": "Hosting",
            "p": [
                "The website is hosted by Hostinger International Ltd.<br/>Address: 61 Lordou Vironos Street, 6023 Larnaca, Cyprus.<br/>Phone: +370 5 205 5550.",
                "The Digital·Humans platform's processing operations (language models, vector database) are powered by Anthropic PBC (San Francisco, USA) and OpenAI Inc. (San Francisco, USA), under the data processing agreements they offer.",
            ],
        },
        {
            "h": "Intellectual property",
            "p": [
                "All content on digital-humans.fr — text, images, logos, visual identity, source code — is the property of Sam Hatit unless otherwise stated. Any reproduction, representation, or distribution, in whole or in part, without prior written authorization is prohibited.",
                "Names and trademarks mentioned for illustrative purposes (Salesforce, Apex, LWC, etc.) remain the property of their respective owners.",
            ],
        },
        {
            "h": "Liability",
            "p": [
                "The information published on this website is provided for general purposes only. The publisher endeavors to ensure its accuracy but cannot be held liable for errors, omissions, or temporary unavailability of the service.",
                "Deliverables produced by the Digital·Humans platform (SDS documents, architecture designs, generated code) are decision-support outputs intended for qualified professionals. They must be systematically reviewed and validated by the client's technical teams before any production use.",
            ],
        },
        {
            "h": "Governing law",
            "p": [
                "This notice is governed by French law. Any dispute shall fall under the exclusive jurisdiction of the courts of Paris, subject to mandatory consumer protection rules where applicable.",
            ],
        },
    ],
}

CGV_FR = {
    "title": "Conditions générales de vente",
    "updated": "Dernière mise à jour : 1er mai 2026",
    "sections": [
        {
            "h": "1. Objet",
            "p": [
                "Les présentes conditions régissent l'accès et l'utilisation de la plateforme Digital·Humans (ci-après « la Plateforme ») éditée par Sam Hatit, entrepreneur individuel.",
                "La Plateforme propose un studio Salesforce automatisé reposant sur un ensemble d'agents conversationnels assistés par intelligence artificielle, accessible via abonnement mensuel.",
            ],
        },
        {
            "h": "2. Paliers d'abonnement",
            "p": [
                "<strong>Gratuit (Free)</strong> — Accès limité à la conversation avec deux agents (Sophie, Olivia). Aucun stockage des échanges, aucune mémoire persistante. Sans engagement.",
                "<strong>Pro — 49 € HT par mois</strong> — Accès à l'ensemble des onze agents, upload de documents, mémoire persistante, deux Solution Design Specifications (SDS) par mois inclus. Pas de génération de code ni de déploiement.",
                "<strong>Team — 1 490 € HT par mois</strong> — Périmètre Pro complété par la phase BUILD (génération Apex, LWC, Admin) et le déploiement SFDX vers environnement sandbox. La mise en production reste expressément exclue et réservée aux contrats Enterprise.",
                "<strong>Enterprise — Sur devis</strong> — Déploiement sur infrastructure dédiée, choix du fournisseur de modèle, support contractuel personnalisé.",
            ],
        },
        {
            "h": "3. Prix et modalités de paiement",
            "p": [
                "Les prix indiqués s'entendent hors taxes. La TVA n'est pas applicable au régime de la franchise en base (article 293 B du CGI) — mention obligatoire en attente de bascule au régime réel.",
                "Le paiement s'effectue par carte bancaire via le prestataire Stripe. Le client autorise Digital·Humans à débiter son moyen de paiement à chaque échéance mensuelle.",
                "Toute mensualité commencée est due. En cas d'échec de paiement, l'accès aux fonctions payantes est suspendu après une période de grâce de cinq jours ouvrés.",
            ],
        },
        {
            "h": "4. Durée et résiliation",
            "p": [
                "L'abonnement est conclu pour une durée d'un mois, reconductible tacitement. Le client peut résilier à tout moment depuis son espace personnel ; la résiliation prend effet à la fin de la période en cours.",
                "Aucun remboursement prorata temporis n'est appliqué pour les périodes entamées.",
                "Pour les contrats Enterprise, les durées et modalités de résiliation sont fixées contractuellement.",
            ],
        },
        {
            "h": "5. Obligations du client",
            "p": [
                "Le client s'engage à fournir des informations exactes lors de la création de son compte, à respecter la confidentialité de ses identifiants, et à utiliser la Plateforme conformément à sa destination professionnelle.",
                "Le client s'interdit notamment de tenter de contourner les limites techniques de son palier, de télécharger des contenus illicites, ou d'utiliser la Plateforme à des fins de réingénierie.",
            ],
        },
        {
            "h": "6. Garanties et limites de responsabilité",
            "p": [
                "La Plateforme est fournie « en l'état », sans garantie d'absence d'erreurs ou d'interruption. Les livrables générés constituent une assistance technique destinée à des professionnels qualifiés et doivent être revus avant tout usage opérationnel.",
                "La responsabilité de l'éditeur est limitée au montant des sommes effectivement réglées par le client au cours des douze derniers mois précédant le fait générateur.",
                "Aucune garantie n'est apportée quant à l'aptitude des livrables à un usage particulier, ni à leur conformité réglementaire dans des domaines spécifiques (santé, défense, données sensibles).",
            ],
        },
        {
            "h": "7. Données personnelles",
            "p": [
                "Le traitement des données personnelles est régi par la <a href=\"/privacy\">Politique de confidentialité</a>, partie intégrante des présentes conditions.",
            ],
        },
        {
            "h": "8. Droit de rétractation",
            "p": [
                "Pour les abonnements souscrits par des consommateurs (personnes physiques agissant à des fins n'entrant pas dans le cadre de leur activité professionnelle), un droit de rétractation de quatorze jours est applicable conformément aux articles L221-18 et suivants du Code de la consommation.",
                "Le client renonce expressément à ce droit en demandant l'exécution immédiate du service avant la fin du délai de rétractation. La case correspondante doit être cochée lors de la souscription.",
                "Pour les abonnements souscrits par des professionnels, le droit de rétractation ne s'applique pas.",
            ],
        },
        {
            "h": "9. Modifications",
            "p": [
                "L'éditeur peut modifier les présentes conditions à tout moment. Les changements substantiels sont notifiés au client par courriel au moins trente jours avant leur entrée en vigueur. La poursuite de l'abonnement après cette date vaut acceptation.",
            ],
        },
        {
            "h": "10. Droit applicable et juridiction",
            "p": [
                "Les présentes conditions sont régies par le droit français. Tout litige sera soumis aux tribunaux compétents de Paris, sauf disposition impérative contraire applicable au consommateur.",
            ],
        },
    ],
}

CGV_EN = {
    "title": "Terms of Sale",
    "updated": "Last updated: May 1, 2026",
    "sections": [
        {
            "h": "1. Purpose",
            "p": [
                "These terms govern access to and use of the Digital·Humans platform (hereinafter \"the Platform\") published by Sam Hatit, sole trader.",
                "The Platform provides an automated Salesforce studio composed of conversational agents assisted by artificial intelligence, accessible through monthly subscription.",
            ],
        },
        {
            "h": "2. Subscription tiers",
            "p": [
                "<strong>Free</strong> — Limited access to conversation with two agents (Sophie, Olivia). No exchange storage, no persistent memory. No commitment.",
                "<strong>Pro — €49 / month (excl. VAT)</strong> — Access to all eleven agents, file upload, persistent memory, two SDS deliverables per month included. No code generation, no deployment.",
                "<strong>Team — €1,490 / month (excl. VAT)</strong> — Pro scope plus the BUILD phase (Apex, LWC, Admin generation) and SFDX deployment to sandbox environments only. Production deployment is expressly excluded and reserved for Enterprise contracts.",
                "<strong>Enterprise — On quote</strong> — Dedicated infrastructure deployment, choice of model provider, custom contractual support.",
            ],
        },
        {
            "h": "3. Pricing and payment",
            "p": [
                "Prices are stated excluding tax. VAT is not applicable under the French small-business exemption (article 293 B of the General Tax Code).",
                "Payment is made by credit card through the provider Stripe. The customer authorizes Digital·Humans to charge their payment method on each monthly billing date.",
                "Any started month is due. If a payment fails, access to paid features is suspended after a five-business-day grace period.",
            ],
        },
        {
            "h": "4. Duration and termination",
            "p": [
                "The subscription is concluded for one month, automatically renewable. The customer may terminate at any time from their account; termination takes effect at the end of the current period.",
                "No prorata refund is granted for started periods.",
                "For Enterprise contracts, duration and termination terms are set contractually.",
            ],
        },
        {
            "h": "5. Customer obligations",
            "p": [
                "The customer agrees to provide accurate information when creating an account, to keep credentials confidential, and to use the Platform consistently with its professional purpose.",
                "The customer agrees not to attempt to bypass the technical limits of their tier, upload unlawful content, or use the Platform for reverse-engineering purposes.",
            ],
        },
        {
            "h": "6. Warranties and liability",
            "p": [
                "The Platform is provided \"as is,\" without warranty of being error-free or uninterrupted. Generated deliverables are technical assistance intended for qualified professionals and must be reviewed before any operational use.",
                "The publisher's liability is limited to the amount of fees actually paid by the customer during the twelve months preceding the triggering event.",
                "No warranty is given as to the deliverables' fitness for a particular purpose, nor to their regulatory compliance in specific domains (healthcare, defense, sensitive data).",
            ],
        },
        {
            "h": "7. Personal data",
            "p": [
                "Processing of personal data is governed by the <a href=\"/privacy\">Privacy Policy</a>, an integral part of these terms.",
            ],
        },
        {
            "h": "8. Right of withdrawal",
            "p": [
                "For subscriptions taken out by consumers (natural persons acting outside their professional activity), a fourteen-day withdrawal period applies under articles L221-18 et seq. of the French Consumer Code.",
                "The customer expressly waives this right by requesting immediate performance of the service before the end of the withdrawal period — the corresponding box must be checked at signup.",
                "For subscriptions taken out by professionals, the right of withdrawal does not apply.",
            ],
        },
        {
            "h": "9. Amendments",
            "p": [
                "The publisher may amend these terms at any time. Substantial changes are notified to the customer by email at least thirty days before their effective date. Continued subscription after that date constitutes acceptance.",
            ],
        },
        {
            "h": "10. Governing law and jurisdiction",
            "p": [
                "These terms are governed by French law. Any dispute shall be submitted to the competent courts of Paris, subject to any mandatory consumer protection rules.",
            ],
        },
    ],
}

PRIVACY_FR = {
    "title": "Politique de confidentialité",
    "updated": "Dernière mise à jour : 1er mai 2026",
    "sections": [
        {
            "h": "1. Responsable de traitement",
            "p": [
                "Le responsable du traitement des données personnelles collectées via la Plateforme Digital·Humans est Sam Hatit, entrepreneur individuel.",
                "Contact : <a href=\"mailto:hello@digital-humans.fr\">hello@digital-humans.fr</a>",
            ],
        },
        {
            "h": "2. Données collectées",
            "p": [
                "<strong>Données de compte</strong> : adresse électronique, mot de passe haché, nom (optionnel), date d'inscription. Base légale : exécution du contrat (article 6.1.b RGPD).",
                "<strong>Données de facturation</strong> : raison sociale, numéro de TVA, identifiant client Stripe, historique des paiements. Base légale : exécution du contrat et obligation légale comptable.",
                "<strong>Contenu des conversations</strong> : pour les paliers Pro et Team, les échanges avec les agents et les fichiers téléversés sont conservés pour assurer la continuité du service. Pour le palier Free, les conversations ne sont pas conservées au-delà de la session.",
                "<strong>Données techniques</strong> : adresse IP, identifiants de session, type de navigateur, traces d'erreur. Base légale : intérêt légitime (sécurité du service).",
            ],
        },
        {
            "h": "3. Finalités",
            "p": [
                "Les données collectées sont utilisées exclusivement pour : fournir le service souscrit, traiter les paiements, assurer la sécurité de la Plateforme, communiquer les évolutions significatives du service, et respecter les obligations légales et fiscales applicables.",
                "Aucune donnée n'est utilisée à des fins publicitaires, ni cédée à des tiers à des fins commerciales.",
            ],
        },
        {
            "h": "4. Durées de conservation",
            "p": [
                "<strong>Compte actif</strong> : pour la durée de l'abonnement, plus douze mois après la dernière connexion.",
                "<strong>Données comptables</strong> : dix ans (obligation légale).",
                "<strong>Conversations Pro/Team</strong> : pour la durée de l'abonnement, plus trente jours après résiliation. Suppression automatisée ensuite, hors archives techniques de sécurité.",
                "<strong>Logs techniques</strong> : douze mois maximum.",
            ],
        },
        {
            "h": "5. Sous-traitants",
            "p": [
                "Les fournisseurs suivants traitent des données pour notre compte dans le cadre d'accords de sous-traitance conformes au RGPD :",
                "<strong>Hostinger International Ltd.</strong> (Chypre, UE) — hébergement des serveurs et de la base de données.",
                "<strong>Stripe Payments Europe Ltd.</strong> (Irlande, UE) — traitement des paiements par carte.",
                "<strong>Anthropic PBC</strong> (États-Unis) — fourniture des modèles de langage Claude. Engagement Zero Data Retention activé : aucune conservation des prompts et des réponses au-delà du temps strict de traitement.",
                "<strong>OpenAI Inc.</strong> (États-Unis) — fourniture de modèles d'embedding pour l'indexation documentaire.",
                "Les transferts hors Union européenne sont encadrés par les clauses contractuelles types adoptées par la Commission européenne.",
            ],
        },
        {
            "h": "6. Vos droits",
            "p": [
                "Conformément au Règlement général sur la protection des données et à la loi Informatique et Libertés, vous disposez des droits suivants : accès, rectification, effacement, limitation du traitement, portabilité, opposition, et retrait du consentement le cas échéant.",
                "Pour exercer ces droits, écrivez-nous à <a href=\"mailto:hello@digital-humans.fr\">hello@digital-humans.fr</a>. Nous répondons dans un délai d'un mois maximum.",
                "Vous disposez également du droit d'introduire une réclamation auprès de la Commission Nationale de l'Informatique et des Libertés (<a href=\"https://www.cnil.fr/\" target=\"_blank\" rel=\"noopener\">cnil.fr</a>).",
            ],
        },
        {
            "h": "7. Cookies",
            "p": [
                "La Plateforme utilise uniquement des cookies strictement nécessaires à son fonctionnement (session d'authentification, préférences de langue et de thème). Aucun cookie publicitaire ni de mesure d'audience tierce n'est déposé sans consentement.",
            ],
        },
        {
            "h": "8. Sécurité",
            "p": [
                "Les communications sont chiffrées en TLS. Les mots de passe sont stockés sous forme hachée. Les secrets d'API sont gérés via un coffre dédié. Les sauvegardes de la base de données sont chiffrées au repos.",
                "Tout incident de sécurité affectant des données personnelles serait notifié à la CNIL et aux personnes concernées dans les conditions prévues par les articles 33 et 34 du RGPD.",
            ],
        },
    ],
}

PRIVACY_EN = {
    "title": "Privacy Policy",
    "updated": "Last updated: May 1, 2026",
    "sections": [
        {
            "h": "1. Data controller",
            "p": [
                "The controller of personal data collected through the Digital·Humans Platform is Sam Hatit, sole trader.",
                "Contact: <a href=\"mailto:hello@digital-humans.fr\">hello@digital-humans.fr</a>",
            ],
        },
        {
            "h": "2. Data collected",
            "p": [
                "<strong>Account data</strong>: email address, hashed password, name (optional), signup date. Legal basis: contract performance (GDPR article 6.1.b).",
                "<strong>Billing data</strong>: company name, VAT number, Stripe customer ID, payment history. Legal basis: contract performance and legal accounting obligations.",
                "<strong>Conversation content</strong>: for Pro and Team tiers, exchanges with agents and uploaded files are retained to ensure service continuity. For the Free tier, conversations are not kept beyond the session.",
                "<strong>Technical data</strong>: IP address, session identifiers, browser type, error traces. Legal basis: legitimate interest (service security).",
            ],
        },
        {
            "h": "3. Purposes",
            "p": [
                "Collected data is used exclusively to: provide the subscribed service, process payments, secure the Platform, communicate significant service changes, and comply with applicable legal and tax obligations.",
                "No data is used for advertising purposes nor transferred to third parties for commercial purposes.",
            ],
        },
        {
            "h": "4. Retention periods",
            "p": [
                "<strong>Active account</strong>: for the subscription duration, plus twelve months after last login.",
                "<strong>Accounting data</strong>: ten years (legal obligation).",
                "<strong>Pro/Team conversations</strong>: for the subscription duration, plus thirty days after termination. Automated deletion afterwards, except for technical security archives.",
                "<strong>Technical logs</strong>: twelve months maximum.",
            ],
        },
        {
            "h": "5. Sub-processors",
            "p": [
                "The following providers process data on our behalf under GDPR-compliant data processing agreements:",
                "<strong>Hostinger International Ltd.</strong> (Cyprus, EU) — server and database hosting.",
                "<strong>Stripe Payments Europe Ltd.</strong> (Ireland, EU) — card payment processing.",
                "<strong>Anthropic PBC</strong> (United States) — provision of Claude language models. Zero Data Retention commitment is activated: prompts and responses are not retained beyond the strict processing time.",
                "<strong>OpenAI Inc.</strong> (United States) — provision of embedding models for document indexing.",
                "Transfers outside the European Union are framed by the standard contractual clauses adopted by the European Commission.",
            ],
        },
        {
            "h": "6. Your rights",
            "p": [
                "In accordance with the General Data Protection Regulation, you have the following rights: access, rectification, erasure, restriction of processing, portability, objection, and withdrawal of consent where applicable.",
                "To exercise these rights, write to us at <a href=\"mailto:hello@digital-humans.fr\">hello@digital-humans.fr</a>. We respond within one month maximum.",
                "You also have the right to lodge a complaint with the French data protection authority (<a href=\"https://www.cnil.fr/\" target=\"_blank\" rel=\"noopener\">cnil.fr</a>) or your local supervisory authority.",
            ],
        },
        {
            "h": "7. Cookies",
            "p": [
                "The Platform uses only strictly necessary cookies (authentication session, language and theme preferences). No third-party advertising or analytics cookies are dropped without consent.",
            ],
        },
        {
            "h": "8. Security",
            "p": [
                "Communications are encrypted in TLS. Passwords are stored hashed. API secrets are managed via a dedicated vault. Database backups are encrypted at rest.",
                "Any security incident affecting personal data would be notified to the data protection authority and to the persons concerned under the conditions provided by GDPR articles 33 and 34.",
            ],
        },
    ],
}

ALL = {
    "legal":   {"fr": LEGAL_FR,   "en": LEGAL_EN},
    "cgv":     {"fr": CGV_FR,     "en": CGV_EN},
    "privacy": {"fr": PRIVACY_FR, "en": PRIVACY_EN},
}

if __name__ == "__main__":
    import json, sys
    print(f"FR/EN content prepared. Sections counts:")
    for k, v in ALL.items():
        print(f"  {k}: FR={len(v['fr']['sections'])} EN={len(v['en']['sections'])}")
