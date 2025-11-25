/**
 * PRD Review Page - Display and edit Product Requirements Document
 */
import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import pmService from '../../services/pmService';

export default function PRDReview() {
  const { projectId } = useParams();
  const navigate = useNavigate();

  const [prdContent, setPrdContent] = useState('');
  const [isEditing, setIsEditing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [generating, setGenerating] = useState(false);

  useEffect(() => {
    loadPRD();
  }, [projectId]);

  const loadPRD = async () => {
    try {
      setLoading(true);
      const response = await pmService.getPRD(projectId);
      setPrdContent(response.prd_content || '');
    } catch (error) {
      console.error('Error loading PRD:', error);
      alert('Failed to load PRD');
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      await pmService.updatePRD(projectId, prdContent);
      setIsEditing(false);
      alert('PRD saved successfully');
    } catch (error) {
      console.error('Error saving PRD:', error);
      alert('Failed to save PRD');
    } finally {
      setSaving(false);
    }
  };

  const handleGenerateUserStories = async () => {
    try {
      setGenerating(true);
      await pmService.generateUserStories(projectId);
      navigate(`/projects/${projectId}/user-stories`);
    } catch (error) {
      console.error('Error generating user stories:', error);
      alert('Failed to generate user stories');
    } finally {
      setGenerating(false);
    }
  };

  const handleRegenerate = () => {
    navigate(`/projects/${projectId}/pm-dialogue`);
  };

  const handleDownload = () => {
    const blob = new Blob([prdContent], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `PRD_Project_${projectId}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-pm-primary mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading PRD...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-6xl mx-auto px-4">
        {/* Header */}
        <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">
                Product Requirements Document
              </h1>
              <p className="text-gray-600 mt-2">
                Review and validate your PRD before generating user stories
              </p>
            </div>
            <div className="flex gap-3">
              <button
                onClick={() => setIsEditing(!isEditing)}
                className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
              >
                {isEditing ? 'Cancel Edit' : 'Edit Mode'}
              </button>
              <button
                onClick={handleDownload}
                className="px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition-colors"
              >
                📥 Download PRD
              </button>
              <button
                onClick={handleRegenerate}
                className="px-4 py-2 border border-pm-warning text-pm-warning rounded-lg hover:bg-pm-warning hover:text-white transition-colors"
              >
                🔄 Regenerate
              </button>
              <button
                onClick={isEditing ? handleSave : handleGenerateUserStories}
                disabled={isEditing ? saving : generating}
                className="px-6 py-2 bg-pm-success text-white rounded-lg hover:bg-green-600 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
              >
                {isEditing
                  ? saving
                    ? 'Saving...'
                    : 'Save Changes'
                  : generating
                  ? 'Generating...'
                  : '✅ Validate & Continue'}
              </button>
            </div>
          </div>
        </div>

        {/* PRD Content */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-white rounded-lg shadow-sm p-8"
        >
          {isEditing ? (
            <textarea
              value={prdContent}
              onChange={(e) => setPrdContent(e.target.value)}
              className="w-full h-[600px] border border-gray-300 rounded-lg p-4 font-mono text-sm focus:outline-none focus:ring-2 focus:ring-pm-primary resize-none"
              placeholder="Edit PRD content here..."
            />
          ) : (
            <div className="prose max-w-none">
              <div className="whitespace-pre-wrap font-sans">
                {prdContent || 'No PRD content available'}
              </div>
            </div>
          )}
        </motion.div>

        {/* Info Box */}
        {!isEditing && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.3 }}
            className="mt-6 bg-blue-50 border border-blue-200 rounded-lg p-4"
          >
            <div className="flex">
              <div className="flex-shrink-0">
                <span className="text-2xl">ℹ️</span>
              </div>
              <div className="ml-3">
                <h3 className="text-sm font-medium text-blue-900">
                  Next Steps
                </h3>
                <div className="mt-2 text-sm text-blue-700">
                  <p>
                    Once you validate this PRD, the PM will generate:
                  </p>
                  <ul className="list-disc list-inside mt-2 space-y-1">
                    <li>20-50 detailed user stories with acceptance criteria</li>
                    <li>Story points and MoSCoW prioritization</li>
                    <li>Dependencies and technical requirements</li>
                  </ul>
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </div>
    </div>
  );
}
