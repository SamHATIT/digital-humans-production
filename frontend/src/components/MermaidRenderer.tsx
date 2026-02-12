import { useEffect, useRef, useState } from 'react';
import mermaid from 'mermaid';
import { ZoomIn, ZoomOut, Maximize2 } from 'lucide-react';

interface MermaidRendererProps {
  content: string;
}

mermaid.initialize({
  startOnLoad: false,
  theme: 'dark',
  themeVariables: {
    primaryColor: '#2563eb',
    primaryTextColor: '#e2e8f0',
    primaryBorderColor: '#475569',
    lineColor: '#64748b',
    secondaryColor: '#1e293b',
    tertiaryColor: '#0f172a',
    fontFamily: 'ui-monospace, monospace',
    fontSize: '14px',
  },
  securityLevel: 'strict',
  flowchart: { useMaxWidth: true, htmlLabels: true },
  er: { useMaxWidth: true },
  sequence: { useMaxWidth: true },
});

function extractMermaidBlocks(text: string): { type: 'text' | 'mermaid'; content: string }[] {
  const blocks: { type: 'text' | 'mermaid'; content: string }[] = [];
  const regex = /```mermaid\s*\n([\s\S]*?)```/g;
  let lastIndex = 0;
  let match;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      blocks.push({ type: 'text', content: text.slice(lastIndex, match.index) });
    }
    blocks.push({ type: 'mermaid', content: match[1].trim() });
    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < text.length) {
    blocks.push({ type: 'text', content: text.slice(lastIndex) });
  }

  return blocks;
}

let mermaidCounter = 0;

function MermaidDiagram({ code }: { code: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [svg, setSvg] = useState<string>('');
  const [error, setError] = useState<string>('');
  const [zoom, setZoom] = useState(1);

  useEffect(() => {
    const render = async () => {
      try {
        const id = `mermaid-diagram-${++mermaidCounter}`;
        const { svg: renderedSvg } = await mermaid.render(id, code);
        setSvg(renderedSvg);
        setError('');
      } catch (err: any) {
        setError(err.message || 'Failed to render diagram');
        // Clean up any leftover error elements mermaid may have inserted
        const errorEl = document.getElementById(`d${mermaidCounter}`);
        if (errorEl) errorEl.remove();
      }
    };
    render();
  }, [code]);

  const handleZoomIn = () => setZoom((z) => Math.min(z + 0.25, 3));
  const handleZoomOut = () => setZoom((z) => Math.max(z - 0.25, 0.25));
  const handleReset = () => setZoom(1);

  if (error) {
    return (
      <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 my-3">
        <p className="text-red-400 text-sm font-medium mb-1">Diagram render error</p>
        <pre className="text-xs text-red-300 whitespace-pre-wrap">{error}</pre>
        <details className="mt-2">
          <summary className="text-xs text-slate-500 cursor-pointer">Show source</summary>
          <pre className="text-xs text-slate-400 mt-1 whitespace-pre-wrap">{code}</pre>
        </details>
      </div>
    );
  }

  if (!svg) {
    return (
      <div className="flex items-center justify-center py-6">
        <div className="w-5 h-5 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin" />
        <span className="text-slate-400 ml-2 text-sm">Rendering diagram...</span>
      </div>
    );
  }

  return (
    <div className="my-3 bg-slate-900/50 border border-slate-700 rounded-xl overflow-hidden">
      {/* Toolbar */}
      <div className="flex items-center justify-end gap-1 px-3 py-2 border-b border-slate-700/50 bg-slate-800/30">
        <button
          onClick={handleZoomOut}
          className="p-1.5 text-slate-400 hover:text-white hover:bg-slate-700 rounded transition-colors"
          title="Zoom out"
        >
          <ZoomOut className="w-4 h-4" />
        </button>
        <span className="text-xs text-slate-500 min-w-[3rem] text-center">
          {Math.round(zoom * 100)}%
        </span>
        <button
          onClick={handleZoomIn}
          className="p-1.5 text-slate-400 hover:text-white hover:bg-slate-700 rounded transition-colors"
          title="Zoom in"
        >
          <ZoomIn className="w-4 h-4" />
        </button>
        <button
          onClick={handleReset}
          className="p-1.5 text-slate-400 hover:text-white hover:bg-slate-700 rounded transition-colors"
          title="Reset zoom"
        >
          <Maximize2 className="w-4 h-4" />
        </button>
      </div>
      {/* Diagram */}
      <div className="overflow-auto max-h-[600px] p-4">
        <div
          ref={containerRef}
          style={{ transform: `scale(${zoom})`, transformOrigin: 'top left' }}
          className="transition-transform duration-150"
          dangerouslySetInnerHTML={{ __html: svg }}
        />
      </div>
    </div>
  );
}

export default function MermaidRenderer({ content }: MermaidRendererProps) {
  const blocks = extractMermaidBlocks(content);

  return (
    <div>
      {blocks.map((block, i) =>
        block.type === 'mermaid' ? (
          <MermaidDiagram key={i} code={block.content} />
        ) : (
          <pre
            key={i}
            className="text-sm text-slate-300 whitespace-pre-wrap break-words font-mono"
          >
            {block.content}
          </pre>
        )
      )}
    </div>
  );
}

export { extractMermaidBlocks };
