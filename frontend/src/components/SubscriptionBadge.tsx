/**
 * SubscriptionBadge Component - Section 9.3
 * Shows subscription tier and locked features in UI
 *
 * VAGUE 2 / LOT 3 — audit croise du 21/08/2026, « enums de paliers desalignes
 * cote frontend (`premium` vs `pro`, `team` absent de `FeatureGate`) ».
 *
 * Ce fichier connaissait `free | premium | enterprise`. Le backend sert
 * `free | pro | team | enterprise`. `premium` n'existe plus, et `team` etant
 * absent de la table d'ordre de `FeatureGate`, la comparaison portait sur un
 * `undefined` : **un compte Team se voyait refuser par l'UI une fonctionnalite
 * que le backend lui accorde.**
 *
 * Le vocabulaire vit desormais dans `lib/tiers`, teste seul, et le palier
 * requis peut venir directement du payload de `FeatureAccessError` — c'est
 * `FeatureGateFromError` en bas de fichier.
 *
 * ETAT REEL : au 23/08/2026, `grep -rn "SubscriptionBadge\|FeatureGate\|
 * LockedFeature\|useFeatureAccess" frontend/src` ne renvoie que ce fichier.
 * **Aucun appelant.** Le correctif est donc une remise en coherence du
 * vocabulaire, pas un changement de comportement observable : la page qui
 * affiche reellement les paliers, `Pricing.tsx`, utilise deja
 * `free | pro | team | enterprise`. Voir EXECUTION_VAGUE2.md.
 */
import React from 'react';
import { Crown, Lock, Sparkles, Building2, Users } from 'lucide-react';

import {
  type Tier,
  hasTier,
  normalizeTier,
  parseFeatureAccessError,
  tierLabel,
} from '../lib/tiers';

interface SubscriptionBadgeProps {
  /** Accepte aussi `premium`, alias historique de `pro`. */
  tier: Tier | string;
  showUpgrade?: boolean;
}

const tierConfig: Record<Tier, {
  icon: typeof Sparkles;
  color: string;
  borderColor: string;
}> = {
  free: {
    icon: Sparkles,
    color: 'bg-gray-100 text-gray-700',
    borderColor: 'border-gray-200',
  },
  pro: {
    icon: Crown,
    color: 'bg-yellow-100 text-yellow-700',
    borderColor: 'border-yellow-300',
  },
  team: {
    icon: Users,
    color: 'bg-blue-100 text-blue-700',
    borderColor: 'border-blue-300',
  },
  enterprise: {
    icon: Building2,
    color: 'bg-purple-100 text-purple-700',
    borderColor: 'border-purple-300',
  },
};

export const SubscriptionBadge: React.FC<SubscriptionBadgeProps> = ({
  tier,
  showUpgrade = false,
}) => {
  const resolved = normalizeTier(tier);
  const config = tierConfig[resolved];
  const Icon = config.icon;

  return (
    <div className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${config.color} border ${config.borderColor}`}>
      <Icon className="w-3.5 h-3.5" />
      <span>{tierLabel(resolved)}</span>
      {showUpgrade && resolved !== 'enterprise' && (
        <a href="/pricing" className="ml-1 text-blue-600 hover:underline">
          Upgrade
        </a>
      )}
    </div>
  );
};

interface LockedFeatureProps {
  featureName: string;
  requiredTier: Tier | string;
  /** Reprend `message` du payload backend quand il y en a un. */
  message?: string;
  upgradeUrl?: string;
  children?: React.ReactNode;
}

export const LockedFeature: React.FC<LockedFeatureProps> = ({
  featureName,
  requiredTier,
  message,
  upgradeUrl = '/pricing',
  children,
}) => {
  const resolved = normalizeTier(requiredTier);
  const label = tierLabel(resolved);

  return (
    <div className="relative">
      {/* Blurred content */}
      <div className="opacity-50 pointer-events-none blur-sm">
        {children}
      </div>

      {/* Lock overlay */}
      <div className="absolute inset-0 flex items-center justify-center bg-white/80 rounded-lg border-2 border-dashed border-gray-300">
        <div className="text-center p-4">
          <div className="w-12 h-12 mx-auto mb-3 rounded-full bg-gray-100 flex items-center justify-center">
            <Lock className="w-6 h-6 text-gray-500" />
          </div>
          <p className="text-sm font-medium text-gray-700 mb-1">
            {featureName}
          </p>
          <p className="text-xs text-gray-500 mb-3">
            {message ?? `Nécessite l'abonnement ${label}`}
          </p>
          <a
            href={upgradeUrl}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 text-white text-xs font-medium rounded-lg hover:bg-blue-700 transition-colors"
          >
            <Crown className="w-3.5 h-3.5" />
            Passer à {label}
          </a>
        </div>
      </div>
    </div>
  );
};

interface FeatureGateProps {
  feature: string;
  userTier: Tier | string;
  requiredTier: Tier | string;
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

export const FeatureGate: React.FC<FeatureGateProps> = ({
  feature,
  userTier,
  requiredTier,
  children,
  fallback,
}) => {
  if (hasTier(userTier, requiredTier)) {
    return <>{children}</>;
  }

  if (fallback) {
    return <>{fallback}</>;
  }

  return (
    <LockedFeature featureName={feature} requiredTier={requiredTier}>
      {children}
    </LockedFeature>
  );
};

interface FeatureGateFromErrorProps {
  /** Corps du 403 rendu par le backend, brut. */
  error: unknown;
  children: React.ReactNode;
}

/**
 * Variante qui ne devine rien : le palier requis, le libelle et l'URL d'upgrade
 * viennent du payload de `FeatureAccessError`. C'est le raccrochage demande par
 * l'audit — une constante recopiee dans le frontend se desaligne, un payload
 * non.
 *
 * Rend les enfants tels quels si l'erreur n'est pas un refus de palier : un
 * `limit_exceeded` ou un 403 d'authentification ne se traite pas avec une
 * invite d'upgrade.
 */
export const FeatureGateFromError: React.FC<FeatureGateFromErrorProps> = ({
  error,
  children,
}) => {
  const refusal = parseFeatureAccessError(error);
  if (!refusal) return <>{children}</>;

  return (
    <LockedFeature
      featureName={refusal.feature}
      requiredTier={refusal.requiredTier}
      message={refusal.message}
      upgradeUrl={refusal.upgradeUrl}
    >
      {children}
    </LockedFeature>
  );
};

// Hook for checking feature access
export const useFeatureAccess = (userTier: Tier | string) => {
  const resolved = normalizeTier(userTier);

  return {
    hasFeature: (requiredTier: Tier | string) => hasTier(resolved, requiredTier),
    // Les seuils sont releves de `TIER_FEATURES` (backend/app/models/
    // subscription.py), pas devines. Matrice au 23/08/2026 :
    //   build_phase      free:F pro:F team:T ent:T  -> Team
    //   git_integration  free:F pro:F team:T ent:T  -> Team
    //   custom_templates free:F pro:F team:F ent:T  -> Enterprise
    // L'ancienne version accordait BUILD et Git des le palier 1 (`premium`),
    // donc a un compte Pro, que le backend refuse en 403.
    canUseBuildPhase: hasTier(resolved, 'team'),
    canUseGitIntegration: hasTier(resolved, 'team'),
    canUseCustomTemplates: hasTier(resolved, 'enterprise'),
    tier: resolved,
  };
};

export default SubscriptionBadge;
