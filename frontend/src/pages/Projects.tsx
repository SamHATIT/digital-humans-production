import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Plus, Loader2, FileText } from 'lucide-react';
import { projects } from '../services/api';

interface Project {
  id: number;
  name: string;
  salesforce_product?: string;
  organization_type?: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export default function Projects() {
  const [projectsList, setProjectsList] = useState<Project[]>([]);
  const [filter, setFilter] = useState('all');
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    loadProjects();
  }, [filter]);

  const loadProjects = async () => {
    try {
      setIsLoading(true);
      const data = await projects.list(0, 50, filter === 'all' ? undefined : filter);
      setProjectsList(data);
    } catch (error) {
      console.error('Error loading projects:', error);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-7xl mx-auto">
        <div className="flex justify-between items-center mb-8">
          <h1 className="text-4xl font-bold">Projects</h1>
          <Link
            to="/projects/new"
            className="bg-blue-600 text-white px-6 py-3 rounded-lg hover:bg-blue-700 flex items-center gap-2 transition"
          >
            <Plus size={20} />
            New Project
          </Link>
        </div>

        {/* Filters */}
        <div className="flex gap-4 mb-6">
          <FilterButton active={filter === 'all'} onClick={() => setFilter('all')}>
            All Projects
          </FilterButton>
          <FilterButton active={filter === 'draft'} onClick={() => setFilter('draft')}>
            Draft
          </FilterButton>
          <FilterButton active={filter === 'ready'} onClick={() => setFilter('ready')}>
            Ready
          </FilterButton>
          <FilterButton active={filter === 'active'} onClick={() => setFilter('active')}>
            Active
          </FilterButton>
          <FilterButton active={filter === 'completed'} onClick={() => setFilter('completed')}>
            Completed
          </FilterButton>
        </div>

        {/* Projects Grid */}
        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="animate-spin text-blue-600" size={48} />
          </div>
        ) : projectsList.length === 0 ? (
          <div className="bg-white rounded-lg shadow-md p-12 text-center">
            <FileText className="mx-auto mb-4 text-gray-400" size={64} />
            <h2 className="text-2xl font-bold text-gray-900 mb-2">No projects found</h2>
            <p className="text-gray-600 mb-6">
              {filter === 'all'
                ? 'Get started by creating your first project'
                : `No projects with status "${filter}"`
              }
            </p>
            <Link
              to="/projects/new"
              className="inline-flex items-center gap-2 bg-blue-600 text-white px-6 py-3 rounded-lg hover:bg-blue-700"
            >
              <Plus size={20} />
              Create Project
            </Link>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {projectsList.map(project => (
              <ProjectCard key={project.id} project={project} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// Filter Button Component
interface FilterButtonProps {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}

function FilterButton({ active, onClick, children }: FilterButtonProps) {
  return (
    <button
      onClick={onClick}
      className={`px-4 py-2 rounded-lg font-medium transition ${
        active
          ? 'bg-blue-600 text-white'
          : 'bg-white text-gray-700 border border-gray-300 hover:bg-gray-50'
      }`}
    >
      {children}
    </button>
  );
}

// Project Card Component
function ProjectCard({ project }: { project: Project }) {
  const statusColors: Record<string, string> = {
    draft: 'bg-gray-100 text-gray-800',
    ready: 'bg-blue-100 text-blue-800',
    active: 'bg-green-100 text-green-800',
    completed: 'bg-purple-100 text-purple-800',
  };

  return (
    <Link
      to={`/execution/${project.id}`}
      className="block bg-white border border-gray-200 rounded-lg p-6 hover:border-blue-300 hover:shadow-md transition"
    >
      <div className="mb-4">
        <h3 className="text-xl font-bold text-gray-900 mb-2">{project.name}</h3>
        <div className="flex flex-wrap gap-2 text-sm text-gray-600">
          {project.salesforce_product && (
            <span className="bg-gray-100 px-2 py-1 rounded">{project.salesforce_product}</span>
          )}
          {project.organization_type && (
            <span className="bg-gray-100 px-2 py-1 rounded">{project.organization_type}</span>
          )}
        </div>
      </div>

      <div className="flex items-center justify-between">
        <span className={`px-3 py-1 rounded-full text-xs font-medium ${statusColors[project.status] || 'bg-gray-100 text-gray-800'}`}>
          {project.status}
        </span>
        <span className="text-sm text-gray-500">
          {new Date(project.updated_at).toLocaleDateString()}
        </span>
      </div>
    </Link>
  );
}
