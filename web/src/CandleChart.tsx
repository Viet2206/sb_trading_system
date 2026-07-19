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
import { Candle } from "./api";

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

type CandleChartProps = {
  candles: Candle[];
  drawMode: boolean;
  trendLines: TrendLine[];
  onTrendLinesChange: (lines: TrendLine[]) => void;
};

export function CandleChart({
  candles,
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
  const onTrendLinesChangeRef = useRef(onTrendLinesChange);
  const [svgLines, setSvgLines] = useState<SvgLine[]>([]);
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
    redrawTrendLines();
  }, [trendLines]);

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
      upColor: "#16a34a",
      downColor: "#dc2626",
      borderUpColor: "#15803d",
      borderDownColor: "#b91c1c",
      wickUpColor: "#166534",
      wickDownColor: "#991b1b",
    });

    chartRef.current = chart;
    seriesRef.current = series;

    chart.timeScale().subscribeVisibleTimeRangeChange(() => redrawTrendLines());

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
    redrawTrendLines();
  }, [chartData]);

  useEffect(() => {
    if (!drawMode) {
      pendingPointRef.current = null;
      setPendingPoint(null);
    }
  }, [drawMode]);

  function redrawTrendLines() {
    const chart = chartRef.current;
    const series = seriesRef.current;
    if (!chart || !series) return;

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
