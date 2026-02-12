import { useMemo } from 'react';
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import { Activity, DollarSign, Clock, Zap } from 'lucide-react';

interface AgentMetric {
  agent_name: string;
  tokens_used?: number;
  cost?: number;
  duration_seconds?: number;
  status?: string;
}

interface PhaseTiming {
  phase: string;
  duration_seconds: number;
  cost?: number;
}

interface ExecutionMetricsProps {
  agents: AgentMetric[];
  phases?: PhaseTiming[];
  totalCost?: number;
  cumulativeCosts?: { timestamp: string; cost: number }[];
}

const AGENT_COLORS = [
  '#06b6d4', // cyan
  '#8b5cf6', // purple
  '#10b981', // green
  '#f59e0b', // amber
  '#ec4899', // pink
  '#3b82f6', // blue
  '#ef4444', // red
  '#14b8a6', // teal
  '#f97316', // orange
  '#6366f1', // indigo
  '#84cc16', // lime
];

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const mins = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  return secs > 0 ? `${mins}m ${secs}s` : `${mins}m`;
}

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

export default function ExecutionMetrics({
  agents,
  phases,
  totalCost,
  cumulativeCosts,
}: ExecutionMetricsProps) {
  const tokenData = useMemo(
    () =>
      agents
        .filter((a) => (a.tokens_used || 0) > 0)
        .map((a) => ({
          name: a.agent_name.split(' (')[0],
          tokens: a.tokens_used || 0,
        }))
        .sort((a, b) => b.tokens - a.tokens),
    [agents]
  );

  const phaseData = useMemo(
    () =>
      (phases || []).map((p) => ({
        name: p.phase,
        duration: Math.round(p.duration_seconds),
        cost: p.cost || 0,
      })),
    [phases]
  );

  const costData = useMemo(() => {
    if (cumulativeCosts && cumulativeCosts.length > 0) {
      return cumulativeCosts.map((c) => ({
        time: new Date(c.timestamp).toLocaleTimeString([], {
          hour: '2-digit',
          minute: '2-digit',
        }),
        cost: c.cost,
      }));
    }
    // Fallback: compute cumulative from agents
    let cumulative = 0;
    return agents
      .filter((a) => (a.cost || 0) > 0)
      .map((a) => {
        cumulative += a.cost || 0;
        return {
          time: a.agent_name.split(' (')[0],
          cost: parseFloat(cumulative.toFixed(2)),
        };
      });
  }, [agents, cumulativeCosts]);

  const totalTokens = agents.reduce((sum, a) => sum + (a.tokens_used || 0), 0);
  const totalDuration = agents.reduce((sum, a) => sum + (a.duration_seconds || 0), 0);
  const effectiveTotalCost =
    totalCost ?? agents.reduce((sum, a) => sum + (a.cost || 0), 0);

  return (
    <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-2xl p-5">
      <div className="flex items-center gap-2 mb-4">
        <Activity className="w-5 h-5 text-purple-400" />
        <h3 className="text-lg font-semibold text-white">Execution Metrics</h3>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-3 gap-3 mb-5">
        <div className="bg-slate-900/50 border border-slate-700 rounded-xl px-4 py-3">
          <div className="flex items-center gap-2 mb-1">
            <Zap className="w-3.5 h-3.5 text-cyan-400" />
            <span className="text-xs text-slate-500">Total Tokens</span>
          </div>
          <p className="text-lg font-bold text-white">{formatTokens(totalTokens)}</p>
        </div>
        <div className="bg-slate-900/50 border border-slate-700 rounded-xl px-4 py-3">
          <div className="flex items-center gap-2 mb-1">
            <DollarSign className="w-3.5 h-3.5 text-green-400" />
            <span className="text-xs text-slate-500">Total Cost</span>
          </div>
          <p className="text-lg font-bold text-white">${effectiveTotalCost.toFixed(2)}</p>
        </div>
        <div className="bg-slate-900/50 border border-slate-700 rounded-xl px-4 py-3">
          <div className="flex items-center gap-2 mb-1">
            <Clock className="w-3.5 h-3.5 text-amber-400" />
            <span className="text-xs text-slate-500">Total Time</span>
          </div>
          <p className="text-lg font-bold text-white">{formatDuration(totalDuration)}</p>
        </div>
      </div>

      {/* Tokens per agent (bar chart) */}
      {tokenData.length > 0 && (
        <div className="mb-5">
          <p className="text-xs text-slate-400 font-medium mb-2">Tokens by Agent</p>
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={tokenData} layout="vertical" margin={{ left: 0, right: 16 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" horizontal={false} />
                <XAxis
                  type="number"
                  tickFormatter={formatTokens}
                  tick={{ fill: '#64748b', fontSize: 10 }}
                  axisLine={{ stroke: '#475569' }}
                />
                <YAxis
                  type="category"
                  dataKey="name"
                  width={80}
                  tick={{ fill: '#94a3b8', fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip
                  formatter={(value) => [formatTokens(Number(value ?? 0)), 'Tokens']}
                  contentStyle={{
                    backgroundColor: '#1e293b',
                    border: '1px solid #475569',
                    borderRadius: '8px',
                    fontSize: '12px',
                  }}
                  itemStyle={{ color: '#e2e8f0' }}
                  labelStyle={{ color: '#94a3b8' }}
                />
                <Bar dataKey="tokens" radius={[0, 4, 4, 0]} maxBarSize={24}>
                  {tokenData.map((_, i) => (
                    <Cell key={i} fill={AGENT_COLORS[i % AGENT_COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Cumulative cost (line chart) */}
      {costData.length > 1 && (
        <div className="mb-5">
          <p className="text-xs text-slate-400 font-medium mb-2">Cumulative Cost</p>
          <div className="h-40">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={costData} margin={{ left: 0, right: 16 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis
                  dataKey="time"
                  tick={{ fill: '#64748b', fontSize: 10 }}
                  axisLine={{ stroke: '#475569' }}
                />
                <YAxis
                  tickFormatter={(v) => `$${v}`}
                  tick={{ fill: '#64748b', fontSize: 10 }}
                  axisLine={{ stroke: '#475569' }}
                />
                <Tooltip
                  formatter={(value) => [`$${Number(value ?? 0).toFixed(2)}`, 'Cost']}
                  contentStyle={{
                    backgroundColor: '#1e293b',
                    border: '1px solid #475569',
                    borderRadius: '8px',
                    fontSize: '12px',
                  }}
                  itemStyle={{ color: '#e2e8f0' }}
                  labelStyle={{ color: '#94a3b8' }}
                />
                <Line
                  type="monotone"
                  dataKey="cost"
                  stroke="#10b981"
                  strokeWidth={2}
                  dot={{ fill: '#10b981', r: 3 }}
                  activeDot={{ r: 5 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Duration per phase (bar chart) */}
      {phaseData.length > 0 && (
        <div>
          <p className="text-xs text-slate-400 font-medium mb-2">Duration by Phase</p>
          <div className="h-40">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={phaseData} margin={{ left: 0, right: 16 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis
                  dataKey="name"
                  tick={{ fill: '#94a3b8', fontSize: 10 }}
                  axisLine={{ stroke: '#475569' }}
                />
                <YAxis
                  tickFormatter={(v) => formatDuration(v)}
                  tick={{ fill: '#64748b', fontSize: 10 }}
                  axisLine={{ stroke: '#475569' }}
                />
                <Tooltip
                  formatter={(value) => [formatDuration(Number(value ?? 0)), 'Duration']}
                  contentStyle={{
                    backgroundColor: '#1e293b',
                    border: '1px solid #475569',
                    borderRadius: '8px',
                    fontSize: '12px',
                  }}
                  itemStyle={{ color: '#e2e8f0' }}
                  labelStyle={{ color: '#94a3b8' }}
                />
                <Bar dataKey="duration" fill="#8b5cf6" radius={[4, 4, 0, 0]} maxBarSize={40} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  );
}
