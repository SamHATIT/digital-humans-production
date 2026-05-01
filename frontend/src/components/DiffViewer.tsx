import { useMemo } from 'react';
import { GitBranch } from 'lucide-react';

interface DiffViewerProps {
  oldText: string;
  newText: string;
  oldLabel?: string;
  newLabel?: string;
}

interface DiffLine {
  type: 'unchanged' | 'added' | 'removed';
  content: string;
  oldLineNo: number | null;
  newLineNo: number | null;
}

function computeDiff(oldLines: string[], newLines: string[]): DiffLine[] {
  // Simple LCS-based diff
  const m = oldLines.length;
  const n = newLines.length;

  // Build LCS table
  const dp: number[][] = Array.from({ length: m + 1 }, () => Array(n + 1).fill(0));
  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      if (oldLines[i - 1] === newLines[j - 1]) {
        dp[i][j] = dp[i - 1][j - 1] + 1;
      } else {
        dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1]);
      }
    }
  }

  // Backtrack to build diff
  const result: DiffLine[] = [];
  let i = m;
  let j = n;

  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && oldLines[i - 1] === newLines[j - 1]) {
      result.unshift({
        type: 'unchanged',
        content: oldLines[i - 1],
        oldLineNo: i,
        newLineNo: j,
      });
      i--;
      j--;
    } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
      result.unshift({
        type: 'added',
        content: newLines[j - 1],
        oldLineNo: null,
        newLineNo: j,
      });
      j--;
    } else if (i > 0) {
      result.unshift({
        type: 'removed',
        content: oldLines[i - 1],
        oldLineNo: i,
        newLineNo: null,
      });
      i--;
    }
  }

  return result;
}

export default function DiffViewer({
  oldText,
  newText,
  oldLabel = 'Original',
  newLabel = 'Modified',
}: DiffViewerProps) {
  const diffLines = useMemo(
    () => computeDiff(oldText.split('\n'), newText.split('\n')),
    [oldText, newText]
  );

  const stats = useMemo(() => {
    let added = 0;
    let removed = 0;
    for (const line of diffLines) {
      if (line.type === 'added') added++;
      if (line.type === 'removed') removed++;
    }
    return { added, removed };
  }, [diffLines]);

  const lineStyles: Record<string, string> = {
    unchanged: '',
    added: 'bg-sage/10',
    removed: 'bg-error/10',
  };

  const lineGutterStyles: Record<string, string> = {
    unchanged: 'text-bone-4',
    added: 'text-sage/60 bg-sage/5',
    removed: 'text-error/60 bg-error/5',
  };

  const linePrefixes: Record<string, string> = {
    unchanged: ' ',
    added: '+',
    removed: '-',
  };

  const linePrefixColors: Record<string, string> = {
    unchanged: 'text-bone-4',
    added: 'text-sage',
    removed: 'text-error',
  };

  return (
    <div className="bg-ink border border-bone/10 rounded-xl overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-bone/10 bg-ink-2">
        <div className="flex items-center gap-2">
          <GitBranch className="w-4 h-4 text-plum" />
          <span className="text-sm font-medium text-bone">Changes</span>
        </div>
        <div className="flex items-center gap-3 text-xs">
          <span className="text-bone-4">{oldLabel}</span>
          <span className="text-bone-4">&rarr;</span>
          <span className="text-bone-4">{newLabel}</span>
          <span className="text-sage">+{stats.added}</span>
          <span className="text-error">-{stats.removed}</span>
        </div>
      </div>

      {/* Diff content */}
      <div className="overflow-x-auto max-h-[500px] overflow-y-auto">
        <table className="w-full text-xs font-mono">
          <tbody>
            {diffLines.map((line, idx) => (
              <tr key={idx} className={lineStyles[line.type]}>
                {/* Old line number */}
                <td
                  className={`px-2 py-0.5 text-right select-none w-10 border-r border-bone/10 ${lineGutterStyles[line.type]}`}
                >
                  {line.oldLineNo ?? ''}
                </td>
                {/* New line number */}
                <td
                  className={`px-2 py-0.5 text-right select-none w-10 border-r border-bone/10 ${lineGutterStyles[line.type]}`}
                >
                  {line.newLineNo ?? ''}
                </td>
                {/* Prefix */}
                <td
                  className={`px-1 py-0.5 select-none w-4 ${linePrefixColors[line.type]}`}
                >
                  {linePrefixes[line.type]}
                </td>
                {/* Content */}
                <td className="px-2 py-0.5 text-bone-3 whitespace-pre">
                  {line.content}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
