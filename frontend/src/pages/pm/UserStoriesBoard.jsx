/**
 * User Stories Board Page - Kanban-style user stories management
 */
import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import pmService from '../../services/pmService';

const PRIORITIES = ['Must Have', 'Should Have', 'Could Have', "Won't Have"];

export default function UserStoriesBoard() {
  const { projectId } = useParams();
  const navigate = useNavigate();

  const [userStories, setUserStories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedStory, setSelectedStory] = useState(null);
  const [generating, setGenerating] = useState(false);

  useEffect(() => {
    loadUserStories();
  }, [projectId]);

  const loadUserStories = async () => {
    try {
      setLoading(true);
      const response = await pmService.getUserStories(projectId);
      setUserStories(response.user_stories || []);
    } catch (error) {
      console.error('Error loading user stories:', error);
      alert('Failed to load user stories');
    } finally {
      setLoading(false);
    }
  };

  const getStoriesByPriority = (priority) => {
    return userStories.filter((story) => story.priority === priority);
  };

  const getTotalPoints = (priority) => {
    return getStoriesByPriority(priority).reduce(
      (sum, story) => sum + (story.story_points || 0),
      0
    );
  };

  const getTotalStoryPoints = () => {
    return userStories.reduce(
      (sum, story) => sum + (story.story_points || 0),
      0
    );
  };

  const handleStoryClick = (story) => {
    setSelectedStory(story);
  };

  const handleCloseModal = () => {
    setSelectedStory(null);
  };

  const handleValidateAndContinue = async () => {
    try {
      setGenerating(true);
      await pmService.generateRoadmap(projectId);
      navigate(`/projects/${projectId}/roadmap`);
    } catch (error) {
      console.error('Error generating roadmap:', error);
      alert('Failed to generate roadmap');
    } finally {
      setGenerating(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-pm-primary mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading user stories...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-7xl mx-auto px-4">
        {/* Header */}
        <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">
                User Stories Board
              </h1>
              <p className="text-gray-600 mt-2">
                Total: {userStories.length} stories | {getTotalStoryPoints()}{' '}
                story points
              </p>
            </div>
            <div className="flex gap-3">
              <button
                onClick={() => navigate(`/projects/${projectId}/prd-review`)}
                className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
              >
                ← Back to PRD
              </button>
              <button
                onClick={handleValidateAndContinue}
                disabled={generating}
                className="px-6 py-2 bg-pm-success text-white rounded-lg hover:bg-green-600 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
              >
                {generating ? 'Generating...' : '✅ Validate & Continue to Roadmap'}
              </button>
            </div>
          </div>
        </div>

        {/* Kanban Board */}
        <div className="grid grid-cols-4 gap-4">
          {PRIORITIES.map((priority) => {
            const stories = getStoriesByPriority(priority);
            const points = getTotalPoints(priority);

            return (
              <div key={priority} className="bg-white rounded-lg shadow-sm p-4">
                <div className="mb-4">
                  <h2 className="font-semibold text-gray-900">{priority}</h2>
                  <p className="text-sm text-gray-600">
                    {stories.length} stories | {points} pts
                  </p>
                </div>

                <div className="space-y-3">
                  {stories.map((story) => (
                    <motion.div
                      key={story.id}
                      initial={{ opacity: 0, scale: 0.95 }}
                      animate={{ opacity: 1, scale: 1 }}
                      whileHover={{ scale: 1.02 }}
                      onClick={() => handleStoryClick(story)}
                      className="bg-gray-50 border border-gray-200 rounded-lg p-3 cursor-pointer hover:shadow-md transition-all"
                    >
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-xs font-mono text-gray-500">
                          {story.id}
                        </span>
                        <span className="text-xs font-semibold text-pm-primary">
                          {story.story_points} pts
                        </span>
                      </div>
                      <h3 className="text-sm font-medium text-gray-900 mb-2">
                        {story.title}
                      </h3>
                      <p className="text-xs text-gray-600 line-clamp-2">
                        {story.description}
                      </p>
                      {story.dependencies && story.dependencies.length > 0 && (
                        <div className="mt-2 flex flex-wrap gap-1">
                          {story.dependencies.map((dep, idx) => (
                            <span
                              key={idx}
                              className="text-xs bg-yellow-100 text-yellow-800 px-2 py-0.5 rounded"
                            >
                              {dep}
                            </span>
                          ))}
                        </div>
                      )}
                    </motion.div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>

        {/* Story Detail Modal */}
        {selectedStory && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            onClick={handleCloseModal}
            className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4"
          >
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              onClick={(e) => e.stopPropagation()}
              className="bg-white rounded-lg shadow-xl max-w-2xl w-full p-6 max-h-[80vh] overflow-y-auto"
            >
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-bold text-gray-900">
                  {selectedStory.id}: {selectedStory.title}
                </h2>
                <button
                  onClick={handleCloseModal}
                  className="text-gray-500 hover:text-gray-700"
                >
                  ✕
                </button>
              </div>

              <div className="space-y-4">
                <div>
                  <h3 className="font-semibold text-gray-700 mb-2">
                    Description
                  </h3>
                  <p className="text-gray-600">{selectedStory.description}</p>
                </div>

                <div>
                  <h3 className="font-semibold text-gray-700 mb-2">
                    Acceptance Criteria
                  </h3>
                  <ul className="space-y-2">
                    {selectedStory.acceptance_criteria?.map((criteria, idx) => (
                      <li
                        key={idx}
                        className="flex items-start text-gray-600 text-sm"
                      >
                        <span className="text-pm-success mr-2">✓</span>
                        <span>{criteria}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <h3 className="font-semibold text-gray-700 mb-2">
                      Priority
                    </h3>
                    <span className="inline-block bg-pm-primary text-white px-3 py-1 rounded">
                      {selectedStory.priority}
                    </span>
                  </div>
                  <div>
                    <h3 className="font-semibold text-gray-700 mb-2">
                      Story Points
                    </h3>
                    <span className="inline-block bg-gray-200 text-gray-900 px-3 py-1 rounded">
                      {selectedStory.story_points} points
                    </span>
                  </div>
                </div>

                {selectedStory.dependencies &&
                  selectedStory.dependencies.length > 0 && (
                    <div>
                      <h3 className="font-semibold text-gray-700 mb-2">
                        Dependencies
                      </h3>
                      <div className="flex flex-wrap gap-2">
                        {selectedStory.dependencies.map((dep, idx) => (
                          <span
                            key={idx}
                            className="bg-yellow-100 text-yellow-800 px-3 py-1 rounded"
                          >
                            {dep}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
              </div>
            </motion.div>
          </motion.div>
        )}
      </div>
    </div>
  );
}
