/**
 * Canonical Studio ensemble — 11 agents répartis en 5 actes.
 *
 * Source de vérité pour A5.2 (Casting · EnsembleDisplay) et A5.3 (Théâtre ·
 * AgentStage, StudioTimeline). Le fichier `lib/constants.ts` reste pour
 * l'instant en place pour les usages legacy (`MANDATORY_AGENTS`, etc.) ;
 * les pages Studio doivent consommer ce module.
 */

export type StudioAct = 'I' | 'II' | 'III' | 'IV' | 'V';

/**
 * Tokens d'accent par acte, exposés en utilitaires Tailwind via
 * `styles/tokens.css` (`text-indigo`, `bg-plum`, `border-terra`…).
 */
export type AgentAccent = 'indigo' | 'plum' | 'terra' | 'sage' | 'ochre';

export interface StudioAgent {
  id: string;
  /** Prénom + rôle court — affichage Studio. */
  name: { en: string; fr: string };
  /** Métier détaillé (sous-titre). */
  role: { en: string; fr: string };
  /** Tagline d'une ligne pour les cartes. */
  tagline: { en: string; fr: string };
  act: StudioAct;
  accent: AgentAccent;
  /** Filename canonique : `/avatars/{small|large}/{slug}.png`. */
  slug: string;
}

export const STUDIO_ENSEMBLE: StudioAgent[] = [
  // ── Act I · Direction ────────────────────────────────────────────────
  {
    id: 'pm',
    name: { en: 'Sophie', fr: 'Sophie' },
    role: { en: 'Project Manager · Direction', fr: 'Cheffe de projet · Direction' },
    tagline: {
      en: 'Holds the baton, sets the tempo.',
      fr: 'Tient la baguette, donne le tempo.',
    },
    act: 'I',
    accent: 'indigo',
    slug: 'sophie-pm',
  },
  // ── Act II · Visionaries ─────────────────────────────────────────────
  {
    id: 'ba',
    name: { en: 'Olivia', fr: 'Olivia' },
    role: { en: 'Business Analyst · Visionary', fr: 'Business Analyste · Visionnaire' },
    tagline: {
      en: 'Listens to the brief, names the truth.',
      fr: 'Écoute le brief, nomme la vérité.',
    },
    act: 'II',
    accent: 'plum',
    slug: 'olivia-ba',
  },
  {
    id: 'research_analyst',
    name: { en: 'Emma', fr: 'Emma' },
    role: { en: 'Research Analyst · Visionary', fr: 'Analyste recherche · Visionnaire' },
    tagline: {
      en: 'Maps the use cases, validates coverage.',
      fr: 'Cartographie les cas d’usage, valide la couverture.',
    },
    act: 'II',
    accent: 'plum',
    slug: 'emma-research',
  },
  {
    id: 'architect',
    name: { en: 'Marcus', fr: 'Marcus' },
    role: { en: 'Solution Architect · Visionary', fr: 'Architecte solution · Visionnaire' },
    tagline: {
      en: 'Draws the structure, foresees the load.',
      fr: 'Dessine la structure, anticipe la charge.',
    },
    act: 'II',
    accent: 'plum',
    slug: 'marcus-architect',
  },
  // ── Act III · Builders ───────────────────────────────────────────────
  {
    id: 'apex',
    name: { en: 'Diego', fr: 'Diego' },
    role: { en: 'Apex Developer · Builder', fr: 'Développeur Apex · Bâtisseur' },
    tagline: {
      en: 'Forges the back-end logic in Apex.',
      fr: 'Forge la logique back-end en Apex.',
    },
    act: 'III',
    accent: 'terra',
    slug: 'diego-apex',
  },
  {
    id: 'lwc',
    name: { en: 'Zara', fr: 'Zara' },
    role: { en: 'LWC Developer · Builder', fr: 'Développeuse LWC · Bâtisseuse' },
    tagline: {
      en: 'Composes the Lightning interface.',
      fr: 'Compose l’interface Lightning.',
    },
    act: 'III',
    accent: 'terra',
    slug: 'zara-lwc',
  },
  {
    id: 'admin',
    name: { en: 'Raj', fr: 'Raj' },
    role: { en: 'Administrator · Builder', fr: 'Administrateur · Bâtisseur' },
    tagline: {
      en: 'Configures objects, flows and rules.',
      fr: 'Configure objets, flows et règles.',
    },
    act: 'III',
    accent: 'terra',
    slug: 'raj-admin',
  },
  // ── Act IV · Guardians ───────────────────────────────────────────────
  {
    id: 'qa',
    name: { en: 'Elena', fr: 'Elena' },
    role: { en: 'QA Engineer · Guardian', fr: 'Ingénieure QA · Gardienne' },
    tagline: {
      en: 'Asks: does it hold under pressure?',
      fr: 'Vérifie que tout tient sous pression.',
    },
    act: 'IV',
    accent: 'sage',
    slug: 'elena-qa',
  },
  {
    id: 'devops',
    name: { en: 'Jordan', fr: 'Jordan' },
    role: { en: 'DevOps Engineer · Guardian', fr: 'Ingénieur DevOps · Gardien' },
    tagline: {
      en: 'Wires the pipeline, guards the deploy.',
      fr: 'Câble la pipeline, garde le déploiement.',
    },
    act: 'IV',
    accent: 'sage',
    slug: 'jordan-devops',
  },
  // ── Act V · Stage ────────────────────────────────────────────────────
  {
    id: 'data',
    name: { en: 'Aisha', fr: 'Aisha' },
    role: { en: 'Data Migration · Stage', fr: 'Spécialiste migration · Scène' },
    tagline: {
      en: 'Moves the data without losing a row.',
      fr: 'Migre la donnée sans perdre une ligne.',
    },
    act: 'V',
    accent: 'ochre',
    slug: 'aisha-data',
  },
  {
    id: 'trainer',
    name: { en: 'Lucas', fr: 'Lucas' },
    role: { en: 'Trainer · Stage', fr: 'Formateur · Scène' },
    tagline: {
      en: 'Hands the keys to the people on stage.',
      fr: 'Remet les clés aux personnes en scène.',
    },
    act: 'V',
    accent: 'ochre',
    slug: 'lucas-trainer',
  },
];

/** Map agentId → accent token. Inconnu → `brass` (fallback neutre). */
export function getAgentAccent(agentId: string | null | undefined): AgentAccent | 'brass' {
  if (!agentId) return 'brass';
  const agent = STUDIO_ENSEMBLE.find((a) => a.id === agentId);
  return agent?.accent ?? 'brass';
}

/** Avatar path canonical : `/avatars/{small|large}/{slug}.png`. */
export function getAgentAvatar(
  agentId: string,
  size: 'small' | 'large' = 'small',
): string {
  const agent = STUDIO_ENSEMBLE.find((a) => a.id === agentId);
  const slug = agent?.slug ?? 'sophie-pm';
  return `/avatars/${size}/${slug}.png`;
}

export const ACT_LABELS: Record<StudioAct, { en: string; fr: string }> = {
  I: { en: 'Act I · Direction', fr: 'Acte I · Direction' },
  II: { en: 'Act II · Visionaries', fr: 'Acte II · Visionnaires' },
  III: { en: 'Act III · Builders', fr: 'Acte III · Bâtisseurs' },
  IV: { en: 'Act IV · Guardians', fr: 'Acte IV · Gardiens' },
  V: { en: 'Act V · Stage', fr: 'Acte V · Scène' },
};

/** Groupe les 11 agents par acte (ordre I→V). */
export function groupByAct(): { act: StudioAct; agents: StudioAgent[] }[] {
  const acts: StudioAct[] = ['I', 'II', 'III', 'IV', 'V'];
  return acts.map((act) => ({
    act,
    agents: STUDIO_ENSEMBLE.filter((a) => a.act === act),
  }));
}
