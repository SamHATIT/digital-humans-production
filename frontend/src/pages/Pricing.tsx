/**
 * Pricing Page - Section 9.3
 * Shows subscription tiers comparison
 */
import React from 'react';
import { Check, X, Crown, Sparkles, Building2 } from 'lucide-react';

interface TierFeature {
  name: string;
  free: boolean | string;
  premium: boolean | string;
  enterprise: boolean | string;
}

const features: TierFeature[] = [
  // SDS Phase
  { name: 'Extraction des Business Requirements', free: true, premium: true, enterprise: true },
  { name: 'Génération des Use Cases', free: true, premium: true, enterprise: true },
  { name: 'Solution Design', free: true, premium: true, enterprise: true },
  { name: 'Document SDS (Word/PDF)', free: true, premium: true, enterprise: true },
  { name: 'Max BRs par projet', free: '30', premium: '100', enterprise: 'Illimité' },
  { name: 'Max projets', free: '3', premium: '20', enterprise: 'Illimité' },
  // BUILD Phase
  { name: 'Phase BUILD (génération de code)', free: false, premium: true, enterprise: true },
  { name: 'Déploiement SFDX', free: false, premium: true, enterprise: true },
  { name: 'Intégration Git', free: false, premium: true, enterprise: true },
  { name: 'Multi-environnements', free: false, premium: true, enterprise: true },
  // Advanced
  { name: 'Templates personnalisés', free: false, premium: false, enterprise: true },
  { name: 'Support prioritaire', free: false, premium: true, enterprise: true },
  { name: 'Support dédié', free: false, premium: false, enterprise: true },
  { name: 'Agents personnalisés', free: false, premium: false, enterprise: true },
  { name: 'Accès API', free: false, premium: false, enterprise: true },
  { name: 'SSO / SAML', free: false, premium: false, enterprise: true },
];

const FeatureValue: React.FC<{ value: boolean | string }> = ({ value }) => {
  if (typeof value === 'string') {
    return <span className="text-sm font-medium text-gray-900">{value}</span>;
  }
  return value ? (
    <Check className="w-5 h-5 text-green-500 mx-auto" />
  ) : (
    <X className="w-5 h-5 text-gray-300 mx-auto" />
  );
};

const Pricing: React.FC = () => {
  return (
    <div className="min-h-screen bg-gray-50 py-12 px-4">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="text-center mb-12">
          <h1 className="text-4xl font-bold text-gray-900 mb-4">
            Tarifs Digital Humans
          </h1>
          <p className="text-xl text-gray-600 max-w-2xl mx-auto">
            Automatisez votre développement Salesforce avec l'IA. 
            Commencez gratuitement et passez à l'échelle.
          </p>
        </div>

        {/* Pricing Cards */}
        <div className="grid md:grid-cols-3 gap-8 mb-16">
          {/* Free Tier */}
          <div className="bg-white rounded-2xl shadow-lg border border-gray-200 p-8">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-gray-100 flex items-center justify-center">
                <Sparkles className="w-5 h-5 text-gray-600" />
              </div>
              <div>
                <h3 className="text-xl font-bold text-gray-900">Free</h3>
                <p className="text-sm text-gray-500">SDS Generator</p>
              </div>
            </div>
            <div className="mb-6">
              <span className="text-4xl font-bold text-gray-900">0€</span>
              <span className="text-gray-500">/mois</span>
            </div>
            <p className="text-gray-600 mb-6">
              Parfait pour découvrir la génération automatique de SDS.
            </p>
            <button className="w-full py-3 px-4 bg-gray-100 text-gray-700 font-medium rounded-lg hover:bg-gray-200 transition-colors">
              Commencer gratuitement
            </button>
            <ul className="mt-6 space-y-3">
              <li className="flex items-center gap-2 text-sm text-gray-600">
                <Check className="w-4 h-4 text-green-500" />
                Génération de SDS
              </li>
              <li className="flex items-center gap-2 text-sm text-gray-600">
                <Check className="w-4 h-4 text-green-500" />
                Export Word/PDF
              </li>
              <li className="flex items-center gap-2 text-sm text-gray-600">
                <Check className="w-4 h-4 text-green-500" />
                Jusqu'à 3 projets
              </li>
            </ul>
          </div>

          {/* Premium Tier */}
          <div className="bg-white rounded-2xl shadow-xl border-2 border-yellow-400 p-8 relative">
            <div className="absolute -top-3 left-1/2 -translate-x-1/2">
              <span className="bg-yellow-400 text-yellow-900 text-xs font-bold px-3 py-1 rounded-full">
                POPULAIRE
              </span>
            </div>
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-yellow-100 flex items-center justify-center">
                <Crown className="w-5 h-5 text-yellow-600" />
              </div>
              <div>
                <h3 className="text-xl font-bold text-gray-900">Premium</h3>
                <p className="text-sm text-gray-500">Full Automation</p>
              </div>
            </div>
            <div className="mb-6">
              <span className="text-4xl font-bold text-gray-900">99€</span>
              <span className="text-gray-500">/mois</span>
            </div>
            <p className="text-gray-600 mb-6">
              Automatisation complète du développement Salesforce.
            </p>
            <button className="w-full py-3 px-4 bg-yellow-500 text-white font-medium rounded-lg hover:bg-yellow-600 transition-colors">
              Passer à Premium
            </button>
            <ul className="mt-6 space-y-3">
              <li className="flex items-center gap-2 text-sm text-gray-600">
                <Check className="w-4 h-4 text-green-500" />
                Tout Free +
              </li>
              <li className="flex items-center gap-2 text-sm text-gray-600">
                <Check className="w-4 h-4 text-green-500" />
                Phase BUILD (code Apex, LWC, Flows)
              </li>
              <li className="flex items-center gap-2 text-sm text-gray-600">
                <Check className="w-4 h-4 text-green-500" />
                Déploiement SFDX automatique
              </li>
              <li className="flex items-center gap-2 text-sm text-gray-600">
                <Check className="w-4 h-4 text-green-500" />
                Intégration Git
              </li>
              <li className="flex items-center gap-2 text-sm text-gray-600">
                <Check className="w-4 h-4 text-green-500" />
                Jusqu'à 20 projets
              </li>
            </ul>
          </div>

          {/* Enterprise Tier */}
          <div className="bg-white rounded-2xl shadow-lg border border-gray-200 p-8">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-purple-100 flex items-center justify-center">
                <Building2 className="w-5 h-5 text-purple-600" />
              </div>
              <div>
                <h3 className="text-xl font-bold text-gray-900">Enterprise</h3>
                <p className="text-sm text-gray-500">Custom Solution</p>
              </div>
            </div>
            <div className="mb-6">
              <span className="text-4xl font-bold text-gray-900">Sur devis</span>
            </div>
            <p className="text-gray-600 mb-6">
              Solution personnalisée pour les grandes équipes.
            </p>
            <button className="w-full py-3 px-4 bg-purple-600 text-white font-medium rounded-lg hover:bg-purple-700 transition-colors">
              Nous contacter
            </button>
            <ul className="mt-6 space-y-3">
              <li className="flex items-center gap-2 text-sm text-gray-600">
                <Check className="w-4 h-4 text-green-500" />
                Tout Premium +
              </li>
              <li className="flex items-center gap-2 text-sm text-gray-600">
                <Check className="w-4 h-4 text-green-500" />
                Projets illimités
              </li>
              <li className="flex items-center gap-2 text-sm text-gray-600">
                <Check className="w-4 h-4 text-green-500" />
                Templates personnalisés
              </li>
              <li className="flex items-center gap-2 text-sm text-gray-600">
                <Check className="w-4 h-4 text-green-500" />
                Agents IA personnalisés
              </li>
              <li className="flex items-center gap-2 text-sm text-gray-600">
                <Check className="w-4 h-4 text-green-500" />
                SSO / API Access
              </li>
            </ul>
          </div>
        </div>

        {/* Feature Comparison Table */}
        <div className="bg-white rounded-2xl shadow-lg overflow-hidden">
          <div className="px-6 py-4 bg-gray-50 border-b">
            <h2 className="text-xl font-bold text-gray-900">Comparaison détaillée</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b">
                  <th className="text-left py-4 px-6 font-medium text-gray-500">Fonctionnalité</th>
                  <th className="text-center py-4 px-6 font-medium text-gray-500 w-32">Free</th>
                  <th className="text-center py-4 px-6 font-medium text-gray-500 w-32 bg-yellow-50">Premium</th>
                  <th className="text-center py-4 px-6 font-medium text-gray-500 w-32">Enterprise</th>
                </tr>
              </thead>
              <tbody>
                {features.map((feature, index) => (
                  <tr key={feature.name} className={index % 2 === 0 ? 'bg-gray-50' : ''}>
                    <td className="py-3 px-6 text-sm text-gray-700">{feature.name}</td>
                    <td className="py-3 px-6 text-center">
                      <FeatureValue value={feature.free} />
                    </td>
                    <td className="py-3 px-6 text-center bg-yellow-50/50">
                      <FeatureValue value={feature.premium} />
                    </td>
                    <td className="py-3 px-6 text-center">
                      <FeatureValue value={feature.enterprise} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* FAQ */}
        <div className="mt-16 text-center">
          <h2 className="text-2xl font-bold text-gray-900 mb-4">Des questions ?</h2>
          <p className="text-gray-600 mb-6">
            Notre équipe est là pour vous aider à choisir la formule adaptée à vos besoins.
          </p>
          <a 
            href="mailto:contact@digital-humans.ai"
            className="inline-flex items-center gap-2 px-6 py-3 bg-gray-900 text-white font-medium rounded-lg hover:bg-gray-800 transition-colors"
          >
            Contacter l'équipe commerciale
          </a>
        </div>
      </div>
    </div>
  );
};

export default Pricing;
