import {
  CandlestickData,
  CandlestickSeries,
  createChart,
  IChartApi,
  ISeriesApi,
  UTCTimestamp,
} from "lightweight-charts";
import { useEffect, useMemo, useRef, useState } from "react";
import { Candle, OverlayResponse } from "./api";

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

type SvgDayPeriod = {
  id: string;
  label: string;
  x: number;
  width: number;
  height: number;
  variant: "even" | "odd";
};

type SvgDaySeparator = {
  id: string;
  x: number;
  height: number;
};

type SvgDayCloseSegment = {
  id: string;
  x1: number;
  x2: number;
  y: number;
  color: string;
  dashArray: string | undefined;
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
};

export function CandleChart({
  candles,
  overlays,
}: CandleChartProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const overlaysRef = useRef(overlays);
  const [svgLevels, setSvgLevels] = useState<SvgLevel[]>([]);
  const [svgSessions, setSvgSessions] = useState<SvgSession[]>([]);
  const [svgDayPeriods, setSvgDayPeriods] = useState<SvgDayPeriod[]>([]);
  const [svgDaySeparators, setSvgDaySeparators] = useState<SvgDaySeparator[]>([]);
  const [svgDayCloseSegments, setSvgDayCloseSegments] = useState<SvgDayCloseSegment[]>([]);
  const [svgSetupLabels, setSvgSetupLabels] = useState<SvgLabel[]>([]);

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
    overlaysRef.current = overlays;
    redrawOverlays();
  }, [overlays]);

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
        vertLines: { visible: false },
        horzLines: { visible: false },
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
    redrawOverlays();
  }, [chartData]);

  function redrawOverlays() {
    const chart = chartRef.current;
    const series = seriesRef.current;
    if (!chart || !series) return;

    const pane = containerRef.current?.getBoundingClientRect();
    const paneWidth = pane?.width ?? 0;
    const paneHeight = pane?.height ?? 0;

    const nextLevels = (overlaysRef.current?.levels ?? [])
      .map((level) => {
        const y = series.priceToCoordinate(level.price);
        if (y == null) return null;
        return {
          key: level.key,
          label: level.label,
          y: Number(y),
          labelX: Math.max(12, paneWidth - 112),
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

    const nextDayPeriods = (overlaysRef.current?.day_periods ?? [])
      .map((period) => {
        const x1 = chart.timeScale().timeToCoordinate(toTimestamp(period.start_time));
        const x2 = chart.timeScale().timeToCoordinate(toTimestamp(period.end_time));
        if (x1 == null || x2 == null || paneHeight <= 0) return null;
        const left = Math.min(Number(x1), Number(x2));
        const right = Math.max(Number(x1), Number(x2));
        return {
          id: period.id,
          label: period.label,
          x: left,
          width: Math.max(16, right - left),
          height: Math.max(0, paneHeight - 28),
          variant: period.variant,
        };
      })
      .filter((period): period is SvgDayPeriod => period !== null);

    const nextDaySeparators = nextDayPeriods.map((period) => ({
      id: `separator-${period.id}`,
      x: period.x,
      height: period.height,
    }));

    const nextDayCloseSegments = (overlaysRef.current?.day_close_segments ?? [])
      .map((segment) => {
        const x1 = chart.timeScale().timeToCoordinate(toTimestamp(segment.start_time));
        const x2 = chart.timeScale().timeToCoordinate(toTimestamp(segment.end_time));
        const y = series.priceToCoordinate(segment.price);
        if (x1 == null || x2 == null || y == null) return null;

        const left = Math.min(Number(x1), Number(x2));
        const right = Math.max(Number(x1), Number(x2));
        return {
          id: segment.id,
          x1: left,
          x2: right,
          y: Number(y),
          color: segment.color,
          dashArray: dashArray(segment.style),
        };
      })
      .filter((segment): segment is SvgDayCloseSegment => segment !== null);

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
    setSvgDayPeriods(nextDayPeriods);
    setSvgDaySeparators(nextDaySeparators);
    setSvgDayCloseSegments(nextDayCloseSegments);
    setSvgSetupLabels(nextSetupLabels);
  }

  return (
    <div className="chart-frame">
      <div ref={containerRef} className="chart-container" />
      <svg className="chart-overlay" aria-hidden="true">
        {svgDayPeriods.map((period) => (
          <g key={period.id}>
            <rect
              x={period.x}
              y={0}
              width={period.width}
              height={period.height}
              className={`day-period-box ${period.variant}`}
            />
            <text
              x={period.x + period.width / 2}
              y={period.height - 10}
              className="day-period-label"
            >
              {period.label}
            </text>
          </g>
        ))}
        {svgDaySeparators.map((separator) => (
          <line
            key={separator.id}
            x1={separator.x}
            y1={0}
            x2={separator.x}
            y2={separator.height}
            className="day-separator-line"
          />
        ))}
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
        {svgDayCloseSegments.map((segment) => (
          <g key={segment.id}>
            <line
              x1={segment.x1}
              y1={segment.y}
              x2={segment.x2}
              y2={segment.y}
              stroke={segment.color}
              strokeDasharray={segment.dashArray}
              className="day-close-segment"
            />
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
        {svgSetupLabels.map((label) => (
          <text key={label.id} x={label.x} y={label.y} className={`setup-label setup-${label.kind}`}>
            {label.label}
          </text>
        ))}
      </svg>
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
