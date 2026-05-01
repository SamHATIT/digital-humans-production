interface StudioPlaceholderCoverProps {
  monogram?: string;
  className?: string;
}

/**
 * Placeholder Studio cover : cadre brass + monogramme Cormorant.
 * Utilisé pour les projets sans cover image dédiée.
 */
export default function StudioPlaceholderCover({
  monogram = 'DH',
  className = '',
}: StudioPlaceholderCoverProps) {
  return (
    <svg
      viewBox="0 0 400 280"
      role="img"
      aria-label={`Studio cover ${monogram}`}
      className={className}
      preserveAspectRatio="xMidYMid slice"
    >
      <rect width="400" height="280" fill="var(--ink-2)" />
      <rect
        x="14"
        y="14"
        width="372"
        height="252"
        fill="none"
        stroke="var(--brass)"
        strokeOpacity="0.45"
        strokeWidth="1"
      />
      <line
        x1="14"
        y1="240"
        x2="386"
        y2="240"
        stroke="var(--brass)"
        strokeOpacity="0.25"
      />
      <text
        x="200"
        y="155"
        textAnchor="middle"
        fontFamily="Cormorant Garamond, Georgia, serif"
        fontStyle="italic"
        fontSize="68"
        fill="var(--bone-2)"
      >
        {monogram}
      </text>
      <text
        x="200"
        y="262"
        textAnchor="middle"
        fontFamily="JetBrains Mono, Menlo, monospace"
        fontSize="9"
        letterSpacing="3"
        fill="var(--bone-4)"
      >
        AUTONOMOUS · STUDIO
      </text>
    </svg>
  );
}
