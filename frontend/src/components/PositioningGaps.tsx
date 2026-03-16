interface Props {
  gaps: string[];
}

export function PositioningGaps({ gaps }: Props) {
  if (gaps.length === 0) return null;

  return (
    <div className="positioning-gaps panel">
      <h2>Positioning White Space</h2>
      <p className="gaps-subtitle">
        Opportunities no one in this market is currently owning:
      </p>
      <ol className="gaps-list">
        {gaps.map((gap, i) => (
          <li key={i} className="gap-item">
            {gap}
          </li>
        ))}
      </ol>
    </div>
  );
}
