import { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { 
  Loader2, ChevronRight, ChevronLeft, Check, 
  Building2, Target, Cloud, GitBranch, FileText, Rocket,
  AlertCircle, CheckCircle2
} from 'lucide-react';
import { wizard } from '../services/api';
import Navbar from '../components/Navbar';

// Types
type ProjectType = 'greenfield' | 'existing';
type TargetObjective = 'sds_only' | 'sds_and_build';

interface WizardData {
  // Step 1: Basic Info
  name: string;
  description: string;
  project_code: string;
  client_name: string;
  client_contact_name: string;
  client_contact_email: string;
  client_contact_phone: string;
  start_date: string;
  end_date: string;
  // Step 2: Project Type
  project_type: ProjectType;
  salesforce_product: string;
  // Step 3: Objective
  target_objective: TargetObjective;
  // Step 4: Salesforce
  sf_instance_url: string;
  sf_username: string;
  sf_access_token: string;
  // Step 5: Git
  git_repo_url: string;
  git_branch: string;
  git_token: string;
  // Step 6: Requirements
  business_requirements: string;
  selected_sds_agents: string[];
  existing_systems: string;
  compliance_requirements: string;
  expected_users: string;
  expected_data_volume: string;
}

const STEPS = [
  { id: 1, title: 'Informations', icon: Building2 },
  { id: 2, title: 'Type', icon: Target },
  { id: 3, title: 'Objectif', icon: Rocket },
  { id: 4, title: 'Salesforce', icon: Cloud },
  { id: 5, title: 'Git', icon: GitBranch },
  { id: 6, title: 'Exigences', icon: FileText },
];

const SF_PRODUCTS = [
  'Sales Cloud', 'Service Cloud', 'Marketing Cloud', 
  'Commerce Cloud', 'Experience Cloud', 'Platform'
];

const DEFAULT_AGENTS = ['qa', 'devops', 'data', 'trainer'];

export default function ProjectWizard() {
  const navigate = useNavigate();
  const { projectId } = useParams();
  
  const [currentStep, setCurrentStep] = useState(1);
  const [projectIdState, setProjectIdState] = useState<number | null>(projectId ? parseInt(projectId) : null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [sfTestResult, setSfTestResult] = useState<{success: boolean; message: string} | null>(null);
  const [gitTestResult, setGitTestResult] = useState<{success: boolean; message: string} | null>(null);
  
  const [data, setData] = useState<WizardData>({
    name: '',
    description: '',
    project_code: '',
    client_name: '',
    client_contact_name: '',
    client_contact_email: '',
    client_contact_phone: '',
    start_date: '',
    end_date: '',
    project_type: 'greenfield',
    salesforce_product: 'Sales Cloud',
    target_objective: 'sds_only',
    sf_instance_url: '',
    sf_username: '',
    sf_access_token: '',
    git_repo_url: '',
    git_branch: 'main',
    git_token: '',
    business_requirements: '',
    selected_sds_agents: DEFAULT_AGENTS,
    existing_systems: '',
    compliance_requirements: '',
    expected_users: '',
    expected_data_volume: '',
  });

  // Load existing project data if editing
  useEffect(() => {
    if (projectId) {
      loadProjectProgress();
    }
  }, [projectId]);

  const loadProjectProgress = async () => {
    try {
      const progress = await wizard.getProgress(parseInt(projectId!));
      setCurrentStep(progress.wizard_step || 1);
      setProjectIdState(progress.project_id);
    } catch (err) {
      console.error('Failed to load progress:', err);
    }
  };

  const updateField = (field: keyof WizardData, value: any) => {
    setData(prev => ({ ...prev, [field]: value }));
  };

  const validateStep = (): boolean => {
    setError('');
    
    switch (currentStep) {
      case 1:
        if (!data.name.trim()) {
          setError('Le nom du projet est requis');
          return false;
        }
        break;
      case 6:
        if (!data.business_requirements.trim() || data.business_requirements.length < 20) {
          setError('Les exigences métier doivent contenir au moins 20 caractères');
          return false;
        }
        break;
    }
    return true;
  };

  const handleNext = async () => {
    if (!validateStep()) return;
    
    setIsLoading(true);
    setError('');
    
    try {
      if (currentStep === 1 && !projectIdState) {
        // Create project
        const result = await wizard.create({
          name: data.name,
          description: data.description,
          project_code: data.project_code,
          client_name: data.client_name,
          client_contact_name: data.client_contact_name,
          client_contact_email: data.client_contact_email,
          client_contact_phone: data.client_contact_phone,
          start_date: data.start_date || undefined,
          end_date: data.end_date || undefined,
        });
        setProjectIdState(result.project_id);
        setCurrentStep(2);
      } else if (projectIdState) {
        // Update step
        const stepData = getStepData(currentStep);
        await wizard.updateStep(projectIdState, currentStep, stepData);
        
        if (currentStep < 6) {
          // Skip step 4 if greenfield, skip step 5 if SDS only
          let nextStep = currentStep + 1;
          if (nextStep === 4 && data.project_type === 'greenfield') {
            nextStep = 5;
          }
          if (nextStep === 5 && data.target_objective === 'sds_only') {
            nextStep = 6;
          }
          setCurrentStep(nextStep);
        } else {
          // Wizard complete - redirect to execution
          navigate(`/execution/${projectIdState}`);
        }
      }
    } catch (err: any) {
      setError(err.message || 'Une erreur est survenue');
    } finally {
      setIsLoading(false);
    }
  };

  const handleBack = () => {
    if (currentStep > 1) {
      let prevStep = currentStep - 1;
      // Skip step 5 if SDS only
      if (prevStep === 5 && data.target_objective === 'sds_only') {
        prevStep = 4;
      }
      // Skip step 4 if greenfield
      if (prevStep === 4 && data.project_type === 'greenfield') {
        prevStep = 3;
      }
      setCurrentStep(prevStep);
    }
  };

  const getStepData = (step: number) => {
    switch (step) {
      case 1:
        return {
          name: data.name,
          description: data.description,
          project_code: data.project_code,
          client_name: data.client_name,
          client_contact_name: data.client_contact_name,
          client_contact_email: data.client_contact_email,
          client_contact_phone: data.client_contact_phone,
          start_date: data.start_date,
          end_date: data.end_date,
        };
      case 2:
        return {
          project_type: data.project_type,
          salesforce_product: data.salesforce_product,
        };
      case 3:
        return { target_objective: data.target_objective };
      case 4:
        return {
          sf_instance_url: data.sf_instance_url,
          sf_username: data.sf_username,
          sf_access_token: data.sf_access_token,
        };
      case 5:
        return {
          git_repo_url: data.git_repo_url,
          git_branch: data.git_branch,
          git_token: data.git_token,
        };
      case 6:
        return {
          business_requirements: data.business_requirements,
          selected_sds_agents: data.selected_sds_agents,
          existing_systems: data.existing_systems,
          compliance_requirements: data.compliance_requirements,
          expected_users: parseInt(data.expected_users) || null,
          expected_data_volume: data.expected_data_volume,
        };
      default:
        return {};
    }
  };

  const testSalesforce = async () => {
    if (!projectIdState) return;
    setIsLoading(true);
    try {
      // First save current SF data
      await wizard.updateStep(projectIdState, 4, {
        sf_instance_url: data.sf_instance_url,
        sf_username: data.sf_username,
        sf_access_token: data.sf_access_token,
      });
      // Then test
      const result = await wizard.testSalesforce(projectIdState);
      setSfTestResult(result);
    } catch (err: any) {
      setSfTestResult({ success: false, message: err.message });
    } finally {
      setIsLoading(false);
    }
  };

  const testGit = async () => {
    if (!projectIdState) return;
    setIsLoading(true);
    try {
      // First save current Git data
      await wizard.updateStep(projectIdState, 5, {
        git_repo_url: data.git_repo_url,
        git_branch: data.git_branch,
        git_token: data.git_token,
      });
      // Then test
      const result = await wizard.testGit(projectIdState);
      setGitTestResult(result);
    } catch (err: any) {
      setGitTestResult({ success: false, message: err.message });
    } finally {
      setIsLoading(false);
    }
  };

  // Determine which steps to show
  const visibleSteps = STEPS.filter(step => {
    if (step.id === 4 && data.project_type === 'greenfield') return false;
    if (step.id === 5 && data.target_objective === 'sds_only') return false;
    return true;
  });

  return (
    <div className="min-h-screen bg-[#0B1120]">
      <Navbar />

      {/* Background */}
      <div className="fixed top-0 left-0 w-full h-full pointer-events-none">
        <div className="absolute top-[-20%] right-[-10%] w-[600px] h-[600px] bg-purple-900/20 rounded-full blur-[150px]" />
        <div className="absolute bottom-[-20%] left-[-10%] w-[600px] h-[600px] bg-cyan-900/15 rounded-full blur-[150px]" />
      </div>

      <main className="relative max-w-4xl mx-auto px-4 py-10">
        {/* Header */}
        <div className="mb-8 text-center">
          <h1 className="text-3xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-purple-500">
            Nouveau Projet
          </h1>
          <p className="mt-2 text-slate-400">
            Configurez votre projet en quelques étapes
          </p>
        </div>

        {/* Progress Steps */}
        <div className="mb-8">
          <div className="flex justify-between items-center">
            {visibleSteps.map((step, index) => {
              const Icon = step.icon;
              const isActive = step.id === currentStep;
              const isCompleted = step.id < currentStep;
              
              return (
                <div key={step.id} className="flex items-center">
                  <div className={`flex flex-col items-center ${index > 0 ? 'ml-4' : ''}`}>
                    <div className={`
                      w-12 h-12 rounded-full flex items-center justify-center transition-all
                      ${isActive ? 'bg-cyan-500 text-white' : 
                        isCompleted ? 'bg-green-500 text-white' : 
                        'bg-slate-700 text-slate-400'}
                    `}>
                      {isCompleted ? <Check className="w-6 h-6" /> : <Icon className="w-6 h-6" />}
                    </div>
                    <span className={`mt-2 text-xs ${isActive ? 'text-cyan-400' : 'text-slate-500'}`}>
                      {step.title}
                    </span>
                  </div>
                  {index < visibleSteps.length - 1 && (
                    <div className={`h-0.5 w-12 mx-2 ${isCompleted ? 'bg-green-500' : 'bg-slate-700'}`} />
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Error */}
        {error && (
          <div className="mb-6 bg-red-500/10 border border-red-500/30 rounded-xl p-4 text-red-400 flex items-center gap-2">
            <AlertCircle className="w-5 h-5" />
            {error}
          </div>
        )}

        {/* Step Content */}
        <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-2xl p-6">
          {currentStep === 1 && (
            <Step1BasicInfo data={data} updateField={updateField} />
          )}
          {currentStep === 2 && (
            <Step2ProjectType data={data} updateField={updateField} products={SF_PRODUCTS} />
          )}
          {currentStep === 3 && (
            <Step3Objective data={data} updateField={updateField} />
          )}
          {currentStep === 4 && (
            <Step4Salesforce 
              data={data} 
              updateField={updateField} 
              onTest={testSalesforce}
              testResult={sfTestResult}
              isLoading={isLoading}
            />
          )}
          {currentStep === 5 && (
            <Step5Git 
              data={data} 
              updateField={updateField}
              onTest={testGit}
              testResult={gitTestResult}
              isLoading={isLoading}
            />
          )}
          {currentStep === 6 && (
            <Step6Requirements data={data} updateField={updateField} />
          )}
        </div>

        {/* Navigation */}
        <div className="mt-6 flex justify-between">
          <button
            onClick={handleBack}
            disabled={currentStep === 1 || isLoading}
            className={`
              flex items-center gap-2 px-6 py-3 rounded-xl transition-all
              ${currentStep === 1 ? 'opacity-50 cursor-not-allowed bg-slate-700' : 
                'bg-slate-700 hover:bg-slate-600 text-white'}
            `}
          >
            <ChevronLeft className="w-5 h-5" />
            Précédent
          </button>

          <button
            onClick={handleNext}
            disabled={isLoading}
            className="flex items-center gap-2 px-6 py-3 rounded-xl bg-gradient-to-r from-cyan-500 to-purple-500 text-white font-medium hover:opacity-90 transition-all disabled:opacity-50"
          >
            {isLoading && <Loader2 className="w-5 h-5 animate-spin" />}
            {currentStep === 6 ? 'Créer le projet' : 'Suivant'}
            {currentStep < 6 && <ChevronRight className="w-5 h-5" />}
          </button>
        </div>
      </main>
    </div>
  );
}

// Step Components
function Step1BasicInfo({ data, updateField }: { data: WizardData; updateField: (f: keyof WizardData, v: any) => void }) {
  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold text-white flex items-center gap-2">
        <Building2 className="w-6 h-6 text-cyan-400" />
        Informations du projet
      </h2>
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="md:col-span-2">
          <label className="block text-sm text-slate-400 mb-2">Nom du projet *</label>
          <input
            type="text"
            value={data.name}
            onChange={(e) => updateField('name', e.target.value)}
            className="w-full px-4 py-3 bg-slate-900/50 border border-slate-600 rounded-xl text-white focus:border-cyan-500 focus:outline-none"
            placeholder="Ex: CRM Modernization"
          />
        </div>
        
        <div className="md:col-span-2">
          <label className="block text-sm text-slate-400 mb-2">Description</label>
          <textarea
            value={data.description}
            onChange={(e) => updateField('description', e.target.value)}
            className="w-full px-4 py-3 bg-slate-900/50 border border-slate-600 rounded-xl text-white focus:border-cyan-500 focus:outline-none"
            rows={2}
            placeholder="Brève description du projet"
          />
        </div>

        <div>
          <label className="block text-sm text-slate-400 mb-2">Code projet</label>
          <input
            type="text"
            value={data.project_code}
            onChange={(e) => updateField('project_code', e.target.value)}
            className="w-full px-4 py-3 bg-slate-900/50 border border-slate-600 rounded-xl text-white focus:border-cyan-500 focus:outline-none"
            placeholder="PRJ-2025-001"
          />
        </div>

        <div>
          <label className="block text-sm text-slate-400 mb-2">Nom du client</label>
          <input
            type="text"
            value={data.client_name}
            onChange={(e) => updateField('client_name', e.target.value)}
            className="w-full px-4 py-3 bg-slate-900/50 border border-slate-600 rounded-xl text-white focus:border-cyan-500 focus:outline-none"
            placeholder="Acme Corp"
          />
        </div>

        <div>
          <label className="block text-sm text-slate-400 mb-2">Contact client</label>
          <input
            type="text"
            value={data.client_contact_name}
            onChange={(e) => updateField('client_contact_name', e.target.value)}
            className="w-full px-4 py-3 bg-slate-900/50 border border-slate-600 rounded-xl text-white focus:border-cyan-500 focus:outline-none"
            placeholder="Jean Dupont"
          />
        </div>

        <div>
          <label className="block text-sm text-slate-400 mb-2">Email contact</label>
          <input
            type="email"
            value={data.client_contact_email}
            onChange={(e) => updateField('client_contact_email', e.target.value)}
            className="w-full px-4 py-3 bg-slate-900/50 border border-slate-600 rounded-xl text-white focus:border-cyan-500 focus:outline-none"
            placeholder="jean@acme.com"
          />
        </div>

        <div>
          <label className="block text-sm text-slate-400 mb-2">Date de début</label>
          <input
            type="date"
            value={data.start_date}
            onChange={(e) => updateField('start_date', e.target.value)}
            className="w-full px-4 py-3 bg-slate-900/50 border border-slate-600 rounded-xl text-white focus:border-cyan-500 focus:outline-none"
          />
        </div>

        <div>
          <label className="block text-sm text-slate-400 mb-2">Date de fin prévue</label>
          <input
            type="date"
            value={data.end_date}
            onChange={(e) => updateField('end_date', e.target.value)}
            className="w-full px-4 py-3 bg-slate-900/50 border border-slate-600 rounded-xl text-white focus:border-cyan-500 focus:outline-none"
          />
        </div>
      </div>
    </div>
  );
}

function Step2ProjectType({ data, updateField, products }: { data: WizardData; updateField: (f: keyof WizardData, v: any) => void; products: string[] }) {
  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold text-white flex items-center gap-2">
        <Target className="w-6 h-6 text-cyan-400" />
        Type de projet
      </h2>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <button
          onClick={() => updateField('project_type', 'greenfield')}
          className={`p-6 rounded-xl border-2 transition-all text-left ${
            data.project_type === 'greenfield' 
              ? 'border-cyan-500 bg-cyan-500/10' 
              : 'border-slate-600 bg-slate-900/50 hover:border-slate-500'
          }`}
        >
          <div className="text-2xl mb-2">🌱</div>
          <h3 className="text-lg font-medium text-white">Greenfield</h3>
          <p className="text-sm text-slate-400 mt-1">
            Nouvelle implémentation Salesforce sans org existant
          </p>
        </button>

        <button
          onClick={() => updateField('project_type', 'existing')}
          className={`p-6 rounded-xl border-2 transition-all text-left ${
            data.project_type === 'existing' 
              ? 'border-cyan-500 bg-cyan-500/10' 
              : 'border-slate-600 bg-slate-900/50 hover:border-slate-500'
          }`}
        >
          <div className="text-2xl mb-2">🔄</div>
          <h3 className="text-lg font-medium text-white">Existant</h3>
          <p className="text-sm text-slate-400 mt-1">
            Évolution d'un org Salesforce existant
          </p>
        </button>
      </div>

      <div>
        <label className="block text-sm text-slate-400 mb-2">Produit Salesforce</label>
        <select
          value={data.salesforce_product}
          onChange={(e) => updateField('salesforce_product', e.target.value)}
          className="w-full px-4 py-3 bg-slate-900/50 border border-slate-600 rounded-xl text-white focus:border-cyan-500 focus:outline-none"
        >
          {products.map(p => (
            <option key={p} value={p}>{p}</option>
          ))}
        </select>
      </div>
    </div>
  );
}

function Step3Objective({ data, updateField }: { data: WizardData; updateField: (f: keyof WizardData, v: any) => void }) {
  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold text-white flex items-center gap-2">
        <Rocket className="w-6 h-6 text-cyan-400" />
        Objectif du projet
      </h2>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <button
          onClick={() => updateField('target_objective', 'sds_only')}
          className={`p-6 rounded-xl border-2 transition-all text-left ${
            data.target_objective === 'sds_only' 
              ? 'border-cyan-500 bg-cyan-500/10' 
              : 'border-slate-600 bg-slate-900/50 hover:border-slate-500'
          }`}
        >
          <div className="text-2xl mb-2">📄</div>
          <h3 className="text-lg font-medium text-white">SDS uniquement</h3>
          <p className="text-sm text-slate-400 mt-1">
            Générer le document de spécifications (gratuit)
          </p>
          <span className="inline-block mt-3 px-3 py-1 bg-green-500/20 text-green-400 text-xs rounded-full">
            Gratuit
          </span>
        </button>

        <button
          onClick={() => updateField('target_objective', 'sds_and_build')}
          className={`p-6 rounded-xl border-2 transition-all text-left ${
            data.target_objective === 'sds_and_build' 
              ? 'border-purple-500 bg-purple-500/10' 
              : 'border-slate-600 bg-slate-900/50 hover:border-slate-500'
          }`}
        >
          <div className="text-2xl mb-2">🚀</div>
          <h3 className="text-lg font-medium text-white">SDS + BUILD</h3>
          <p className="text-sm text-slate-400 mt-1">
            Générer le SDS et déployer automatiquement
          </p>
          <span className="inline-block mt-3 px-3 py-1 bg-purple-500/20 text-purple-400 text-xs rounded-full">
            Premium
          </span>
        </button>
      </div>
    </div>
  );
}

function Step4Salesforce({ data, updateField, onTest, testResult, isLoading }: { 
  data: WizardData; 
  updateField: (f: keyof WizardData, v: any) => void;
  onTest: () => void;
  testResult: {success: boolean; message: string} | null;
  isLoading: boolean;
}) {
  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold text-white flex items-center gap-2">
        <Cloud className="w-6 h-6 text-cyan-400" />
        Connexion Salesforce
      </h2>
      <p className="text-slate-400 text-sm">
        Connectez votre org Salesforce pour analyser la configuration existante
      </p>

      <div className="space-y-4">
        <div>
          <label className="block text-sm text-slate-400 mb-2">URL de l'instance</label>
          <input
            type="url"
            value={data.sf_instance_url}
            onChange={(e) => updateField('sf_instance_url', e.target.value)}
            className="w-full px-4 py-3 bg-slate-900/50 border border-slate-600 rounded-xl text-white focus:border-cyan-500 focus:outline-none"
            placeholder="https://mycompany.my.salesforce.com"
          />
        </div>

        <div>
          <label className="block text-sm text-slate-400 mb-2">Nom d'utilisateur</label>
          <input
            type="text"
            value={data.sf_username}
            onChange={(e) => updateField('sf_username', e.target.value)}
            className="w-full px-4 py-3 bg-slate-900/50 border border-slate-600 rounded-xl text-white focus:border-cyan-500 focus:outline-none"
            placeholder="admin@mycompany.com"
          />
        </div>

        <div>
          <label className="block text-sm text-slate-400 mb-2">Access Token</label>
          <input
            type="password"
            value={data.sf_access_token}
            onChange={(e) => updateField('sf_access_token', e.target.value)}
            className="w-full px-4 py-3 bg-slate-900/50 border border-slate-600 rounded-xl text-white focus:border-cyan-500 focus:outline-none"
            placeholder="••••••••••••"
          />
        </div>

        <button
          onClick={onTest}
          disabled={isLoading || !data.sf_instance_url}
          className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg transition-all disabled:opacity-50 flex items-center gap-2"
        >
          {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Cloud className="w-4 h-4" />}
          Tester la connexion
        </button>

        {testResult && (
          <div className={`p-4 rounded-xl flex items-center gap-2 ${
            testResult.success ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'
          }`}>
            {testResult.success ? <CheckCircle2 className="w-5 h-5" /> : <AlertCircle className="w-5 h-5" />}
            {testResult.message}
          </div>
        )}
      </div>
    </div>
  );
}

function Step5Git({ data, updateField, onTest, testResult, isLoading }: { 
  data: WizardData; 
  updateField: (f: keyof WizardData, v: any) => void;
  onTest: () => void;
  testResult: {success: boolean; message: string} | null;
  isLoading: boolean;
}) {
  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold text-white flex items-center gap-2">
        <GitBranch className="w-6 h-6 text-cyan-400" />
        Repository Git
      </h2>
      <p className="text-slate-400 text-sm">
        Configurez le repository pour le déploiement du code généré
      </p>

      <div className="space-y-4">
        <div>
          <label className="block text-sm text-slate-400 mb-2">URL du repository</label>
          <input
            type="url"
            value={data.git_repo_url}
            onChange={(e) => updateField('git_repo_url', e.target.value)}
            className="w-full px-4 py-3 bg-slate-900/50 border border-slate-600 rounded-xl text-white focus:border-cyan-500 focus:outline-none"
            placeholder="https://github.com/org/repo"
          />
        </div>

        <div>
          <label className="block text-sm text-slate-400 mb-2">Branche</label>
          <input
            type="text"
            value={data.git_branch}
            onChange={(e) => updateField('git_branch', e.target.value)}
            className="w-full px-4 py-3 bg-slate-900/50 border border-slate-600 rounded-xl text-white focus:border-cyan-500 focus:outline-none"
            placeholder="main"
          />
        </div>

        <div>
          <label className="block text-sm text-slate-400 mb-2">Personal Access Token</label>
          <input
            type="password"
            value={data.git_token}
            onChange={(e) => updateField('git_token', e.target.value)}
            className="w-full px-4 py-3 bg-slate-900/50 border border-slate-600 rounded-xl text-white focus:border-cyan-500 focus:outline-none"
            placeholder="ghp_••••••••••••"
          />
        </div>

        <button
          onClick={onTest}
          disabled={isLoading || !data.git_repo_url}
          className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg transition-all disabled:opacity-50 flex items-center gap-2"
        >
          {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <GitBranch className="w-4 h-4" />}
          Tester la connexion
        </button>

        {testResult && (
          <div className={`p-4 rounded-xl flex items-center gap-2 ${
            testResult.success ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'
          }`}>
            {testResult.success ? <CheckCircle2 className="w-5 h-5" /> : <AlertCircle className="w-5 h-5" />}
            {testResult.message}
          </div>
        )}
      </div>
    </div>
  );
}

function Step6Requirements({ data, updateField }: { data: WizardData; updateField: (f: keyof WizardData, v: any) => void }) {
  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold text-white flex items-center gap-2">
        <FileText className="w-6 h-6 text-cyan-400" />
        Exigences métier
      </h2>

      <div>
        <label className="block text-sm text-slate-400 mb-2">
          Décrivez vos besoins métier *
        </label>
        <textarea
          value={data.business_requirements}
          onChange={(e) => updateField('business_requirements', e.target.value)}
          className="w-full px-4 py-3 bg-slate-900/50 border border-slate-600 rounded-xl text-white focus:border-cyan-500 focus:outline-none"
          rows={6}
          placeholder="Décrivez les fonctionnalités attendues, les processus métier à automatiser, les intégrations nécessaires..."
        />
        <p className="mt-1 text-xs text-slate-500">
          {data.business_requirements.length} caractères (minimum 20)
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm text-slate-400 mb-2">Systèmes existants</label>
          <input
            type="text"
            value={data.existing_systems}
            onChange={(e) => updateField('existing_systems', e.target.value)}
            className="w-full px-4 py-3 bg-slate-900/50 border border-slate-600 rounded-xl text-white focus:border-cyan-500 focus:outline-none"
            placeholder="ERP, CRM legacy, etc."
          />
        </div>

        <div>
          <label className="block text-sm text-slate-400 mb-2">Contraintes de conformité</label>
          <input
            type="text"
            value={data.compliance_requirements}
            onChange={(e) => updateField('compliance_requirements', e.target.value)}
            className="w-full px-4 py-3 bg-slate-900/50 border border-slate-600 rounded-xl text-white focus:border-cyan-500 focus:outline-none"
            placeholder="RGPD, SOC2, etc."
          />
        </div>

        <div>
          <label className="block text-sm text-slate-400 mb-2">Nombre d'utilisateurs prévus</label>
          <input
            type="number"
            value={data.expected_users}
            onChange={(e) => updateField('expected_users', e.target.value)}
            className="w-full px-4 py-3 bg-slate-900/50 border border-slate-600 rounded-xl text-white focus:border-cyan-500 focus:outline-none"
            placeholder="100"
          />
        </div>

        <div>
          <label className="block text-sm text-slate-400 mb-2">Volume de données</label>
          <select
            value={data.expected_data_volume}
            onChange={(e) => updateField('expected_data_volume', e.target.value)}
            className="w-full px-4 py-3 bg-slate-900/50 border border-slate-600 rounded-xl text-white focus:border-cyan-500 focus:outline-none"
          >
            <option value="">Sélectionner...</option>
            <option value="small">Petit (&lt; 100K records)</option>
            <option value="medium">Moyen (100K - 1M)</option>
            <option value="large">Grand (1M - 10M)</option>
            <option value="enterprise">Enterprise (&gt; 10M)</option>
          </select>
        </div>
      </div>
    </div>
  );
}
