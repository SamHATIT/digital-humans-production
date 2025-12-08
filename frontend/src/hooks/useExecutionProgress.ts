/**
 * Custom hook for real-time execution progress via SSE (Server-Sent Events)
 * FRNT-04: Replaces polling with SSE for real-time updates
 */
import { useState, useEffect, useCallback, useRef } from 'react';

interface AgentStatus {
  agent_name: string;
  status: 'pending' | 'in_progress' | 'completed' | 'failed';
  progress: number;
  current_task?: string;
  output_summary?: string;
}

interface ExecutionProgress {
  execution_id: number;
  status: string;
  overall_progress: number;
  current_phase?: string;
  agent_progress: AgentStatus[];
  sds_document_path?: string;
  event?: string;
  message?: string;
}

export const useExecutionProgress = (executionId: number | null) => {
  const [progress, setProgress] = useState<ExecutionProgress | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const fallbackIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Fallback to polling if SSE fails
  const startPolling = useCallback(async (execId: number) => {
    const fetchProgress = async () => {
      try {
        const token = localStorage.getItem('token');
        const response = await fetch(`/api/pm-orchestrator/execute/${execId}/progress`, {
          headers: { 'Authorization': `Bearer ${token}` }
        });
        if (response.ok) {
          const data = await response.json();
          setProgress(data);
          setIsConnected(true);
          
          // Stop polling if finished
          if (data.status === 'COMPLETED' || data.status === 'FAILED' || data.status === 'CANCELLED') {
            if (fallbackIntervalRef.current) {
              clearInterval(fallbackIntervalRef.current);
              fallbackIntervalRef.current = null;
            }
          }
        }
      } catch (err) {
        console.error('Polling error:', err);
      }
    };
    
    fetchProgress();
    fallbackIntervalRef.current = setInterval(fetchProgress, 2000);
  }, []);

  useEffect(() => {
    if (!executionId) return;

    const token = localStorage.getItem('token');
    if (!token) {
      setError('No authentication token');
      return;
    }

    // Try SSE connection first
    const sseUrl = `/api/pm-orchestrator/execute/${executionId}/progress/stream?token=${encodeURIComponent(token)}`;
    
    try {
      console.log('🔌 Connecting to SSE:', sseUrl);
      const eventSource = new EventSource(sseUrl);
      eventSourceRef.current = eventSource;

      eventSource.onopen = () => {
        console.log('✅ SSE connected');
        setIsConnected(true);
        setError(null);
      };

      eventSource.onmessage = (event) => {
        try {
          const data: ExecutionProgress = JSON.parse(event.data);
          console.log('📨 SSE message:', data);
          
          // Handle special events
          if (data.event === 'close' || data.event === 'timeout') {
            console.log('🔌 SSE stream ended:', data.event);
            eventSource.close();
            setIsConnected(false);
            return;
          }
          
          if (data.event === 'error') {
            console.error('SSE error event:', data.message);
            setError(data.message || 'SSE error');
            return;
          }
          
          setProgress(data);
          
          // Close connection if execution finished
          if (data.status === 'COMPLETED' || data.status === 'FAILED' || data.status === 'CANCELLED') {
            console.log('✅ Execution finished, closing SSE');
            eventSource.close();
            setIsConnected(false);
          }
        } catch (e) {
          console.error('Error parsing SSE data:', e);
        }
      };

      eventSource.onerror = (err) => {
        console.warn('⚠️ SSE error, falling back to polling:', err);
        eventSource.close();
        setIsConnected(false);
        
        // Fallback to polling
        startPolling(executionId);
      };

    } catch (e) {
      console.warn('SSE not supported, using polling');
      startPolling(executionId);
    }

    // Cleanup
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
      if (fallbackIntervalRef.current) {
        clearInterval(fallbackIntervalRef.current);
        fallbackIntervalRef.current = null;
      }
      setIsConnected(false);
    };
  }, [executionId, startPolling]);

  return { progress, isConnected, error };
};
