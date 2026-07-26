import {
  CandlestickData,
  CandlestickSeries,
  createChart,
  IChartApi,
  ISeriesApi,
  LineData,
  LineSeries,
  UTCTimestamp,
} from "lightweight-charts";
import { useEffect, useMemo, useRef, useState } from "react";
import { Candle, OverlayResponse } from "./api";
import { ChartSettings, lineDashArray } from "./chartSettings";

const emaDefinitions = [
  { period: 9, colorKey: "ema9Color", lineWidth: 2 },
  { period: 21, colorKey: "ema21Color", lineWidth: 2 },
  { period: 50, colorKey: "ema50Color", lineWidth: 1 },
  { period: 100, colorKey: "ema100Color", lineWidth: 1 },
  { period: 200, colorKey: "ema200Color", lineWidth: 1 },
] as const;

type EmaPeriod = (typeof emaDefinitions)[number]["period"];

type SvgLevel = {
  key: string;
  label: string;
  x1: number;
  y: number;
  labelX: number;
  price: number;
  color: string;
};

type SvgSession = {
  id: string;
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

type SvgMonthSeparator = {
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
};

type SvgDayRangePipe = {
  id: string;
  x1: number;
  x2: number;
  yHigh: number;
  yLow: number;
  previousYHigh?: number;
  previousYLow?: number;
  nextYHigh?: number;
  nextYLow?: number;
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
  showFiveEma: boolean;
  defaultViewDays: number;
  settings: ChartSettings;
};

export function CandleChart({
  candles,
  overlays,
  showFiveEma,
  defaultViewDays,
  settings,
}: CandleChartProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const emaSeriesRef = useRef<Map<EmaPeriod, ISeriesApi<"Line">>>(new Map());
  const overlaysRef = useRef(overlays);
  const chartDataRef = useRef<CandlestickData[]>([]);
  const settingsRef = useRef(settings);
  const redrawFrameRef = useRef<number | null>(null);
  const followupRedrawFrameRef = useRef<number | null>(null);
  const [svgLevels, setSvgLevels] = useState<SvgLevel[]>([]);
  const [svgSessions, setSvgSessions] = useState<SvgSession[]>([]);
  const [svgDayPeriods, setSvgDayPeriods] = useState<SvgDayPeriod[]>([]);
  const [svgDaySeparators, setSvgDaySeparators] = useState<SvgDaySeparator[]>([]);
  const [svgMonthSeparators, setSvgMonthSeparators] = useState<SvgMonthSeparator[]>([]);
  const [svgDayRangePipes, setSvgDayRangePipes] = useState<SvgDayRangePipe[]>([]);
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

  const emaData = useMemo(() => {
    if (!showFiveEma) return new Map<EmaPeriod, LineData[]>();
    return new Map<EmaPeriod, LineData[]>(
      emaDefinitions.map(({ period }) => [
        period,
        calculateEma(chartData, period),
      ]),
    );
  }, [chartData, showFiveEma]);

  useEffect(() => {
    overlaysRef.current = overlays;
    scheduleOverlayRedraw();
  }, [overlays]);

  useEffect(() => {
    settingsRef.current = settings;
    chartRef.current?.applyOptions({
      timeScale: {
        rightOffset: settings.rightOffsetBars,
      },
    });
    applyDefaultVisibleRange();
    scheduleOverlayRedraw();
  }, [settings]);

  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      autoSize: true,
      layout: {
        background: { color: "#ffffff" },
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
        rightOffset: settings.rightOffsetBars,
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

    for (const definition of emaDefinitions) {
      const emaSeries = chart.addSeries(LineSeries, {
        color: settings[definition.colorKey],
        lineWidth: definition.lineWidth,
        visible: false,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      });
      emaSeriesRef.current.set(definition.period, emaSeries);
    }

    chartRef.current = chart;
    seriesRef.current = series;

    const handleRangeChange = () => scheduleOverlayRedraw();
    const handleSizeChange = () => scheduleOverlayRedraw();
    chart.timeScale().subscribeVisibleTimeRangeChange(handleRangeChange);
    chart.timeScale().subscribeSizeChange(handleSizeChange);

    const resizeObserver = new ResizeObserver(() => scheduleOverlayRedraw());
    resizeObserver.observe(containerRef.current);
    scheduleOverlayRedraw();

    return () => {
      resizeObserver.disconnect();
      chart.timeScale().unsubscribeVisibleTimeRangeChange(handleRangeChange);
      chart.timeScale().unsubscribeSizeChange(handleSizeChange);
      cancelScheduledOverlayRedraw();
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
      emaSeriesRef.current.clear();
    };
  }, []);

  useEffect(() => {
    if (!seriesRef.current) return;
    chartDataRef.current = chartData;
    seriesRef.current.setData(chartData);
    applyDefaultVisibleRange();
    scheduleOverlayRedraw();
  }, [chartData, defaultViewDays]);

  useEffect(() => {
    for (const definition of emaDefinitions) {
      const emaSeries = emaSeriesRef.current.get(definition.period);
      if (!emaSeries) continue;
      emaSeries.setData(emaData.get(definition.period) ?? []);
      emaSeries.applyOptions({
        color: settings[definition.colorKey],
        visible: showFiveEma,
      });
    }
  }, [emaData, settings, showFiveEma]);

  function scheduleOverlayRedraw() {
    if (redrawFrameRef.current != null) {
      window.cancelAnimationFrame(redrawFrameRef.current);
    }
    if (followupRedrawFrameRef.current != null) {
      window.cancelAnimationFrame(followupRedrawFrameRef.current);
      followupRedrawFrameRef.current = null;
    }

    redrawFrameRef.current = window.requestAnimationFrame(() => {
      redrawFrameRef.current = null;
      redrawOverlays();

      // Lightweight Charts completes autoscaling during its own animation frame.
      // A follow-up pass keeps SVG coordinates aligned with the settled scales.
      followupRedrawFrameRef.current = window.requestAnimationFrame(() => {
        followupRedrawFrameRef.current = null;
        redrawOverlays();
      });
    });
  }

  function cancelScheduledOverlayRedraw() {
    if (redrawFrameRef.current != null) {
      window.cancelAnimationFrame(redrawFrameRef.current);
      redrawFrameRef.current = null;
    }
    if (followupRedrawFrameRef.current != null) {
      window.cancelAnimationFrame(followupRedrawFrameRef.current);
      followupRedrawFrameRef.current = null;
    }
  }

  function redrawOverlays() {
    const chart = chartRef.current;
    const series = seriesRef.current;
    if (!chart || !series) return;
    const currentSettings = settingsRef.current;

    const pane = containerRef.current?.getBoundingClientRect();
    const paneWidth = pane?.width ?? 0;
    const paneHeight = pane?.height ?? 0;

    const nextLevels = (overlaysRef.current?.levels ?? [])
      .map((level) => {
        const y = series.priceToCoordinate(level.price);
        const x1 = level.start_time
          ? coordinateForTime(chart, toTimestamp(level.start_time), chartDataRef.current)
          : 0;
        if (y == null) return null;
        return {
          key: level.key,
          label: level.label,
          x1: Number(x1 ?? 0),
          y: Number(y),
          labelX: Math.max(12, paneWidth - 82),
          price: level.price,
          color: currentSettings.horizontalLevelColor,
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
          x: left,
          y: top,
          width: Math.max(2, right - left),
          height: Math.max(2, bottom - top),
          color: sessionColor(session.id, currentSettings),
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

    const nextMonthSeparators = (overlaysRef.current?.month_separators ?? [])
      .map((separator) => {
        const x = chart.timeScale().timeToCoordinate(toTimestamp(separator.time));
        if (x == null || paneHeight <= 0) return null;
        return {
          id: separator.id,
          x: Number(x),
          height: Math.max(0, paneHeight - 28),
        };
      })
      .filter((separator): separator is SvgMonthSeparator => separator !== null);

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
          color: currentSettings.previousCloseColor,
        };
      })
      .filter((segment): segment is SvgDayCloseSegment => segment !== null);

    const dayRangePipeSegments = (overlaysRef.current?.day_range_pipes ?? [])
      .map((pipe) => {
        const x1 = chart.timeScale().timeToCoordinate(toTimestamp(pipe.start_time));
        const x2 = chart.timeScale().timeToCoordinate(toTimestamp(pipe.end_time));
        const yHigh = series.priceToCoordinate(pipe.high);
        const yLow = series.priceToCoordinate(pipe.low);
        if (x1 == null || x2 == null || yHigh == null || yLow == null) return null;

        const left = Math.min(Number(x1), Number(x2));
        const right = Math.max(Number(x1), Number(x2));
        return {
          id: pipe.id,
          x1: left,
          x2: right,
          yHigh: Number(yHigh),
          yLow: Number(yLow),
          color: currentSettings.previousRangePipeColor,
        };
      })
      .filter((pipe): pipe is SvgDayRangePipe => pipe !== null);
    const nextDayRangePipes = dayRangePipeSegments
      .sort((left, right) => left.x1 - right.x1)
      .map((pipe, index, pipes) => {
        const previous = pipes[index - 1];
        const next = pipes[index + 1];
        return {
          ...pipe,
          previousYHigh: previous?.yHigh,
          previousYLow: previous?.yLow,
          nextYHigh: next?.yHigh,
          nextYLow: next?.yLow,
        };
      });

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
    setSvgMonthSeparators(nextMonthSeparators);
    setSvgDayRangePipes(nextDayRangePipes);
    setSvgDayCloseSegments(nextDayCloseSegments);
    setSvgSetupLabels(nextSetupLabels);
  }

  function applyDefaultVisibleRange() {
    const chart = chartRef.current;
    if (!chart || !candles.length) return;

    const end = toTimestamp(candles[candles.length - 1].candle_time);
    const start = Math.max(
      toTimestamp(candles[0].candle_time),
      (end - defaultViewDays * 24 * 60 * 60) as UTCTimestamp,
    ) as UTCTimestamp;
    const startIndex = Math.max(
      0,
      chartDataRef.current.findIndex((candle) => Number(candle.time) >= Number(start)),
    );

    chart.timeScale().setVisibleLogicalRange({
      from: startIndex,
      to: Math.max(0, candles.length - 1 + settings.rightOffsetBars),
    });
  }

  return (
    <div className="chart-frame">
      <div ref={containerRef} className="chart-container" />
      {showFiveEma ? (
        <div className="ema-legend" aria-label="EMA legend">
          {emaDefinitions.map((definition) => (
            <span key={definition.period} className="ema-legend-item">
              <span
                className="ema-legend-line"
                style={{ backgroundColor: settings[definition.colorKey] }}
              />
              EMA {definition.period}
            </span>
          ))}
        </div>
      ) : null}
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
              style={{ fill: settings.weekdayLabelColor }}
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
            style={{ stroke: settings.daySeparatorColor }}
          />
        ))}
        {svgMonthSeparators.map((separator) => (
          <line
            key={separator.id}
            x1={separator.x}
            y1={0}
            x2={separator.x}
            y2={separator.height}
            className="month-separator-line"
            style={{ stroke: settings.monthSeparatorColor }}
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
          </g>
        ))}
        {svgDayRangePipes.map((pipe) => (
          <g key={pipe.id} className="day-range-pipe">
            <path
              d={roundedPipePath(
                pipe.x1,
                pipe.x2,
                pipe.previousYHigh,
                pipe.yHigh,
                pipe.nextYHigh,
                settings.previousRangePipeCornerRadius,
              )}
              stroke={pipe.color}
              className="day-range-pipe-line"
              strokeDasharray={lineDashArray(settings.previousRangePipeStyle)}
              fill="none"
            />
            <path
              d={roundedPipePath(
                pipe.x1,
                pipe.x2,
                pipe.previousYLow,
                pipe.yLow,
                pipe.nextYLow,
                settings.previousRangePipeCornerRadius,
              )}
              stroke={pipe.color}
              className="day-range-pipe-line"
              strokeDasharray={lineDashArray(settings.previousRangePipeStyle)}
              fill="none"
            />
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
              className="day-close-segment"
              strokeDasharray={lineDashArray(settings.previousCloseStyle)}
            />
          </g>
        ))}
        {svgLevels.map((level) => (
          <g key={level.key}>
            <line
              x1={level.x1}
              y1={level.y}
              x2="100%"
              y2={level.y}
              stroke={level.color}
              className="level-line"
              strokeDasharray={lineDashArray(settings.horizontalLevelStyle)}
            />
            <text x={level.labelX} y={level.y} fill={level.color} className="level-label">
              {level.label}
            </text>
          </g>
        ))}
        {svgSetupLabels.map((label) => (
          <text
            key={label.id}
            x={label.x}
            y={label.y}
            className={`setup-label setup-${label.kind}`}
            style={{ fill: settings.signalLabelColor }}
          >
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

function sessionColor(sessionId: string, settings: ChartSettings) {
  if (sessionId.startsWith("asia-")) return settings.asiaSessionFillColor;
  if (sessionId.startsWith("london-")) return settings.londonSessionFillColor;
  if (sessionId.startsWith("new_york-")) return settings.newYorkSessionFillColor;
  return settings.asiaSessionFillColor;
}

function coordinateForTime(
  chart: IChartApi,
  target: UTCTimestamp,
  data: CandlestickData[],
): number | null {
  const exact = chart.timeScale().timeToCoordinate(target);
  if (exact != null) return Number(exact);

  const targetValue = Number(target);
  const nextCandle = data.find((candle) => Number(candle.time) >= targetValue);
  if (!nextCandle) return null;

  const coordinate = chart.timeScale().timeToCoordinate(nextCandle.time);
  return coordinate == null ? null : Number(coordinate);
}

function roundedPipePath(
  x1: number,
  x2: number,
  previousY: number | undefined,
  y: number,
  nextY: number | undefined,
  requestedRadius: number,
) {
  const startRadius = pipeCornerRadius(previousY, y, requestedRadius);
  const endRadius = pipeCornerRadius(y, nextY, requestedRadius);
  const commands: string[] = [];

  if (previousY == null || startRadius === 0) {
    commands.push(`M ${x1} ${previousY ?? y}`);
    if (previousY != null && previousY !== y) {
      commands.push(`V ${y}`);
    }
  } else {
    const direction = y > previousY ? 1 : -1;
    commands.push(`M ${x1 - startRadius} ${previousY}`);
    commands.push(
      `Q ${x1} ${previousY} ${x1} ${previousY + direction * startRadius}`,
    );
    commands.push(`V ${y - direction * startRadius}`);
    commands.push(`Q ${x1} ${y} ${x1 + startRadius} ${y}`);
  }

  commands.push(`H ${Math.max(x1 + startRadius, x2 - endRadius)}`);
  return commands.join(" ");
}

function pipeCornerRadius(
  fromY: number | undefined,
  toY: number | undefined,
  requestedRadius: number,
) {
  if (fromY == null || toY == null || fromY === toY) return 0;
  return Math.min(requestedRadius, Math.abs(toY - fromY) / 2);
}

function calculateEma(data: CandlestickData[], period: number): LineData[] {
  if (data.length < period) return [];

  const multiplier = 2 / (period + 1);
  let ema = data
    .slice(0, period)
    .reduce((total, candle) => total + candle.close, 0) / period;
  const values: LineData[] = [
    {
      time: data[period - 1].time,
      value: ema,
    },
  ];

  for (let index = period; index < data.length; index += 1) {
    ema = (data[index].close - ema) * multiplier + ema;
    values.push({
      time: data[index].time,
      value: ema,
    });
  }

  return values;
}
