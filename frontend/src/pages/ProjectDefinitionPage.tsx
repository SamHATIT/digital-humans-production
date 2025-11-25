import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowRight, Save } from 'lucide-react';
import { SALESFORCE_PRODUCTS, ORGANIZATION_TYPES } from '../lib/constants';

export default function ProjectDefinitionPage() {
  const navigate = useNavigate();
  const [formData, setFormData] = useState({
    name: '',
    salesforce_product: '',
    organization_type: '',
    business_requirements: '',
    existing_systems: '',
    compliance_requirements: '',
    expected_users: '',
    expected_data_volume: '',
    architecture_notes: ''
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    // TODO: Save project to backend
    console.log('Project data:', formData);
    // Navigate to execution page
    navigate('/execution');
  };

  return (
    <div className="max-w-4xl mx-auto">
      <header className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">
          Define Your Salesforce Project
        </h1>
        <p className="text-gray-600">
          Provide clear project requirements for AI agents
        </p>
      </header>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Project Information */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <h2 className="text-xl font-semibold mb-4">Project Information</h2>

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Project Name *
              </label>
              <input
                type="text"
                required
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="e.g., Service Cloud Implementation for TechCorp"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Salesforce Product *
              </label>
              <select
                required
                value={formData.salesforce_product}
                onChange={(e) => setFormData({ ...formData, salesforce_product: e.target.value })}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                <option value="">Select a product...</option>
                {SALESFORCE_PRODUCTS.map(product => (
                  <option key={product} value={product}>{product}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Organization Type *
              </label>
              <select
                required
                value={formData.organization_type}
                onChange={(e) => setFormData({ ...formData, organization_type: e.target.value })}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                <option value="">Select type...</option>
                {ORGANIZATION_TYPES.map(type => (
                  <option key={type} value={type}>{type}</option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* Business Requirements */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <h2 className="text-xl font-semibold mb-2">Business Requirements</h2>
          <p className="text-sm text-gray-600 mb-4">
            Describe WHAT needs to be achieved (3-7 bullet points max)
          </p>

          <textarea
            required
            value={formData.business_requirements}
            onChange={(e) => setFormData({ ...formData, business_requirements: e.target.value })}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            rows={8}
            placeholder="Example:
- Enable customer self-service through web portal
- Automate case routing based on product categories
- Integrate with existing ERP system for order status"
          />
        </div>

        {/* Technical Constraints */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <h2 className="text-xl font-semibold mb-4">Technical Constraints & Context</h2>

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Existing Systems & Integrations
              </label>
              <textarea
                value={formData.existing_systems}
                onChange={(e) => setFormData({ ...formData, existing_systems: e.target.value })}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                rows={3}
                placeholder="List existing systems, APIs, data sources..."
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Compliance & Security Requirements
              </label>
              <textarea
                value={formData.compliance_requirements}
                onChange={(e) => setFormData({ ...formData, compliance_requirements: e.target.value })}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                rows={3}
                placeholder="e.g., GDPR, HIPAA, data residency requirements..."
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Expected Number of Users
                </label>
                <input
                  type="number"
                  value={formData.expected_users}
                  onChange={(e) => setFormData({ ...formData, expected_users: e.target.value })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  placeholder="e.g., 500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Expected Data Volume
                </label>
                <input
                  type="text"
                  value={formData.expected_data_volume}
                  onChange={(e) => setFormData({ ...formData, expected_data_volume: e.target.value })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  placeholder="e.g., 100K records/month"
                />
              </div>
            </div>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex justify-between items-center pt-6 border-t border-gray-200">
          <button
            type="button"
            className="flex items-center gap-2 px-6 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition"
          >
            <Save size={16} />
            Save as Draft
          </button>

          <button
            type="submit"
            className="flex items-center gap-2 px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition"
          >
            Continue to Execution
            <ArrowRight size={16} />
          </button>
        </div>
      </form>
    </div>
  );
}
