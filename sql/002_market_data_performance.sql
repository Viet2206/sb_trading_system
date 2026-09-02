CREATE TABLE IF NOT EXISTS market.candle_summary (
    symbol_id BIGINT NOT NULL REFERENCES market.symbols(symbol_id) ON DELETE CASCADE,
    timeframe TEXT NOT NULL,
    first_candle TIMESTAMPTZ NOT NULL,
    last_candle TIMESTAMPTZ NOT NULL,
    candles BIGINT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (symbol_id, timeframe)
);

CREATE INDEX IF NOT EXISTS candle_summary_last_candle_idx
    ON market.candle_summary (last_candle DESC);

INSERT INTO market.candle_summary (
    symbol_id,
    timeframe,
    first_candle,
    last_candle,
    candles,
    updated_at
)
SELECT
    symbol_id,
    timeframe,
    min(candle_time),
    max(candle_time),
    count(*),
    now()
FROM market.candles
GROUP BY symbol_id, timeframe
ON CONFLICT (symbol_id, timeframe) DO UPDATE SET
    first_candle = EXCLUDED.first_candle,
    last_candle = EXCLUDED.last_candle,
    candles = EXCLUDED.candles,
    updated_at = now();
