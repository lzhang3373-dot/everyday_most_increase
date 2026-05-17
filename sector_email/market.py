from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from io import StringIO
from time import sleep
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import pandas_market_calendars as mcal
import requests
import yfinance as yf


SECTOR_ETFS: dict[str, str] = {
    "Communication Services": "XLC",
    "Consumer Discretionary": "XLY",
    "Consumer Staples": "XLP",
    "Energy": "XLE",
    "Financials": "XLF",
    "Health Care": "XLV",
    "Industrials": "XLI",
    "Information Technology": "XLK",
    "Materials": "XLB",
    "Real Estate": "XLRE",
    "Utilities": "XLU",
}

SECTOR_CN: dict[str, str] = {
    "Communication Services": "通信服务",
    "Consumer Discretionary": "可选消费",
    "Consumer Staples": "必需消费",
    "Energy": "能源",
    "Financials": "金融",
    "Health Care": "医疗保健",
    "Industrials": "工业",
    "Information Technology": "信息技术",
    "Materials": "原材料",
    "Real Estate": "房地产",
    "Utilities": "公用事业",
}


@dataclass(frozen=True)
class StockMove:
    ticker: str
    company: str
    close: float
    change_pct: float
    volume: int | None = None
    market_cap: int | None = None
    trailing_pe: float | None = None
    forward_pe: float | None = None
    beta: float | None = None
    dividend_yield: float | None = None
    fifty_two_week_high: float | None = None
    fifty_two_week_low: float | None = None


@dataclass(frozen=True)
class SectorReport:
    trade_date: date
    sector: str
    sector_cn: str
    sector_etf: str
    sector_return_pct: float
    top_stocks: list[StockMove]


def resolve_trade_date(target_date: str | None, tz_name: str, data_delay_minutes: int) -> date:
    tz = ZoneInfo(tz_name)
    now = datetime.now(tz)
    trade_day = datetime.strptime(target_date, "%Y-%m-%d").date() if target_date else now.date()

    nyse = mcal.get_calendar("NYSE")
    schedule = nyse.schedule(start_date=trade_day, end_date=trade_day)
    if schedule.empty:
        raise RuntimeError(f"{trade_day.isoformat()} 是美股休市日，没有可发送的正常收盘数据。")

    if not target_date:
        market_close = schedule.iloc[0]["market_close"].to_pydatetime().astimezone(tz)
        ready_at = market_close + timedelta(minutes=data_delay_minutes)
        if now < ready_at:
            raise RuntimeError(
                f"{trade_day.isoformat()} 美股尚未完成收盘数据更新，预计 {ready_at:%Y-%m-%d %H:%M %Z} 后可运行。"
            )

    return trade_day


def get_sp500_constituents() -> pd.DataFrame:
    response = requests.get(
        "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
        headers={"User-Agent": "Mozilla/5.0 sector-email-bot/1.0"},
        timeout=30,
    )
    response.raise_for_status()
    tables = pd.read_html(StringIO(response.text))
    df = tables[0][["Symbol", "Security", "GICS Sector"]].copy()
    df["Symbol"] = df["Symbol"].str.replace(".", "-", regex=False)
    return df


def _download_daily(tickers: list[str], trade_date: date) -> pd.DataFrame:
    start = trade_date - timedelta(days=10)
    end = trade_date + timedelta(days=1)
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            data = yf.download(
                tickers=tickers,
                start=start.isoformat(),
                end=end.isoformat(),
                auto_adjust=False,
                progress=False,
                group_by="ticker",
                threads=False,
            )
            if not data.empty:
                return data
        except Exception as exc:
            last_error = exc
        sleep(2 * (attempt + 1))

    if last_error:
        raise RuntimeError(f"行情接口请求失败：{last_error}") from last_error
    raise RuntimeError("行情接口返回空数据。")


def _ticker_frame(data: pd.DataFrame, ticker: str) -> pd.DataFrame:
    if isinstance(data.columns, pd.MultiIndex):
        if ticker not in data.columns.get_level_values(0):
            return pd.DataFrame()
        frame = data[ticker].copy()
    else:
        frame = data.copy()
    frame.index = pd.to_datetime(frame.index).date
    return frame.dropna(how="all")


def _daily_return(data: pd.DataFrame, ticker: str, trade_date: date) -> tuple[float, float, int | None]:
    frame = _ticker_frame(data, ticker)
    if frame.empty or trade_date not in frame.index:
        raise RuntimeError(f"{ticker} 缺少 {trade_date.isoformat()} 的收盘数据。")

    frame = frame.sort_index()
    pos = list(frame.index).index(trade_date)
    if pos == 0:
        raise RuntimeError(f"{ticker} 缺少前一交易日数据，无法计算涨跌幅。")

    close = float(frame.iloc[pos]["Close"])
    prev_close = float(frame.iloc[pos - 1]["Close"])
    if pd.isna(close) or pd.isna(prev_close) or prev_close <= 0:
        raise RuntimeError(f"{ticker} 收盘价数据不完整。")

    volume = None
    if "Volume" in frame.columns and not pd.isna(frame.iloc[pos]["Volume"]):
        volume = int(frame.iloc[pos]["Volume"])
    return close, (close / prev_close - 1) * 100, volume


def _clean_float(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _clean_int(value: Any) -> int | None:
    if value is None or pd.isna(value):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _get_ticker_info(ticker: str) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            instrument = yf.Ticker(ticker)
            if hasattr(instrument, "get_info"):
                return instrument.get_info()
            return instrument.info
        except Exception as exc:
            last_error = exc
            sleep(2 * (attempt + 1))
    print(f"Warning: failed to fetch fundamentals for {ticker}: {last_error}")
    return {}


def _enrich_with_fundamentals(stocks: list[StockMove]) -> list[StockMove]:
    enriched: list[StockMove] = []
    for stock in stocks:
        info = _get_ticker_info(stock.ticker)
        enriched.append(
            StockMove(
                ticker=stock.ticker,
                company=stock.company,
                close=stock.close,
                change_pct=stock.change_pct,
                volume=stock.volume,
                market_cap=_clean_int(info.get("marketCap")),
                trailing_pe=_clean_float(info.get("trailingPE")),
                forward_pe=_clean_float(info.get("forwardPE")),
                beta=_clean_float(info.get("beta")),
                dividend_yield=_clean_float(info.get("dividendYield")),
                fifty_two_week_high=_clean_float(info.get("fiftyTwoWeekHigh")),
                fifty_two_week_low=_clean_float(info.get("fiftyTwoWeekLow")),
            )
        )
    return enriched


def build_sector_report(trade_date: date) -> SectorReport:
    etf_tickers = list(SECTOR_ETFS.values())
    etf_data = _download_daily(etf_tickers, trade_date)

    sector_returns: list[tuple[str, str, float]] = []
    for sector, etf in SECTOR_ETFS.items():
        _, return_pct, _ = _daily_return(etf_data, etf, trade_date)
        sector_returns.append((sector, etf, return_pct))

    if len(sector_returns) != len(SECTOR_ETFS):
        raise RuntimeError("板块 ETF 数据不完整。")

    sector, etf, sector_return_pct = max(sector_returns, key=lambda item: item[2])

    constituents = get_sp500_constituents()
    sector_stocks = constituents[constituents["GICS Sector"] == sector].copy()
    if sector_stocks.empty:
        raise RuntimeError(f"没有找到 {sector} 板块的 S&P 500 成分股。")

    tickers = sector_stocks["Symbol"].tolist()
    stock_data = _download_daily(tickers, trade_date)

    moves: list[StockMove] = []
    errors: list[str] = []
    company_by_ticker = dict(zip(sector_stocks["Symbol"], sector_stocks["Security"]))
    for ticker in tickers:
        try:
            close, change_pct, volume = _daily_return(stock_data, ticker, trade_date)
        except RuntimeError as exc:
            errors.append(str(exc))
            continue
        moves.append(
            StockMove(
                ticker=ticker,
                company=company_by_ticker[ticker],
                close=close,
                change_pct=change_pct,
                volume=volume,
            )
        )

    if len(moves) < 5:
        detail = "; ".join(errors[:5])
        raise RuntimeError(f"{sector} 板块有效个股数据不足 5 只。{detail}")

    top_stocks = sorted(moves, key=lambda item: item.change_pct, reverse=True)[:5]

    return SectorReport(
        trade_date=trade_date,
        sector=sector,
        sector_cn=SECTOR_CN.get(sector, sector),
        sector_etf=etf,
        sector_return_pct=sector_return_pct,
        top_stocks=_enrich_with_fundamentals(top_stocks),
    )
