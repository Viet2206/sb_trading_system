import { useEffect, useMemo, useState } from "react";
import { Activity, LineChart, RefreshCw, Trash2 } from "lucide-react";
import { CandleChart, TrendLine } from "./CandleChart";
import { Candle, CandleSummary, fetchCandles, fetchSummary } from "./api";

const timeframeOrder = ["M1", "M5", "M15", "M30", "H1", "H4", "D1", "W1", "MN1"];

export function App() {
  const [summary, setSummary] = useState<CandleSummary[]>([]);
  const [symbol, setSymbol] = useState("");
  const [timeframe, setTimeframe] = useState("");
  const [candles, setCandles] = useState<Candle[]>([]);
  const [trendLines, setTrendLines] = useState<TrendLine[]>([]);
  const [drawMode, setDrawMode] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const symbols = useMemo(
    () => Array.from(new Set(summary.map((item) => item.broker_symbol))).sort(),
    [summary],
  );

  const timeframes = useMemo(() => {
    const available = summary
      .filter((item) => item.broker_symbol === symbol)
      .map((item) => item.timeframe);
    return available.sort((a, b) => timeframeOrder.indexOf(a) - timeframeOrder.indexOf(b));
  }, [summary, symbol]);

  const currentSummary = summary.find(
    (item) => item.broker_symbol === symbol && item.timeframe === timeframe,
  );

  useEffect(() => {
    void loadSummary();
  }, []);

  useEffect(() => {
    if (!symbol && symbols.length > 0) {
      setSymbol(symbols[0]);
    }
  }, [symbol, symbols]);

  useEffect(() => {
    if (symbol && (!timeframe || !timeframes.includes(timeframe))) {
      setTimeframe(timeframes.includes("M15") ? "M15" : timeframes[0] ?? "");
    }
  }, [symbol, timeframe, timeframes]);

  useEffect(() => {
    if (symbol && timeframe) {
      void loadCandles(symbol, timeframe);
      setTrendLines([]);
    }
  }, [symbol, timeframe]);

  async function loadSummary() {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchSummary();
      setSummary(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load API summary");
    } finally {
      setLoading(false);
    }
  }

  async function loadCandles(nextSymbol = symbol, nextTimeframe = timeframe) {
    if (!nextSymbol || !nextTimeframe) return;
    setLoading(true);
    setError(null);
    try {
      const data = await fetchCandles(nextSymbol, nextTimeframe, 1500);
      setCandles(data.candles);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load candles");
    } finally {
      setLoading(false);
    }
  }

  const latest = candles[candles.length - 1];

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand-row">
          <div className="brand-mark">
            <LineChart size={20} />
          </div>
          <div>
            <h1>SB System</h1>
            <p>Market data workbench</p>
          </div>
        </div>

        <label className="field">
          <span>Symbol</span>
          <select value={symbol} onChange={(event) => setSymbol(event.target.value)}>
            {symbols.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </label>

        <label className="field">
          <span>Timeframe</span>
          <select value={timeframe} onChange={(event) => setTimeframe(event.target.value)}>
            {timeframes.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </label>

        <div className="tool-group">
          <button
            className={drawMode ? "tool-button active" : "tool-button"}
            onClick={() => setDrawMode((value) => !value)}
            title="Draw trend line"
          >
            <LineChart size={18} />
            <span>Trendline</span>
          </button>
          <button
            className="icon-button"
            onClick={() => setTrendLines([])}
            title="Clear trend lines"
          >
            <Trash2 size={18} />
          </button>
          <button
            className="icon-button"
            onClick={() => void loadCandles()}
            title="Refresh candles"
          >
            <RefreshCw size={18} />
          </button>
        </div>

        <div className="status-block">
          <div className="status-title">
            <Activity size={16} />
            <span>{loading ? "Loading" : "Ready"}</span>
          </div>
          {currentSummary ? (
            <>
              <Metric label="Candles" value={currentSummary.candles.toLocaleString()} />
              <Metric label="First" value={formatDate(currentSummary.first_candle)} />
              <Metric label="Last" value={formatDate(currentSummary.last_candle)} />
            </>
          ) : (
            <p className="muted">No summary selected.</p>
          )}
        </div>

        {latest ? (
          <div className="status-block">
            <div className="status-title">Latest Candle</div>
            <Metric label="Time" value={formatDate(latest.candle_time)} />
            <Metric label="Open" value={formatPrice(latest.open)} />
            <Metric label="High" value={formatPrice(latest.high)} />
            <Metric label="Low" value={formatPrice(latest.low)} />
            <Metric label="Close" value={formatPrice(latest.close)} />
          </div>
        ) : null}
      </aside>

      <section className="workspace">
        <div className="topbar">
          <div>
            <h2>
              {symbol || "Symbol"} <span>{timeframe || "Timeframe"}</span>
            </h2>
            <p>
              {drawMode
                ? "Click two points on the chart to draw a trend line."
                : "Pan, zoom, inspect candles, and toggle trendline mode when needed."}
            </p>
          </div>
          <div className="trend-count">{trendLines.length} trend lines</div>
        </div>

        {error ? <div className="error-banner">{error}</div> : null}

        <CandleChart
          candles={candles}
          drawMode={drawMode}
          trendLines={trendLines}
          onTrendLinesChange={setTrendLines}
        />
      </section>
    </main>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function formatDate(value: string) {
  return value.replace("T", " ").replace("+00:00", " UTC");
}

function formatPrice(value: number) {
  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits: 5,
  }).format(value);
}
