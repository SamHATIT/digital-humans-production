/**
 * Lecture des reponses de l'API — PROD-10.
 *
 * Constat d'Astra L526 : cinq parcours ordinaires cassaient sur la **forme**
 * des reponses, pas sur leur contenu. Deux causes, une seule fois chacune :
 *
 *   - `apiCall` faisait `new Error(error.detail)` sans regarder si `detail`
 *     etait un objet. `FeatureAccessError` et `LimitExceededError` en servent
 *     un : le message affiche devenait « [object Object] », et le palier
 *     requis, le code et l'URL d'upgrade etaient perdus en route ;
 *   - les pages lisaient des noms de champs qui n'existent pas dans la
 *     reponse (`assistant_message` pour le chat) ou forcaient une valeur que
 *     le serveur contredit (`submitted` alors qu'il rend `analyzed`).
 *
 * Ces lectures vivent ici, testees par `frontend/tests/apiContracts.test.ts`,
 * plutot que recopiees dans chaque page.
 */

/** Une erreur HTTP qui conserve ce que le serveur a dit. */
export class ApiError extends Error {
  readonly status: number;
  /** `error` du detail structure : `feature_not_available`, `limit_exceeded`… */
  readonly code?: string;
  readonly requiredTier?: string;
  readonly upgradeUrl?: string;
  /** Le corps complet, pour les cas que cette classe ne modelise pas. */
  readonly payload?: unknown;

  constructor(
    message: string,
    options: {
      status: number;
      code?: string;
      requiredTier?: string;
      upgradeUrl?: string;
      payload?: unknown;
    },
  ) {
    super(message);
    this.name = 'ApiError';
    this.status = options.status;
    this.code = options.code;
    this.requiredTier = options.requiredTier;
    this.upgradeUrl = options.upgradeUrl;
    this.payload = options.payload;
  }
}

function texteDeDetailListe(detail: unknown[]): string {
  return detail
    .map((entree) => {
      if (entree && typeof entree === 'object') {
        const e = entree as Record<string, unknown>;
        if (typeof e.msg === 'string') return e.msg;
        if (typeof e.message === 'string') return e.message;
      }
      return typeof entree === 'string' ? entree : JSON.stringify(entree);
    })
    .filter(Boolean)
    .join(', ');
}

/**
 * Construit une `ApiError` a partir d'un statut et du corps de la reponse.
 *
 * Ne rend jamais un message vide : un message vide laisse croire que rien ne
 * s'est passe (regle 6).
 */
export function parseApiError(status: number, body: unknown): ApiError {
  const secours = `HTTP ${status}`;

  if (!body || typeof body !== 'object') {
    const texte = typeof body === 'string' && body.trim() ? body.trim() : secours;
    return new ApiError(texte, { status, payload: body });
  }

  const detail = (body as Record<string, unknown>).detail;

  if (Array.isArray(detail)) {
    const texte = texteDeDetailListe(detail);
    return new ApiError(texte || secours, { status, payload: body });
  }

  if (detail && typeof detail === 'object') {
    const d = detail as Record<string, unknown>;
    const message =
      (typeof d.message === 'string' && d.message) ||
      (typeof d.error === 'string' && d.error) ||
      secours;
    return new ApiError(message, {
      status,
      code: typeof d.error === 'string' ? d.error : undefined,
      requiredTier: typeof d.required_tier === 'string' ? d.required_tier : undefined,
      upgradeUrl: typeof d.upgrade_url === 'string' ? d.upgrade_url : undefined,
      payload: body,
    });
  }

  if (typeof detail === 'string' && detail.trim()) {
    return new ApiError(detail.trim(), { status, payload: body });
  }

  const message = (body as Record<string, unknown>).message;
  if (typeof message === 'string' && message.trim()) {
    return new ApiError(message.trim(), { status, payload: body });
  }

  return new ApiError(secours, { status, payload: body });
}

/**
 * La reponse d'un agent dans une reponse de chat.
 *
 * `POST /api/projects/{id}/chat` rend `message` (schema `SophieResponse`) ;
 * `POST /api/pm-orchestrator/executions/{id}/chat` rend `response`. La page
 * projet lisait `assistant_message`, qui n'existe nulle part : la reponse
 * reussie de Sophie n'apparaissait jamais.
 *
 * Rend `null` — jamais une chaine vide — quand il n'y a rien a afficher, pour
 * que l'appelant puisse le dire au lieu d'ajouter une bulle vide.
 */
export function readChatReply(body: unknown): string | null {
  if (!body || typeof body !== 'object') return null;
  const b = body as Record<string, unknown>;

  const candidats: unknown[] = [b.message, b.response, b.content];
  const imbrique = b.assistant_message;
  if (imbrique && typeof imbrique === 'object') {
    const i = imbrique as Record<string, unknown>;
    candidats.push(i.message, i.content);
  } else if (typeof imbrique === 'string') {
    candidats.push(imbrique);
  }

  for (const candidat of candidats) {
    if (typeof candidat === 'string' && candidat.trim()) return candidat;
  }
  return null;
}

/** Les statuts de change request que le backend connait. */
const CR_STATUTS = [
  'draft',
  'submitted',
  'analyzed',
  'approved',
  'processing',
  'completed',
  'rejected',
] as const;

export type CrStatus = (typeof CR_STATUTS)[number];

/**
 * Le statut d'une CR apres une action, lu **dans la reponse**.
 *
 * `POST .../submit` repond `status: "analyzed"` (il soumet *et* analyse) ;
 * la page forcait « submitted », ce qui faisait disparaitre le bouton
 * d'approbation jusqu'au rechargement de la page.
 *
 * `attendu` sert de repli quand le serveur ne dit rien, ou dit quelque chose
 * d'inconnu : on ne fabrique pas un statut que le backend n'a pas nomme.
 */
export function readCrStatus(body: unknown, attendu: CrStatus): CrStatus {
  const lu = (() => {
    if (!body || typeof body !== 'object') return undefined;
    const b = body as Record<string, unknown>;
    if (typeof b.status === 'string') return b.status;
    const imbrique = b.change_request;
    if (imbrique && typeof imbrique === 'object') {
      const s = (imbrique as Record<string, unknown>).status;
      if (typeof s === 'string') return s;
    }
    return undefined;
  })();

  if (lu && (CR_STATUTS as readonly string[]).includes(lu)) return lu as CrStatus;
  return attendu;
}
