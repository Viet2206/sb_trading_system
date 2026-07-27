import { useEffect, useState } from "react";
import {
  BookOpen,
  Images,
  LoaderCircle,
  Search,
} from "lucide-react";
import {
  buildChartImageIndex,
  chartImageUrl,
  ChartImageIndexStatus,
  ChartImageMatchResponse,
  fetchChartImageIndexStatus,
  researchDocumentUrl,
  searchChartImages,
} from "./api";

type HistoricalMatchesProps = {
  symbol: string;
  timeframe: string;
  refreshKey: number;
};

export function HistoricalMatches({
  symbol,
  timeframe,
  refreshKey,
}: HistoricalMatchesProps) {
  const [status, setStatus] = useState<ChartImageIndexStatus | null>(null);
  const [data, setData] = useState<ChartImageMatchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void loadStatus();
  }, []);

  useEffect(() => {
    setData(null);
    setError(null);
  }, [symbol, timeframe, refreshKey]);

  async function loadStatus() {
    try {
      setStatus(await fetchChartImageIndexStatus());
    } catch (requestError) {
      setError(cleanApiError(requestError));
    }
  }

  async function findMatches() {
    setLoading(true);
    setError(null);
    try {
      let currentStatus = status;
      if (!currentStatus?.ready) {
        currentStatus = await buildChartImageIndex(false);
        setStatus(currentStatus);
      }
      const imageData = captureCurrentChart();
      setData(await searchChartImages(imageData, 5));
    } catch (requestError) {
      setData(null);
      setError(cleanApiError(requestError));
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="historical-matches" aria-labelledby="historical-matches-title">
      <header className="historical-matches-header">
        <div>
          <h3 id="historical-matches-title">Historical Image Matches</h3>
          <p>
            {status?.ready
              ? `${status.images.toLocaleString()} example charts · local visual comparison · no LLM`
              : "The chart-image library will be prepared on first search"}
          </p>
        </div>
        <button
          type="button"
          className="historical-refresh"
          onClick={() => void findMatches()}
          disabled={loading}
          title="Find the five example charts most visually similar to the current chart"
        >
          {loading
            ? <LoaderCircle className="spin" size={16} />
            : <Search size={16} />}
          <span>{loading ? "Comparing" : "Search"}</span>
        </button>
      </header>

      {error ? <div className="historical-match-error">{error}</div> : null}

      {data ? (
        <div className="historical-match-grid">
          {data.matches.map((match) => (
            <article className="historical-match-card" key={match.example_id}>
              <button
                type="button"
                className="historical-match-preview"
                onClick={() => openSource(match.document_id, match.page)}
                title={`Open ${match.document_title}, page ${match.page}`}
              >
                <img
                  src={chartImageUrl(match.example_id)}
                  alt={`${match.document_title}, page ${match.page}`}
                  loading="lazy"
                />
                <span className="match-score">
                  <strong>{match.similarity_percent}%</strong>
                  <small>visual</small>
                </span>
              </button>

              <div className="historical-match-copy">
                <div className="historical-match-title">
                  <span>#{match.rank}</span>
                  <strong title={match.document_title}>{match.document_title}</strong>
                  <small>p. {match.page}</small>
                </div>

                <div className="historical-match-tags">
                  {match.setup_types.length
                    ? match.setup_types.slice(0, 3).map((item) => (
                        <span key={item}>{item}</span>
                      ))
                    : <span>Chart example</span>}
                </div>

                <div className="historical-match-actions">
                  <span className="visual-method">Cosine image similarity</span>
                  <button
                    type="button"
                    className="open-source-button"
                    onClick={() => openSource(match.document_id, match.page)}
                  >
                    <BookOpen size={14} />
                    <span>Source</span>
                  </button>
                </div>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <div className="historical-match-empty">
          <Images size={20} />
          <span>
            Search compares the visible {symbol} {timeframe} chart with every indexed example image.
          </span>
        </div>
      )}
    </section>
  );
}

function captureCurrentChart(): string {
  const container = document.querySelector<HTMLElement>(".chart-container");
  if (!container) {
    throw new Error("The current chart is not ready.");
  }
  const canvases = Array.from(container.querySelectorAll("canvas")).filter(
    (canvas) => {
      const style = window.getComputedStyle(canvas);
      return style.display !== "none" && style.visibility !== "hidden";
    },
  );
  if (!canvases.length) {
    throw new Error("The current chart has not finished rendering.");
  }

  const bounds = container.getBoundingClientRect();
  const scale = Math.min(2, Math.max(1, window.devicePixelRatio || 1));
  const output = document.createElement("canvas");
  output.width = Math.max(1, Math.round(bounds.width * scale));
  output.height = Math.max(1, Math.round(bounds.height * scale));
  const context = output.getContext("2d");
  if (!context) {
    throw new Error("The current chart could not be captured.");
  }
  context.fillStyle = "#ffffff";
  context.fillRect(0, 0, output.width, output.height);

  for (const canvas of canvases) {
    const canvasBounds = canvas.getBoundingClientRect();
    context.drawImage(
      canvas,
      (canvasBounds.left - bounds.left) * scale,
      (canvasBounds.top - bounds.top) * scale,
      canvasBounds.width * scale,
      canvasBounds.height * scale,
    );
  }
  return output.toDataURL("image/jpeg", 0.9);
}

function openSource(documentId: string, page: number) {
  window.open(
    researchDocumentUrl(documentId, page),
    "_blank",
    "noopener,noreferrer",
  );
}

function cleanApiError(error: unknown) {
  const message = error instanceof Error ? error.message : String(error);
  try {
    const payload = JSON.parse(message) as { detail?: string };
    return payload.detail ?? message;
  } catch {
    return message;
  }
}
