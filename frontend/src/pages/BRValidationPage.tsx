import { useEffect, useState } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { 
  FileText, Download, Plus, Check, Loader2, ArrowRight, 
  Edit2, Trash2, X, Save, Filter
} from 'lucide-react';
import Navbar from '../components/Navbar';
import { api } from '../services/api';

interface BusinessRequirement {
  id: number;
  br_id: string;
  category: string | null;
  requirement: string;
  priority: 'must' | 'should' | 'could' | 'wont';
  status: 'pending' | 'validated' | 'modified' | 'deleted';
  source: 'extracted' | 'manual';
  original_text: string | null;
  client_notes: string | null;
  order_index: number;
}

interface BRStats {
  total: number;
  pending: number;
  validated: number;
  modified: number;
  deleted: number;
}

const PRIORITY_COLORS = {
  must: 'bg-red-500/20 text-red-400 border-red-500/30',
  should: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  could: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  wont: 'bg-slate-500/20 text-slate-400 border-slate-500/30',
};

const STATUS_ICONS = {
  pending: '○',
  validated: '✓',
  modified: '⚠️',
  deleted: '🗑️',
};

const CATEGORIES = [
  'Lead Management',
  'Opportunity Management', 
  'Account Management',
  'Contact Management',
  'Case Management',
  'Service Cloud',
  'Sales Cloud',
  'Marketing Cloud',
  'Reports & Dashboards',
  'Integration',
  'Security',
  'Data Migration',
  'User Management',
  'Workflow & Automation',
  'Custom Development',
  'Other'
];

export default function BRValidationPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [searchParams] = useSearchParams();
  const executionId = searchParams.get('executionId');
  const navigate = useNavigate();
  
  const [brs, setBrs] = useState<BusinessRequirement[]>([]);
  const [stats, setStats] = useState<BRStats>({ total: 0, pending: 0, validated: 0, modified: 0, deleted: 0 });
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [isValidating, setIsValidating] = useState(false);
  
  // Modal states
  const [editingBR, setEditingBR] = useState<BusinessRequirement | null>(null);
  const [inlineEditId, setInlineEditId] = useState<number | null>(null);
  const [inlineEditData, setInlineEditData] = useState<Partial<BusinessRequirement>>({});
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [newBR, setNewBR] = useState({ category: '', requirement: '', priority: 'should' as 'must' | 'should' | 'could' | 'wont', client_notes: '' });
  
  // Filter state
  const [filterCategory, setFilterCategory] = useState('');
  const [filterStatus, setFilterStatus] = useState('');

  useEffect(() => {
    fetchBRs();
  }, [projectId]);

  const fetchBRs = async () => {
    try {
      setIsLoading(true);
      const data = await api.get(`/api/br/${projectId}`);
      setBrs(data.brs);
      setStats({
        total: data.total,
        pending: data.pending,
        validated: data.validated,
        modified: data.modified,
        deleted: data.deleted,
      });
    } catch (err: any) {
      setError(err.message || 'Failed to load requirements');
    } finally {
      setIsLoading(false);
    }
  };

  const handleUpdateBR = async () => {
    if (!editingBR) return;
    
    try {
      await api.put(`/api/br/item/${editingBR.id}`, {
        category: editingBR.category,
        requirement: editingBR.requirement,
        priority: editingBR.priority,
        client_notes: editingBR.client_notes,
      });
      setEditingBR(null);
      fetchBRs();
    } catch (err: any) {
      setError(err.message || 'Failed to update requirement');
    }
  };

  const handleDeleteBR = async (brId: number) => {
    if (!confirm('Are you sure you want to delete this requirement?')) return;
    
    try {
      await api.delete(`/api/br/item/${brId}`);
      fetchBRs();
    } catch (err: any) {
      setError(err.message || 'Failed to delete requirement');
    }
  };

  const handleAddBR = async () => {
    if (!newBR.requirement.trim()) return;
    
    try {
      await api.post(`/api/br/${projectId}`, newBR);
      setIsAddModalOpen(false);
      setNewBR({ category: '', requirement: '', priority: 'should', client_notes: '' });
      fetchBRs();
    } catch (err: any) {
      setError(err.message || 'Failed to add requirement');
    }
  };

  const handleValidateAll = async () => {
    setIsValidating(true);
    try {
      // Step 1: Validate all BRs
      await api.post(`/api/br/${projectId}/validate-all`);
      
      // Step 2: If coming from execution, resume it
      if (executionId) {
        await api.post(`/api/pm-orchestrator/execute/${executionId}/resume`);
        navigate(`/execution/${executionId}/monitor`);
      } else {
        // New project flow - go to execution page to start
        navigate(`/execution/${projectId}`);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to validate requirements');
    } finally {
      setIsValidating(false);
    }
  };

  const handleExportCSV = () => {
    const token = localStorage.getItem('token');
    window.open(`/api/br/${projectId}/export?token=${token}`, '_blank');
  };

  const startInlineEdit = (br: BusinessRequirement) => {
    setInlineEditId(br.id);
    setInlineEditData({
      category: br.category,
      requirement: br.requirement,
      priority: br.priority,
      client_notes: br.client_notes,
    });
  };

  const saveInlineEdit = async () => {
    if (inlineEditId === null) return;
    try {
      await api.put(`/api/br/item/${inlineEditId}`, {
        category: inlineEditData.category,
        requirement: inlineEditData.requirement,
        priority: inlineEditData.priority,
        client_notes: inlineEditData.client_notes,
      });
      setInlineEditId(null);
      setInlineEditData({});
      fetchBRs();
    } catch (err: any) {
      setError(err.message || 'Failed to save changes');
    }
  };

  const cancelInlineEdit = () => {
    setInlineEditId(null);
    setInlineEditData({});
  };

  // Filter BRs
  const filteredBRs = brs.filter(br => {
    if (filterCategory && br.category !== filterCategory) return false;
    if (filterStatus && br.status !== filterStatus) return false;
    return true;
  });

  if (isLoading) {
    return (
      <div className="min-h-screen bg-[#0B1120] flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-12 h-12 text-cyan-500 animate-spin mx-auto" />
          <p className="text-slate-400 mt-4">Loading requirements...</p>
        </div>
      </div>
    );
  }

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
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-cyan-500 to-purple-600 flex items-center justify-center">
              <FileText className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="text-3xl font-bold text-white">Business Requirements Review</h1>
              <p className="text-slate-400">Sophie has extracted {stats.total} requirements from your document</p>
            </div>
          </div>
        </div>

        {error && (
          <div className="mb-6 bg-red-500/10 border border-red-500/30 rounded-xl p-4 text-red-400">
            {error}
            <button onClick={() => setError('')} className="ml-4 underline">Dismiss</button>
          </div>
        )}

        {/* Toolbar */}
        <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-xl p-4 mb-6">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <button
                onClick={handleExportCSV}
                className="flex items-center gap-2 px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg transition-colors"
              >
                <Download className="w-4 h-4" />
                Export CSV
              </button>
              <button
                onClick={() => setIsAddModalOpen(true)}
                className="flex items-center gap-2 px-4 py-2 bg-cyan-600 hover:bg-cyan-500 text-white rounded-lg transition-colors"
              >
                <Plus className="w-4 h-4" />
                Add BR
              </button>
              
              {/* Filters */}
              <div className="flex items-center gap-2 ml-4">
                <Filter className="w-4 h-4 text-slate-400" />
                <select
                  value={filterCategory}
                  onChange={(e) => setFilterCategory(e.target.value)}
                  className="bg-slate-700 border border-slate-600 text-white rounded-lg px-3 py-2 text-sm"
                >
                  <option value="">All Categories</option>
                  {CATEGORIES.map(cat => (
                    <option key={cat} value={cat}>{cat}</option>
                  ))}
                </select>
                <select
                  value={filterStatus}
                  onChange={(e) => setFilterStatus(e.target.value)}
                  className="bg-slate-700 border border-slate-600 text-white rounded-lg px-3 py-2 text-sm"
                >
                  <option value="">All Status</option>
                  <option value="pending">Pending</option>
                  <option value="validated">Validated</option>
                  <option value="modified">Modified</option>
                </select>
              </div>
            </div>
            
            <div className="flex items-center gap-4">
              <div className="text-sm text-slate-400">
                <span className="text-green-400">{stats.validated}</span> validated · 
                <span className="text-yellow-400 ml-1">{stats.modified}</span> modified · 
                <span className="text-slate-400 ml-1">{stats.pending}</span> pending
              </div>
            </div>
          </div>
        </div>

        {/* Cards Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
          {filteredBRs.map((br) => {
            const isEditing = inlineEditId === br.id;

            return (
              <div
                key={br.id}
                className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-xl p-5 hover:border-slate-600 transition-all group"
              >
                {/* Card header */}
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-mono text-cyan-400">{br.br_id}</span>
                    <span className="text-lg">{STATUS_ICONS[br.status]}</span>
                  </div>
                  <div className="flex items-center gap-1">
                    {!isEditing && (
                      <>
                        <button
                          onClick={() => startInlineEdit(br)}
                          className="p-1.5 text-slate-500 hover:text-cyan-400 hover:bg-slate-700 rounded opacity-0 group-hover:opacity-100 transition-all"
                          title="Edit inline"
                        >
                          <Edit2 className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => handleDeleteBR(br.id)}
                          className="p-1.5 text-slate-500 hover:text-red-400 hover:bg-slate-700 rounded opacity-0 group-hover:opacity-100 transition-all"
                          title="Delete"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </>
                    )}
                  </div>
                </div>

                {/* Priority + Category badges */}
                <div className="flex items-center gap-2 mb-3 flex-wrap">
                  {isEditing ? (
                    <>
                      <select
                        value={inlineEditData.priority || 'should'}
                        onChange={(e) => setInlineEditData({ ...inlineEditData, priority: e.target.value as any })}
                        className="bg-slate-700 border border-slate-600 text-white rounded px-2 py-1 text-xs"
                      >
                        {(['must', 'should', 'could', 'wont'] as const).map(p => (
                          <option key={p} value={p}>{p.toUpperCase()}</option>
                        ))}
                      </select>
                      <select
                        value={inlineEditData.category || ''}
                        onChange={(e) => setInlineEditData({ ...inlineEditData, category: e.target.value })}
                        className="bg-slate-700 border border-slate-600 text-white rounded px-2 py-1 text-xs"
                      >
                        <option value="">No Category</option>
                        {CATEGORIES.map(cat => (
                          <option key={cat} value={cat}>{cat}</option>
                        ))}
                      </select>
                    </>
                  ) : (
                    <>
                      <span className={`px-2 py-0.5 rounded text-xs font-medium border ${PRIORITY_COLORS[br.priority]}`}>
                        {br.priority.toUpperCase()}
                      </span>
                      {br.category && (
                        <span className="px-2 py-0.5 rounded text-xs font-medium bg-slate-700/50 text-slate-300 border border-slate-600">
                          {br.category}
                        </span>
                      )}
                    </>
                  )}
                </div>

                {/* Requirement text */}
                {isEditing ? (
                  <textarea
                    value={inlineEditData.requirement || ''}
                    onChange={(e) => setInlineEditData({ ...inlineEditData, requirement: e.target.value })}
                    rows={3}
                    className="w-full bg-slate-700 border border-slate-600 text-white rounded-lg px-3 py-2 text-sm mb-2 resize-y"
                  />
                ) : (
                  <p className="text-sm text-white mb-2 leading-relaxed">{br.requirement}</p>
                )}

                {/* Notes */}
                {isEditing ? (
                  <textarea
                    value={inlineEditData.client_notes || ''}
                    onChange={(e) => setInlineEditData({ ...inlineEditData, client_notes: e.target.value })}
                    rows={1}
                    placeholder="Notes (optional)..."
                    className="w-full bg-slate-700 border border-slate-600 text-slate-300 rounded-lg px-3 py-1.5 text-xs mb-2 resize-y"
                  />
                ) : (
                  br.client_notes && (
                    <p className="text-xs text-slate-500 mb-2">Note: {br.client_notes}</p>
                  )
                )}

                {/* Inline edit actions */}
                {isEditing && (
                  <div className="flex gap-2 mt-2 pt-2 border-t border-slate-700">
                    <button
                      onClick={saveInlineEdit}
                      className="flex items-center gap-1 px-3 py-1.5 bg-cyan-600 hover:bg-cyan-500 text-white text-xs rounded-lg transition-colors"
                    >
                      <Save className="w-3 h-3" />
                      Save
                    </button>
                    <button
                      onClick={cancelInlineEdit}
                      className="flex items-center gap-1 px-3 py-1.5 bg-slate-700 hover:bg-slate-600 text-white text-xs rounded-lg transition-colors"
                    >
                      <X className="w-3 h-3" />
                      Cancel
                    </button>
                  </div>
                )}

                {/* Source indicator */}
                {br.source === 'extracted' && (
                  <div className="mt-2 pt-2 border-t border-slate-700/50">
                    <span className="text-[10px] text-slate-600">Extracted by Sophie</span>
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {filteredBRs.length === 0 && (
          <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-xl p-8 mb-8 text-center text-slate-400">
            No requirements found. {filterCategory || filterStatus ? 'Try adjusting filters.' : ''}
          </div>
        )}

        {/* Add BR Card */}
        <div className="mb-8">
          <button
            onClick={() => setIsAddModalOpen(true)}
            className="w-full bg-slate-800/30 border-2 border-dashed border-slate-700 hover:border-cyan-500/50 rounded-xl p-6 text-center transition-colors group"
          >
            <Plus className="w-6 h-6 text-slate-500 group-hover:text-cyan-400 mx-auto mb-2 transition-colors" />
            <span className="text-sm text-slate-500 group-hover:text-slate-300 transition-colors">
              Add a new Business Requirement
            </span>
          </button>
        </div>

        {/* Action Buttons */}
        <div className="flex justify-between items-center">
          <button
            onClick={() => navigate('/projects')}
            className="px-6 py-3 bg-slate-700 hover:bg-slate-600 text-white rounded-xl transition-colors"
          >
            Cancel
          </button>
          
          <button
            onClick={handleValidateAll}
            disabled={isValidating || stats.total === 0}
            className="flex items-center gap-3 px-8 py-4 bg-gradient-to-r from-green-500 to-emerald-600 text-white font-semibold rounded-xl hover:from-green-600 hover:to-emerald-700 transition-all shadow-lg shadow-green-500/30 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isValidating ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                Validating...
              </>
            ) : (
              <>
                <Check className="w-5 h-5" />
                Validate All & Continue to Analysis
                <ArrowRight className="w-5 h-5" />
              </>
            )}
          </button>
        </div>
      </main>

      {/* Edit Modal */}
      {editingBR && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-slate-800 border border-slate-700 rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <div className="p-6 border-b border-slate-700 flex items-center justify-between">
              <h2 className="text-xl font-bold text-white flex items-center gap-2">
                <Edit2 className="w-5 h-5 text-cyan-400" />
                Edit {editingBR.br_id}
              </h2>
              <button onClick={() => setEditingBR(null)} className="text-slate-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>
            
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-400 mb-2">Category</label>
                <select
                  value={editingBR.category || ''}
                  onChange={(e) => setEditingBR({ ...editingBR, category: e.target.value })}
                  className="w-full bg-slate-700 border border-slate-600 text-white rounded-lg px-4 py-2"
                >
                  <option value="">Select category...</option>
                  {CATEGORIES.map(cat => (
                    <option key={cat} value={cat}>{cat}</option>
                  ))}
                </select>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-slate-400 mb-2">Requirement</label>
                <textarea
                  value={editingBR.requirement}
                  onChange={(e) => setEditingBR({ ...editingBR, requirement: e.target.value })}
                  rows={4}
                  className="w-full bg-slate-700 border border-slate-600 text-white rounded-lg px-4 py-2"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-slate-400 mb-2">Priority</label>
                <div className="flex gap-3">
                  {(['must', 'should', 'could', 'wont'] as const).map(p => (
                    <label key={p} className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="radio"
                        name="priority"
                        checked={editingBR.priority === p}
                        onChange={() => setEditingBR({ ...editingBR, priority: p })}
                        className="text-cyan-500"
                      />
                      <span className={`px-2 py-1 rounded text-xs font-medium border ${PRIORITY_COLORS[p]}`}>
                        {p.toUpperCase()}
                      </span>
                    </label>
                  ))}
                </div>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-slate-400 mb-2">Notes (optional)</label>
                <textarea
                  value={editingBR.client_notes || ''}
                  onChange={(e) => setEditingBR({ ...editingBR, client_notes: e.target.value })}
                  rows={2}
                  placeholder="Add any notes about this requirement..."
                  className="w-full bg-slate-700 border border-slate-600 text-white rounded-lg px-4 py-2"
                />
              </div>
              
              {editingBR.original_text && editingBR.source === 'extracted' && (
                <div>
                  <label className="block text-sm font-medium text-slate-400 mb-2">Original (from Sophie)</label>
                  <div className="bg-slate-900/50 border border-slate-600 rounded-lg p-3 text-sm text-slate-400">
                    {editingBR.original_text}
                  </div>
                </div>
              )}
            </div>
            
            <div className="p-6 border-t border-slate-700 flex justify-end gap-3">
              <button
                onClick={() => setEditingBR(null)}
                className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg"
              >
                Cancel
              </button>
              <button
                onClick={handleUpdateBR}
                className="flex items-center gap-2 px-4 py-2 bg-cyan-600 hover:bg-cyan-500 text-white rounded-lg"
              >
                <Save className="w-4 h-4" />
                Save Changes
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Add Modal */}
      {isAddModalOpen && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-slate-800 border border-slate-700 rounded-2xl w-full max-w-2xl">
            <div className="p-6 border-b border-slate-700 flex items-center justify-between">
              <h2 className="text-xl font-bold text-white flex items-center gap-2">
                <Plus className="w-5 h-5 text-green-400" />
                Add New Requirement
              </h2>
              <button onClick={() => setIsAddModalOpen(false)} className="text-slate-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>
            
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-400 mb-2">Category</label>
                <select
                  value={newBR.category}
                  onChange={(e) => setNewBR({ ...newBR, category: e.target.value })}
                  className="w-full bg-slate-700 border border-slate-600 text-white rounded-lg px-4 py-2"
                >
                  <option value="">Select category...</option>
                  {CATEGORIES.map(cat => (
                    <option key={cat} value={cat}>{cat}</option>
                  ))}
                </select>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-slate-400 mb-2">Requirement *</label>
                <textarea
                  value={newBR.requirement}
                  onChange={(e) => setNewBR({ ...newBR, requirement: e.target.value })}
                  rows={4}
                  placeholder="Describe the business requirement..."
                  className="w-full bg-slate-700 border border-slate-600 text-white rounded-lg px-4 py-2"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-slate-400 mb-2">Priority</label>
                <div className="flex gap-3">
                  {(['must', 'should', 'could', 'wont'] as const).map(p => (
                    <label key={p} className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="radio"
                        name="newPriority"
                        checked={newBR.priority === p}
                        onChange={() => setNewBR({ ...newBR, priority: p })}
                        className="text-cyan-500"
                      />
                      <span className={`px-2 py-1 rounded text-xs font-medium border ${PRIORITY_COLORS[p]}`}>
                        {p.toUpperCase()}
                      </span>
                    </label>
                  ))}
                </div>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-slate-400 mb-2">Notes (optional)</label>
                <textarea
                  value={newBR.client_notes}
                  onChange={(e) => setNewBR({ ...newBR, client_notes: e.target.value })}
                  rows={2}
                  placeholder="Add any notes..."
                  className="w-full bg-slate-700 border border-slate-600 text-white rounded-lg px-4 py-2"
                />
              </div>
            </div>
            
            <div className="p-6 border-t border-slate-700 flex justify-end gap-3">
              <button
                onClick={() => setIsAddModalOpen(false)}
                className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg"
              >
                Cancel
              </button>
              <button
                onClick={handleAddBR}
                disabled={!newBR.requirement.trim()}
                className="flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-500 text-white rounded-lg disabled:opacity-50"
              >
                <Plus className="w-4 h-4" />
                Add Requirement
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
