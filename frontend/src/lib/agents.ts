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

/**
 * Récupère un agent par id ; null si inconnu.
 */
export function getAgentById(agentId: string | null | undefined): StudioAgent | null {
  if (!agentId) return null;
  return STUDIO_ENSEMBLE.find((a) => a.id === agentId) ?? null;
}

/**
 * Reconnaît un agent depuis un libellé libre venu du backend, type
 * "Sophie (PM)", "research_analyst", "Emma (Research Analyst)", "marcus", etc.
 */
export function findAgentByLabel(label: string | null | undefined): StudioAgent | null {
  if (!label) return null;
  const lower = label.toLowerCase();

  const direct = STUDIO_ENSEMBLE.find((a) => a.id === lower);
  if (direct) return direct;

  for (const agent of STUDIO_ENSEMBLE) {
    if (lower.startsWith(agent.name.en.toLowerCase())) return agent;
    if (lower.startsWith(agent.name.fr.toLowerCase())) return agent;
  }
  // Try the parenthesised id, ex. "Emma (research_analyst)".
  const inner = lower.match(/\(([^)]+)\)/)?.[1];
  if (inner) {
    const normalized = inner.replace(/\s+/g, '_');
    const byInner = STUDIO_ENSEMBLE.find(
      (a) => a.id === normalized || a.id === inner,
    );
    if (byInner) return byInner;
  }
  return null;
}

/**
 * Tailwind classes (Studio palette) par token d'accent.
 * Utilisé pour border/text/bg/ring uniformes dans tout le Théâtre.
 */
export type AccentToken = AgentAccent | 'brass';

export const ACCENT_TEXT: Record<AccentToken, string> = {
  indigo: 'text-indigo',
  plum: 'text-plum',
  terra: 'text-terra',
  sage: 'text-sage',
  ochre: 'text-ochre',
  brass: 'text-brass',
};

export const ACCENT_BORDER: Record<AccentToken, string> = {
  indigo: 'border-indigo/50',
  plum: 'border-plum/50',
  terra: 'border-terra/50',
  sage: 'border-sage/50',
  ochre: 'border-ochre/50',
  brass: 'border-brass/40',
};

export const ACCENT_BORDER_STRONG: Record<AccentToken, string> = {
  indigo: 'border-indigo',
  plum: 'border-plum',
  terra: 'border-terra',
  sage: 'border-sage',
  ochre: 'border-ochre',
  brass: 'border-brass',
};

export const ACCENT_BG_SOFT: Record<AccentToken, string> = {
  indigo: 'bg-indigo/10',
  plum: 'bg-plum/10',
  terra: 'bg-terra/10',
  sage: 'bg-sage/10',
  ochre: 'bg-ochre/10',
  brass: 'bg-brass/10',
};

/**
 * Phases de la pièce SDS dans l'ordre canonique d'apparition.
 * Sert de base au StudioTimeline et au mapping execution_state ⇄ acte.
 */
export interface TheatreStep {
  id: string;
  agentId: string;
  /** Court : « Act I · The Brief ». */
  label: { en: string; fr: string };
  /** Long : « Sophie listens, names the requirements. ». */
  cue: { en: string; fr: string };
}

export const SDS_STEPS: TheatreStep[] = [
  {
    id: 'sds-1',
    agentId: 'pm',
    label: { en: 'Act I · The Brief', fr: 'Acte I · Le Brief' },
    cue: {
      en: 'Sophie reads the brief and writes the Business Requirements.',
      fr: 'Sophie lit le brief et rédige les exigences métier.',
    },
  },
  {
    id: 'sds-2',
    agentId: 'ba',
    label: { en: 'Act II · Use cases', fr: 'Acte II · Cas d’usage' },
    cue: {
      en: 'Olivia translates each requirement into testable use cases.',
      fr: 'Olivia transforme chaque exigence en cas d’usage testables.',
    },
  },
  {
    id: 'sds-2b',
    agentId: 'research_analyst',
    label: { en: 'Act II · Coverage', fr: 'Acte II · Couverture' },
    cue: {
      en: 'Emma maps the use cases and validates coverage.',
      fr: 'Emma cartographie les cas d’usage et valide la couverture.',
    },
  },
  {
    id: 'sds-3',
    agentId: 'architect',
    label: { en: 'Act II · Architecture', fr: 'Acte II · Architecture' },
    cue: {
      en: 'Marcus draws the data model, the flows, the security.',
      fr: 'Marcus dessine le modèle de données, les flows, la sécurité.',
    },
  },
  {
    id: 'sds-4',
    agentId: 'qa',
    label: { en: 'Act IV · Expert specs', fr: 'Acte IV · Spécifications' },
    cue: {
      en: 'Elena, Jordan, Aisha and Lucas write their detailed specs.',
      fr: 'Elena, Jordan, Aisha et Lucas rédigent leurs spécifications.',
    },
  },
  {
    id: 'sds-5',
    agentId: 'research_analyst',
    label: { en: 'Act V · The SDS', fr: 'Acte V · Le SDS' },
    cue: {
      en: 'Emma assembles every voice into the final SDS.',
      fr: 'Emma assemble toutes les voix dans le SDS final.',
    },
  },
];

export const BUILD_STEPS: TheatreStep[] = [
  {
    id: 'build-data',
    agentId: 'admin',
    label: { en: 'Phase 1 · Data model', fr: 'Phase 1 · Modèle de données' },
    cue: {
      en: 'Raj configures objects, fields and record types.',
      fr: 'Raj configure objets, champs et record types.',
    },
  },
  {
    id: 'build-apex',
    agentId: 'apex',
    label: { en: 'Phase 2 · Business logic', fr: 'Phase 2 · Logique métier' },
    cue: {
      en: 'Diego forges the Apex back-end and tests.',
      fr: 'Diego forge la logique Apex et les tests.',
    },
  },
  {
    id: 'build-lwc',
    agentId: 'lwc',
    label: { en: 'Phase 3 · UI', fr: 'Phase 3 · Interface' },
    cue: {
      en: 'Zara composes the Lightning Web Components.',
      fr: 'Zara compose les Lightning Web Components.',
    },
  },
  {
    id: 'build-flow',
    agentId: 'admin',
    label: { en: 'Phase 4 · Automation', fr: 'Phase 4 · Automatisation' },
    cue: {
      en: 'Raj wires flows and validation rules.',
      fr: 'Raj câble flows et règles de validation.',
    },
  },
  {
    id: 'build-security',
    agentId: 'admin',
    label: { en: 'Phase 5 · Security', fr: 'Phase 5 · Sécurité' },
    cue: {
      en: 'Raj defines profiles, permission sets and OWD.',
      fr: 'Raj définit profils, permission sets et OWD.',
    },
  },
  {
    id: 'build-data-mig',
    agentId: 'data',
    label: { en: 'Phase 6 · Data migration', fr: 'Phase 6 · Migration' },
    cue: {
      en: 'Aisha imports the data without losing a row.',
      fr: 'Aisha migre la donnée sans perdre une ligne.',
    },
  },
];

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
