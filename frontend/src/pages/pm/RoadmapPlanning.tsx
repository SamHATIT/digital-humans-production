/**
 * Roadmap Planning Page — Timeline visualization (legacy).
 * Page non routée actuellement, refonte prévue en A5.3.
 */
import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { motion } from 'framer-motion';
import pmService from '../../services/pmService';
import type { Roadmap } from '../../services/pmService';

export default function RoadmapPlanning() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();

  const [roadmap, setRoadmap] = useState<Roadmap | null>(null);
  const [loading, setLoading] = useState(true);
  const [validating, setValidating] = useState(false);

  useEffect(() => {
    if (!projectId) return;
    let cancelled = false;
    setLoading(true);
    pmService
      .getRoadmap(projectId)
      .then((response) => {
        if (!cancelled) setRoadmap(response.roadmap ?? null);
      })
      .catch(() => {
        if (!cancelled) window.alert('Failed to load roadmap');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  const handleValidateRoadmap = async () => {
    if (!projectId) return;
    setValidating(true);
    try {
      window.alert('Roadmap validated! Execution can now be launched.');
      navigate(`/projects/${projectId}/execution`);
    } catch {
      window.alert('Failed to validate roadmap');
    } finally {
      setValidating(false);
    }
  };

  const getProgressPercentage = (phaseIndex: number, totalPhases: number) =>
    ((phaseIndex + 1) / totalPhases) * 100;

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto" />
          <p className="mt-4 text-gray-600">Loading roadmap...</p>
        </div>
      </div>
    );
  }

  if (!roadmap) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <p className="text-gray-600">No roadmap available</p>
          <button
            onClick={() => projectId && navigate(`/projects/${projectId}/user-stories`)}
            className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            Go Back
          </button>
        </div>
      </div>
    );
  }

  const phases = roadmap.phases ?? [];

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-6xl mx-auto px-4">
        <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">Implementation Roadmap</h1>
              <p className="text-gray-600 mt-2">
                Timeline: {roadmap.total_duration_weeks} weeks | {phases.length} phases
              </p>
            </div>
            <div className="flex gap-3">
              <button
                onClick={() => projectId && navigate(`/projects/${projectId}/user-stories`)}
                className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
              >
                ← Back to Stories
              </button>
              <button
                onClick={() => void handleValidateRoadmap()}
                disabled={validating}
                className="px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
              >
                {validating ? 'Validating...' : '✅ Validate & Launch Execution'}
              </button>
            </div>
          </div>
        </div>

        <div className="space-y-6">
          {phases.map((phase, index) => (
            <motion.div
              key={index}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: index * 0.1 }}
              className="bg-white rounded-lg shadow-sm p-6"
            >
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center">
                  <div className="w-10 h-10 bg-blue-600 text-white rounded-full flex items-center justify-center font-bold mr-4">
                    {index + 1}
                  </div>
                  <div>
                    <h2 className="text-xl font-bold text-gray-900">{phase.name}</h2>
                    <p className="text-sm text-gray-600">Duration: {phase.duration_weeks} weeks</p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-sm text-gray-600">
                    {phase.user_stories?.length || 0} user stories
                  </p>
                </div>
              </div>

              <div className="mb-4">
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${getProgressPercentage(index, phases.length)}%` }}
                    transition={{ duration: 0.5, delay: index * 0.1 }}
                    className="bg-blue-600 h-2 rounded-full"
                    style={{ width: `${getProgressPercentage(index, phases.length)}%` }}
                  />
                </div>
              </div>

              <div className="grid grid-cols-3 gap-6">
                <div>
                  <h3 className="font-semibold text-gray-700 mb-2">User Stories</h3>
                  <div className="space-y-1">
                    {phase.user_stories?.map((storyId, idx) => (
                      <div key={idx} className="text-sm bg-gray-50 px-3 py-1 rounded">
                        {storyId}
                      </div>
                    ))}
                  </div>
                </div>

                <div>
                  <h3 className="font-semibold text-gray-700 mb-2">Deliverables</h3>
                  <ul className="space-y-1">
                    {phase.deliverables?.map((deliverable, idx) => (
                      <li key={idx} className="text-sm text-gray-600 flex items-start">
                        <span className="text-green-600 mr-2">📦</span>
                        <span>{deliverable}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                <div>
                  <h3 className="font-semibold text-gray-700 mb-2">Success Criteria</h3>
                  <ul className="space-y-1">
                    {phase.success_criteria?.map((criteria, idx) => (
                      <li key={idx} className="text-sm text-gray-600 flex items-start">
                        <span className="text-green-600 mr-2">✓</span>
                        <span>{criteria}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </motion.div>
          ))}
        </div>

        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.5 }}
          className="mt-6 bg-blue-50 border border-blue-200 rounded-lg p-4"
        >
          <div className="flex">
            <div className="flex-shrink-0">
              <span className="text-2xl">🚀</span>
            </div>
            <div className="ml-3">
              <h3 className="text-sm font-medium text-blue-900">Ready to Launch</h3>
              <div className="mt-2 text-sm text-blue-700">
                <p>Once you validate this roadmap, the system will:</p>
                <ul className="list-disc list-inside mt-2 space-y-1">
                  <li>Create an execution plan for all agents</li>
                  <li>Generate all technical specifications</li>
                  <li>Implement code and configurations</li>
                  <li>Produce training materials</li>
                  <li>Generate final deliverables (Functional Specs, Technical Specs, etc.)</li>
                </ul>
              </div>
            </div>
          </div>
        </motion.div>
      </div>
    </div>
  );
}
