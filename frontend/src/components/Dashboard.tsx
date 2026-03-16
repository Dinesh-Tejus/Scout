import type { ResearchState } from "../hooks/useWebSocket";
import { ResearchFeed } from "./ResearchFeed";
import { MarketPatterns } from "./MarketPatterns";
import { PositioningGaps } from "./PositioningGaps";

interface Props {
  research: ResearchState;
}

export function Dashboard({ research }: Props) {
  const hasResults =
    Object.keys(research.competitors).length > 0 ||
    research.patterns !== null ||
    research.positioning_gaps.length > 0;

  if (!hasResults) return null;

  return (
    <div className="dashboard">
      <ResearchFeed
        competitors={research.competitors}
        activeTool={research.active_tool}
      />

      {research.patterns && (
        <div className="synthesis-panels">
          <MarketPatterns patterns={research.patterns} />
          <PositioningGaps gaps={research.positioning_gaps} />
        </div>
      )}

      {research.is_complete && (
        <div className="complete-banner">
          ✓ Research complete
        </div>
      )}

      {research.error && (
        <div className="error-banner">
          ⚠ {research.error}
        </div>
      )}
    </div>
  );
}
