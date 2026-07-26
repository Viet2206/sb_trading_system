export type LineStyle = "solid" | "dashed" | "dotted";

export type ChartSettings = {
  horizontalLevelColor: string;
  horizontalLevelStyle: LineStyle;
  previousCloseColor: string;
  previousCloseStyle: LineStyle;
  previousRangePipeColor: string;
  previousRangePipeStyle: LineStyle;
  previousRangePipeCornerRadius: number;
  asiaSessionFillColor: string;
  londonSessionFillColor: string;
  newYorkSessionFillColor: string;
  daySeparatorColor: string;
  monthSeparatorColor: string;
  weekdayLabelColor: string;
  signalLabelColor: string;
  cibBullishColor: string;
  cibBearishColor: string;
  ema9Color: string;
  ema21Color: string;
  ema50Color: string;
  ema100Color: string;
  ema200Color: string;
  rightOffsetBars: number;
  updateIntervalMinutes: number;
};

const STORAGE_KEY = "sb-system-chart-settings-v1";

export const defaultChartSettings: ChartSettings = {
  horizontalLevelColor: "#8e8f90",
  horizontalLevelStyle: "solid",
  previousCloseColor: "#16a34a",
  previousCloseStyle: "solid",
  previousRangePipeColor: "#64748b",
  previousRangePipeStyle: "dashed",
  previousRangePipeCornerRadius: 7,
  asiaSessionFillColor: "#bae6fd",
  londonSessionFillColor: "#bbf7d0",
  newYorkSessionFillColor: "#fed7aa",
  daySeparatorColor: "#cbd5e1",
  monthSeparatorColor: "#64748b",
  weekdayLabelColor: "#b30000",
  signalLabelColor: "#ff0000",
  cibBullishColor: "#16a34a",
  cibBearishColor: "#ef4444",
  ema9Color: "#dc2626",
  ema21Color: "#2563eb",
  ema50Color: "#16a34a",
  ema100Color: "#9333ea",
  ema200Color: "#d97706",
  rightOffsetBars: 20,
  updateIntervalMinutes: 5,
};

export function loadChartSettings(): ChartSettings {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return defaultChartSettings;
    return sanitizeSettings(JSON.parse(raw));
  } catch {
    return defaultChartSettings;
  }
}

export function saveChartSettings(settings: ChartSettings) {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
}

export function lineDashArray(style: LineStyle) {
  if (style === "dashed") return "5 4";
  if (style === "dotted") return "1 4";
  return undefined;
}

function sanitizeSettings(value: Partial<ChartSettings>): ChartSettings {
  return {
    ...defaultChartSettings,
    ...value,
    horizontalLevelStyle: sanitizeLineStyle(value.horizontalLevelStyle),
    previousCloseStyle: sanitizeLineStyle(value.previousCloseStyle),
    previousRangePipeStyle: sanitizeLineStyle(value.previousRangePipeStyle),
    previousRangePipeCornerRadius: sanitizeCornerRadius(
      value.previousRangePipeCornerRadius,
    ),
    rightOffsetBars: sanitizeOffset(value.rightOffsetBars),
    updateIntervalMinutes: sanitizeInterval(value.updateIntervalMinutes),
  };
}

function sanitizeLineStyle(value: unknown): LineStyle {
  return value === "solid" || value === "dashed" || value === "dotted"
    ? value
    : "solid";
}

function sanitizeOffset(value: unknown) {
  return typeof value === "number" && Number.isFinite(value)
    ? Math.min(40, Math.max(0, Math.round(value)))
    : defaultChartSettings.rightOffsetBars;
}

function sanitizeCornerRadius(value: unknown) {
  return typeof value === "number" && Number.isFinite(value)
    ? Math.min(16, Math.max(0, Math.round(value)))
    : defaultChartSettings.previousRangePipeCornerRadius;
}

function sanitizeInterval(value: unknown) {
  return typeof value === "number" && Number.isFinite(value)
    ? Math.min(60, Math.max(1, Math.round(value)))
    : defaultChartSettings.updateIntervalMinutes;
}
