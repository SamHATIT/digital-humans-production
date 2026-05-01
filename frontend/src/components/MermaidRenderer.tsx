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
    primaryColor: '#1C1C1F',
    primaryTextColor: '#E5E1D8',
    primaryBorderColor: '#C8A97E',
    lineColor: '#B5B0A4',
    secondaryColor: '#141416',
    tertiaryColor: '#0A0A0B',
    fontFamily: '"Cormorant Garamond", Georgia, serif',
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
      <div className="bg-error/10 border border-error/30 p-4 my-3">
        <p className="text-error text-sm font-mono mb-1">Diagram render error</p>
        <pre className="text-xs text-error/80 whitespace-pre-wrap">{error}</pre>
        <details className="mt-2">
          <summary className="text-xs text-bone-4 cursor-pointer">Show source</summary>
          <pre className="text-xs text-bone-3 mt-1 whitespace-pre-wrap">{code}</pre>
        </details>
      </div>
    );
  }

  if (!svg) {
    return (
      <div className="flex items-center justify-center py-6">
        <div className="w-5 h-5 border-2 border-brass border-t-transparent rounded-full animate-spin" />
        <span className="text-bone-3 ml-2 text-sm font-mono text-[11px] tracking-eyebrow uppercase">
          Rendering diagram…
        </span>
      </div>
    );
  }

  return (
    <div className="my-3 bg-ink border border-bone/10 overflow-hidden">
      {/* Toolbar */}
      <div className="flex items-center justify-end gap-1 px-3 py-2 border-b border-bone/10 bg-ink-2">
        <button
          onClick={handleZoomOut}
          className="p-1.5 text-bone-4 hover:text-bone hover:bg-ink-3 transition-colors"
          title="Zoom out"
        >
          <ZoomOut className="w-4 h-4" />
        </button>
        <span className="text-[11px] font-mono text-bone-4 min-w-[3rem] text-center">
          {Math.round(zoom * 100)}%
        </span>
        <button
          onClick={handleZoomIn}
          className="p-1.5 text-bone-4 hover:text-bone hover:bg-ink-3 transition-colors"
          title="Zoom in"
        >
          <ZoomIn className="w-4 h-4" />
        </button>
        <button
          onClick={handleReset}
          className="p-1.5 text-bone-4 hover:text-bone hover:bg-ink-3 transition-colors"
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
            className="text-sm text-bone-2 whitespace-pre-wrap break-words font-mono"
          >
            {block.content}
          </pre>
        )
      )}
    </div>
  );
}

export { extractMermaidBlocks };
