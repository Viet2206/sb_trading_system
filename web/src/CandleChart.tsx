import {
  CandlestickData,
  CandlestickSeries,
  createChart,
  IChartApi,
  ISeriesApi,
  UTCTimestamp,
} from "lightweight-charts";
import type { MouseEvent } from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Candle, OverlayResponse } from "./api";

type TrendPoint = {
  time: UTCTimestamp;
  price: number;
};

export type TrendLine = {
  id: string;
  start: TrendPoint;
  end: TrendPoint;
};

type SvgLine = {
  id: string;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
};

type SvgLevel = {
  key: string;
  label: string;
  y: number;
  labelX: number;
  price: number;
  color: string;
  dashArray: string | undefined;
};

type SvgSession = {
  id: string;
  label: string;
  x: number;
  y: number;
  width: number;
  height: number;
  color: string;
};

type SvgLabel = {
  id: string;
  x: number;
  y: number;
  label: string;
  kind: string;
};

type CandleChartProps = {
  candles: Candle[];
  overlays: OverlayResponse | null;
  drawMode: boolean;
  trendLines: TrendLine[];
  onTrendLinesChange: (lines: TrendLine[]) => void;
};

export function CandleChart({
  candles,
  overlays,
  drawMode,
  trendLines,
  onTrendLinesChange,
}: CandleChartProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const pendingPointRef = useRef<TrendPoint | null>(null);
  const drawModeRef = useRef(drawMode);
  const trendLinesRef = useRef(trendLines);
  const overlaysRef = useRef(overlays);
  const onTrendLinesChangeRef = useRef(onTrendLinesChange);
  const [svgLines, setSvgLines] = useState<SvgLine[]>([]);
  const [svgLevels, setSvgLevels] = useState<SvgLevel[]>([]);
  const [svgSessions, setSvgSessions] = useState<SvgSession[]>([]);
  const [svgDayLabels, setSvgDayLabels] = useState<SvgLabel[]>([]);
  const [svgSetupLabels, setSvgSetupLabels] = useState<SvgLabel[]>([]);
  const [pendingPoint, setPendingPoint] = useState<TrendPoint | null>(null);

  const chartData = useMemo<CandlestickData[]>(() => {
    return candles.map((candle) => ({
      time: toTimestamp(candle.candle_time),
      open: candle.open,
      high: candle.high,
      low: candle.low,
      close: candle.close,
    }));
  }, [candles]);

  useEffect(() => {
    drawModeRef.current = drawMode;
  }, [drawMode]);

  useEffect(() => {
    trendLinesRef.current = trendLines;
    redrawOverlays();
  }, [trendLines]);

  useEffect(() => {
    overlaysRef.current = overlays;
    redrawOverlays();
  }, [overlays]);

  useEffect(() => {
    onTrendLinesChangeRef.current = onTrendLinesChange;
  }, [onTrendLinesChange]);

  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      autoSize: true,
      layout: {
        background: { color: "#f8fafc" },
        textColor: "#1f2937",
        fontFamily: "Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, sans-serif",
      },
      grid: {
        vertLines: { color: "#e2e8f0" },
        horzLines: { color: "#e2e8f0" },
      },
      crosshair: {
        mode: 1,
      },
      rightPriceScale: {
        borderColor: "#cbd5e1",
      },
      timeScale: {
        borderColor: "#cbd5e1",
        timeVisible: true,
        secondsVisible: false,
      },
    });

    const series = chart.addSeries(CandlestickSeries, {
      upColor: "#ffffff",
      downColor: "#111827",
      borderUpColor: "#111827",
      borderDownColor: "#111827",
      wickUpColor: "#111827",
      wickDownColor: "#111827",
    });

    chartRef.current = chart;
    seriesRef.current = series;

    chart.timeScale().subscribeVisibleTimeRangeChange(() => redrawOverlays());

    return () => {
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!seriesRef.current) return;
    seriesRef.current.setData(chartData);
    chartRef.current?.timeScale().fitContent();
    pendingPointRef.current = null;
    setPendingPoint(null);
    redrawOverlays();
  }, [chartData]);

  useEffect(() => {
    if (!drawMode) {
      pendingPointRef.current = null;
      setPendingPoint(null);
    }
  }, [drawMode]);

  function redrawOverlays() {
    const chart = chartRef.current;
    const series = seriesRef.current;
    if (!chart || !series) return;

    const pane = containerRef.current?.getBoundingClientRect();
    const paneWidth = pane?.width ?? 0;

    const nextLines = trendLinesRef.current
      .map((line) => {
        const x1 = chart.timeScale().timeToCoordinate(line.start.time);
        const x2 = chart.timeScale().timeToCoordinate(line.end.time);
        const y1 = series.priceToCoordinate(line.start.price);
        const y2 = series.priceToCoordinate(line.end.price);

        if (x1 == null || x2 == null || y1 == null || y2 == null) return null;
        return {
          id: line.id,
          x1: Number(x1),
          y1: Number(y1),
          x2: Number(x2),
          y2: Number(y2),
        };
      })
      .filter((line): line is SvgLine => line !== null);

    const nextLevels = (overlaysRef.current?.levels ?? [])
      .map((level) => {
        const y = series.priceToCoordinate(level.price);
        if (y == null) return null;
        return {
          key: level.key,
          label: level.label,
          y: Number(y),
          labelX: Math.max(8, paneWidth - 82),
          price: level.price,
          color: level.color,
          dashArray: dashArray(level.style),
        };
      })
      .filter((level): level is SvgLevel => level !== null);

    const nextSessions = (overlaysRef.current?.sessions ?? [])
      .map((session) => {
        const x1 = chart.timeScale().timeToCoordinate(toTimestamp(session.start_time));
        const x2 = chart.timeScale().timeToCoordinate(toTimestamp(session.end_time));
        const yHigh = series.priceToCoordinate(session.high);
        const yLow = series.priceToCoordinate(session.low);
        if (x1 == null || x2 == null || yHigh == null || yLow == null) return null;
        const left = Math.min(Number(x1), Number(x2));
        const right = Math.max(Number(x1), Number(x2));
        const top = Math.min(Number(yHigh), Number(yLow));
        const bottom = Math.max(Number(yHigh), Number(yLow));
        return {
          id: session.id,
          label: session.label,
          x: left,
          y: top,
          width: Math.max(2, right - left),
          height: Math.max(2, bottom - top),
          color: session.color,
        };
      })
      .filter((session): session is SvgSession => session !== null);

    const nextDayLabels = (overlaysRef.current?.day_labels ?? [])
      .map((label) => {
        const x = chart.timeScale().timeToCoordinate(toTimestamp(label.time));
        if (x == null) return null;
        return {
          id: `${label.kind}-${label.time}`,
          x: Number(x),
          y: 18,
          label: label.label,
          kind: label.kind,
        };
      })
      .filter((label): label is SvgLabel => label !== null);

    const setupLabelCounts = new Map<string, number>();
    const nextSetupLabels = (overlaysRef.current?.setup_labels ?? [])
      .map((label) => {
        const x = chart.timeScale().timeToCoordinate(toTimestamp(label.time));
        const y = label.price == null ? null : series.priceToCoordinate(label.price);
        if (x == null || y == null) return null;

        const countKey = `${label.time}-${Math.round(Number(x))}`;
        const offset = setupLabelCounts.get(countKey) ?? 0;
        setupLabelCounts.set(countKey, offset + 1);

        return {
          id: `${label.kind}-${label.time}-${offset}`,
          x: Number(x),
          y: Number(y) - 24 - offset * 24,
          label: label.label,
          kind: label.kind,
        };
      })
      .filter((label): label is SvgLabel => label !== null);

    if (paneWidth <= 0) {
      setSvgLevels([]);
    } else {
      setSvgLevels(nextLevels);
    }
    setSvgSessions(nextSessions);
    setSvgDayLabels(nextDayLabels);
    setSvgSetupLabels(nextSetupLabels);
    setSvgLines(nextLines);
  }

  function handleChartClick(event: MouseEvent<HTMLDivElement>) {
    const chart = chartRef.current;
    const series = seriesRef.current;
    if (!chart || !series || !drawModeRef.current) return;

    const rect = event.currentTarget.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    const time = chart.timeScale().coordinateToTime(x);
    const price = series.coordinateToPrice(y);

    if (time == null || price == null) return;

    const point = {
      time: time as UTCTimestamp,
      price,
    };

    if (!pendingPointRef.current) {
      pendingPointRef.current = point;
      setPendingPoint(point);
      return;
    }

    const nextLine: TrendLine = {
      id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
      start: pendingPointRef.current,
      end: point,
    };
    pendingPointRef.current = null;
    setPendingPoint(null);
    onTrendLinesChangeRef.current([...trendLinesRef.current, nextLine]);
  }

  return (
    <div
      className={drawMode ? "chart-frame drawing" : "chart-frame"}
      onClick={handleChartClick}
    >
      <div ref={containerRef} className="chart-container" />
      <svg className="trend-overlay" aria-hidden="true">
        {svgSessions.map((session) => (
          <g key={session.id}>
            <rect
              x={session.x}
              y={session.y}
              width={session.width}
              height={session.height}
              fill={session.color}
              className="session-box"
            />
            <text x={session.x + 4} y={session.y + 14} className="session-label">
              {session.label}
            </text>
          </g>
        ))}
        {svgLevels.map((level) => (
          <g key={level.key}>
            <line
              x1={0}
              y1={level.y}
              x2="100%"
              y2={level.y}
              stroke={level.color}
              strokeDasharray={level.dashArray}
              className="level-line"
            />
            <text x={level.labelX} y={level.y - 5} fill={level.color} className="level-label">
              {level.label}
            </text>
          </g>
        ))}
        {svgDayLabels.map((label) => (
          <text key={label.id} x={label.x} y={label.y} className="day-label">
            {label.label}
          </text>
        ))}
        {svgSetupLabels.map((label) => (
          <text key={label.id} x={label.x} y={label.y} className={`setup-label setup-${label.kind}`}>
            {label.label}
          </text>
        ))}
        {svgLines.map((line) => (
          <line
            key={line.id}
            x1={line.x1}
            y1={line.y1}
            x2={line.x2}
            y2={line.y2}
            className="trend-line"
          />
        ))}
      </svg>
      {drawMode && pendingPoint ? (
        <div className="draw-hint">Select the second point</div>
      ) : null}
      {!candles.length ? <div className="empty-state">No candles loaded</div> : null}
    </div>
  );
}

function toTimestamp(value: string): UTCTimestamp {
  return Math.floor(new Date(value).getTime() / 1000) as UTCTimestamp;
}

function dashArray(style: string): string | undefined {
  if (style === "dashed") return "8 6";
  if (style === "dotted") return "2 5";
  return undefined;
}
