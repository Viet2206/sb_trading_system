import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import {
  BookOpen,
  Check,
  CircleHelp,
  RefreshCw,
  SearchX,
  X,
} from "lucide-react";
import {
  HistoricalExampleMatch,
  HistoricalExampleMatchResponse,
  fetchHistoricalExampleMatches,
  researchDocumentUrl,
  researchPageImageUrl,
  saveHistoricalExampleFeedback,
} from "./api";

type HistoricalMatchesProps = {
  symbol: string;
  timeframe: string;
  refreshKey: number;
};

type Verdict = "relevant" | "not_relevant" | "unsure";

export function HistoricalMatches({
  symbol,
  timeframe,
  refreshKey,
}: HistoricalMatchesProps) {
  const [data, setData] = useState<HistoricalExampleMatchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [reviewing, setReviewing] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (symbol && timeframe) void loadMatches();
  }, [symbol, timeframe, refreshKey]);

  async function loadMatches() {
    setLoading(true);
    setError(null);
    try {
      setData(await fetchHistoricalExampleMatches(symbol, timeframe, 8));
    } catch (requestError) {
      setData(null);
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Historical examples are unavailable.",
      );
    } finally {
      setLoading(false);
    }
  }

  async function review(match: HistoricalExampleMatch, verdict: Verdict) {
    if (!data) return;
    const key = `${match.document_id}-${match.page}`;
    setReviewing(key);
    setError(null);
    try {
      await saveHistoricalExampleFeedback({
        fingerprint_id: data.fingerprint.id,
        document_id: match.document_id,
        page: match.page,
        verdict,
        symbol,
        timeframe,
      });
      setData((current) => current && ({
        ...current,
        matches: current.matches.map((item) =>
          item.document_id === match.document_id && item.page === match.page
            ? { ...item, review_verdict: verdict }
            : item
        ),
      }));
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Could not save example review.",
      );
    } finally {
      setReviewing(null);
    }
  }

  return (
    <section className="historical-matches" aria-labelledby="historical-matches-title">
      <header className="historical-matches-header">
        <div>
          <h3 id="historical-matches-title">Historical Matches</h3>
          <p>
            {data
              ? `${symbol} ${timeframe} · ${data.score_meaning}`
              : `${symbol} ${timeframe} · Context-ranked SB source examples`}
          </p>
        </div>
        <button
          type="button"
          className="historical-refresh"
          onClick={() => void loadMatches()}
          disabled={loading || !symbol || !timeframe}
          title="Refresh historical matches"
        >
          <RefreshCw size={16} />
          <span>{loading ? "Matching" : "Refresh"}</span>
        </button>
      </header>

      {data ? (
        <div className="fingerprint-strip">
          <FingerprintItem
            label="Signal"
            value={signalSummary(data.fingerprint)}
          />
          <FingerprintItem label="Direction" value={data.fingerprint.candidate_direction} />
          <FingerprintItem label="Week" value={data.fingerprint.weekly_state} />
          <FingerprintItem label="Location" value={joinOrWatch(data.fingerprint.price_location)} />
        </div>
      ) : null}

      {error ? <div className="historical-match-error">{cleanApiError(error)}</div> : null}

      <div className="historical-match-grid">
        {data?.matches.map((match) => {
          const reviewKey = `${match.document_id}-${match.page}`;
          return (
            <article className="historical-match-card" key={reviewKey}>
              <button
                type="button"
                className="historical-match-preview"
                onClick={() =>
                  window.open(
                    researchDocumentUrl(match.document_id, match.page),
                    "_blank",
                    "noopener,noreferrer",
                  )
                }
                title={`Open ${match.document_title}, page ${match.page}`}
              >
                <img
                  src={researchPageImageUrl(match.document_id, match.page)}
                  alt={`${match.document_title}, page ${match.page}`}
                  loading="lazy"
                />
                <span className={`match-score ${match.match_band}`}>
                  <strong>{match.match_score}</strong>
                  <small>match</small>
                </span>
              </button>

              <div className="historical-match-copy">
                <div className="historical-match-title">
                  <span>#{match.rank}</span>
                  <strong>{match.document_title}</strong>
                  <small>p. {match.page}</small>
                </div>

                <div className="historical-match-tags">
                  {match.basis.slice(0, 3).map((item) => <span key={item}>{item}</span>)}
                </div>

                <div className="match-component-row">
                  <MatchComponent
                    label="Evidence"
                    value={match.components.research_relevance}
                  />
                  <MatchComponent
                    label="Setup"
                    value={match.components.setup_alignment}
                  />
                  <MatchComponent
                    label="Direction"
                    value={match.components.direction_alignment}
                  />
                </div>

                <div className="historical-match-actions">
                  <button
                    type="button"
                    className="open-source-button"
                    onClick={() =>
                      window.open(
                        researchDocumentUrl(match.document_id, match.page),
                        "_blank",
                        "noopener,noreferrer",
                      )
                    }
                  >
                    <BookOpen size={14} />
                    <span>Source</span>
                  </button>
                  <div className="match-review-actions" aria-label="Review this match">
                    <ReviewButton
                      active={match.review_verdict === "relevant"}
                      disabled={reviewing === reviewKey}
                      title="Mark as relevant"
                      onClick={() => void review(match, "relevant")}
                      icon={<Check size={15} />}
                    />
                    <ReviewButton
                      active={match.review_verdict === "unsure"}
                      disabled={reviewing === reviewKey}
                      title="Mark as unsure"
                      onClick={() => void review(match, "unsure")}
                      icon={<CircleHelp size={15} />}
                    />
                    <ReviewButton
                      active={match.review_verdict === "not_relevant"}
                      disabled={reviewing === reviewKey}
                      title="Mark as not relevant"
                      onClick={() => void review(match, "not_relevant")}
                      icon={<X size={15} />}
                    />
                  </div>
                </div>
              </div>
            </article>
          );
        })}
      </div>

      {!loading && data?.count === 0 ? (
        <div className="historical-match-empty">
          <SearchX size={20} />
          <span>No source examples matched the current context.</span>
        </div>
      ) : null}
      {loading && !data ? (
        <div className="historical-match-empty">
          <RefreshCw size={20} />
          <span>Ranking historical examples</span>
        </div>
      ) : null}
    </section>
  );
}

function FingerprintItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="fingerprint-item">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function MatchComponent({ label, value }: { label: string; value: number }) {
  const percentage = Math.round(value * 100);
  return (
    <div className="match-component">
      <div>
        <span>{label}</span>
        <strong>{percentage}</strong>
      </div>
      <span className="match-component-track">
        <span style={{ width: `${percentage}%` }} />
      </span>
    </div>
  );
}

function ReviewButton({
  active,
  disabled,
  title,
  onClick,
  icon,
}: {
  active: boolean;
  disabled: boolean;
  title: string;
  onClick: () => void;
  icon: ReactNode;
}) {
  return (
    <button
      type="button"
      className={active ? "match-review-button active" : "match-review-button"}
      disabled={disabled}
      title={title}
      aria-label={title}
      onClick={onClick}
    >
      {icon}
    </button>
  );
}

function joinOrWatch(values: string[]) {
  return values.length ? values.join(", ") : "Watch";
}

function signalSummary(fingerprint: HistoricalExampleMatchResponse["fingerprint"]) {
  if (fingerprint.current_signal_labels.length) {
    return fingerprint.current_signal_labels.join(", ");
  }
  if (fingerprint.previous_signal_labels.length) {
    return `Previous: ${fingerprint.previous_signal_labels.join(", ")}`;
  }
  return "Watch";
}

function cleanApiError(message: string) {
  try {
    const payload = JSON.parse(message) as { detail?: string };
    return payload.detail ?? message;
  } catch {
    return message;
  }
}
