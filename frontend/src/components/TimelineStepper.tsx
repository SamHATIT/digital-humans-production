import { CheckCircle, AlertCircle, Pause, Loader2 } from 'lucide-react';

export interface PhaseInfo {
  number: number;
  label: string;
  agents: string;
  status: 'completed' | 'active' | 'waiting_hitl' | 'pending' | 'failed';
  hasDeliverables: boolean;
}

interface TimelineStepperProps {
  phases: PhaseInfo[];
  onPhaseClick: (phaseNumber: number) => void;
}

const statusConfig = {
  completed: {
    circle: 'bg-green-500 border-green-400',
    line: 'bg-green-500',
    text: 'text-green-400',
    subtext: 'text-green-400/70',
    icon: CheckCircle,
    pulse: false,
  },
  active: {
    circle: 'bg-blue-500 border-blue-400 animate-pulse',
    line: 'bg-slate-600',
    text: 'text-white',
    subtext: 'text-blue-300',
    icon: Loader2,
    pulse: true,
  },
  waiting_hitl: {
    circle: 'bg-amber-500 border-amber-400',
    line: 'bg-slate-600',
    text: 'text-amber-400',
    subtext: 'text-amber-400/70',
    icon: Pause,
    pulse: false,
  },
  pending: {
    circle: 'bg-slate-700 border-slate-500',
    line: 'bg-slate-600',
    text: 'text-slate-500',
    subtext: 'text-slate-600',
    icon: null,
    pulse: false,
  },
  failed: {
    circle: 'bg-red-500 border-red-400',
    line: 'bg-slate-600',
    text: 'text-red-400',
    subtext: 'text-red-400/70',
    icon: AlertCircle,
    pulse: false,
  },
};

export default function TimelineStepper({ phases, onPhaseClick }: TimelineStepperProps) {
  return (
    <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-2xl p-6 mb-8">
      {/* Desktop: horizontal layout */}
      <div className="hidden sm:flex items-start justify-between relative">
        {phases.map((phase, idx) => {
          const config = statusConfig[phase.status];
          const Icon = config.icon;
          const isLast = idx === phases.length - 1;
          const isClickable = phase.hasDeliverables || phase.status === 'waiting_hitl';

          return (
            <div key={phase.number} className="flex-1 flex flex-col items-center relative">
              {/* Connector line (between circles) */}
              {!isLast && (
                <div className="absolute top-5 left-[calc(50%+20px)] right-[calc(-50%+20px)] h-0.5">
                  <div
                    className={`h-full ${
                      phase.status === 'completed' ? 'bg-green-500' : 'bg-slate-600'
                    }`}
                  />
                </div>
              )}

              {/* Circle */}
              <button
                onClick={() => isClickable && onPhaseClick(phase.number)}
                disabled={!isClickable}
                className={`relative z-10 w-10 h-10 rounded-full border-2 flex items-center justify-center transition-all ${
                  config.circle
                } ${isClickable ? 'cursor-pointer hover:scale-110 hover:shadow-lg' : 'cursor-default'}`}
                title={isClickable ? `View Phase ${phase.number}` : undefined}
              >
                {Icon ? (
                  <Icon className={`w-5 h-5 text-white ${config.pulse ? 'animate-spin' : ''}`} />
                ) : (
                  <span className="text-sm font-bold text-slate-400">{phase.number}</span>
                )}
              </button>

              {/* Label */}
              <p className={`mt-2 text-sm font-medium text-center ${config.text}`}>
                {phase.label}
              </p>
              <p className={`text-xs text-center ${config.subtext}`}>
                {phase.agents}
              </p>
            </div>
          );
        })}
      </div>

      {/* Mobile: vertical layout */}
      <div className="sm:hidden space-y-3">
        {phases.map((phase, idx) => {
          const config = statusConfig[phase.status];
          const Icon = config.icon;
          const isLast = idx === phases.length - 1;
          const isClickable = phase.hasDeliverables || phase.status === 'waiting_hitl';

          return (
            <div key={phase.number} className="flex items-start gap-3">
              {/* Circle + vertical line */}
              <div className="flex flex-col items-center">
                <button
                  onClick={() => isClickable && onPhaseClick(phase.number)}
                  disabled={!isClickable}
                  className={`w-8 h-8 rounded-full border-2 flex items-center justify-center flex-shrink-0 transition-all ${
                    config.circle
                  } ${isClickable ? 'cursor-pointer hover:scale-110' : 'cursor-default'}`}
                >
                  {Icon ? (
                    <Icon className={`w-4 h-4 text-white ${config.pulse ? 'animate-spin' : ''}`} />
                  ) : (
                    <span className="text-xs font-bold text-slate-400">{phase.number}</span>
                  )}
                </button>
                {!isLast && (
                  <div
                    className={`w-0.5 h-8 mt-1 ${
                      phase.status === 'completed' ? 'bg-green-500' : 'bg-slate-600'
                    }`}
                  />
                )}
              </div>

              {/* Text */}
              <div className="pt-1">
                <p className={`text-sm font-medium ${config.text}`}>{phase.label}</p>
                <p className={`text-xs ${config.subtext}`}>{phase.agents}</p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
