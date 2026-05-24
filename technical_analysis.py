"""
Technical Analysis module for NiftyMind.
Fetches OHLCV data from Yahoo Finance and computes indicators
that are passed to the AI as structured context alongside news.

Indicators computed:
  - RSI (14-period)         — momentum / overbought-oversold signal
  - 20-day SMA              — trend direction
  - Volume ratio            — today's volume vs 20-day average (spike detection)
  - Price vs SMA %          — how far price is above/below the trend line
"""

from typing import Dict, Optional
from config import logger

try:
    import yfinance as yf
    import pandas as pd
    _YFINANCE_AVAILABLE = True
except ImportError:
    _YFINANCE_AVAILABLE = False
    logger.warning("yfinance not installed — technical indicators unavailable. Run: pip install yfinance pandas")


def _compute_rsi(prices: "pd.Series", period: int = 14) -> float:
    """Compute RSI for the most recent data point."""
    delta = prices.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=period, min_periods=period).mean().iloc[-1]
    avg_loss = loss.rolling(window=period, min_periods=period).mean().iloc[-1]
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def get_technical_snapshot(symbol: str) -> Optional[Dict]:
    """
    Fetches 60 days of daily OHLCV data for a NSE symbol and returns a
    structured dict of key technical indicators for use in AI prompts.

    Args:
        symbol: NSE ticker (e.g. "RELIANCE") — auto-appended with ".NS" for Yahoo Finance.

    Returns:
        Dict with keys: symbol, ltp, rsi_14, sma_20, price_vs_sma_pct,
                        volume_ratio, signal_summary
        Returns None if data cannot be fetched.
    """
    if not _YFINANCE_AVAILABLE:
        return None

    yf_symbol = f"{symbol}.NS"
    try:
        # Use Ticker.history() — always returns a clean flat DataFrame, no MultiIndex issues
        ticker = yf.Ticker(yf_symbol)
        df = ticker.history(period="60d", interval="1d", auto_adjust=True)

        if df is None or len(df) < 21:
            logger.warning(f"[TA] Insufficient data for {symbol} ({len(df) if df is not None else 0} rows).")
            return None

        close = df["Close"].astype(float)
        volume = df["Volume"].astype(float)

        ltp = round(float(close.iloc[-1]), 2)
        sma_20 = round(float(close.rolling(20).mean().iloc[-1]), 2)
        rsi = _compute_rsi(close)
        price_vs_sma_pct = round(((ltp - sma_20) / sma_20) * 100, 2)

        vol_today = float(volume.iloc[-1])
        vol_avg_20 = float(volume.rolling(20).mean().iloc[-1])
        volume_ratio = round(vol_today / vol_avg_20, 2) if vol_avg_20 > 0 else 1.0

        # Human-readable signal summary for the AI prompt
        rsi_signal = (
            "OVERBOUGHT" if rsi > 70
            else "OVERSOLD" if rsi < 30
            else "NEUTRAL"
        )
        trend_signal = (
            "ABOVE_SMA (bullish)" if price_vs_sma_pct > 2
            else "BELOW_SMA (bearish)" if price_vs_sma_pct < -2
            else "AT_SMA (neutral)"
        )
        volume_signal = (
            "HIGH_VOLUME (strong conviction)" if volume_ratio > 1.5
            else "LOW_VOLUME (weak conviction)" if volume_ratio < 0.7
            else "NORMAL_VOLUME"
        )

        return {
            "symbol": symbol,
            "ltp": ltp,
            "rsi_14": rsi,
            "sma_20": sma_20,
            "price_vs_sma_pct": price_vs_sma_pct,
            "volume_ratio": volume_ratio,
            "rsi_signal": rsi_signal,
            "trend_signal": trend_signal,
            "volume_signal": volume_signal,
            "signal_summary": (
                f"RSI={rsi} ({rsi_signal}), "
                f"Price={ltp} vs SMA20={sma_20} ({price_vs_sma_pct:+.1f}%, {trend_signal}), "
                f"Volume={volume_ratio:.1f}x avg ({volume_signal})"
            ),
        }

    except Exception as e:
        logger.warning(f"[TA] Failed to fetch data for {symbol}: {e}")
        return None


def get_ta_context_for_universe(symbols: list) -> str:
    """
    Returns a formatted multi-stock TA summary string for use in the AI buy prompt.
    Fetches TA for all symbols in parallel using threading.

    Args:
        symbols: List of NSE tickers to analyse.

    Returns:
        Formatted string like:
        "RELIANCE: RSI=62 (NEUTRAL), Price=2450 vs SMA20=2380 (+2.9%, ABOVE_SMA), Volume=1.3x avg"
        "INFY: RSI=35 (OVERSOLD), ..."
    """
    if not _YFINANCE_AVAILABLE:
        return "Technical analysis unavailable (yfinance not installed)."

    from concurrent.futures import ThreadPoolExecutor, as_completed

    results = {}
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(get_technical_snapshot, sym): sym for sym in symbols}
        for future in as_completed(futures):
            sym = futures[future]
            try:
                data = future.result()
                if data:
                    results[sym] = data
            except Exception as e:
                logger.warning(f"[TA] Error for {sym}: {e}")

    if not results:
        return "Technical analysis data unavailable."

    lines = ["=== Technical Indicators (use to filter AI buy recommendations) ==="]
    for sym in symbols:
        if sym in results:
            d = results[sym]
            lines.append(f"  {sym}: {d['signal_summary']}")
        else:
            lines.append(f"  {sym}: data unavailable")

    return "\n".join(lines)


if __name__ == "__main__":
    from config import LIQUID_UNIVERSE
    print(get_ta_context_for_universe(LIQUID_UNIVERSE[:5]))
