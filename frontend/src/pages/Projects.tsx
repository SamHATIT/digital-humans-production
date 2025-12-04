import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Loader2, CheckCircle, AlertCircle, Clock, Zap, Trash2, ArrowRight, FolderOpen } from 'lucide-react';
import { projects } from '../services/api';
import Navbar from '../components/Navbar';

interface Project {
  id: number;
  name: string;
  description?: string;
  status: string;
  created_at: string;
}

export default function Projects() {
  const navigate = useNavigate();
  const [projectList, setProjectList] = useState<Project[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchProjects = async () => {
      try {
        const data = await projects.list(0, 50);
        setProjectList(data.projects || data || []);
      } catch (err: any) {
        console.error('Failed to fetch projects:', err);
        setError(err.message || 'Failed to load projects');
      } finally {
        setIsLoading(false);
      }
    };

    fetchProjects();
  }, []);

  const handleDelete = async (projectId: number, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm('Are you sure you want to delete this project?')) return;

    try {
      await projects.delete(projectId);
      setProjectList((prev) => prev.filter((p) => p.id !== projectId));
    } catch (err: any) {
      console.error('Failed to delete project:', err);
      alert('Failed to delete project');
    }
  };

  const getStatusConfig = (status: string) => {
    const configs: Record<string, { color: string; icon: typeof CheckCircle }> = {
      completed: { color: 'bg-green-500/20 text-green-400 border-green-500/30', icon: CheckCircle },
      in_progress: { color: 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30', icon: Zap },
      ready: { color: 'bg-purple-500/20 text-purple-400 border-purple-500/30', icon: Clock },
      failed: { color: 'bg-red-500/20 text-red-400 border-red-500/30', icon: AlertCircle },
      draft: { color: 'bg-slate-500/20 text-slate-400 border-slate-500/30', icon: Clock },
    };
    return configs[status] || configs.draft;
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
        <div className="mb-10">
          <h1 className="text-3xl font-extrabold text-white">All Projects</h1>
          <p className="text-slate-400 mt-1">Manage and monitor your Salesforce implementations</p>
        </div>

        {error && (
          <div className="mb-6 bg-red-500/10 border border-red-500/30 rounded-xl p-4 text-red-400">
            {error}
          </div>
        )}

        {isLoading ? (
          <div className="text-center py-20">
            <Loader2 className="w-12 h-12 text-cyan-500 animate-spin mx-auto" />
            <p className="text-slate-400 mt-4">Loading projects...</p>
          </div>
        ) : projectList.length === 0 ? (
          <div className="text-center py-20 bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-2xl">
            <FolderOpen className="w-16 h-16 text-slate-600 mx-auto mb-4" />
            <p className="text-slate-400 mb-4">No projects found</p>
            <button
              onClick={() => navigate('/projects/new')}
              className="inline-flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-cyan-500 to-purple-600 text-white font-medium rounded-xl"
            >
              Create Your First Project
            </button>
          </div>
        ) : (
          <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-2xl overflow-hidden">
            <div className="divide-y divide-slate-700">
              {projectList.map((project) => {
                const config = getStatusConfig(project.status);
                const StatusIcon = config.icon;

                return (
                  <div
                    key={project.id}
                    onClick={() => navigate(`/execution/${project.id}`)}
                    className="p-5 hover:bg-slate-700/30 cursor-pointer transition-all flex items-center justify-between group"
                  >
                    <div className="flex-1 min-w-0">
                      <h3 className="font-medium text-white group-hover:text-cyan-400 transition-colors truncate">
                        {project.name}
                      </h3>
                      {project.description && (
                        <p className="text-sm text-slate-500 truncate mt-1">{project.description}</p>
                      )}
                      <p className="text-xs text-slate-600 mt-1">
                        Created {new Date(project.created_at).toLocaleDateString()}
                      </p>
                    </div>

                    <div className="flex items-center gap-4 ml-4">
                      <span
                        className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium border ${config.color}`}
                      >
                        <StatusIcon className="w-3 h-3" />
                        {project.status}
                      </span>

                      <button
                        onClick={(e) => handleDelete(project.id, e)}
                        className="p-2 rounded-lg text-slate-500 hover:text-red-400 hover:bg-red-500/10 transition-all opacity-0 group-hover:opacity-100"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>

                      <ArrowRight className="w-5 h-5 text-slate-500 group-hover:text-cyan-400 transition-colors" />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
