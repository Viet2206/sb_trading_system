# Native Weekly Template Indicators

These indicators port the SB Trading System `weekly_template` overlay to native
broker charts:

- `mt5/SBWeeklyTemplate.mq5` for MetaTrader 5
- `ctrader/SBWeeklyTemplate.cs` for cTrader Automate

They do not include the separate **5 EMA** or **Major Round Number** templates.

## Included Layers

- Previous month high/low: `PMH`, `PML`
- Current month first trading-day high/low
- Previous week high/low: `PWH`, `PWL`
- Latest Friday close
- Current Monday high/low
- Previous-day high/low pipes with high-to-high and low-to-low connectors
- Previous-day close segments within each current day
- UTC day and month separators
- UTC weekday labels
- Asia 03:00-06:00, London 09:00-12:00, New York 15:00-18:00 session fills
- Previous-day Closing Inside Breakout markers
- Provisional `Inside Day`, `FGD`, `FRD`, `3DL`, and `3DS` daily labels

The intraday day/session/pipe/CIB layers are hidden on H4 and D1, matching the web
platform. Context levels and setup labels remain available.

The deterministic setup labels have the same provisional status as the web
platform. Validate them against manually tagged Stacey Burke examples before using
them as trading signals.

## MetaTrader 5

1. In MT5, choose **File > Open Data Folder**.
2. Open `MQL5/Indicators`.
3. Copy `SBWeeklyTemplate.mq5` into that folder.
4. Open the file in MetaEditor and press **F7** to compile.
5. Refresh the Navigator, then attach **SB Weekly Template** to a chart.

The session inputs are expressed in UTC. MT5 chart objects use broker server time,
so set **Server UTC Offset Hours** to the broker server offset. For example, use `2`
when the broker server is UTC+2.

MT5 D1 candles still use the broker's own daily candle boundary. The offset translates
session windows, UTC day separators, and weekday labels, but it cannot redefine the
broker's native D1 OHLC. Use a broker with UTC daily candles or compare the resulting
daily levels with the web/cTrader version when exact UTC-day parity matters.

## cTrader

1. Open **Automate** in cTrader.
2. Create a new indicator named `SBWeeklyTemplate`.
3. Replace the generated source with `ctrader/SBWeeklyTemplate.cs`.
4. Build the indicator.
5. Add it to a chart.

The cTrader indicator declares `TimeZones.UTC`, so no server offset setting is
required. Ensure enough D1 and chart history is loaded for the selected lookback.

## Defaults

Both indicators default to:

- 45 visible-history days
- gray solid context levels
- gray dashed previous-day pipes
- green previous-day close segments
- lightly filled session ranges without text labels
- red weekday/setup labels
- two-bar-wide CIB markers

Every layer, color, line style, and session time can be adjusted in the indicator
parameters.
