import { useEffect, useMemo, useState } from "react";
import {
  BrainCircuit,
  ClipboardList,
  Layers3,
  LineChart,
  PanelLeftClose,
  PanelLeftOpen,
  RefreshCw,
  Settings,
} from "lucide-react";
import { CandleChart } from "./CandleChart";
import { DailyChecklistPage } from "./DailyChecklistPage";
import { ResearchPage } from "./ResearchPage";
import { SettingsPage } from "./SettingsPage";
import {
  Candle,
  CandleSummary,
  OverlayResponse,
  fetchCandles,
  fetchOverlays,
  fetchRuntimeSettings,
  fetchSummary,
  updateRuntimeSettings,
} from "./api";
import { ChartSettings, loadChartSettings, saveChartSettings } from "./chartSettings";
import {
  loadActiveOverlayTemplates,
  OverlayTemplateId,
  overlayTemplates,
  saveActiveOverlayTemplates,
} from "./overlayTemplates";

const timeframeOrder = ["M1", "M5", "M15", "M30", "H1", "H4", "D1", "W1", "MN1"];
const intradayWindowTimeframes = new Set(["M1", "M5", "M15", "M30", "H1"]);
const SIDEBAR_STORAGE_KEY = "sb-trading-system-sidebar-collapsed";
type Page = "chart" | "checklist" | "settings";

export function App() {
  const [activePage, setActivePage] = useState<Page>("chart");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => loadSidebarCollapsed());
  const [summary, setSummary] = useState<CandleSummary[]>([]);
  const [symbol, setSymbol] = useState("");
  const [timeframe, setTimeframe] = useState("");
  const [candles, setCandles] = useState<Candle[]>([]);
  const [overlays, setOverlays] = useState<OverlayResponse | null>(null);
  const [activeOverlayTemplates, setActiveOverlayTemplates] = useState<
    OverlayTemplateId[]
  >(() => loadActiveOverlayTemplates());
  const [chartSettings, setChartSettings] = useState<ChartSettings>(() => loadChartSettings());
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
    return Array.from(new Set(["M1", ...available])).sort(
      (a, b) => timeframeOrder.indexOf(a) - timeframeOrder.indexOf(b),
    );
  }, [summary, symbol]);

  useEffect(() => {
    void loadSummary();
    void loadRuntimeSettings();
  }, []);

  useEffect(() => {
    saveChartSettings(chartSettings);
  }, [chartSettings]);

  useEffect(() => {
    saveActiveOverlayTemplates(activeOverlayTemplates);
  }, [activeOverlayTemplates]);

  useEffect(() => {
    const timeout = window.setTimeout(() => {
      void updateRuntimeSettings({
        update_interval_minutes: chartSettings.updateIntervalMinutes,
      }).catch(() => {
        // The UI setting still works locally if the backend is not running.
      });
    }, 300);

    return () => window.clearTimeout(timeout);
  }, [chartSettings.updateIntervalMinutes]);

  useEffect(() => {
    window.localStorage.setItem(SIDEBAR_STORAGE_KEY, String(sidebarCollapsed));
  }, [sidebarCollapsed]);

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

  useEffect(() => {
    if (!symbol || !timeframe) return;

    const interval = window.setInterval(() => {
      void loadCandles(symbol, timeframe);
    }, chartSettings.updateIntervalMinutes * 60 * 1000);

    return () => window.clearInterval(interval);
  }, [symbol, timeframe, chartSettings.updateIntervalMinutes]);

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

  async function loadRuntimeSettings() {
    try {
      const runtime = await fetchRuntimeSettings();
      setChartSettings((current) => ({
        ...current,
        updateIntervalMinutes: runtime.update_interval_minutes,
      }));
    } catch {
      // Local browser settings remain usable while the backend starts.
    }
  }

  async function loadCandles(nextSymbol = symbol, nextTimeframe = timeframe) {
    if (!nextSymbol || !nextTimeframe) return;
    setLoading(true);
    setError(null);
    try {
      const [candleData, overlayData] = await Promise.all([
        fetchCandles(nextSymbol, nextTimeframe),
        fetchOverlays(nextSymbol, nextTimeframe),
      ]);
      setCandles(candleData.candles);
      setOverlays(overlayData);
    } catch (err) {
      setCandles([]);
      setOverlays(null);
      setError(err instanceof Error ? err.message : "Failed to load candles");
    } finally {
      setLoading(false);
    }
  }

  async function refreshChart() {
    if (!symbol || !timeframe) return;
    setLoading(true);
    setError(null);
    try {
      const [summaryData, candleData, overlayData] = await Promise.all([
        fetchSummary(),
        fetchCandles(symbol, timeframe),
        fetchOverlays(symbol, timeframe),
      ]);
      setSummary(summaryData);
      setCandles(candleData.candles);
      setOverlays(overlayData);
    } catch (err) {
      setCandles([]);
      setOverlays(null);
      setError(err instanceof Error ? err.message : "Failed to refresh chart");
    } finally {
      setLoading(false);
    }
  }

  function toggleOverlayTemplate(templateId: OverlayTemplateId) {
    setActiveOverlayTemplates((current) =>
      current.includes(templateId)
        ? current.filter((id) => id !== templateId)
        : [...current, templateId],
    );
  }

  return (
    <main className={sidebarCollapsed ? "app-shell sidebar-collapsed" : "app-shell"}>
      <aside className="sidebar">
        <div className="brand-row">
          <div className="brand-copy">
            <h1>SB Trading System</h1>
            <p>Same thing every week, over and over again</p>
          </div>
        </div>

        <nav className="side-nav" aria-label="Workspace pages">
          <button
            className={activePage === "chart" ? "nav-button active" : "nav-button"}
            onClick={() => setActivePage("chart")}
            title="Chart"
          >
            <LineChart size={17} />
            <span>Chart</span>
          </button>
          <button
            className={activePage === "checklist" ? "nav-button active" : "nav-button"}
            onClick={() => setActivePage("checklist")}
            title="Daily Checklist"
          >
            <ClipboardList size={17} />
            <span>Daily Checklist</span>
          </button>
          <button
            className={activePage === "settings" ? "nav-button active" : "nav-button"}
            onClick={() => setActivePage("settings")}
            title="Setting"
          >
            <Settings size={17} />
            <span>Setting</span>
          </button>
        </nav>

        <button
          className="collapse-button"
          onClick={() => setSidebarCollapsed((value) => !value)}
          title={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {sidebarCollapsed ? <PanelLeftOpen size={17} /> : <PanelLeftClose size={17} />}
          <span>{sidebarCollapsed ? "Expand" : "Collapse"}</span>
        </button>
      </aside>

      <section className="workspace">
        <div className="topbar">
          <div className="topbar-main">
            {activePage === "chart" ? (
              <>
                <h2>
                  {symbol || "Symbol"} <span>{timeframe || "Timeframe"}</span>
                </h2>
                <p>
                  {candles.length
                    ? `${candles.length.toLocaleString()} loaded candles / default view ${chartWindowDays(timeframe)} days / update ${chartSettings.updateIntervalMinutes} min`
                    : "Loading chart"}
                </p>
              </>
            ) : activePage === "checklist" ? (
              <>
                <h2>Daily Checklist</h2>
                <p>Wait until there is money laying in the corner</p>
              </>
            ) : (
              <>
                <h2>Setting</h2>
                <p>Adjust chart colors, line styles, spacing, and update timing</p>
              </>
            )}
          </div>

          {activePage === "chart" ? (
            <div className="chart-toolbar">
              <div className="overlay-template-toggles" aria-label="Chart templates">
                {overlayTemplates.map((template) => {
                  const active = activeOverlayTemplates.includes(template.id);
                  return (
                    <button
                      key={template.id}
                      type="button"
                      className={active ? "template-toggle active" : "template-toggle"}
                      aria-pressed={active}
                      onClick={() => toggleOverlayTemplate(template.id)}
                      title={`${active ? "Hide" : "Show"} ${template.label}`}
                    >
                      <Layers3 size={16} />
                      <span>{template.label}</span>
                    </button>
                  );
                })}
              </div>

              <label className="chart-control">
                <span>Symbol</span>
                <select value={symbol} onChange={(event) => setSymbol(event.target.value)}>
                  {symbols.map((item) => (
                    <option key={item} value={item}>
                      {item}
                    </option>
                  ))}
                </select>
              </label>

              <label className="chart-control compact">
                <span>Timeframe</span>
                <select value={timeframe} onChange={(event) => setTimeframe(event.target.value)}>
                  {timeframes.map((item) => (
                    <option key={item} value={item}>
                      {item}
                    </option>
                  ))}
                </select>
              </label>

              <button
                className="chart-refresh-button"
                onClick={() => void refreshChart()}
                title="Refresh candles and available timeframes"
              >
                <RefreshCw size={17} />
                <span>{loading ? "Loading" : "Refresh"}</span>
              </button>
            </div>
          ) : null}
        </div>

        <div className="workspace-alerts">
          {error ? <div className="error-banner">{error}</div> : null}
        </div>

        <div className="workspace-pages">
          <section
            className={activePage === "chart" ? "workspace-page chart-page active" : "workspace-page chart-page"}
            aria-hidden={activePage !== "chart"}
          >
            <div className="chart-stage">
              <CandleChart
                candles={candles}
                overlays={
                  activeOverlayTemplates.includes("weekly_template")
                    ? overlays
                    : null
                }
                showFiveEma={activeOverlayTemplates.includes("five_ema")}
                defaultViewDays={chartWindowDays(timeframe)}
                settings={chartSettings}
              />
            </div>

            <section className="chart-research-section" aria-labelledby="chart-research-title">
              <header className="chart-research-heading">
                <BrainCircuit size={20} />
                <div>
                  <h3 id="chart-research-title">Research &amp; Pattern Comparison</h3>
                  <p>{symbol} {timeframe} market context</p>
                </div>
              </header>
              <ResearchPage
                summary={summary}
                currentSymbol={symbol}
                currentTimeframe={timeframe}
              />
            </section>
          </section>

          <section
            className={activePage === "checklist" ? "workspace-page active" : "workspace-page"}
            aria-hidden={activePage !== "checklist"}
          >
            <DailyChecklistPage />
          </section>

          <section
            className={activePage === "settings" ? "workspace-page active" : "workspace-page"}
            aria-hidden={activePage !== "settings"}
          >
            <SettingsPage settings={chartSettings} onChange={setChartSettings} />
          </section>
        </div>
      </section>
    </main>
  );
}

function preferredDefaultSymbol(symbols: string[]) {
  return symbols.find((item) => item === "XAUUSD.pc")
    ?? symbols.find((item) => item === "XAUUSD+")
    ?? symbols.find((item) => item.startsWith("XAUUSD"))
    ?? symbols[0];
}

function chartWindowDays(timeframe: string) {
  return intradayWindowTimeframes.has(timeframe) ? 7 : 30;
}

function loadSidebarCollapsed() {
  return window.localStorage.getItem(SIDEBAR_STORAGE_KEY) === "true";
}
