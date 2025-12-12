/**
 * SubscriptionBadge Component - Section 9.3
 * Shows subscription tier and locked features in UI
 */
import React from 'react';
import { Crown, Lock, Sparkles, Building2 } from 'lucide-react';

interface SubscriptionBadgeProps {
  tier: 'free' | 'premium' | 'enterprise';
  showUpgrade?: boolean;
}

const tierConfig = {
  free: {
    label: 'Free',
    icon: Sparkles,
    color: 'bg-gray-100 text-gray-700',
    borderColor: 'border-gray-200'
  },
  premium: {
    label: 'Premium',
    icon: Crown,
    color: 'bg-yellow-100 text-yellow-700',
    borderColor: 'border-yellow-300'
  },
  enterprise: {
    label: 'Enterprise',
    icon: Building2,
    color: 'bg-purple-100 text-purple-700',
    borderColor: 'border-purple-300'
  }
};

export const SubscriptionBadge: React.FC<SubscriptionBadgeProps> = ({ 
  tier, 
  showUpgrade = false 
}) => {
  const config = tierConfig[tier];
  const Icon = config.icon;

  return (
    <div className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${config.color} border ${config.borderColor}`}>
      <Icon className="w-3.5 h-3.5" />
      <span>{config.label}</span>
      {showUpgrade && tier !== 'enterprise' && (
        <a href="/pricing" className="ml-1 text-blue-600 hover:underline">
          Upgrade
        </a>
      )}
    </div>
  );
};

interface LockedFeatureProps {
  featureName: string;
  requiredTier: 'premium' | 'enterprise';
  children?: React.ReactNode;
}

export const LockedFeature: React.FC<LockedFeatureProps> = ({
  featureName,
  requiredTier,
  children
}) => {
  const tierLabel = requiredTier === 'premium' ? 'Premium' : 'Enterprise';
  
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
            Nécessite l'abonnement {tierLabel}
          </p>
          <a 
            href="/pricing"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 text-white text-xs font-medium rounded-lg hover:bg-blue-700 transition-colors"
          >
            <Crown className="w-3.5 h-3.5" />
            Passer à {tierLabel}
          </a>
        </div>
      </div>
    </div>
  );
};

interface FeatureGateProps {
  feature: string;
  userTier: 'free' | 'premium' | 'enterprise';
  requiredTier: 'premium' | 'enterprise';
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

export const FeatureGate: React.FC<FeatureGateProps> = ({
  feature,
  userTier,
  requiredTier,
  children,
  fallback
}) => {
  const tierOrder = { free: 0, premium: 1, enterprise: 2 };
  const hasAccess = tierOrder[userTier] >= tierOrder[requiredTier];

  if (hasAccess) {
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

// Hook for checking feature access
export const useFeatureAccess = (userTier: 'free' | 'premium' | 'enterprise') => {
  const tierOrder = { free: 0, premium: 1, enterprise: 2 };
  
  return {
    hasFeature: (requiredTier: 'free' | 'premium' | 'enterprise') => {
      return tierOrder[userTier] >= tierOrder[requiredTier];
    },
    canUseBuildPhase: tierOrder[userTier] >= 1,
    canUseGitIntegration: tierOrder[userTier] >= 1,
    canUseCustomTemplates: tierOrder[userTier] >= 2,
    tier: userTier
  };
};

export default SubscriptionBadge;
