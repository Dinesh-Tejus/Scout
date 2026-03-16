import type { CompetitorCard as CompetitorCardType } from "../types";
import { CompetitorCard } from "./CompetitorCard";

interface Props {
  competitors: Record<string, CompetitorCardType>;
  activeTool: string | null;
}

export function ResearchFeed({ competitors, activeTool }: Props) {
  const cards = Object.values(competitors);
  const isEmpty = cards.length === 0;

  return (
    <div className="research-feed">
      <h2 className="feed-title">{isEmpty ? "Brand Landscape" : "Competitors Found"}</h2>

      {activeTool && (
        <div className="feed-status">
          <span className="spinner" />
          Running <strong>{activeTool.replace(/_/g, " ")}</strong>…
        </div>
      )}

      <div className="card-grid">
        {isEmpty ? (
          <div className="feed-empty">
            <span className="feed-empty-icon">🔍🖼️</span>
            <div className="feed-empty-title">Images incoming soon</div>
            <p className="feed-empty-sub">Results appear as Scout searches</p>
          </div>
        ) : (
          cards.map((c) => <CompetitorCard key={c.id} competitor={c} />)
        )}
      </div>
    </div>
  );
}
