import type { CompetitorCard as CompetitorCardType } from "../types";

interface Props {
  competitor: CompetitorCardType;
  researchAborted?: boolean;
}

export function CompetitorCard({ competitor, researchAborted }: Props) {
  const { name, website, image_url, images, analysis } = competitor;
  const primaryImage = images?.[0];

  return (
    <div className="competitor-card">
      <div className="card-image-wrapper">
        {primaryImage ? (
          <a
            href={primaryImage.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="card-image-link"
          >
            <img
              src={primaryImage.image_url}
              alt={name}
              className="card-image"
              loading="lazy"
              onError={(e) => {
                (e.target as HTMLImageElement).style.display = "none";
              }}
            />
          </a>
        ) : image_url ? (
          <img
            src={image_url}
            alt={`${name} brand`}
            className="card-image"
            loading="lazy"
            onError={(e) => {
              (e.target as HTMLImageElement).style.display = "none";
            }}
          />
        ) : (
          <div className="card-image-placeholder">No image</div>
        )}
      </div>

      <div className="card-body">
        <div className="card-header">
          <h3 className="card-name">{name}</h3>
          <a
            href={website}
            target="_blank"
            rel="noopener noreferrer"
            className="card-website"
          >
            ↗
          </a>
        </div>

        {analysis ? (
          <div className="card-analysis">
            <div className="color-swatches">
              {analysis.dominant_colors.map((hex) => (
                <span
                  key={hex}
                  className="color-swatch"
                  style={{ backgroundColor: hex }}
                  title={hex}
                />
              ))}
            </div>

            <div className="analysis-tags">
              <span className="tag">{analysis.typography_style}</span>
              <span className="tag">{analysis.photography_approach}</span>
              <span className="tag mood">{analysis.mood}</span>
            </div>

            <p className="demographic">{analysis.target_demographic}</p>
            <p className="positioning">{analysis.positioning_summary}</p>
          </div>
        ) : researchAborted ? (
          <div className="card-analyzing">
            <span className="analysis-aborted">—</span>
          </div>
        ) : (
          <div className="card-analyzing">
            <span className="spinner" /> Analyzing…
          </div>
        )}
      </div>
    </div>
  );
}
