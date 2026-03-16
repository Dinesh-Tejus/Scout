import type { MarketPatterns as MarketPatternsType } from "../types";

interface Props {
  patterns: MarketPatternsType;
}

export function MarketPatterns({ patterns }: Props) {
  return (
    <div className="market-patterns panel">
      <h2>Market Patterns</h2>

      <div className="pattern-row">
        <h3>Dominant Color Families</h3>
        <ul>
          {patterns.dominant_color_families.map((f) => (
            <li key={f}>{f}</li>
          ))}
        </ul>
      </div>

      <div className="pattern-row">
        <h3>Common Visual Styles</h3>
        <ul>
          {patterns.common_visual_styles.map((s) => (
            <li key={s}>{s}</li>
          ))}
        </ul>
      </div>

      <div className="pattern-row">
        <h3>Market Mood</h3>
        <p className="mood-badge">{patterns.market_mood}</p>
      </div>

      <div className="pattern-row">
        <h3>Overrepresented Approaches</h3>
        <ul className="overrep-list">
          {patterns.overrepresented_approaches.map((a) => (
            <li key={a}>{a}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}
