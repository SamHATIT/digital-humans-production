import { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Loader2, Rocket, FileText, Users } from 'lucide-react';
import { projects } from '../services/api';
import Navbar from '../components/Navbar';
import WorkflowEditor from '../components/WorkflowEditor';
import { MANDATORY_AGENTS } from '../constants';

export default function NewProject() {
  const navigate = useNavigate();
  const [name, setName] = useState('');
  const [businessRequirements, setBusinessRequirements] = useState('');
  const [salesforceProduct, setSalesforceProduct] = useState('Sales Cloud');
  const [organizationType, setOrganizationType] = useState('New Implementation');
  const [selectedAgents, setSelectedAgents] = useState<string[]>(MANDATORY_AGENTS);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSelectionChange = useCallback((agents: string[]) => {
    // Ensure mandatory agents are always included
    const withMandatory = Array.from(new Set([...MANDATORY_AGENTS, ...agents]));
    setSelectedAgents(withMandatory);
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setError('Project name is required');
      return;
    }
    if (!businessRequirements.trim() || businessRequirements.trim().length < 10) {
      setError('Business requirements must be at least 10 characters');
      return;
    }

    setError('');
    setIsLoading(true);

    try {
      const project = await projects.create({
        name: name.trim(),
        description: businessRequirements.trim(),
        salesforce_product: salesforceProduct,
        organization_type: organizationType,
        business_requirements: businessRequirements.trim(),
        selected_agents: selectedAgents,
      });

      navigate(`/execution/${project.id}`);
    } catch (err: any) {
      console.error('Failed to create project:', err);
      // Better error handling
      if (err.detail) {
        if (Array.isArray(err.detail)) {
          setError(err.detail.map((e: any) => e.msg || e).join(', '));
        } else {
          setError(String(err.detail));
        }
      } else {
        setError(err.message || 'Failed to create project');
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#0B1120]">
      <Navbar />

      {/* Background Effects */}
      <div className="fixed top-0 left-0 w-full h-full pointer-events-none">
        <div className="absolute top-[-20%] right-[-10%] w-[600px] h-[600px] bg-purple-900/20 rounded-full blur-[150px]" />
        <div className="absolute bottom-[-20%] left-[-10%] w-[600px] h-[600px] bg-cyan-900/15 rounded-full blur-[150px]" />
      </div>

      <main className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
        {/* Header */}
        <div className="mb-10 text-center">
          <h1 className="text-4xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-purple-500">
            Create New Project
          </h1>
          <p className="mt-2 text-slate-400">
            Design your workflow and assign agents to each phase
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-8">
          {error && (
            <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 text-red-400">
              {error}
            </div>
          )}

          {/* Project Details */}
          <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-2xl p-6">
            <div className="flex items-center gap-3 mb-6">
              <div className="w-10 h-10 rounded-xl bg-cyan-500/20 flex items-center justify-center">
                <FileText className="w-5 h-5 text-cyan-400" />
              </div>
              <h2 className="text-xl font-bold text-white">Project Details</h2>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <label className="block text-sm font-medium text-slate-400 mb-2">
                  Project Name *
                </label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full bg-slate-900/50 border border-slate-600 rounded-xl px-4 py-3 text-white placeholder-slate-500 focus:ring-2 focus:ring-cyan-500 focus:border-transparent outline-none transition-all"
                  placeholder="e.g. CRM Migration 2024"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-400 mb-2">
                  Salesforce Product *
                </label>
                <select
                  value={salesforceProduct}
                  onChange={(e) => setSalesforceProduct(e.target.value)}
                  className="w-full bg-slate-900/50 border border-slate-600 rounded-xl px-4 py-3 text-white focus:ring-2 focus:ring-cyan-500 focus:border-transparent outline-none transition-all"
                >
                  <option value="Sales Cloud">Sales Cloud</option>
                  <option value="Service Cloud">Service Cloud</option>
                  <option value="Marketing Cloud">Marketing Cloud</option>
                  <option value="Commerce Cloud">Commerce Cloud</option>
                  <option value="Experience Cloud">Experience Cloud</option>
                  <option value="Field Service">Field Service</option>
                  <option value="CPQ">CPQ</option>
                  <option value="Multiple Products">Multiple Products</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-400 mb-2">
                  Organization Type *
                </label>
                <select
                  value={organizationType}
                  onChange={(e) => setOrganizationType(e.target.value)}
                  className="w-full bg-slate-900/50 border border-slate-600 rounded-xl px-4 py-3 text-white focus:ring-2 focus:ring-cyan-500 focus:border-transparent outline-none transition-all"
                >
                  <option value="New Implementation">New Implementation</option>
                  <option value="Existing Org Enhancement">Existing Org Enhancement</option>
                  <option value="Migration">Migration</option>
                  <option value="Integration Project">Integration Project</option>
                </select>
              </div>

              <div className="md:col-span-2">
                <label className="block text-sm font-medium text-slate-400 mb-2">
                  Business Requirements *
                </label>
                <textarea
                  value={businessRequirements}
                  onChange={(e) => setBusinessRequirements(e.target.value)}
                  rows={5}
                  className="w-full bg-slate-900/50 border border-slate-600 rounded-xl px-4 py-3 text-white placeholder-slate-500 focus:ring-2 focus:ring-cyan-500 focus:border-transparent outline-none transition-all resize-none"
                  placeholder="Describe your business requirements, objectives, and key features needed (minimum 10 characters)..."
                  required
                />
              </div>
            </div>
          </div>

          {/* Workflow Editor */}
          <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-2xl p-6">
            <div className="flex items-center gap-3 mb-6">
              <div className="w-10 h-10 rounded-xl bg-purple-500/20 flex items-center justify-center">
                <Users className="w-5 h-5 text-purple-400" />
              </div>
              <div>
                <h2 className="text-xl font-bold text-white">Workflow & Agent Assignment</h2>
                <p className="text-sm text-slate-400">Drag agents between phases to customize your workflow</p>
              </div>
            </div>

            <WorkflowEditor onSelectionChange={handleSelectionChange} />
          </div>

          {/* Summary & Submit */}
          <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-2xl p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-slate-400 text-sm">Selected Agents</p>
                <p className="text-2xl font-bold text-white">{selectedAgents.length} / 10</p>
              </div>

              <button
                type="submit"
                disabled={isLoading || !name.trim() || businessRequirements.trim().length < 10}
                className="inline-flex items-center gap-2 px-8 py-4 bg-gradient-to-r from-cyan-500 to-purple-600 text-white font-medium rounded-xl hover:from-cyan-600 hover:to-purple-700 transition-all shadow-lg shadow-cyan-500/25 hover:shadow-cyan-500/40 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" />
                    Creating...
                  </>
                ) : (
                  <>
                    <Rocket className="w-5 h-5" />
                    Create & Launch
                  </>
                )}
              </button>
            </div>
          </div>
        </form>
      </main>
    </div>
  );
}
