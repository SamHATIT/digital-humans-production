import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { ArrowLeft, MessageSquare, Upload, Loader2, ArrowRight } from 'lucide-react';
import { projects } from '../services/api';

type ProjectMode = 'pm' | 'technical' | null;

interface ProjectFormData {
  name: string;
  salesforce_product: string;
  organization_type: string;
  business_requirements?: string;
  key_stakeholders?: string;
  timeline?: string;
  budget_constraints?: string;
}

interface UploadedFile {
  file: File;
  name: string;
  size: number;
  content?: string;
}

export default function NewProject() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [mode, setMode] = useState<ProjectMode>(null);
  const [step, setStep] = useState(1);
  const [isLoading, setIsLoading] = useState(false);
  const [formData, setFormData] = useState<ProjectFormData>({
    name: '',
    salesforce_product: '',
    organization_type: '',
    business_requirements: '',
    key_stakeholders: '',
    timeline: '',
    budget_constraints: '',
  });
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);
  const [isDragging, setIsDragging] = useState(false);

  useEffect(() => {
    const modeParam = searchParams.get('mode');
    if (modeParam === 'pm' || modeParam === 'technical') {
      setMode(modeParam);
    }
  }, [searchParams]);

  const handleModeSelection = (selectedMode: ProjectMode) => {
    setMode(selectedMode);
    navigate(`/projects/new?mode=${selectedMode}`);
  };

  const handleInputChange = (field: keyof ProjectFormData, value: string) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      await processFiles(Array.from(e.target.files));
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      await processFiles(Array.from(e.dataTransfer.files));
    }
  };

  const processFiles = async (files: File[]) => {
    const validFiles = files.filter(file => {
      const ext = file.name.split('.').pop()?.toLowerCase();
      return ['pdf', 'doc', 'docx', 'txt'].includes(ext || '');
    });
    
    if (validFiles.length === 0) {
      alert('Please upload PDF, DOC, DOCX, or TXT files only.');
      return;
    }
    
    const fileObjects: UploadedFile[] = [];
    
    for (const file of validFiles) {
      // Pour les fichiers TXT, lire le contenu directement
      if (file.name.endsWith('.txt')) {
        try {
          const text = await file.text();
          fileObjects.push({
            file: file,
            name: file.name,
            size: file.size,
            content: text
          });
        } catch (error) {
          console.error('Error reading file:', error);
        }
      } else {
        // Pour PDF, DOC, DOCX - on stocke juste le fichier
        // Le backend devra le traiter
        fileObjects.push({
          file: file,
          name: file.name,
          size: file.size,
        });
      }
    }
    
    setUploadedFiles(fileObjects);
  };

  const removeFile = (index: number) => {
    setUploadedFiles(prev => prev.filter((_, i) => i !== index));
  };

  const handleCreateProject = async () => {
    try {
      setIsLoading(true);
      
      // Construire business_requirements en concaténant tous les champs
      let businessReq = formData.business_requirements || '';
      
      if (formData.key_stakeholders) {
        businessReq += `\n\nKey Stakeholders:\n${formData.key_stakeholders}`;
      }
      if (formData.timeline) {
        businessReq += `\n\nTimeline: ${formData.timeline}`;
      }
      if (formData.budget_constraints) {
        businessReq += `\n\nBudget Constraints:\n${formData.budget_constraints}`;
      }
      
      // Si un fichier a été uploadé, ajouter son contenu
      if (uploadedFiles.length > 0 && uploadedFiles[0].content) {
        businessReq = uploadedFiles[0].content + '\n\n' + businessReq;
      }
      
      const projectData = {
        name: formData.name,
        salesforce_product: formData.salesforce_product,
        organization_type: formData.organization_type,
        business_requirements: businessReq.trim() || 'To be defined',
      };
      
      const newProject = await projects.create(projectData);
      navigate(`/execution/${newProject.id}`);
    } catch (error: any) {
      console.error('Error creating project:', error);
      const errorMsg = error.response?.data?.detail || error.message || 'Failed to create project';
      alert(`Error: ${errorMsg}`);
    } finally {
      setIsLoading(false);
    }
  };

  // Mode Selection Screen
  if (!mode) {
    return (
      <div className="min-h-screen bg-gray-50 p-8">
        <div className="max-w-5xl mx-auto">
          <button
            onClick={() => navigate('/projects')}
            className="flex items-center gap-2 text-gray-600 hover:text-gray-900 mb-8"
          >
            <ArrowLeft size={20} />
            Back to Projects
          </button>

          <div className="text-center mb-12">
            <h1 className="text-4xl font-bold mb-4">Create New Project</h1>
            <p className="text-xl text-gray-600">Choose how you want to define your project</p>
          </div>

          <div className="grid md:grid-cols-2 gap-8">
            {/* PM Dialogue Mode */}
            <button
              onClick={() => handleModeSelection('pm')}
              className="bg-white border-2 border-gray-200 rounded-xl p-8 hover:border-blue-500 hover:shadow-lg transition text-left group"
            >
              <div className="flex items-center gap-4 mb-4">
                <div className="bg-blue-100 p-4 rounded-lg group-hover:bg-blue-500 transition">
                  <MessageSquare className="text-blue-600 group-hover:text-white" size={32} />
                </div>
                <h2 className="text-2xl font-bold">PM Dialogue</h2>
              </div>
              <p className="text-gray-600 mb-4">
                Answer guided questions to help us understand your project needs. Perfect for business users who want to describe their requirements conversationally.
              </p>
              <ul className="space-y-2 text-sm text-gray-600">
                <li className="flex items-start gap-2">
                  <span className="text-blue-600 font-bold">•</span>
                  Step-by-step project definition
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-blue-600 font-bold">•</span>
                  Business-focused questions
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-blue-600 font-bold">•</span>
                  No technical knowledge required
                </li>
              </ul>
              <div className="mt-6 text-blue-600 font-medium group-hover:translate-x-2 transition-transform flex items-center gap-2">
                Get Started <ArrowRight size={20} />
              </div>
            </button>

            {/* Technical Upload Mode */}
            <button
              onClick={() => handleModeSelection('technical')}
              className="bg-white border-2 border-gray-200 rounded-xl p-8 hover:border-green-500 hover:shadow-lg transition text-left group"
            >
              <div className="flex items-center gap-4 mb-4">
                <div className="bg-green-100 p-4 rounded-lg group-hover:bg-green-500 transition">
                  <Upload className="text-green-600 group-hover:text-white" size={32} />
                </div>
                <h2 className="text-2xl font-bold">Technical Upload</h2>
              </div>
              <p className="text-gray-600 mb-4">
                Upload your project charter and existing documentation. Ideal for technical users who have detailed project specifications ready.
              </p>
              <ul className="space-y-2 text-sm text-gray-600">
                <li className="flex items-start gap-2">
                  <span className="text-green-600 font-bold">•</span>
                  Quick project setup
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-green-600 font-bold">•</span>
                  Upload existing documents
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-green-600 font-bold">•</span>
                  For users with detailed specs
                </li>
              </ul>
              <div className="mt-6 text-green-600 font-medium group-hover:translate-x-2 transition-transform flex items-center gap-2">
                Get Started <ArrowRight size={20} />
              </div>
            </button>
          </div>
        </div>
      </div>
    );
  }

  // PM Dialogue Wizard
  if (mode === 'pm') {
    return (
      <div className="min-h-screen bg-gray-50 p-8">
        <div className="max-w-3xl mx-auto">
          <button
            onClick={() => setMode(null)}
            className="flex items-center gap-2 text-gray-600 hover:text-gray-900 mb-8"
          >
            <ArrowLeft size={20} />
            Back to Mode Selection
          </button>

          <div className="bg-white rounded-lg shadow-md p-8">
            <div className="mb-8">
              <div className="flex items-center gap-4 mb-6">
                <div className="bg-blue-100 p-3 rounded-lg">
                  <MessageSquare className="text-blue-600" size={28} />
                </div>
                <div>
                  <h1 className="text-3xl font-bold">PM Dialogue Mode</h1>
                  <p className="text-gray-600">Step {step} of 3</p>
                </div>
              </div>

              {/* Progress Bar */}
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div
                  className="bg-blue-600 h-2 rounded-full transition-all"
                  style={{ width: `${(step / 3) * 100}%` }}
                />
              </div>
            </div>

            {/* Step 1: Basic Information */}
            {step === 1 && (
              <div className="space-y-6">
                <h2 className="text-xl font-bold mb-4">Basic Project Information</h2>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Project Name *
                  </label>
                  <input
                    type="text"
                    value={formData.name}
                    onChange={(e) => handleInputChange('name', e.target.value)}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    placeholder="e.g., Customer Portal Enhancement"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Salesforce Product *
                  </label>
                  <select
                    value={formData.salesforce_product}
                    onChange={(e) => handleInputChange('salesforce_product', e.target.value)}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  >
                    <option value="">Select a product...</option>
                    <option value="Sales Cloud">Sales Cloud</option>
                    <option value="Service Cloud">Service Cloud</option>
                    <option value="Marketing Cloud">Marketing Cloud</option>
                    <option value="Commerce Cloud">Commerce Cloud</option>
                    <option value="Experience Cloud">Experience Cloud</option>
                    <option value="Financial Services Cloud">Financial Services Cloud</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Organization Type *
                  </label>
                  <select
                    value={formData.organization_type}
                    onChange={(e) => handleInputChange('organization_type', e.target.value)}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  >
                    <option value="">Select organization type...</option>
                    <option value="Enterprise">Enterprise</option>
                    <option value="SMB">Small/Medium Business</option>
                    <option value="Non-Profit">Non-Profit</option>
                    <option value="Education">Education</option>
                    <option value="Government">Government</option>
                  </select>
                </div>
              </div>
            )}

            {/* Step 2: Business Context */}
            {step === 2 && (
              <div className="space-y-6">
                <h2 className="text-xl font-bold mb-4">Business Context</h2>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Business Requirements
                  </label>
                  <textarea
                    value={formData.business_requirements}
                    onChange={(e) => handleInputChange('business_requirements', e.target.value)}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    rows={4}
                    placeholder="What are the main goals of this project?"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Key Stakeholders
                  </label>
                  <textarea
                    value={formData.key_stakeholders}
                    onChange={(e) => handleInputChange('key_stakeholders', e.target.value)}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    rows={3}
                    placeholder="Who are the main stakeholders involved?"
                  />
                </div>
              </div>
            )}

            {/* Step 3: Project Constraints */}
            {step === 3 && (
              <div className="space-y-6">
                <h2 className="text-xl font-bold mb-4">Project Constraints</h2>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Timeline
                  </label>
                  <input
                    type="text"
                    value={formData.timeline}
                    onChange={(e) => handleInputChange('timeline', e.target.value)}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    placeholder="e.g., 3 months, Q2 2025"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Budget Constraints
                  </label>
                  <textarea
                    value={formData.budget_constraints}
                    onChange={(e) => handleInputChange('budget_constraints', e.target.value)}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    rows={3}
                    placeholder="Any budget limitations or considerations?"
                  />
                </div>
              </div>
            )}

            {/* Navigation Buttons */}
            <div className="flex justify-between mt-8 pt-6 border-t">
              <button
                onClick={() => step > 1 ? setStep(step - 1) : setMode(null)}
                className="px-6 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition"
              >
                Back
              </button>

              {step < 3 ? (
                <button
                  onClick={() => setStep(step + 1)}
                  disabled={!formData.name || !formData.salesforce_product || !formData.organization_type}
                  className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition disabled:bg-gray-300 disabled:cursor-not-allowed flex items-center gap-2"
                >
                  Next <ArrowRight size={20} />
                </button>
              ) : (
                <button
                  onClick={handleCreateProject}
                  disabled={isLoading || !formData.name || !formData.salesforce_product || !formData.organization_type}
                  className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition disabled:bg-gray-300 disabled:cursor-not-allowed flex items-center gap-2"
                >
                  {isLoading ? (
                    <>
                      <Loader2 className="animate-spin" size={20} />
                      Creating...
                    </>
                  ) : (
                    'Create Project'
                  )}
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Technical Upload Mode
  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-3xl mx-auto">
        <button
          onClick={() => setMode(null)}
          className="flex items-center gap-2 text-gray-600 hover:text-gray-900 mb-8"
        >
          <ArrowLeft size={20} />
          Back to Mode Selection
        </button>

        <div className="bg-white rounded-lg shadow-md p-8">
          <div className="flex items-center gap-4 mb-8">
            <div className="bg-green-100 p-3 rounded-lg">
              <Upload className="text-green-600" size={28} />
            </div>
            <div>
              <h1 className="text-3xl font-bold">Technical Upload Mode</h1>
              <p className="text-gray-600">Quick setup with your existing documentation</p>
            </div>
          </div>

          <div className="space-y-6">
            {/* Basic Info */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Project Name *
              </label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => handleInputChange('name', e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent"
                placeholder="e.g., Customer Portal Enhancement"
              />
            </div>

            <div className="grid md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Salesforce Product *
                </label>
                <select
                  value={formData.salesforce_product}
                  onChange={(e) => handleInputChange('salesforce_product', e.target.value)}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent"
                >
                  <option value="">Select a product...</option>
                  <option value="Sales Cloud">Sales Cloud</option>
                  <option value="Service Cloud">Service Cloud</option>
                  <option value="Marketing Cloud">Marketing Cloud</option>
                  <option value="Commerce Cloud">Commerce Cloud</option>
                  <option value="Experience Cloud">Experience Cloud</option>
                  <option value="Financial Services Cloud">Financial Services Cloud</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Organization Type *
                </label>
                <select
                  value={formData.organization_type}
                  onChange={(e) => handleInputChange('organization_type', e.target.value)}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent"
                >
                  <option value="">Select type...</option>
                  <option value="Enterprise">Enterprise</option>
                  <option value="SMB">Small/Medium Business</option>
                  <option value="Non-Profit">Non-Profit</option>
                  <option value="Education">Education</option>
                  <option value="Government">Government</option>
                </select>
              </div>
            </div>

            {/* File Upload */}
            <div 
              className={`border-2 border-dashed rounded-lg p-8 text-center transition ${
                isDragging 
                  ? 'border-green-500 bg-green-50' 
                  : 'border-gray-300 hover:border-green-500'
              }`}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
            >
              <Upload className="mx-auto text-gray-400 mb-4" size={48} />
              <p className="text-lg font-medium text-gray-700 mb-2">Upload Project Charter</p>
              <p className="text-sm text-gray-500 mb-4">
                Drag and drop your files here, or click to browse
              </p>
              <input
                type="file"
                multiple
                className="hidden"
                id="file-upload"
                accept=".pdf,.doc,.docx,.txt"
                onChange={handleFileSelect}
              />
              <label
                htmlFor="file-upload"
                className="inline-block px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 cursor-pointer transition"
              >
                Choose Files
              </label>
              <p className="text-xs text-gray-500 mt-2">
                Supported formats: PDF, DOC, DOCX, TXT
              </p>
            </div>

            {/* Liste des fichiers uploadés */}
            {uploadedFiles.length > 0 && (
              <div className="space-y-2">
                <p className="text-sm font-medium text-gray-700">Uploaded Files:</p>
                {uploadedFiles.map((file, index) => (
                  <div 
                    key={index}
                    className="flex items-center justify-between bg-gray-50 p-3 rounded-lg"
                  >
                    <div className="flex items-center gap-3">
                      <Upload size={20} className="text-gray-400" />
                      <div>
                        <p className="text-sm font-medium">{file.name}</p>
                        <p className="text-xs text-gray-500">
                          {(file.size / 1024).toFixed(2)} KB
                          {file.content && ` • ${file.content.split(' ').length} words`}
                        </p>
                      </div>
                    </div>
                    <button
                      onClick={() => removeFile(index)}
                      className="text-red-600 hover:text-red-800 text-sm"
                    >
                      Remove
                    </button>
                  </div>
                ))}
              </div>
            )}

            {/* Action Buttons */}
            <div className="flex justify-between pt-6 border-t">
              <button
                onClick={() => setMode(null)}
                className="px-6 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition"
              >
                Back
              </button>

              <button
                onClick={handleCreateProject}
                disabled={isLoading || !formData.name || !formData.salesforce_product || !formData.organization_type}
                className="px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition disabled:bg-gray-300 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="animate-spin" size={20} />
                    Creating...
                  </>
                ) : (
                  'Create Project'
                )}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
