from __future__ import annotations

import html
import smtplib
from email.message import EmailMessage

from .config import Settings
from .market import SectorReport


def _fmt_pct(value: float) -> str:
    return f"{value:+.2f}%"


def _fmt_price(value: float) -> str:
    return f"${value:,.2f}"


def _fmt_optional_float(value: float | None, digits: int = 2) -> str:
    if value is None:
        return "N/A"
    return f"{value:.{digits}f}"


def _fmt_optional_pct(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value * 100:.2f}%"


def _fmt_large_number(value: int | None) -> str:
    if value is None:
        return "N/A"
    if abs(value) >= 1_000_000_000_000:
        return f"${value / 1_000_000_000_000:.2f}T"
    if abs(value) >= 1_000_000_000:
        return f"${value / 1_000_000_000:.2f}B"
    if abs(value) >= 1_000_000:
        return f"${value / 1_000_000:.2f}M"
    return f"${value:,.0f}"


def _fmt_volume(value: int | None) -> str:
    if value is None:
        return "N/A"
    if value >= 1_000_000:
        return f"{value / 1_000_000:.2f}M"
    if value >= 1_000:
        return f"{value / 1_000:.2f}K"
    return f"{value:,}"


def _fmt_52w_range(low: float | None, high: float | None) -> str:
    if low is None or high is None:
        return "N/A"
    return f"${low:.2f} - ${high:.2f}"


def build_success_email(report: SectorReport) -> tuple[str, str, str]:
    subject = f"美股收盘板块日报 | {report.trade_date.isoformat()} | 最强：{report.sector_cn}"
    rows = "\n".join(
        f"""
        <tr>
          <td>{html.escape(stock.ticker)}</td>
          <td>{html.escape(stock.company)}</td>
          <td style="text-align:right;">{_fmt_price(stock.close)}</td>
          <td style="text-align:right;color:#0f7b3f;">{_fmt_pct(stock.change_pct)}</td>
          <td style="text-align:right;">{_fmt_large_number(stock.market_cap)}</td>
          <td style="text-align:right;">{_fmt_optional_float(stock.trailing_pe)}</td>
          <td style="text-align:right;">{_fmt_optional_float(stock.forward_pe)}</td>
          <td style="text-align:right;">{_fmt_optional_float(stock.beta)}</td>
          <td style="text-align:right;">{_fmt_optional_pct(stock.dividend_yield)}</td>
          <td style="text-align:right;">{_fmt_52w_range(stock.fifty_two_week_low, stock.fifty_two_week_high)}</td>
          <td style="text-align:right;">{_fmt_volume(stock.volume)}</td>
        </tr>
        """
        for stock in report.top_stocks
    )
    leader = report.top_stocks[0]
    summary = (
        f"{report.trade_date.isoformat()} 美股主要板块中，{report.sector_cn}"
        f"（{report.sector_etf}）表现最强，板块涨幅为 {_fmt_pct(report.sector_return_pct)}。"
        f"该板块内 {leader.company}（{leader.ticker}）领涨，单日涨幅 {_fmt_pct(leader.change_pct)}。"
    )

    text = "\n".join(
        [
            f"日期：{report.trade_date.isoformat()}",
            f"当天最强板块：{report.sector_cn}（{report.sector} / {report.sector_etf}）",
            f"板块涨幅：{_fmt_pct(report.sector_return_pct)}",
            "",
            "前五只股票：",
            *[
                (
                    f"{idx}. {stock.ticker} | {stock.company} | 收盘价 {_fmt_price(stock.close)} "
                    f"| 当日涨幅 {_fmt_pct(stock.change_pct)} | 市值 {_fmt_large_number(stock.market_cap)} "
                    f"| Trailing PE {_fmt_optional_float(stock.trailing_pe)} "
                    f"| Forward PE {_fmt_optional_float(stock.forward_pe)} | Beta {_fmt_optional_float(stock.beta)} "
                    f"| 股息率 {_fmt_optional_pct(stock.dividend_yield)} "
                    f"| 52周区间 {_fmt_52w_range(stock.fifty_two_week_low, stock.fifty_two_week_high)} "
                    f"| 成交量 {_fmt_volume(stock.volume)}"
                )
                for idx, stock in enumerate(report.top_stocks, start=1)
            ],
            "",
            f"简短总结：{summary}",
        ]
    )

    html_body = f"""
    <html>
      <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; color:#1f2937;">
        <h2>美股每日收盘后板块涨幅报告</h2>
        <p><strong>日期：</strong>{report.trade_date.isoformat()}</p>
        <p><strong>当天最强板块：</strong>{html.escape(report.sector_cn)}（{html.escape(report.sector)} / {report.sector_etf}）</p>
        <p><strong>板块涨幅：</strong><span style="color:#0f7b3f;">{_fmt_pct(report.sector_return_pct)}</span></p>
        <table cellpadding="8" cellspacing="0" border="1" style="border-collapse:collapse;border-color:#d1d5db;">
          <thead style="background:#f3f4f6;">
            <tr>
              <th>股票代码</th>
              <th>公司名</th>
              <th>收盘价</th>
              <th>当日涨幅</th>
              <th>市值</th>
              <th>Trailing PE</th>
              <th>Forward PE</th>
              <th>Beta</th>
              <th>股息率</th>
              <th>52周区间</th>
              <th>成交量</th>
            </tr>
          </thead>
          <tbody>{rows}</tbody>
        </table>
        <p><strong>简短总结：</strong>{html.escape(summary)}</p>
      </body>
    </html>
    """
    return subject, text, html_body


def build_error_email(error: Exception) -> tuple[str, str, str]:
    subject = "美股收盘板块日报 | 异常提醒"
    text = f"美股每日收盘后板块涨幅邮件系统运行失败。\n\n异常信息：{error}"
    html_body = f"""
    <html>
      <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; color:#1f2937;">
        <h2>美股板块日报异常提醒</h2>
        <p>系统未能生成正常日报，可能原因包括当天休市、收盘数据尚未完整、行情 API 报错或 SMTP 配置异常。</p>
        <p><strong>异常信息：</strong>{html.escape(str(error))}</p>
      </body>
    </html>
    """
    return subject, text, html_body


def send_email(settings: Settings, subject: str, text: str, html_body: str) -> None:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.mail_from
    msg["To"] = ", ".join(settings.mail_to)
    if settings.mail_cc:
        msg["Cc"] = ", ".join(settings.mail_cc)

    msg.set_content(text)
    msg.add_alternative(html_body, subtype="html")

    recipients = settings.mail_to + settings.mail_cc
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as server:
        server.ehlo()
        server.starttls()
        server.login(settings.smtp_username, settings.smtp_password)
        server.send_message(msg, to_addrs=recipients)
