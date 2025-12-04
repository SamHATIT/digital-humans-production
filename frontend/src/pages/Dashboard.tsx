import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { FolderPlus, Clock, CheckCircle, AlertCircle, Zap, ArrowRight } from 'lucide-react';
import { projects } from '../services/api';
import Navbar from '../components/Navbar';

interface DashboardStats {
  total_projects: number;
  active_executions: number;
  completed_projects: number;
}

interface Project {
  id: number;
  name: string;
  status: string;
  created_at: string;
}

export default function Dashboard() {
  const navigate = useNavigate();
  const [stats, setStats] = useState<DashboardStats>({
    total_projects: 0,
    active_executions: 0,
    completed_projects: 0,
  });
  const [recentProjects, setRecentProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [statsData, projectsData] = await Promise.all([
          projects.getDashboardStats(),
          projects.list(0, 5),
        ]);
        setStats(statsData);
        setRecentProjects(projectsData.projects || projectsData || []);
      } catch (error) {
        console.error('Failed to fetch dashboard data:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  const getStatusBadge = (status: string) => {
    const configs: Record<string, { color: string; icon: typeof CheckCircle }> = {
      completed: { color: 'bg-green-500/20 text-green-400 border-green-500/30', icon: CheckCircle },
      in_progress: { color: 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30', icon: Zap },
      ready: { color: 'bg-purple-500/20 text-purple-400 border-purple-500/30', icon: Clock },
      failed: { color: 'bg-red-500/20 text-red-400 border-red-500/30', icon: AlertCircle },
      draft: { color: 'bg-slate-500/20 text-slate-400 border-slate-500/30', icon: Clock },
    };
    const config = configs[status] || configs.draft;
    const Icon = config.icon;

    return (
      <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium border ${config.color}`}>
        <Icon className="w-3 h-3" />
        {status}
      </span>
    );
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
        {/* Welcome Section */}
        <div className="mb-10 text-center">
          <h1 className="text-4xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-purple-500">
            Welcome to Digital Humans
          </h1>
          <p className="mt-2 text-slate-400 max-w-2xl mx-auto">
            Your AI-powered Salesforce automation system. Create projects and let your digital workforce handle the rest.
          </p>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-10">
          <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-2xl p-6 hover:border-cyan-500/30 transition-all">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-slate-400 text-sm font-medium">Total Projects</p>
                <p className="text-3xl font-bold text-white mt-1">{stats.total_projects}</p>
              </div>
              <div className="w-12 h-12 rounded-xl bg-cyan-500/20 flex items-center justify-center">
                <FolderPlus className="w-6 h-6 text-cyan-400" />
              </div>
            </div>
          </div>

          <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-2xl p-6 hover:border-green-500/30 transition-all">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-slate-400 text-sm font-medium">Active</p>
                <p className="text-3xl font-bold text-green-400 mt-1">{stats.active_executions}</p>
              </div>
              <div className="w-12 h-12 rounded-xl bg-green-500/20 flex items-center justify-center">
                <Zap className="w-6 h-6 text-green-400" />
              </div>
            </div>
          </div>

          <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-2xl p-6 hover:border-purple-500/30 transition-all">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-slate-400 text-sm font-medium">Completed</p>
                <p className="text-3xl font-bold text-purple-400 mt-1">{stats.completed_projects}</p>
              </div>
              <div className="w-12 h-12 rounded-xl bg-purple-500/20 flex items-center justify-center">
                <CheckCircle className="w-6 h-6 text-purple-400" />
              </div>
            </div>
          </div>
        </div>

        {/* Quick Actions */}
        <div className="mb-10">
          <Link
            to="/projects/new"
            className="inline-flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-cyan-500 to-purple-600 text-white font-medium rounded-xl hover:from-cyan-600 hover:to-purple-700 transition-all shadow-lg shadow-cyan-500/25 hover:shadow-cyan-500/40"
          >
            <FolderPlus className="w-5 h-5" />
            Create New Project
            <ArrowRight className="w-4 h-4" />
          </Link>
        </div>

        {/* Recent Projects */}
        <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-2xl overflow-hidden">
          <div className="p-6 border-b border-slate-700">
            <h2 className="text-xl font-bold text-white">Recent Projects</h2>
          </div>

          {loading ? (
            <div className="p-10 text-center">
              <div className="animate-spin w-8 h-8 border-2 border-cyan-500 border-t-transparent rounded-full mx-auto" />
              <p className="text-slate-400 mt-4">Loading projects...</p>
            </div>
          ) : recentProjects.length === 0 ? (
            <div className="p-10 text-center">
              <p className="text-slate-400">No projects yet. Create your first one!</p>
            </div>
          ) : (
            <div className="divide-y divide-slate-700">
              {recentProjects.map((project) => (
                <div
                  key={project.id}
                  onClick={() => navigate(`/execution/${project.id}`)}
                  className="p-4 hover:bg-slate-700/30 cursor-pointer transition-all flex items-center justify-between group"
                >
                  <div>
                    <h3 className="font-medium text-white group-hover:text-cyan-400 transition-colors">
                      {project.name}
                    </h3>
                    <p className="text-sm text-slate-500">
                      Created {new Date(project.created_at).toLocaleDateString()}
                    </p>
                  </div>
                  <div className="flex items-center gap-3">
                    {getStatusBadge(project.status)}
                    <ArrowRight className="w-4 h-4 text-slate-500 group-hover:text-cyan-400 transition-colors" />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
