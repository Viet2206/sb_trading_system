import { RotateCcw } from "lucide-react";
import {
  ChartSettings,
  LineStyle,
  defaultChartSettings,
} from "./chartSettings";

type SettingsPageProps = {
  settings: ChartSettings;
  onChange: (settings: ChartSettings) => void;
};

type ColorField = {
  key: keyof Pick<
    ChartSettings,
    | "horizontalLevelColor"
    | "previousCloseColor"
    | "previousRangePipeColor"
    | "asiaSessionFillColor"
    | "londonSessionFillColor"
    | "newYorkSessionFillColor"
    | "daySeparatorColor"
    | "monthSeparatorColor"
    | "weekdayLabelColor"
    | "signalLabelColor"
  >;
  label: string;
};

type StyleField = {
  key: keyof Pick<
    ChartSettings,
    "horizontalLevelStyle" | "previousCloseStyle" | "previousRangePipeStyle"
  >;
  label: string;
};

const colorFields: ColorField[] = [
  { key: "horizontalLevelColor", label: "Context Levels (PWH/PWL/Mon/Fri)" },
  { key: "previousCloseColor", label: "Previous Day Close Segments" },
  { key: "previousRangePipeColor", label: "Previous Day High/Low Pipe" },
  { key: "asiaSessionFillColor", label: "Asia Session" },
  { key: "londonSessionFillColor", label: "London Session" },
  { key: "newYorkSessionFillColor", label: "New York Session" },
  { key: "daySeparatorColor", label: "Day Separators" },
  { key: "monthSeparatorColor", label: "Month Separators" },
  { key: "weekdayLabelColor", label: "Weekday Labels" },
  { key: "signalLabelColor", label: "Signal Labels" },
];

const styleFields: StyleField[] = [
  { key: "horizontalLevelStyle", label: "Context Levels (PWH/PWL/Mon/Fri)" },
  { key: "previousCloseStyle", label: "Previous Day Close Segments" },
  { key: "previousRangePipeStyle", label: "Previous Day High/Low Pipe" },
];

const lineStyles: LineStyle[] = ["solid", "dashed", "dotted"];

export function SettingsPage({ settings, onChange }: SettingsPageProps) {
  function update<K extends keyof ChartSettings>(key: K, value: ChartSettings[K]) {
    onChange({ ...settings, [key]: value });
  }

  return (
    <div className="settings-page">
      <section className="settings-section">
        <div className="settings-section-title">
          <h3>Overlay Colors</h3>
        </div>
        <div className="settings-grid">
          {colorFields.map((field) => (
            <label key={field.key} className="setting-row">
              <span>{field.label}</span>
              <div className="color-control">
                <input
                  type="color"
                  aria-label={`${field.label} color picker`}
                  value={settings[field.key]}
                  onInput={(event) =>
                    update(field.key, (event.target as HTMLInputElement).value)
                  }
                  onChange={(event) => update(field.key, event.target.value)}
                />
                <input
                  data-testid={`setting-${field.key}`}
                  value={settings[field.key]}
                  onChange={(event) => update(field.key, event.target.value)}
                  spellCheck={false}
                />
              </div>
            </label>
          ))}
        </div>
      </section>

      <section className="settings-section">
        <div className="settings-section-title">
          <h3>Line Styles</h3>
        </div>
        <div className="settings-grid compact">
          {styleFields.map((field) => (
            <label key={field.key} className="setting-row">
              <span>{field.label}</span>
              <select
                data-testid={`setting-${field.key}`}
                value={settings[field.key]}
                onChange={(event) => update(field.key, event.target.value as LineStyle)}
              >
                {lineStyles.map((style) => (
                  <option key={style} value={style}>
                    {style}
                  </option>
                ))}
              </select>
            </label>
          ))}
        </div>
        <label className="setting-row range-row">
          <span>Previous Day Pipe Corner Radius</span>
          <input
            data-testid="setting-previousRangePipeCornerRadius"
            type="number"
            min={0}
            max={16}
            step={1}
            value={settings.previousRangePipeCornerRadius}
            onChange={(event) =>
              update("previousRangePipeCornerRadius", Number(event.target.value))
            }
          />
        </label>
      </section>

      <section className="settings-section">
        <div className="settings-section-title">
          <h3>Chart Updates</h3>
        </div>
        <label className="setting-row range-row">
          <span>Update Interval Minutes</span>
          <input
            data-testid="setting-updateIntervalMinutes"
            type="number"
            min={1}
            max={60}
            step={1}
            value={settings.updateIntervalMinutes}
            onChange={(event) => update("updateIntervalMinutes", Number(event.target.value))}
          />
        </label>
      </section>

      <section className="settings-section">
        <div className="settings-section-title">
          <h3>Chart Space</h3>
        </div>
        <label className="setting-row range-row">
          <span>Right Offset Bars</span>
          <input
            data-testid="setting-rightOffsetBars"
            type="number"
            min={0}
            max={40}
            step={1}
            value={settings.rightOffsetBars}
            onChange={(event) => update("rightOffsetBars", Number(event.target.value))}
          />
        </label>
      </section>

      <button
        className="reset-button"
        onClick={() => onChange(defaultChartSettings)}
        title="Restore default chart settings"
      >
        <RotateCcw size={17} />
        <span>Reset Defaults</span>
      </button>
    </div>
  );
}
