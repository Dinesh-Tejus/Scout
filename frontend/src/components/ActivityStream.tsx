import { useState } from "react";
import type { ActivityEntry } from "../types";

const CATEGORY_ICONS: Record<ActivityEntry["category"], string> = {
  thinking: "💭",
  search: "🔍",
  result: "📡",
  vision: "👁",
  extract: "📄",
  tool: "⚙️",
  info: "✓",
  error: "✗",
};

function formatTime(ts: number): string {
  return new Date(ts).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

interface Props {
  activityLog: ActivityEntry[];
  onOpenChange?: (open: boolean) => void;
}

export function ActivityStream({ activityLog, onOpenChange }: Props) {
  const [isOpen, setIsOpen] = useState(false);
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());

  const toggle = () => {
    const next = !isOpen;
    setIsOpen(next);
    onOpenChange?.(next);
  };

  const toggleRaw = (id: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  return (
    <div className={`activity-drawer${isOpen ? " activity-drawer--open" : ""}`}>
      <div
        className="activity-drawer-header"
        onClick={toggle}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => e.key === "Enter" && toggle()}
      >
        <span className="activity-drawer-title">
          Activity Stream
          {activityLog.length > 0 && (
            <span className="activity-count-badge">{activityLog.length}</span>
          )}
        </span>
        <span className="activity-drawer-chevron">{isOpen ? "▼" : "▲"}</span>
      </div>

      {isOpen && (
        <div className="activity-drawer-body">
          {activityLog.length === 0 ? (
            <div className="activity-empty">No activity yet — start a voice session</div>
          ) : (
            activityLog.map((entry) => (
              <div
                key={entry.id}
                className={`activity-entry activity-entry--${entry.category}`}
              >
                <span className="activity-icon">{CATEGORY_ICONS[entry.category]}</span>
                <span className="activity-time">{formatTime(entry.timestamp)}</span>
                <span className="activity-label">{entry.label}</span>
                {entry.detail && (
                  <span className="activity-detail">{entry.detail}</span>
                )}
                {entry.rawData !== undefined && (
                  <button
                    className="activity-raw-btn"
                    onClick={(e) => {
                      e.stopPropagation();
                      toggleRaw(entry.id);
                    }}
                    title="Show raw data"
                  >
                    {"{ }"}
                  </button>
                )}
                {expandedIds.has(entry.id) && entry.rawData !== undefined && (
                  <div className="activity-entry-raw">
                    <pre>{JSON.stringify(entry.rawData, null, 2)}</pre>
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
