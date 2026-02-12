import { useState, useMemo, type ReactNode } from 'react';
import { ChevronDown, ChevronRight, List, FileText } from 'lucide-react';
import MermaidRenderer from './MermaidRenderer';

interface SDSPreviewProps {
  content: string;
  title?: string;
}

interface TOCEntry {
  id: string;
  level: number;
  text: string;
}

function parseHeadings(markdown: string): TOCEntry[] {
  const entries: TOCEntry[] = [];
  const lines = markdown.split('\n');
  for (const line of lines) {
    const match = line.match(/^(#{2,4})\s+(.+)/);
    if (match) {
      const level = match[1].length;
      const text = match[2].replace(/[*_`]/g, '').trim();
      const id = text
        .toLowerCase()
        .replace(/[^a-z0-9\s-]/g, '')
        .replace(/\s+/g, '-');
      entries.push({ id, level, text });
    }
  }
  return entries;
}

function renderMarkdownSection(text: string): ReactNode {
  // Simple markdown rendering: bold, italic, inline code, lists, links
  const lines = text.split('\n');
  const elements: ReactNode[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    // Skip heading lines (handled by sections)
    if (/^#{2,4}\s+/.test(line)) {
      i++;
      continue;
    }

    // Bullet list
    if (/^\s*[-*]\s/.test(line)) {
      const listItems: string[] = [];
      while (i < lines.length && /^\s*[-*]\s/.test(lines[i])) {
        listItems.push(lines[i].replace(/^\s*[-*]\s/, ''));
        i++;
      }
      elements.push(
        <ul key={`ul-${i}`} className="list-disc list-inside space-y-1 my-2 text-slate-300 text-sm">
          {listItems.map((item, j) => (
            <li key={j} dangerouslySetInnerHTML={{ __html: inlineFormat(item) }} />
          ))}
        </ul>
      );
      continue;
    }

    // Numbered list
    if (/^\s*\d+\.\s/.test(line)) {
      const listItems: string[] = [];
      while (i < lines.length && /^\s*\d+\.\s/.test(lines[i])) {
        listItems.push(lines[i].replace(/^\s*\d+\.\s/, ''));
        i++;
      }
      elements.push(
        <ol key={`ol-${i}`} className="list-decimal list-inside space-y-1 my-2 text-slate-300 text-sm">
          {listItems.map((item, j) => (
            <li key={j} dangerouslySetInnerHTML={{ __html: inlineFormat(item) }} />
          ))}
        </ol>
      );
      continue;
    }

    // Table detection
    if (line.includes('|') && i + 1 < lines.length && /^\s*\|[\s:|-]+\|\s*$/.test(lines[i + 1])) {
      const tableLines: string[] = [];
      while (i < lines.length && lines[i].includes('|')) {
        tableLines.push(lines[i]);
        i++;
      }
      elements.push(renderTable(tableLines, i));
      continue;
    }

    // Empty line
    if (line.trim() === '') {
      i++;
      continue;
    }

    // Regular paragraph
    elements.push(
      <p
        key={`p-${i}`}
        className="text-slate-300 text-sm my-1.5 leading-relaxed"
        dangerouslySetInnerHTML={{ __html: inlineFormat(line) }}
      />
    );
    i++;
  }

  return <>{elements}</>;
}

function inlineFormat(text: string): string {
  return text
    .replace(/`([^`]+)`/g, '<code class="px-1.5 py-0.5 bg-slate-700 text-cyan-300 rounded text-xs font-mono">$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong class="text-white font-semibold">$1</strong>')
    .replace(/\*([^*]+)\*/g, '<em class="text-slate-200">$1</em>')
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" class="text-cyan-400 underline hover:text-cyan-300" target="_blank" rel="noopener noreferrer">$1</a>');
}

function renderTable(lines: string[], key: number): ReactNode {
  const parseRow = (line: string) =>
    line
      .split('|')
      .map((c) => c.trim())
      .filter(Boolean);

  const headers = parseRow(lines[0]);
  const rows = lines.slice(2).map(parseRow);

  return (
    <div key={`table-${key}`} className="overflow-x-auto my-3">
      <table className="w-full text-sm border border-slate-700 rounded-lg overflow-hidden">
        <thead className="bg-slate-800/80">
          <tr>
            {headers.map((h, i) => (
              <th
                key={i}
                className="px-3 py-2 text-left text-slate-300 font-medium border-b border-slate-700"
                dangerouslySetInnerHTML={{ __html: inlineFormat(h) }}
              />
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-700/50">
          {rows.map((row, ri) => (
            <tr key={ri} className="hover:bg-slate-800/30">
              {row.map((cell, ci) => (
                <td
                  key={ci}
                  className="px-3 py-2 text-slate-400"
                  dangerouslySetInnerHTML={{ __html: inlineFormat(cell) }}
                />
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

interface Section {
  id: string;
  level: number;
  title: string;
  content: string;
}

function parseSections(markdown: string): Section[] {
  const sections: Section[] = [];
  const lines = markdown.split('\n');
  let current: Section | null = null;
  const contentLines: string[] = [];

  const flush = () => {
    if (current) {
      current.content = contentLines.join('\n').trim();
      sections.push(current);
      contentLines.length = 0;
    }
  };

  for (const line of lines) {
    const match = line.match(/^(#{2,4})\s+(.+)/);
    if (match) {
      flush();
      const text = match[2].replace(/[*_`]/g, '').trim();
      current = {
        id: text
          .toLowerCase()
          .replace(/[^a-z0-9\s-]/g, '')
          .replace(/\s+/g, '-'),
        level: match[1].length,
        title: text,
        content: '',
      };
    } else {
      contentLines.push(line);
    }
  }
  flush();

  return sections;
}

export default function SDSPreview({ content, title }: SDSPreviewProps) {
  const [collapsedSections, setCollapsedSections] = useState<Set<string>>(new Set());
  const [showTOC, setShowTOC] = useState(true);

  const toc = useMemo(() => parseHeadings(content), [content]);
  const sections = useMemo(() => parseSections(content), [content]);

  const toggleSection = (id: string) => {
    setCollapsedSections((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const scrollToSection = (id: string) => {
    const el = document.getElementById(`sds-section-${id}`);
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  // Pre-section content (before first heading)
  const preContent = useMemo(() => {
    const firstHeading = content.search(/^#{2,4}\s+/m);
    if (firstHeading > 0) return content.slice(0, firstHeading).trim();
    return '';
  }, [content]);

  return (
    <div className="flex gap-4 max-h-[80vh]">
      {/* Table of Contents sidebar */}
      {showTOC && toc.length > 0 && (
        <nav className="w-64 flex-shrink-0 bg-slate-900/60 border border-slate-700 rounded-xl p-4 overflow-y-auto">
          <div className="flex items-center gap-2 mb-3 pb-2 border-b border-slate-700">
            <List className="w-4 h-4 text-cyan-400" />
            <span className="text-sm font-medium text-white">Table of Contents</span>
          </div>
          <ul className="space-y-1">
            {toc.map((entry) => (
              <li key={entry.id}>
                <button
                  onClick={() => scrollToSection(entry.id)}
                  className="w-full text-left text-sm text-slate-400 hover:text-cyan-400 transition-colors py-1 truncate"
                  style={{ paddingLeft: `${(entry.level - 2) * 12}px` }}
                >
                  {entry.text}
                </button>
              </li>
            ))}
          </ul>
        </nav>
      )}

      {/* Main content */}
      <div className="flex-1 overflow-y-auto bg-slate-900/40 border border-slate-700 rounded-xl">
        {/* Header bar */}
        <div className="sticky top-0 z-10 flex items-center justify-between px-5 py-3 bg-slate-800/90 backdrop-blur-sm border-b border-slate-700">
          <div className="flex items-center gap-2">
            <FileText className="w-4 h-4 text-purple-400" />
            <span className="text-sm font-medium text-white">
              {title || 'SDS Document'}
            </span>
          </div>
          {toc.length > 0 && (
            <button
              onClick={() => setShowTOC(!showTOC)}
              className="text-xs text-slate-400 hover:text-white transition-colors"
            >
              {showTOC ? 'Hide' : 'Show'} TOC
            </button>
          )}
        </div>

        <div className="p-5">
          {/* Pre-heading content */}
          {preContent && (
            <div className="mb-4">
              <MermaidRenderer content={preContent} />
            </div>
          )}

          {/* Sections */}
          {sections.map((section) => {
            const isCollapsed = collapsedSections.has(section.id);
            const HeadingTag = section.level === 2 ? 'h2' : section.level === 3 ? 'h3' : 'h4';
            const headingSizes: Record<number, string> = {
              2: 'text-xl font-bold text-white',
              3: 'text-lg font-semibold text-slate-100',
              4: 'text-base font-medium text-slate-200',
            };

            return (
              <div
                key={section.id}
                id={`sds-section-${section.id}`}
                className="mb-4"
              >
                <button
                  onClick={() => toggleSection(section.id)}
                  className="flex items-center gap-2 w-full text-left group py-2"
                >
                  {isCollapsed ? (
                    <ChevronRight className="w-4 h-4 text-slate-500 group-hover:text-cyan-400 flex-shrink-0" />
                  ) : (
                    <ChevronDown className="w-4 h-4 text-slate-500 group-hover:text-cyan-400 flex-shrink-0" />
                  )}
                  <HeadingTag className={headingSizes[section.level]}>
                    {section.title}
                  </HeadingTag>
                </button>

                {!isCollapsed && section.content && (
                  <div className="pl-6 border-l border-slate-700/50">
                    {section.content.includes('```mermaid') ? (
                      <MermaidRenderer content={section.content} />
                    ) : (
                      renderMarkdownSection(section.content)
                    )}
                  </div>
                )}
              </div>
            );
          })}

          {sections.length === 0 && (
            <MermaidRenderer content={content} />
          )}
        </div>
      </div>
    </div>
  );
}
