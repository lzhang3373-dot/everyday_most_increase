# 美股每日收盘后板块涨幅邮件系统

这是一个 Python 自动邮件系统，会在美股收盘后获取主要板块当日涨跌幅，找出当天最强板块，并列出该板块内 S&P 500 成分股中当日涨幅最大的前 5 只股票及关键基本面指标。

## 功能

- 每天美股收盘后运行一次
- 使用 SPDR 主要板块 ETF 判断最强板块
- 使用 S&P 500 同 GICS 板块成分股筛选前 5 只领涨股票
- 前 5 只股票展示收盘价、当日涨幅、市值、Trailing PE、Forward PE、Beta、股息率、52 周区间和成交量
- 生成中文 HTML + 纯文本邮件
- 通过 SMTP 发送日报
- 如果当天休市、数据未完整、行情接口报错或其他异常，会发送异常提醒邮件
- 支持本地 `.env` 和 GitHub Actions Secrets

## 安装

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 配置

复制配置模板：

```bash
cp .env.example .env
```

填写 `.env`：

```ini
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email@example.com
SMTP_PASSWORD=your_app_password
MAIL_FROM=your_email@example.com
MAIL_TO=receiver@example.com
MAIL_CC=
TIMEZONE=America/New_York
DATA_DELAY_MINUTES=45
```

如果使用 Gmail，建议使用 App Password，不要使用邮箱登录密码。

## 本地运行

正常运行：

```bash
python3 main.py
```

指定日期测试：

```bash
TARGET_DATE=2026-05-15 python3 main.py
```

注意：指定日期时仍会尝试发送邮件。

## GitHub Actions Secrets

在 GitHub 仓库中进入 `Settings` -> `Secrets and variables` -> `Actions`，添加：

- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `MAIL_FROM`
- `MAIL_TO`
- `MAIL_CC`（可选）

## 数据来源说明

- 板块表现：使用 11 只 SPDR Select Sector ETF：
  - XLC、XLY、XLP、XLE、XLF、XLV、XLI、XLK、XLB、XLRE、XLU
- 个股池：Wikipedia 的 S&P 500 成分股列表
- 行情和基本面数据：Yahoo Finance，经 `yfinance` 获取

## 定时策略

GitHub Actions 的 `Scheduled US Sector Email` workflow 设置为美国工作日 UTC 23:17 运行。这个时间覆盖美股夏令时和冬令时的正常收盘后窗口。脚本内部会再次检查 NYSE 是否交易、是否已经过了配置的收盘后数据延迟时间。
