import { useState, useEffect } from 'react';
import { 
  X, Cloud, GitBranch, Loader2, CheckCircle, AlertCircle, 
  ExternalLink, Settings, Eye, EyeOff, Terminal, Key
} from 'lucide-react';
import api from '../services/api';

interface ProjectSettingsModalProps {
  projectId: number;
  isOpen: boolean;
  onClose: () => void;
  onSaved: () => void;
  initialTab?: 'salesforce' | 'git';
}

interface ProjectSettings {
  sf_instance_url: string;
  sf_username: string;
  sf_consumer_key: string;
  sf_consumer_secret: string;
  sf_connected: boolean;
  sf_connection_date: string | null;
  sf_auth_method: string | null;
  git_repo_url: string;
  git_branch: string;
  git_token: string;
  git_connected: boolean;
  git_connection_date: string | null;
}

type SFAuthMethod = 'sfdx' | 'oauth';

export default function ProjectSettingsModal({ 
  projectId, 
  isOpen, 
  onClose, 
  onSaved,
  initialTab = 'salesforce' 
}: ProjectSettingsModalProps) {
  const [activeTab, setActiveTab] = useState<'salesforce' | 'git'>(initialTab);
  const [sfAuthMethod, setSfAuthMethod] = useState<SFAuthMethod>('sfdx');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);
  const [showSecret, setShowSecret] = useState(false);
  const [showGitToken, setShowGitToken] = useState(false);
  
  const [settings, setSettings] = useState<ProjectSettings>({
    sf_instance_url: '',
    sf_username: '',
    sf_consumer_key: '',
    sf_consumer_secret: '',
    sf_connected: false,
    sf_connection_date: null,
    sf_auth_method: null,
    git_repo_url: '',
    git_branch: 'main',
    git_token: '',
    git_connected: false,
    git_connection_date: null,
  });

  useEffect(() => {
    if (isOpen) {
      loadSettings();
    }
  }, [isOpen, projectId]);

  const loadSettings = async () => {
    setLoading(true);
    try {
      const response = await api.get(`/api/projects/${projectId}/settings`);
      setSettings({
        sf_instance_url: response.sf_instance_url || '',
        sf_username: response.sf_username || '',
        sf_consumer_key: response.sf_consumer_key || '',
        sf_consumer_secret: '',
        sf_connected: response.sf_connected || false,
        sf_connection_date: response.sf_connection_date,
        sf_auth_method: response.sf_auth_method || null,
        git_repo_url: response.git_repo_url || '',
        git_branch: response.git_branch || 'main',
        git_token: '',
        git_connected: response.git_connected || false,
        git_connection_date: response.git_connection_date,
      });
      // Set auth method based on what's saved
      if (response.sf_auth_method) {
        setSfAuthMethod(response.sf_auth_method as SFAuthMethod);
      }
    } catch (error) {
      console.error('Failed to load settings:', error);
    } finally {
      setLoading(false);
    }
  };

  const saveSettings = async () => {
    setSaving(true);
    setTestResult(null);
    try {
      await api.put(`/api/projects/${projectId}/settings`, {
        ...settings,
        sf_auth_method: sfAuthMethod
      });
      setTestResult({ success: true, message: 'Settings saved successfully!' });
      onSaved();
    } catch (error: any) {
      setTestResult({ 
        success: false, 
        message: error.response?.data?.detail || 'Failed to save settings' 
      });
    } finally {
      setSaving(false);
    }
  };

  const testSalesforceConnection = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      // Save settings first with auth method
      await api.put(`/api/projects/${projectId}/settings`, {
        ...settings,
        sf_auth_method: sfAuthMethod
      });
      const response = await api.post(`/api/projects/${projectId}/test-salesforce`, {
        auth_method: sfAuthMethod
      });
      setTestResult({ 
        success: response.success, 
        message: response.message || 'Connection successful!' 
      });
      if (response.success) {
        setSettings(prev => ({ 
          ...prev, 
          sf_connected: true, 
          sf_connection_date: new Date().toISOString(),
          sf_auth_method: sfAuthMethod
        }));
      }
    } catch (error: any) {
      setTestResult({ 
        success: false, 
        message: error.response?.data?.detail || error.response?.data?.message || 'Connection failed' 
      });
    } finally {
      setTesting(false);
    }
  };

  const testGitConnection = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      await api.put(`/api/projects/${projectId}/settings`, settings);
      const response = await api.post(`/api/projects/${projectId}/test-git`);
      setTestResult({ 
        success: response.success, 
        message: response.message || 'Connection successful!' 
      });
      if (response.success) {
        setSettings(prev => ({ ...prev, git_connected: true, git_connection_date: new Date().toISOString() }));
      }
    } catch (error: any) {
      setTestResult({ 
        success: false, 
        message: error.response?.data?.detail || 'Connection failed' 
      });
    } finally {
      setTesting(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
      <div className="bg-[#1a2744] rounded-xl w-full max-w-2xl max-h-[90vh] overflow-hidden">
        {/* Header */}
        <div className="p-4 border-b border-gray-700 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Settings className="w-5 h-5 text-cyan-400" />
            <h2 className="text-lg font-semibold text-white">Project Settings</h2>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-white">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-gray-700">
          <button
            onClick={() => { setActiveTab('salesforce'); setTestResult(null); }}
            className={`flex-1 py-3 px-4 flex items-center justify-center gap-2 transition-colors ${
              activeTab === 'salesforce' 
                ? 'text-cyan-400 border-b-2 border-cyan-400 bg-[#0d1829]' 
                : 'text-gray-400 hover:text-white'
            }`}
          >
            <Cloud className="w-4 h-4" />
            Salesforce
            {settings.sf_connected && <CheckCircle className="w-4 h-4 text-green-500" />}
          </button>
          <button
            onClick={() => { setActiveTab('git'); setTestResult(null); }}
            className={`flex-1 py-3 px-4 flex items-center justify-center gap-2 transition-colors ${
              activeTab === 'git' 
                ? 'text-cyan-400 border-b-2 border-cyan-400 bg-[#0d1829]' 
                : 'text-gray-400 hover:text-white'
            }`}
          >
            <GitBranch className="w-4 h-4" />
            Git Repository
            {settings.git_connected && <CheckCircle className="w-4 h-4 text-green-500" />}
          </button>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto max-h-[60vh]">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-8 h-8 animate-spin text-cyan-400" />
            </div>
          ) : activeTab === 'salesforce' ? (
            <div className="space-y-4">
              {/* Connection Status */}
              {settings.sf_connected && (
                <div className="bg-green-900/30 border border-green-700 p-4 rounded-lg mb-4">
                  <div className="flex items-center gap-3">
                    <CheckCircle className="w-5 h-5 text-green-400" />
                    <div>
                      <span className="text-green-400 font-medium">Connected</span>
                      <span className="text-gray-400 text-sm ml-2">
                        via {settings.sf_auth_method === 'oauth' ? 'OAuth' : 'SFDX CLI'}
                      </span>
                    </div>
                  </div>
                  {settings.sf_username && (
                    <p className="text-sm text-gray-300 mt-1 ml-8">{settings.sf_username}</p>
                  )}
                </div>
              )}

              {/* Auth Method Selection */}
              <div className="bg-[#0d1829] p-4 rounded-lg">
                <label className="block text-sm font-medium text-gray-300 mb-3">Authentication Method</label>
                <div className="grid grid-cols-2 gap-3">
                  <button
                    type="button"
                    onClick={() => setSfAuthMethod('sfdx')}
                    className={`p-4 rounded-lg border-2 transition-all text-left ${
                      sfAuthMethod === 'sfdx'
                        ? 'border-cyan-500 bg-cyan-900/20'
                        : 'border-gray-600 hover:border-gray-500'
                    }`}
                  >
                    <div className="flex items-center gap-2 mb-2">
                      <Terminal className={`w-5 h-5 ${sfAuthMethod === 'sfdx' ? 'text-cyan-400' : 'text-gray-400'}`} />
                      <span className={`font-medium ${sfAuthMethod === 'sfdx' ? 'text-cyan-400' : 'text-gray-300'}`}>
                        SFDX CLI
                      </span>
                    </div>
                    <p className="text-xs text-gray-500">
                      Use existing Salesforce CLI authentication. Recommended for developers.
                    </p>
                  </button>
                  <button
                    type="button"
                    onClick={() => setSfAuthMethod('oauth')}
                    className={`p-4 rounded-lg border-2 transition-all text-left ${
                      sfAuthMethod === 'oauth'
                        ? 'border-cyan-500 bg-cyan-900/20'
                        : 'border-gray-600 hover:border-gray-500'
                    }`}
                  >
                    <div className="flex items-center gap-2 mb-2">
                      <Key className={`w-5 h-5 ${sfAuthMethod === 'oauth' ? 'text-cyan-400' : 'text-gray-400'}`} />
                      <span className={`font-medium ${sfAuthMethod === 'oauth' ? 'text-cyan-400' : 'text-gray-300'}`}>
                        OAuth App
                      </span>
                    </div>
                    <p className="text-xs text-gray-500">
                      Use Connected App credentials. Best for production environments.
                    </p>
                  </button>
                </div>
              </div>

              {/* SFDX Method */}
              {sfAuthMethod === 'sfdx' && (
                <div className="space-y-4">
                  <div className="bg-blue-900/20 border border-blue-800 p-4 rounded-lg">
                    <h4 className="text-sm font-medium text-blue-400 mb-2">SFDX CLI Authentication</h4>
                    <p className="text-xs text-gray-400 mb-3">
                      Enter the Salesforce username that is authenticated via SFDX CLI on the server.
                    </p>
                    <div className="bg-[#0a1628] p-3 rounded font-mono text-xs text-gray-300">
                      <span className="text-gray-500">$</span> sfdx auth:web:login -a my-org
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm text-gray-400 mb-1">Salesforce Username *</label>
                    <input
                      type="text"
                      value={settings.sf_username}
                      onChange={(e) => setSettings({ ...settings, sf_username: e.target.value })}
                      placeholder="user@company.com"
                      className="w-full bg-[#0d1829] rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-cyan-500"
                    />
                  </div>
                </div>
              )}

              {/* OAuth Method */}
              {sfAuthMethod === 'oauth' && (
                <div className="space-y-4">
                  <div className="bg-amber-900/20 border border-amber-800 p-4 rounded-lg">
                    <h4 className="text-sm font-medium text-amber-400 mb-2">Connected App Setup Required</h4>
                    <p className="text-xs text-gray-400">
                      Create a Connected App in Salesforce Setup → App Manager → New Connected App.
                      Enable OAuth with "Full access" scope and "Enable Client Credentials Flow".
                    </p>
                  </div>

                  <div>
                    <label className="block text-sm text-gray-400 mb-1">Instance URL *</label>
                    <input
                      type="url"
                      value={settings.sf_instance_url}
                      onChange={(e) => setSettings({ ...settings, sf_instance_url: e.target.value })}
                      placeholder="https://mycompany.my.salesforce.com"
                      className="w-full bg-[#0d1829] rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-cyan-500"
                    />
                  </div>

                  <div>
                    <label className="block text-sm text-gray-400 mb-1">Username *</label>
                    <input
                      type="text"
                      value={settings.sf_username}
                      onChange={(e) => setSettings({ ...settings, sf_username: e.target.value })}
                      placeholder="admin@mycompany.com"
                      className="w-full bg-[#0d1829] rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-cyan-500"
                    />
                  </div>

                  <div>
                    <label className="block text-sm text-gray-400 mb-1">Consumer Key (Client ID) *</label>
                    <input
                      type="text"
                      value={settings.sf_consumer_key}
                      onChange={(e) => setSettings({ ...settings, sf_consumer_key: e.target.value })}
                      placeholder="3MVG9d8..."
                      className="w-full bg-[#0d1829] rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-cyan-500"
                    />
                  </div>

                  <div>
                    <label className="block text-sm text-gray-400 mb-1">Consumer Secret (Client Secret) *</label>
                    <div className="relative">
                      <input
                        type={showSecret ? 'text' : 'password'}
                        value={settings.sf_consumer_secret}
                        onChange={(e) => setSettings({ ...settings, sf_consumer_secret: e.target.value })}
                        placeholder="Enter your Consumer Secret"
                        className="w-full bg-[#0d1829] rounded-lg px-4 py-3 pr-10 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-cyan-500"
                      />
                      <button
                        type="button"
                        onClick={() => setShowSecret(!showSecret)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-white"
                      >
                        {showSecret ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          ) : (
            /* Git Tab */
            <div className="space-y-4">
              {settings.git_connected && (
                <div className="bg-green-900/30 border border-green-700 p-4 rounded-lg mb-4">
                  <div className="flex items-center gap-3">
                    <CheckCircle className="w-5 h-5 text-green-400" />
                    <span className="text-green-400 font-medium">Connected</span>
                  </div>
                  {settings.git_repo_url && (
                    <p className="text-sm text-gray-300 mt-1 ml-8">{settings.git_repo_url}</p>
                  )}
                </div>
              )}

              <div className="bg-[#0d1829] p-4 rounded-lg mb-4">
                <h3 className="text-sm font-medium text-cyan-400 mb-2">Git Repository Configuration</h3>
                <p className="text-xs text-gray-400">
                  Connect your Git repository to enable version control during the BUILD phase.
                </p>
              </div>

              <div>
                <label className="block text-sm text-gray-400 mb-1">Repository URL *</label>
                <input
                  type="url"
                  value={settings.git_repo_url}
                  onChange={(e) => setSettings({ ...settings, git_repo_url: e.target.value })}
                  placeholder="https://github.com/username/repository"
                  className="w-full bg-[#0d1829] rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-cyan-500"
                />
              </div>

              <div>
                <label className="block text-sm text-gray-400 mb-1">Branch</label>
                <input
                  type="text"
                  value={settings.git_branch}
                  onChange={(e) => setSettings({ ...settings, git_branch: e.target.value })}
                  placeholder="main"
                  className="w-full bg-[#0d1829] rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-cyan-500"
                />
              </div>

              <div>
                <label className="block text-sm text-gray-400 mb-1">Personal Access Token *</label>
                <div className="relative">
                  <input
                    type={showGitToken ? 'text' : 'password'}
                    value={settings.git_token}
                    onChange={(e) => setSettings({ ...settings, git_token: e.target.value })}
                    placeholder="ghp_xxxxxxxxxxxxxxxxxxxx"
                    className="w-full bg-[#0d1829] rounded-lg px-4 py-3 pr-10 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-cyan-500"
                  />
                  <button
                    type="button"
                    onClick={() => setShowGitToken(!showGitToken)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-white"
                  >
                    {showGitToken ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
                <p className="text-xs text-gray-500 mt-1">
                  <a 
                    href="https://github.com/settings/tokens/new" 
                    target="_blank" 
                    rel="noopener noreferrer"
                    className="text-cyan-400 hover:underline inline-flex items-center gap-1"
                  >
                    Create a GitHub token <ExternalLink className="w-3 h-3" />
                  </a>
                  {' '}with repo access
                </p>
              </div>
            </div>
          )}

          {/* Test Result */}
          {testResult && (
            <div className={`mt-4 p-3 rounded-lg flex items-start gap-2 ${
              testResult.success ? 'bg-green-900/30 text-green-400' : 'bg-red-900/30 text-red-400'
            }`}>
              {testResult.success ? (
                <CheckCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
              ) : (
                <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
              )}
              <span className="text-sm">{testResult.message}</span>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-gray-700 flex justify-between gap-3">
          <button
            onClick={activeTab === 'salesforce' ? testSalesforceConnection : testGitConnection}
            disabled={testing || saving}
            className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg flex items-center gap-2 disabled:opacity-50"
          >
            {testing ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              activeTab === 'salesforce' ? <Cloud className="w-4 h-4" /> : <GitBranch className="w-4 h-4" />
            )}
            Test Connection
          </button>
          
          <div className="flex gap-3">
            <button
              onClick={onClose}
              className="px-4 py-2 bg-gray-600 hover:bg-gray-700 text-white rounded-lg"
            >
              Cancel
            </button>
            <button
              onClick={saveSettings}
              disabled={saving}
              className="px-4 py-2 bg-cyan-600 hover:bg-cyan-700 text-white rounded-lg flex items-center gap-2 disabled:opacity-50"
            >
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle className="w-4 h-4" />}
              Save Settings
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
