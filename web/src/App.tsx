import { useEffect, useMemo, useRef, useState } from "react";
import type {
  CSSProperties,
  KeyboardEvent as ReactKeyboardEvent,
  PointerEvent as ReactPointerEvent,
} from "react";
import {
  BrainCircuit,
  ClipboardList,
  Layers3,
  LineChart,
  PanelLeftClose,
  PanelLeftOpen,
  PanelRightClose,
  PanelRightOpen,
  RefreshCw,
  Settings,
} from "lucide-react";
import { CandleChart } from "./CandleChart";
import { DailyChecklistPage } from "./DailyChecklistPage";
import { HistoricalMatches } from "./HistoricalMatches";
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
const ANALYST_PANEL_STORAGE_KEY = "sb-trading-system-analyst-panel-expanded";
const ANALYST_PANEL_WIDTH_STORAGE_KEY = "sb-trading-system-analyst-panel-width";
const ANALYST_PANEL_MIN_WIDTH = 360;
const ANALYST_PANEL_MAX_WIDTH = 640;
const ANALYST_PANEL_DEFAULT_WIDTH = 420;
type Page = "chart" | "checklist" | "settings";

export function App() {
  const [activePage, setActivePage] = useState<Page>("chart");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => loadSidebarCollapsed());
  const [analystExpanded, setAnalystExpanded] = useState(() => loadAnalystExpanded());
  const [analystPanelWidth, setAnalystPanelWidth] = useState(() =>
    loadAnalystPanelWidth(),
  );
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
  const [chartRefreshKey, setChartRefreshKey] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const chartRequestRef = useRef(0);
  const analystResizeRef = useRef<{
    pointerId: number;
    startX: number;
    startWidth: number;
  } | null>(null);

  const symbols = useMemo(
    () => Array.from(new Set(summary.map((item) => item.broker_symbol))).sort(),
    [summary],
  );

  const timeframes = useMemo(() => {
    const available = summary
      .filter((item) => item.broker_symbol === symbol)
      .map((item) => item.timeframe);
    return Array.from(new Set(available)).sort(
      (a, b) => timeframeOrder.indexOf(a) - timeframeOrder.indexOf(b),
    );
  }, [summary, symbol]);
  const timeframeAvailable = Boolean(
    symbol && timeframe && timeframes.includes(timeframe),
  );

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
    window.localStorage.setItem(
      ANALYST_PANEL_STORAGE_KEY,
      String(analystExpanded),
    );
  }, [analystExpanded]);

  useEffect(() => {
    window.localStorage.setItem(
      ANALYST_PANEL_WIDTH_STORAGE_KEY,
      String(analystPanelWidth),
    );
  }, [analystPanelWidth]);

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
    if (timeframeAvailable) {
      void loadCandles(symbol, timeframe);
    }
  }, [symbol, timeframe, timeframeAvailable]);

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
    const requestId = ++chartRequestRef.current;
    setLoading(true);
    setError(null);
    try {
      const [candleData, overlayData] = await Promise.all([
        fetchCandles(nextSymbol, nextTimeframe),
        fetchOverlays(nextSymbol, nextTimeframe),
      ]);
      if (requestId !== chartRequestRef.current) return;
      setCandles(candleData.candles);
      setOverlays(overlayData);
      setChartRefreshKey((current) => current + 1);
    } catch (err) {
      if (requestId !== chartRequestRef.current) return;
      setCandles([]);
      setOverlays(null);
      setError(err instanceof Error ? err.message : "Failed to load candles");
    } finally {
      if (requestId === chartRequestRef.current) {
        setLoading(false);
      }
    }
  }

  async function refreshChart() {
    if (!symbol || !timeframe) return;
    const requestId = ++chartRequestRef.current;
    setLoading(true);
    setError(null);
    try {
      const [summaryData, candleData, overlayData] = await Promise.all([
        fetchSummary(),
        fetchCandles(symbol, timeframe),
        fetchOverlays(symbol, timeframe),
      ]);
      if (requestId !== chartRequestRef.current) return;
      setSummary(summaryData);
      setCandles(candleData.candles);
      setOverlays(overlayData);
      setChartRefreshKey((current) => current + 1);
    } catch (err) {
      if (requestId !== chartRequestRef.current) return;
      setCandles([]);
      setOverlays(null);
      setError(err instanceof Error ? err.message : "Failed to refresh chart");
    } finally {
      if (requestId === chartRequestRef.current) {
        setLoading(false);
      }
    }
  }

  function changeSymbol(nextSymbol: string) {
    chartRequestRef.current += 1;
    setCandles([]);
    setOverlays(null);
    setSymbol(nextSymbol);
  }

  function changeTimeframe(nextTimeframe: string) {
    chartRequestRef.current += 1;
    setCandles([]);
    setOverlays(null);
    setTimeframe(nextTimeframe);
  }

  function toggleOverlayTemplate(templateId: OverlayTemplateId) {
    setActiveOverlayTemplates((current) =>
      current.includes(templateId)
        ? current.filter((id) => id !== templateId)
        : [...current, templateId],
    );
  }

  function startAnalystResize(event: ReactPointerEvent<HTMLDivElement>) {
    if (!analystExpanded) return;

    analystResizeRef.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startWidth: analystPanelWidth,
    };
    event.currentTarget.setPointerCapture(event.pointerId);
    document.body.classList.add("resizing-analyst-panel");
  }

  function resizeAnalystPanel(event: ReactPointerEvent<HTMLDivElement>) {
    const resize = analystResizeRef.current;
    if (!resize || resize.pointerId !== event.pointerId) return;

    setAnalystPanelWidth(
      clampAnalystPanelWidth(
        resize.startWidth + resize.startX - event.clientX,
      ),
    );
  }

  function stopAnalystResize(event: ReactPointerEvent<HTMLDivElement>) {
    const resize = analystResizeRef.current;
    if (!resize || resize.pointerId !== event.pointerId) return;

    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    analystResizeRef.current = null;
    document.body.classList.remove("resizing-analyst-panel");
  }

  function resizeAnalystPanelWithKeyboard(
    event: ReactKeyboardEvent<HTMLDivElement>,
  ) {
    const step = event.shiftKey ? 40 : 12;
    let nextWidth: number | null = null;

    if (event.key === "ArrowLeft") nextWidth = analystPanelWidth + step;
    if (event.key === "ArrowRight") nextWidth = analystPanelWidth - step;
    if (event.key === "Home") nextWidth = ANALYST_PANEL_MIN_WIDTH;
    if (event.key === "End") nextWidth = ANALYST_PANEL_MAX_WIDTH;
    if (nextWidth === null) return;

    event.preventDefault();
    setAnalystPanelWidth(clampAnalystPanelWidth(nextWidth));
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
                <select
                  value={symbol}
                  onChange={(event) => changeSymbol(event.target.value)}
                >
                  {symbols.map((item) => (
                    <option key={item} value={item}>
                      {item}
                    </option>
                  ))}
                </select>
              </label>

              <label className="chart-control compact">
                <span>Timeframe</span>
                <select
                  value={timeframe}
                  onChange={(event) => changeTimeframe(event.target.value)}
                >
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
            <div
              className={
                analystExpanded
                  ? "chart-workbench analyst-expanded"
                  : "chart-workbench analyst-collapsed"
              }
              style={
                {
                  "--analyst-panel-width": `${analystPanelWidth}px`,
                } as CSSProperties
              }
            >
              <div className="chart-stage">
                <CandleChart
                  key={`${symbol}-${timeframe}`}
                  symbol={symbol}
                  candles={candles}
                  overlays={
                    activeOverlayTemplates.includes("weekly_template")
                      ? overlays
                      : null
                  }
                  showFiveEma={activeOverlayTemplates.includes("five_ema")}
                  showMajorRoundNumbers={activeOverlayTemplates.includes(
                    "major_round_number",
                  )}
                  showSonicR={activeOverlayTemplates.includes("sonic_r")}
                  defaultViewDays={chartWindowDays(timeframe)}
                  settings={chartSettings}
                />
              </div>

              <div
                className="analyst-resize-handle"
                role="separator"
                aria-label="Resize AI Analyst"
                aria-orientation="vertical"
                aria-valuemin={ANALYST_PANEL_MIN_WIDTH}
                aria-valuemax={ANALYST_PANEL_MAX_WIDTH}
                aria-valuenow={Math.round(analystPanelWidth)}
                tabIndex={analystExpanded ? 0 : -1}
                title="Drag to resize AI Analyst"
                onPointerDown={startAnalystResize}
                onPointerMove={resizeAnalystPanel}
                onPointerUp={stopAnalystResize}
                onPointerCancel={stopAnalystResize}
                onKeyDown={resizeAnalystPanelWithKeyboard}
              />

              <aside className="chart-analyst-panel" aria-label="AI Analyst">
                <header className="chart-analyst-header">
                  <div className="chart-analyst-title">
                    <BrainCircuit size={18} />
                    <strong>AI Analyst</strong>
                  </div>
                  <button
                    type="button"
                    className="analyst-panel-toggle"
                    onClick={() => setAnalystExpanded((value) => !value)}
                    aria-expanded={analystExpanded}
                    aria-controls="chart-analyst-body"
                    title={analystExpanded ? "Collapse AI Analyst" : "Expand AI Analyst"}
                  >
                    {analystExpanded
                      ? <PanelRightClose size={18} />
                      : <PanelRightOpen size={18} />}
                  </button>
                </header>
                <div
                  id="chart-analyst-body"
                  className="chart-analyst-body"
                  aria-hidden={!analystExpanded}
                >
                  <ResearchPage
                    mode="analyst"
                    currentSymbol={symbol}
                    currentTimeframe={timeframe}
                  />
                </div>
              </aside>
            </div>

            <HistoricalMatches
              symbol={symbol}
              timeframe={timeframe}
              refreshKey={chartRefreshKey}
            />

            <section className="chart-research-section" aria-labelledby="chart-research-title">
              <header className="chart-research-heading">
                <BrainCircuit size={20} />
                <div>
                  <h3 id="chart-research-title">Research &amp; Source Library</h3>
                  <p>Search the SB playbook and inspect original evidence</p>
                </div>
              </header>
              <ResearchPage
                mode="browse"
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

function loadAnalystExpanded() {
  return window.localStorage.getItem(ANALYST_PANEL_STORAGE_KEY) !== "false";
}

function clampAnalystPanelWidth(width: number) {
  return Math.min(
    ANALYST_PANEL_MAX_WIDTH,
    Math.max(ANALYST_PANEL_MIN_WIDTH, width),
  );
}

function loadAnalystPanelWidth() {
  const savedWidth = Number(
    window.localStorage.getItem(ANALYST_PANEL_WIDTH_STORAGE_KEY),
  );
  return Number.isFinite(savedWidth) && savedWidth > 0
    ? clampAnalystPanelWidth(savedWidth)
    : ANALYST_PANEL_DEFAULT_WIDTH;
}
