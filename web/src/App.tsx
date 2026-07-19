import { useEffect, useMemo, useState } from "react";
import { LineChart, RefreshCw } from "lucide-react";
import { CandleChart } from "./CandleChart";
import {
  Candle,
  CandleSummary,
  OverlayResponse,
  fetchCandles,
  fetchOverlays,
  fetchSummary,
} from "./api";

const timeframeOrder = ["M1", "M5", "M15", "M30", "H1", "H4", "D1", "W1", "MN1"];

export function App() {
  const [summary, setSummary] = useState<CandleSummary[]>([]);
  const [symbol, setSymbol] = useState("");
  const [timeframe, setTimeframe] = useState("");
  const [candles, setCandles] = useState<Candle[]>([]);
  const [overlays, setOverlays] = useState<OverlayResponse | null>(null);
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
      setSymbol(preferredDefaultSymbol(symbols));
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
      const [candleData, overlayData] = await Promise.all([
        fetchCandles(nextSymbol, nextTimeframe, 1500),
        fetchOverlays(nextSymbol, nextTimeframe, 1500),
      ]);
      setCandles(candleData.candles);
      setOverlays(overlayData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load candles");
    } finally {
      setLoading(false);
    }
  }

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
            className="tool-button"
            onClick={() => void loadCandles()}
            title="Refresh candles"
          >
            <RefreshCw size={18} />
            <span>{loading ? "Loading" : "Refresh"}</span>
          </button>
        </div>
      </aside>

      <section className="workspace">
        <div className="topbar">
          <div>
            <h2>
              {symbol || "Symbol"} <span>{timeframe || "Timeframe"}</span>
            </h2>
            <p>{currentSummary ? `${currentSummary.candles.toLocaleString()} candles` : "Loading chart"}</p>
          </div>
        </div>

        {error ? <div className="error-banner">{error}</div> : null}

        <CandleChart
          candles={candles}
          overlays={overlays}
        />
      </section>
    </main>
  );
}

function preferredDefaultSymbol(symbols: string[]) {
  return symbols.find((item) => item === "XAUUSD+")
    ?? symbols.find((item) => item.startsWith("XAUUSD"))
    ?? symbols[0];
}
