/**
 * Custom hook for real-time execution progress via polling
 */
import { useState, useEffect } from 'react';
import { api } from '../services/api';

interface AgentStatus {
  state: 'waiting' | 'running' | 'completed' | 'error';
  progress: number;
  message: string;
  started_at?: string;
  completed_at?: string;
  error?: string;
}

interface ExecutionProgress {
  execution_id: number;
  status: string;
  agent_statuses?: Record<string, AgentStatus>;
  progress: number;
  current_agent?: string;
  message?: string;
}

export const useExecutionProgress = (executionId: number | null) => {
  const [progress, setProgress] = useState<ExecutionProgress | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!executionId) return;

    let intervalId: NodeJS.Timeout;
    let isMounted = true;

    const fetchProgress = async () => {
      try {
        const response = await api.get(`/api/pm-orchestrator/execute/${executionId}/progress`);
        
        if (!isMounted) return;
        
        console.log('Progress update received:', response.data);
        setProgress(response.data);
        setIsConnected(true);
        setError(null);

        // Stop polling if completed or failed
        if (response.data.status === 'COMPLETED' || response.data.status === 'FAILED') {
          console.log('Execution finished, stopping polling');
          clearInterval(intervalId);
          setIsConnected(false);
        }
      } catch (err: any) {
        console.error('Error fetching progress:', err);
        if (!isMounted) return;
        
        setError(err.response?.data?.detail || 'Failed to fetch progress');
        setIsConnected(false);
      }
    };

    // Initial fetch
    fetchProgress();

    // Poll every 2 seconds
    intervalId = setInterval(fetchProgress, 2000);

    // Cleanup
    return () => {
      isMounted = false;
      clearInterval(intervalId);
      setIsConnected(false);
    };
  }, [executionId]);

  return { progress, isConnected, error };
};
