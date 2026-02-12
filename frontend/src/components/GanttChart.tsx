import { useEffect, useRef, useState } from 'react';
import { Calendar, AlertCircle } from 'lucide-react';

interface WBSTask {
  id: string;
  name: string;
  start?: string;
  end?: string;
  duration?: string;
  progress?: number;
  dependencies?: string;
  custom_class?: string;
}

interface GanttChartProps {
  tasks: WBSTask[];
  title?: string;
}

function parseDuration(duration: string): number {
  const match = duration.match(/(\d+)\s*(d|day|days|w|week|weeks|h|hour|hours)/i);
  if (!match) return 1;
  const val = parseInt(match[1]);
  const unit = match[2].toLowerCase();
  if (unit.startsWith('w')) return val * 7;
  if (unit.startsWith('h')) return Math.max(1, Math.ceil(val / 8));
  return val;
}

function normalizeTasksForGantt(tasks: WBSTask[]): {
  id: string;
  name: string;
  startDay: number;
  durationDays: number;
  progress: number;
  dependencies: string[];
}[] {
  const taskMap = new Map<string, WBSTask>();
  tasks.forEach((t) => taskMap.set(t.id, t));

  // Compute durations
  const durations = new Map<string, number>();
  tasks.forEach((t) => {
    durations.set(t.id, t.duration ? parseDuration(t.duration) : 5);
  });

  // Compute start days (topological order based on deps)
  const startDays = new Map<string, number>();

  const getStartDay = (taskId: string, visited: Set<string> = new Set()): number => {
    if (startDays.has(taskId)) return startDays.get(taskId)!;
    if (visited.has(taskId)) return 0; // circular dep protection
    visited.add(taskId);

    const task = taskMap.get(taskId);
    const deps = task?.dependencies
      ? task.dependencies.split(',').map((d) => d.trim()).filter(Boolean)
      : [];

    let maxEnd = 0;
    for (const dep of deps) {
      if (taskMap.has(dep)) {
        const depStart = getStartDay(dep, visited);
        const depDuration = durations.get(dep) || 5;
        maxEnd = Math.max(maxEnd, depStart + depDuration);
      }
    }

    startDays.set(taskId, maxEnd);
    return maxEnd;
  };

  return tasks.map((t) => ({
    id: t.id,
    name: t.name,
    startDay: getStartDay(t.id),
    durationDays: durations.get(t.id) || 5,
    progress: t.progress || 0,
    dependencies: t.dependencies
      ? t.dependencies.split(',').map((d) => d.trim()).filter(Boolean)
      : [],
  }));
}

export default function GanttChart({ tasks, title }: GanttChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [hoveredTask, setHoveredTask] = useState<string | null>(null);

  if (!tasks || tasks.length === 0) {
    return (
      <div className="bg-slate-900/50 border border-slate-700 rounded-xl p-6 text-center">
        <AlertCircle className="w-8 h-8 text-slate-500 mx-auto mb-2" />
        <p className="text-slate-400 text-sm">No WBS tasks available to display.</p>
      </div>
    );
  }

  const normalized = normalizeTasksForGantt(tasks);
  const totalDays = Math.max(...normalized.map((t) => t.startDay + t.durationDays), 1);
  const dayWidth = Math.max(30, Math.min(60, 800 / totalDays));
  const rowHeight = 36;
  const labelWidth = 220;
  const headerHeight = 32;
  const chartWidth = totalDays * dayWidth;

  const barColors = [
    'from-cyan-500 to-blue-500',
    'from-purple-500 to-indigo-500',
    'from-green-500 to-emerald-500',
    'from-amber-500 to-orange-500',
    'from-pink-500 to-rose-500',
    'from-teal-500 to-cyan-500',
  ];

  return (
    <div className="bg-slate-900/50 border border-slate-700 rounded-xl overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-3 border-b border-slate-700 bg-slate-800/50">
        <Calendar className="w-4 h-4 text-amber-400" />
        <span className="text-sm font-medium text-white">{title || 'WBS Gantt Chart'}</span>
        <span className="text-xs text-slate-500 ml-auto">{tasks.length} tasks &middot; {totalDays} days</span>
      </div>

      {/* Chart */}
      <div ref={containerRef} className="overflow-x-auto">
        <div className="flex" style={{ minWidth: labelWidth + chartWidth }}>
          {/* Task labels column */}
          <div className="flex-shrink-0" style={{ width: labelWidth }}>
            {/* Header spacer */}
            <div
              className="border-b border-r border-slate-700 bg-slate-800/50 px-3 flex items-center"
              style={{ height: headerHeight }}
            >
              <span className="text-xs text-slate-400 font-medium">Task</span>
            </div>
            {/* Task rows */}
            {normalized.map((task) => (
              <div
                key={task.id}
                className={`border-b border-r border-slate-700/50 px-3 flex items-center ${
                  hoveredTask === task.id ? 'bg-slate-700/30' : ''
                }`}
                style={{ height: rowHeight }}
                onMouseEnter={() => setHoveredTask(task.id)}
                onMouseLeave={() => setHoveredTask(null)}
              >
                <span className="text-xs text-slate-300 truncate">{task.name}</span>
              </div>
            ))}
          </div>

          {/* Gantt area */}
          <div className="flex-1 relative">
            {/* Day columns header */}
            <div
              className="flex border-b border-slate-700 bg-slate-800/50"
              style={{ height: headerHeight }}
            >
              {Array.from({ length: totalDays }, (_, i) => (
                <div
                  key={i}
                  className="border-r border-slate-700/30 flex items-center justify-center"
                  style={{ width: dayWidth, minWidth: dayWidth }}
                >
                  <span className="text-[10px] text-slate-500">D{i + 1}</span>
                </div>
              ))}
            </div>

            {/* Task bars */}
            {normalized.map((task, idx) => (
              <div
                key={task.id}
                className={`relative border-b border-slate-700/30 ${
                  hoveredTask === task.id ? 'bg-slate-700/20' : ''
                }`}
                style={{ height: rowHeight }}
                onMouseEnter={() => setHoveredTask(task.id)}
                onMouseLeave={() => setHoveredTask(null)}
              >
                {/* Grid lines */}
                {Array.from({ length: totalDays }, (_, i) => (
                  <div
                    key={i}
                    className="absolute top-0 bottom-0 border-r border-slate-700/20"
                    style={{ left: i * dayWidth, width: dayWidth }}
                  />
                ))}

                {/* Bar */}
                <div
                  className="absolute top-1.5 rounded-md overflow-hidden shadow-sm"
                  style={{
                    left: task.startDay * dayWidth + 2,
                    width: Math.max(task.durationDays * dayWidth - 4, 8),
                    height: rowHeight - 12,
                  }}
                >
                  {/* Background */}
                  <div
                    className={`absolute inset-0 bg-gradient-to-r ${barColors[idx % barColors.length]} opacity-80`}
                  />
                  {/* Progress overlay */}
                  {task.progress > 0 && (
                    <div
                      className="absolute top-0 left-0 bottom-0 bg-white/15"
                      style={{ width: `${task.progress}%` }}
                    />
                  )}
                  {/* Label on bar */}
                  {task.durationDays * dayWidth > 60 && (
                    <div className="absolute inset-0 flex items-center px-2">
                      <span className="text-[10px] text-white font-medium truncate">
                        {task.name}
                      </span>
                    </div>
                  )}
                </div>

                {/* Tooltip */}
                {hoveredTask === task.id && (
                  <div
                    className="absolute z-20 bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 shadow-xl pointer-events-none"
                    style={{
                      left: task.startDay * dayWidth + task.durationDays * dayWidth / 2,
                      top: rowHeight,
                      transform: 'translateX(-50%)',
                    }}
                  >
                    <p className="text-xs text-white font-medium">{task.name}</p>
                    <p className="text-[10px] text-slate-400">
                      Day {task.startDay + 1} - Day {task.startDay + task.durationDays} ({task.durationDays}d)
                    </p>
                    {task.dependencies.length > 0 && (
                      <p className="text-[10px] text-slate-500">
                        Depends: {task.dependencies.join(', ')}
                      </p>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
