from __future__ import annotations

import csv
import http.client
import json
import math
import re
import statistics
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


AS_OF_DATE = "2026-06-28"
TARGET_DIR = Path("data_raw/generated_research/roe_gt10_2026_06_28")
TARGET_EQUITY_EXPOSURE = 55.0
MAX_SINGLE_WEIGHT = 6.0
MAX_INDUSTRY_WEIGHT = 15.0

STOCKS = [
    ("000423", "东阿阿胶"),
    ("000426", "兴业银锡"),
    ("000526", "学大教育"),
    ("000534", "万泽股份"),
    ("000682", "东方电子"),
    ("000999", "华润三九"),
    ("001221", "悍高集团"),
    ("001359", "平安电工"),
    ("001389", "广合科技"),
    ("002130", "沃尔核材"),
    ("002138", "顺络电子"),
    ("002371", "北方华创"),
    ("002463", "沪电股份"),
    ("002595", "豪迈科技"),
    ("002827", "高争民爆"),
    ("002832", "比音勒芬"),
    ("002847", "盐津铺子"),
    ("002880", "卫光生物"),
    ("002895", "川恒股份"),
    ("002947", "恒铭达"),
    ("002979", "雷赛智能"),
    ("003006", "百亚股份"),
    ("600276", "恒瑞医药"),
    ("600285", "羚锐制药"),
    ("600660", "福耀玻璃"),
    ("600809", "山西汾酒"),
    ("600885", "宏发股份"),
    ("600988", "赤峰黄金"),
    ("601126", "四方股份"),
    ("603025", "大豪科技"),
    ("603040", "新坐标"),
    ("603088", "宁波精达"),
    ("603099", "长白山"),
    ("603119", "浙江荣泰"),
    ("603170", "宝立食品"),
    ("603193", "润本股份"),
    ("603199", "九华旅游"),
    ("603338", "浙江鼎力"),
    ("603699", "纽威股份"),
    ("603979", "金诚信"),
    ("605016", "百龙创园"),
    ("605116", "奥锐特"),
    ("605117", "德业股份"),
    ("605499", "东鹏饮料"),
]


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0 Safari/537.36",
}

EASTMONEY_HEADERS = {
    **HEADERS,
    "Referer": "https://emweb.securities.eastmoney.com/",
}

QUOTE_HEADERS = {
    **HEADERS,
    "Referer": "https://quote.eastmoney.com/",
}

CNINFO_HEADERS = {
    **HEADERS,
    "Referer": "http://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/search",
    "Content-Type": "application/x-www-form-urlencoded",
}


@dataclass
class StockResearch:
    code: str
    name: str
    finance_rows: list[dict[str, Any]] = field(default_factory=list)
    profile: dict[str, Any] = field(default_factory=dict)
    quote: dict[str, Any] = field(default_factory=dict)
    klines: list[dict[str, Any]] = field(default_factory=list)
    announcements: list[dict[str, Any]] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    score_parts: dict[str, float] = field(default_factory=dict)
    score: float = 0.0
    rating: str = ""
    suggested_range: str = ""
    portfolio_weight: float = 0.0
    warnings: list[str] = field(default_factory=list)


def market_suffix(code: str) -> str:
    return "SH" if code.startswith("6") else "SZ"


def secid(code: str) -> str:
    prefix = "1" if code.startswith("6") else "0"
    return f"{prefix}.{code}"


def quote_page_url(code: str) -> str:
    return f"https://quote.eastmoney.com/{market_suffix(code).lower()}{code}.html"


def f10_finance_url(code: str) -> str:
    query = urllib.parse.urlencode(
        {
            "reportName": "RPT_F10_FINANCE_MAINFINADATA",
            "columns": "ALL",
            "filter": f'(SECUCODE="{code}.{market_suffix(code)}")',
            "pageNumber": "1",
            "pageSize": "12",
            "sortTypes": "-1",
            "sortColumns": "REPORT_DATE",
            "source": "HSF10",
            "client": "PC",
        }
    )
    return f"https://datacenter.eastmoney.com/securities/api/data/v1/get?{query}"


def request_json(
    url: str,
    headers: dict[str, str] | None = None,
    data: bytes | None = None,
    timeout: int = 12,
) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            req = urllib.request.Request(url, headers=headers or HEADERS, data=data)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
            return json.loads(raw)
        except http.client.IncompleteRead as exc:
            last_error = exc
            partial = exc.partial.decode("utf-8", errors="replace") if exc.partial else ""
            if partial.strip():
                try:
                    return json.loads(partial)
                except json.JSONDecodeError:
                    pass
        except Exception as exc:
            last_error = exc
        if attempt < 3:
            time.sleep(0.8 * attempt)
    assert last_error is not None
    raise last_error


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists() or path.name.endswith("_error.json"):
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def parse_finance_raw(data: dict[str, Any]) -> list[dict[str, Any]]:
    return ((data.get("result") or {}).get("data") or []) if data else []


def fetch_finance(code: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    data = request_json(f10_finance_url(code), EASTMONEY_HEADERS)
    return parse_finance_raw(data), data


def parse_profile_raw(data: dict[str, Any]) -> dict[str, Any]:
    rows = ((data.get("result") or {}).get("data") or []) if data else []
    return rows[0] if rows else {}


def fetch_profile(code: str) -> tuple[dict[str, Any], dict[str, Any]]:
    query = urllib.parse.urlencode(
        {
            "reportName": "RPT_F10_ORG_BASICINFO",
            "columns": "ALL",
            "filter": f'(SECUCODE="{code}.{market_suffix(code)}")',
            "pageNumber": "1",
            "pageSize": "1",
            "source": "HSF10",
            "client": "PC",
        }
    )
    url = f"https://datacenter.eastmoney.com/securities/api/data/v1/get?{query}"
    data = request_json(url, EASTMONEY_HEADERS)
    return parse_profile_raw(data), data


def parse_quote_raw(data: dict[str, Any]) -> dict[str, Any]:
    raw = data.get("data") or {}

    def div100(key: str) -> float | None:
        value = raw.get(key)
        if isinstance(value, (int, float)):
            return value / 100
        return None

    quote = {
        "price": div100("f43"),
        "prev_close": div100("f60"),
        "pct_chg": div100("f170"),
        "market_cap": raw.get("f116") if isinstance(raw.get("f116"), (int, float)) else None,
        "float_market_cap": raw.get("f117") if isinstance(raw.get("f117"), (int, float)) else None,
        "pe_ttm": div100("f162"),
        "pe_static": div100("f163"),
        "pb": div100("f167"),
        "ps": div100("f168"),
        "roe_latest": raw.get("f173") if isinstance(raw.get("f173"), (int, float)) else None,
        "quote_fin_revenue": raw.get("f183") if isinstance(raw.get("f183"), (int, float)) else None,
        "quote_fin_revenue_yoy": raw.get("f184") if isinstance(raw.get("f184"), (int, float)) else None,
        "quote_fin_profit_yoy": raw.get("f185") if isinstance(raw.get("f185"), (int, float)) else None,
        "quote_fin_gross_margin": raw.get("f186") if isinstance(raw.get("f186"), (int, float)) else None,
    }
    return quote


def fetch_quote(code: str) -> tuple[dict[str, Any], dict[str, Any]]:
    fields = ",".join(
        [
            "f43",
            "f44",
            "f45",
            "f46",
            "f48",
            "f57",
            "f58",
            "f60",
            "f116",
            "f117",
            "f162",
            "f163",
            "f167",
            "f168",
            "f170",
            "f173",
            "f183",
            "f184",
            "f185",
            "f186",
        ]
    )
    query = urllib.parse.urlencode({"secid": secid(code), "fields": fields})
    url = f"https://push2.eastmoney.com/api/qt/stock/get?{query}"
    data = request_json(url, QUOTE_HEADERS)
    quote = parse_quote_raw(data)
    return quote, data


def parse_klines_raw(data: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for line in ((data.get("data") or {}).get("klines") or []):
        parts = line.split(",")
        if len(parts) < 11:
            continue
        try:
            rows.append(
                {
                    "date": parts[0],
                    "open": float(parts[1]),
                    "close": float(parts[2]),
                    "high": float(parts[3]),
                    "low": float(parts[4]),
                    "volume": float(parts[5]),
                    "amount": float(parts[6]),
                    "amplitude": float(parts[7]),
                    "pct_chg": float(parts[8]),
                    "change": float(parts[9]),
                    "turnover": float(parts[10]),
                }
            )
        except ValueError:
            continue
    return rows


def fetch_klines(code: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    query = urllib.parse.urlencode(
        {
            "secid": secid(code),
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
            "klt": "101",
            "fqt": "1",
            "beg": "20250101",
            "end": AS_OF_DATE.replace("-", ""),
        }
    )
    url = f"https://push2his.eastmoney.com/api/qt/stock/kline/get?{query}"
    data = request_json(url, QUOTE_HEADERS)
    rows = parse_klines_raw(data)
    return rows, data


def fetch_cninfo_stock_list() -> dict[str, dict[str, Any]]:
    url = "http://www.cninfo.com.cn/new/data/szse_stock.json"
    data = request_json(url, {**HEADERS, "Referer": "http://www.cninfo.com.cn/"})
    return {item.get("code"): item for item in data.get("stockList", [])}


def fetch_announcements(code: str, org_id: str | None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not org_id:
        return [], {"error": "missing cninfo orgId"}
    column = "sse" if code.startswith("6") else "szse"
    plate = "sh" if code.startswith("6") else "sz"
    params = {
        "pageNum": "1",
        "pageSize": "12",
        "column": column,
        "tabName": "fulltext",
        "plate": plate,
        "stock": f"{code},{org_id}",
        "searchkey": "",
        "secid": "",
        "category": "category_ndbg_szsh;category_yjdbg_szsh;category_sjdbg_szsh",
        "trade": "",
        "seDate": f"2025-01-01~{AS_OF_DATE}",
        "sortName": "",
        "sortType": "",
        "isHLtitle": "true",
    }
    encoded = urllib.parse.urlencode(params).encode("utf-8")
    url = "http://www.cninfo.com.cn/new/hisAnnouncement/query"
    data = request_json(url, CNINFO_HEADERS, encoded)
    return data.get("announcements") or [], data


def n(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if math.isnan(float(value)):
            return None
        return float(value)
    try:
        return float(str(value).replace(",", ""))
    except ValueError:
        return None


def clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def get_latest(rows: list[dict[str, Any]], report_type: str | None = None) -> dict[str, Any] | None:
    for row in rows:
        if report_type is None or row.get("REPORT_TYPE") == report_type:
            return row
    return None


def annual_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected = [row for row in rows if row.get("REPORT_TYPE") == "年报"]
    return sorted(selected, key=lambda x: x.get("REPORT_DATE") or "")


def yoy_points(value: float | None, max_points: float) -> float:
    if value is None:
        return max_points * 0.35
    if value <= -30:
        return 0
    if value <= -10:
        return max_points * 0.15
    if value <= 0:
        return max_points * 0.35
    if value <= 10:
        return max_points * 0.55
    if value <= 25:
        return max_points * 0.75
    if value <= 50:
        return max_points * 0.9
    return max_points


def calc_trend_metrics(klines: list[dict[str, Any]]) -> dict[str, Any]:
    if not klines:
        return {}
    closes = [row["close"] for row in klines]
    highs = [row["high"] for row in klines]
    daily_returns = [
        closes[i] / closes[i - 1] - 1 for i in range(1, len(closes)) if closes[i - 1] > 0
    ]

    def period_return(days: int) -> float | None:
        if len(closes) <= days or closes[-days - 1] <= 0:
            return None
        return (closes[-1] / closes[-days - 1] - 1) * 100

    def moving_average(days: int) -> float | None:
        if len(closes) < days:
            return None
        return sum(closes[-days:]) / days

    recent_high = max(highs[-120:]) if len(highs) >= 1 else None
    drawdown = (closes[-1] / recent_high - 1) * 100 if recent_high else None
    vol = None
    if len(daily_returns) >= 20:
        sample = daily_returns[-60:] if len(daily_returns) >= 60 else daily_returns
        vol = statistics.pstdev(sample) * math.sqrt(252) * 100

    return {
        "last_trade_date": klines[-1]["date"],
        "close": closes[-1],
        "return_20d": period_return(20),
        "return_60d": period_return(60),
        "return_120d": period_return(120),
        "drawdown_120d_high": drawdown,
        "volatility_60d_ann": vol,
        "ma20": moving_average(20),
        "ma60": moving_average(60),
        "above_ma60": closes[-1] > moving_average(60) if moving_average(60) else None,
    }


def score_stock(stock: StockResearch) -> None:
    annuals = annual_rows(stock.finance_rows)
    latest_annual = annuals[-1] if annuals else {}
    latest_period = get_latest(stock.finance_rows) or {}
    q1 = latest_period if latest_period.get("REPORT_TYPE") != "年报" else {}
    trend = calc_trend_metrics(stock.klines)

    roe_values = [n(row.get("ROEJQ")) for row in annuals[-3:]]
    roe_values = [value for value in roe_values if value is not None]
    avg_roe = sum(roe_values) / len(roe_values) if roe_values else None
    latest_roe = n(latest_annual.get("ROEJQ"))
    gross_margin = n(latest_annual.get("XSMLL"))
    net_margin = n(latest_annual.get("XSJLL"))

    quality = 0.0
    if avg_roe is not None:
        quality += clip((avg_roe - 8) / 17 * 18, 0, 18)
    if latest_roe is not None:
        quality += clip((latest_roe - 10) / 18 * 5, 0, 5)
    if gross_margin is not None:
        quality += 4 if gross_margin >= 45 else 3 if gross_margin >= 30 else 1.5 if gross_margin >= 20 else 0.5
    if net_margin is not None:
        quality += 3 if net_margin >= 18 else 2 if net_margin >= 10 else 0.8 if net_margin >= 5 else 0
    quality = clip(quality, 0, 30)

    growth = 0.0
    growth += yoy_points(n(latest_annual.get("TOTALOPERATEREVETZ")), 5)
    growth += yoy_points(n(latest_annual.get("PARENTNETPROFITTZ")), 6)
    growth += yoy_points(n(q1.get("TOTALOPERATEREVETZ")), 6)
    growth += yoy_points(n(q1.get("PARENTNETPROFITTZ")), 8)
    growth = clip(growth, 0, 25)

    cash = 0.0
    cfo_np = n(latest_annual.get("NCO_NETPROFIT"))
    debt = n(latest_annual.get("ZCFZL"))
    current_ratio = n(latest_annual.get("LD"))
    if cfo_np is not None:
        cash += 8 if cfo_np >= 1.0 else 6 if cfo_np >= 0.75 else 4 if cfo_np >= 0.45 else 1.5 if cfo_np >= 0 else 0
    if debt is not None:
        cash += 5 if debt <= 35 else 4 if debt <= 50 else 2 if debt <= 65 else 0.5
    if current_ratio is not None:
        cash += 2 if current_ratio >= 1.5 else 1 if current_ratio >= 1 else 0
    cash = clip(cash, 0, 15)

    pe = n(stock.quote.get("pe_ttm"))
    pb = n(stock.quote.get("pb"))
    valuation = 0.0
    if pe is None or pe <= 0:
        valuation += 5
    elif pe < 15:
        valuation += 11
    elif pe < 25:
        valuation += 10
    elif pe < 40:
        valuation += 8
    elif pe < 60:
        valuation += 5.5
    elif pe < 90:
        valuation += 3.5
    else:
        valuation += 2
    q1_profit_yoy = n(q1.get("PARENTNETPROFITTZ"))
    if q1_profit_yoy is not None and q1_profit_yoy > 30:
        valuation += 2
    if q1_profit_yoy is not None and q1_profit_yoy < -10:
        valuation -= 2
    if pb is not None:
        valuation += 2 if pb < 2 else 1 if pb < 4 else -1 if pb > 8 else 0
    valuation = clip(valuation, 0, 15)

    momentum = 0.0
    r60 = n(trend.get("return_60d"))
    r120 = n(trend.get("return_120d"))
    drawdown = n(trend.get("drawdown_120d_high"))
    volatility = n(trend.get("volatility_60d_ann"))
    if r60 is not None:
        momentum += 4 if r60 > 10 else 3 if r60 > 0 else 1.5 if r60 > -10 else 0
    if r120 is not None:
        momentum += 5 if 0 <= r120 <= 50 else 3.5 if r120 > 50 else 2 if r120 > -15 else 0.5
    if drawdown is not None:
        momentum += 3 if drawdown >= -8 else 2 if drawdown >= -15 else 1 if drawdown >= -25 else 0
    if volatility is not None:
        momentum += 2 if volatility <= 35 else 1 if volatility <= 55 else 0
    if trend.get("above_ma60") is True:
        momentum += 1
    momentum = clip(momentum, 0, 15)

    total = quality + growth + cash + valuation + momentum
    risk_penalty = 0.0
    if pe is not None:
        risk_penalty += 2.0 if pe > 60 else 1.0 if pe > 50 else 0.0
    if pb is not None:
        risk_penalty += 3.0 if pb > 10 else 1.0 if pb > 8 else 0.0
    if r120 is not None:
        risk_penalty += 6.0 if r120 > 120 else 4.0 if r120 > 80 else 1.0 if r120 > 50 else 0.0
    if pe is not None and pb is not None and r120 is not None and pe > 50 and pb > 8 and r120 > 80:
        risk_penalty += 4.0
    total = clip(total - risk_penalty, 0, 100)
    if total >= 82:
        rating = "A：重点候选"
        suggested_range = "4%-6%"
    elif total >= 76:
        rating = "A-：可纳入候选"
        suggested_range = "3%-5%"
    elif total >= 70:
        rating = "B+：可小仓配置/等待回调"
        suggested_range = "1.5%-3%"
    elif total >= 62:
        rating = "B：观察仓"
        suggested_range = "0%-1.5%"
    else:
        rating = "C：暂不配置"
        suggested_range = "0%"

    stock.metrics = {
        "latest_annual": latest_annual,
        "latest_period": latest_period,
        "q1": q1,
        "annuals": annuals[-3:],
        "avg_roe_3y": avg_roe,
        "trend": trend,
        "industry": stock.profile.get("BOARD_NAME_1LEVEL")
        or stock.profile.get("EM2016")
        or stock.profile.get("CSRC_INDUSTRY_NAME")
        or "未知",
        "sector_detail": stock.profile.get("BOARD_NAME_2LEVEL") or stock.profile.get("EM2016") or "未知",
    }
    stock.score_parts = {
        "质量": round(quality, 1),
        "成长": round(growth, 1),
        "现金负债": round(cash, 1),
        "估值": round(valuation, 1),
        "走势": round(momentum, 1),
    }
    if risk_penalty > 0:
        stock.score_parts["风险扣分"] = -round(risk_penalty, 1)
    stock.score = round(total, 1)
    stock.rating = rating
    stock.suggested_range = suggested_range

    if len(annuals) < 3:
        stock.warnings.append("上市或可得年报数据不足三年，三年均值参考意义下降。")
    if q1 and n(q1.get("PARENTNETPROFITTZ")) is not None and n(q1.get("PARENTNETPROFITTZ")) < -10:
        stock.warnings.append("最近一期归母净利润同比下滑超过 10%，需要等待后续报告确认。")
    if pe is not None and pe > 60:
        stock.warnings.append("PE(TTM) 高于 60 倍，半年维度需要重视估值回撤风险。")
    if pb is not None and pb > 8:
        stock.warnings.append("PB 高于 8 倍，市场已经给出较高成长预期。")
    if r120 is not None and r120 > 80:
        stock.warnings.append("近 120 日涨幅超过 80%，不适合用重仓方式追高。")
    if drawdown is not None and drawdown < -25:
        stock.warnings.append("股价较 120 日高点回撤超过 25%，趋势修复前不宜重仓。")


def allocate_portfolio(stocks: list[StockResearch]) -> None:
    industry_used: dict[str, float] = {}
    selected = [stock for stock in sorted(stocks, key=lambda s: s.score, reverse=True) if stock.score >= 70]
    for stock in selected:
        if stock.score >= 82:
            base = 5.5
        elif stock.score >= 78:
            base = 4.5
        elif stock.score >= 74:
            base = 3.5
        else:
            base = 2.5
        base = min(base, MAX_SINGLE_WEIGHT)
        industry = stock.metrics.get("industry") or "未知"
        available = max(0.0, MAX_INDUSTRY_WEIGHT - industry_used.get(industry, 0.0))
        weight = min(base, available)
        if sum(s.portfolio_weight for s in stocks) + weight > TARGET_EQUITY_EXPOSURE:
            weight = max(0.0, TARGET_EQUITY_EXPOSURE - sum(s.portfolio_weight for s in stocks))
        stock.portfolio_weight = round(weight, 1)
        industry_used[industry] = industry_used.get(industry, 0.0) + stock.portfolio_weight
        if sum(s.portfolio_weight for s in stocks) >= TARGET_EQUITY_EXPOSURE:
            break


def fmt_num(value: Any, digits: int = 2, suffix: str = "") -> str:
    value = n(value)
    if value is None:
        return "-"
    return f"{value:.{digits}f}{suffix}"


def fmt_pct(value: Any) -> str:
    return fmt_num(value, 2, "%")


def fmt_money(value: Any) -> str:
    value = n(value)
    if value is None:
        return "-"
    sign = "-" if value < 0 else ""
    value = abs(value)
    if value >= 1e8:
        return f"{sign}{value / 1e8:.2f}亿"
    if value >= 1e4:
        return f"{sign}{value / 1e4:.2f}万"
    return f"{sign}{value:.2f}"


def fmt_date(value: Any) -> str:
    if not value:
        return "-"
    return str(value).split(" ")[0]


def clean_title(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text or "")
    return text.replace("*", "").strip()


def cninfo_pdf_url(adjunct_url: str | None) -> str | None:
    if not adjunct_url:
        return None
    return "http://static.cninfo.com.cn/" + adjunct_url.lstrip("/")


def sentence_growth(stock: StockResearch) -> str:
    annual = stock.metrics.get("latest_annual") or {}
    q1 = stock.metrics.get("q1") or {}
    revenue_yoy = n(q1.get("TOTALOPERATEREVETZ"))
    profit_yoy = n(q1.get("PARENTNETPROFITTZ"))
    annual_profit_yoy = n(annual.get("PARENTNETPROFITTZ"))
    if revenue_yoy is None and profit_yoy is None:
        return "最新季度增长数据缺失，半年视角以年报质量和后续公告为主。"
    if profit_yoy is not None and profit_yoy > 30:
        return f"最新季度归母净利润同比 {fmt_pct(profit_yoy)}，短期成长弹性强，但需要确认高增长能否延续。"
    if profit_yoy is not None and profit_yoy > 10:
        return f"最新季度归母净利润同比 {fmt_pct(profit_yoy)}，成长仍处在较健康区间。"
    if profit_yoy is not None and profit_yoy < 0:
        return f"最新季度归母净利润同比 {fmt_pct(profit_yoy)}，短期基本面动能偏弱；2025 年报利润同比为 {fmt_pct(annual_profit_yoy)}。"
    return f"最新季度营收同比 {fmt_pct(revenue_yoy)}、归母净利润同比 {fmt_pct(profit_yoy)}，增长中性。"


def sentence_quality(stock: StockResearch) -> str:
    annual = stock.metrics.get("latest_annual") or {}
    avg_roe = stock.metrics.get("avg_roe_3y")
    roe = n(annual.get("ROEJQ"))
    gross = n(annual.get("XSMLL"))
    debt = n(annual.get("ZCFZL"))
    return (
        f"近三年年报 ROE 均值 {fmt_pct(avg_roe)}，2025 年 ROE {fmt_pct(roe)}；"
        f"毛利率 {fmt_pct(gross)}，资产负债率 {fmt_pct(debt)}。"
    )


def sentence_cash(stock: StockResearch) -> str:
    annual = stock.metrics.get("latest_annual") or {}
    cfo = n(annual.get("NETCASH_OPERATE_PK"))
    np = n(annual.get("PARENTNETPROFIT"))
    ratio = n(annual.get("NCO_NETPROFIT"))
    if ratio is None:
        return f"2025 年经营现金流 {fmt_money(cfo)}，归母净利润 {fmt_money(np)}，现金流匹配度需继续跟踪。"
    if ratio >= 1:
        return f"2025 年经营现金流/净利润约 {fmt_num(ratio, 2)}，利润含金量较好。"
    if ratio >= 0.6:
        return f"2025 年经营现金流/净利润约 {fmt_num(ratio, 2)}，现金流基本可接受。"
    return f"2025 年经营现金流/净利润约 {fmt_num(ratio, 2)}，利润现金转化偏弱。"


def sentence_valuation(stock: StockResearch) -> str:
    pe = stock.quote.get("pe_ttm")
    pb = stock.quote.get("pb")
    trend = stock.metrics.get("trend") or {}
    r120 = trend.get("return_120d")
    dd = trend.get("drawdown_120d_high")
    if n(pe) is not None and n(pe) > 60:
        val = "估值偏贵，适合等业绩兑现或回调后再提高仓位"
    elif n(pe) is not None and n(pe) < 25:
        val = "估值相对温和，若基本面未恶化可关注性价比"
    else:
        val = "估值处在中性区间，需要结合增长持续性判断"
    return f"PE(TTM) {fmt_num(pe, 2)}、PB {fmt_num(pb, 2)}；近 120 日涨跌幅 {fmt_pct(r120)}、较 120 日高点回撤 {fmt_pct(dd)}，{val}。"


def half_year_view(stock: StockResearch) -> str:
    if stock.score >= 82:
        return "财报质量、增长和交易状态综合靠前，半年维度可作为重点候选；更适合分批买入，不追单日急涨。"
    if stock.score >= 76:
        return "基本面表现较好，但可能存在估值或短期波动约束；半年维度适合逢回调配置。"
    if stock.score >= 70:
        return "有配置价值但确定性不够强，适合小仓观察，等待半年报或趋势改善再加仓。"
    if stock.score >= 62:
        return "质量尚可但短期性价比一般，当前以观察为主。"
    return "综合财报、估值和走势后，半年维度暂不建议配置。"


def tracking_plan(stock: StockResearch) -> list[str]:
    q1 = stock.metrics.get("q1") or {}
    annual = stock.metrics.get("latest_annual") or {}
    return [
        f"2026 半年报：重点看营收同比能否维持在 {fmt_pct(n(q1.get('TOTALOPERATEREVETZ')))} 附近或更高。",
        f"利润质量：关注扣非净利润增速、经营现金流/净利润是否不低于 2025 年的 {fmt_num(n(annual.get('NCO_NETPROFIT')), 2)}。",
        "交易纪律：若跌破 60 日均线且基本面无上修，降低仓位；若业绩上修且估值未明显扩张，再考虑加仓。",
    ]


def risk_points(stock: StockResearch) -> list[str]:
    points = list(stock.warnings)
    industry = stock.metrics.get("industry") or "未知"
    pe = n(stock.quote.get("pe_ttm"))
    if industry in {"电子", "电力设备", "机械设备", "计算机"}:
        points.append("成长行业估值弹性大，半年维度受订单、景气度和市场风险偏好影响明显。")
    if industry in {"食品饮料", "医药生物"}:
        points.append("消费/医药类公司需关注终端需求、渠道库存、集采或监管政策变化。")
    if industry in {"有色金属", "基础化工", "煤炭", "石油石化"}:
        points.append("周期类资产需关注商品价格波动和盈利高点回落风险。")
    if pe is not None and pe < 18:
        points.append("低估值不等于低风险，需确认利润没有周期性下行。")
    if not points:
        points.append("若 2026 半年报收入或利润增速明显低于一季报，需要重新评估。")
    return list(dict.fromkeys(points))[:5]


def annual_table(stock: StockResearch) -> str:
    rows = [
        "| 年报 | 营收 | 营收同比 | 归母净利润 | 归母净利同比 | 扣非净利同比 | ROE | 毛利率 | 净利率 | 经营现金流 | 负债率 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in stock.metrics.get("annuals") or []:
        rows.append(
            "| {period} | {rev} | {rev_yoy} | {np} | {np_yoy} | {deduct_yoy} | {roe} | {gross} | {net} | {cfo} | {debt} |".format(
                period=row.get("REPORT_DATE_NAME") or fmt_date(row.get("REPORT_DATE")),
                rev=fmt_money(row.get("TOTALOPERATEREVE")),
                rev_yoy=fmt_pct(row.get("TOTALOPERATEREVETZ")),
                np=fmt_money(row.get("PARENTNETPROFIT")),
                np_yoy=fmt_pct(row.get("PARENTNETPROFITTZ")),
                deduct_yoy=fmt_pct(row.get("KCFJCXSYJLRTZ")),
                roe=fmt_pct(row.get("ROEJQ")),
                gross=fmt_pct(row.get("XSMLL")),
                net=fmt_pct(row.get("XSJLL")),
                cfo=fmt_money(row.get("NETCASH_OPERATE_PK")),
                debt=fmt_pct(row.get("ZCFZL")),
            )
        )
    return "\n".join(rows)


def latest_table(stock: StockResearch) -> str:
    rows = [
        "| 报告期 | 类型 | 披露日 | 营收 | 营收同比 | 归母净利润 | 归母净利同比 | 扣非同比 | ROE | 毛利率 | 净利率 | 经营现金流 | 负债率 |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    candidates = []
    latest_period = stock.metrics.get("latest_period")
    latest_annual = stock.metrics.get("latest_annual")
    if latest_period:
        candidates.append(latest_period)
    if latest_annual and latest_annual is not latest_period:
        candidates.append(latest_annual)
    seen = set()
    for row in candidates:
        key = row.get("REPORT_DATE_NAME")
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            "| {period} | {rtype} | {notice} | {rev} | {rev_yoy} | {np} | {np_yoy} | {deduct_yoy} | {roe} | {gross} | {net} | {cfo} | {debt} |".format(
                period=row.get("REPORT_DATE_NAME") or fmt_date(row.get("REPORT_DATE")),
                rtype=row.get("REPORT_TYPE") or "-",
                notice=fmt_date(row.get("NOTICE_DATE")),
                rev=fmt_money(row.get("TOTALOPERATEREVE")),
                rev_yoy=fmt_pct(row.get("TOTALOPERATEREVETZ")),
                np=fmt_money(row.get("PARENTNETPROFIT")),
                np_yoy=fmt_pct(row.get("PARENTNETPROFITTZ")),
                deduct_yoy=fmt_pct(row.get("KCFJCXSYJLRTZ")),
                roe=fmt_pct(row.get("ROEJQ")),
                gross=fmt_pct(row.get("XSMLL")),
                net=fmt_pct(row.get("XSJLL")),
                cfo=fmt_money(row.get("NETCASH_OPERATE_PK")),
                debt=fmt_pct(row.get("ZCFZL")),
            )
        )
    return "\n".join(rows)


def source_section(stock: StockResearch) -> str:
    lines = [
        f"- 东方财富 F10 财务主数据：[{stock.code}.{market_suffix(stock.code)}]({f10_finance_url(stock.code)})",
        f"- 东方财富行情与 K 线：[{stock.code} {stock.name}]({quote_page_url(stock.code)})",
    ]
    for ann in stock.announcements[:5]:
        title = clean_title(ann.get("announcementTitle"))
        url = cninfo_pdf_url(ann.get("adjunctUrl"))
        date = datetime.fromtimestamp((ann.get("announcementTime") or 0) / 1000).strftime("%Y-%m-%d")
        if url:
            lines.append(f"- 巨潮资讯公告：[{date} {title}]({url})")
    if len(lines) == 2:
        lines.append("- 巨潮资讯公告：未抓到最近年报/季报 PDF 链接，请以交易所与公司公告为准。")
    return "\n".join(lines)


def write_stock_markdown(stock: StockResearch, out_dir: Path) -> None:
    profile = stock.profile
    trend = stock.metrics.get("trend") or {}
    latest = stock.metrics.get("latest_period") or {}
    annual = stock.metrics.get("latest_annual") or {}
    score_parts = " / ".join(f"{k} {v:.1f}" for k, v in stock.score_parts.items())
    weight_text = f"{stock.portfolio_weight:.1f}%" if stock.portfolio_weight > 0 else "0%"
    md = f"""# {stock.code} {stock.name} 财报研究

> 生成日期：{AS_OF_DATE}  
> 口径：东方财富 F10 财务指标、东方财富行情 K 线、巨潮资讯公告链接；最新可得财报通常为 2026 一季报与 2025 年报。  
> 提醒：本文是研究记录，不构成保证收益或适合所有人的个性化投资建议。

## 1. 半年投资结论

| 项目 | 结论 |
|---|---|
| 综合评分 | {stock.score:.1f}/100（{score_parts}） |
| 评级 | {stock.rating} |
| 半年观点 | {half_year_view(stock)} |
| 单股建议仓位区间 | {stock.suggested_range} |
| 默认中性组合权重 | {weight_text} |
| 当前价格 | {fmt_num(stock.quote.get("price"), 2)} 元 |
| PE(TTM) / PB | {fmt_num(stock.quote.get("pe_ttm"), 2)} / {fmt_num(stock.quote.get("pb"), 2)} |
| 总市值 | {fmt_money(stock.quote.get("market_cap"))} |
| 最近交易日 | {trend.get("last_trade_date") or "-"} |

## 2. 公司概况

| 项目 | 内容 |
|---|---|
| 公司全称 | {profile.get("ORG_NAME") or "-"} |
| 一级行业 | {stock.metrics.get("industry") or "-"} |
| 细分行业 | {stock.metrics.get("sector_detail") or "-"} |
| 主营业务 | {profile.get("MAIN_BUSINESS") or "-"} |
| 收入结构 | {profile.get("INCOME_STRU_NAMENEW") or profile.get("INCOME_STRU_NAME") or "-"} |
| 控股股东/实控人 | {profile.get("CONTROL_HOLDER") or "-"} / {profile.get("REAL_CONTROLER") or "-"} |
| 上市日期 | {fmt_date(profile.get("LISTING_DATE"))} |

## 3. 最新财报摘要

{latest_table(stock)}

## 4. 三年质量与成长

{annual_table(stock)}

## 5. 估值与交易状态

| 指标 | 数值 |
|---|---:|
| 最新收盘价 | {fmt_num(stock.quote.get("price"), 2)} 元 |
| 总市值 | {fmt_money(stock.quote.get("market_cap"))} |
| 流通市值 | {fmt_money(stock.quote.get("float_market_cap"))} |
| PE(TTM) | {fmt_num(stock.quote.get("pe_ttm"), 2)} |
| PB | {fmt_num(stock.quote.get("pb"), 2)} |
| 20 日涨跌幅 | {fmt_pct(trend.get("return_20d"))} |
| 60 日涨跌幅 | {fmt_pct(trend.get("return_60d"))} |
| 120 日涨跌幅 | {fmt_pct(trend.get("return_120d"))} |
| 较 120 日高点回撤 | {fmt_pct(trend.get("drawdown_120d_high"))} |
| 60 日年化波动率 | {fmt_pct(trend.get("volatility_60d_ann"))} |

## 6. 财务观察

- 成长：{sentence_growth(stock)}
- 质量：{sentence_quality(stock)}
- 现金流：{sentence_cash(stock)}
- 估值/走势：{sentence_valuation(stock)}

## 7. 半年跟踪计划

"""
    for item in tracking_plan(stock):
        md += f"- {item}\n"
    md += "\n## 8. 主要风险\n\n"
    for item in risk_points(stock):
        md += f"- {item}\n"
    md += f"\n## 9. 数据来源\n\n{source_section(stock)}\n"
    stock_dir = out_dir / f"{stock.code}_{stock.name}"
    stock_dir.mkdir(parents=True, exist_ok=True)
    (stock_dir / "research.md").write_text(md, encoding="utf-8")


def summary_row(stock: StockResearch) -> dict[str, Any]:
    annual = stock.metrics.get("latest_annual") or {}
    q1 = stock.metrics.get("q1") or {}
    trend = stock.metrics.get("trend") or {}
    return {
        "code": stock.code,
        "name": stock.name,
        "industry": stock.metrics.get("industry"),
        "rating": stock.rating,
        "score": stock.score,
        "portfolio_weight": stock.portfolio_weight,
        "suggested_range": stock.suggested_range,
        "price": stock.quote.get("price"),
        "pe_ttm": stock.quote.get("pe_ttm"),
        "pb": stock.quote.get("pb"),
        "market_cap": stock.quote.get("market_cap"),
        "roe_2025": annual.get("ROEJQ"),
        "avg_roe_3y": stock.metrics.get("avg_roe_3y"),
        "rev_yoy_2025": annual.get("TOTALOPERATEREVETZ"),
        "np_yoy_2025": annual.get("PARENTNETPROFITTZ"),
        "rev_yoy_q1": q1.get("TOTALOPERATEREVETZ"),
        "np_yoy_q1": q1.get("PARENTNETPROFITTZ"),
        "cfo_np_2025": annual.get("NCO_NETPROFIT"),
        "debt_2025": annual.get("ZCFZL"),
        "return_60d": trend.get("return_60d"),
        "return_120d": trend.get("return_120d"),
        "drawdown_120d_high": trend.get("drawdown_120d_high"),
        "last_trade_date": trend.get("last_trade_date"),
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def markdown_summary_table(stocks: list[StockResearch]) -> str:
    lines = [
        "| 排名 | 代码 | 名称 | 行业 | 评级 | 分数 | 默认权重 | PE | PB | 2025 ROE | Q1营收YoY | Q1净利YoY | 120日涨跌 | 研究档案 |",
        "|---:|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for idx, stock in enumerate(sorted(stocks, key=lambda s: s.score, reverse=True), 1):
        annual = stock.metrics.get("latest_annual") or {}
        q1 = stock.metrics.get("q1") or {}
        trend = stock.metrics.get("trend") or {}
        rel = f"./{stock.code}_{stock.name}/research.md"
        lines.append(
            f"| {idx} | {stock.code} | {stock.name} | {stock.metrics.get('industry') or '-'} | "
            f"{stock.rating} | {stock.score:.1f} | {stock.portfolio_weight:.1f}% | "
            f"{fmt_num(stock.quote.get('pe_ttm'), 2)} | {fmt_num(stock.quote.get('pb'), 2)} | "
            f"{fmt_pct(annual.get('ROEJQ'))} | {fmt_pct(q1.get('TOTALOPERATEREVETZ'))} | "
            f"{fmt_pct(q1.get('PARENTNETPROFITTZ'))} | {fmt_pct(trend.get('return_120d'))} | "
            f"[打开]({rel}) |"
        )
    return "\n".join(lines)


def portfolio_table(stocks: list[StockResearch]) -> str:
    selected = [s for s in sorted(stocks, key=lambda x: x.portfolio_weight, reverse=True) if s.portfolio_weight > 0]
    lines = [
        "| 代码 | 名称 | 行业 | 默认权重 | 评级 | 核心理由 |",
        "|---|---|---|---:|---|---|",
    ]
    for stock in selected:
        lines.append(
            f"| {stock.code} | {stock.name} | {stock.metrics.get('industry') or '-'} | "
            f"{stock.portfolio_weight:.1f}% | {stock.rating} | {half_year_view(stock)} |"
        )
    cash = 100 - sum(s.portfolio_weight for s in selected)
    lines.append(f"| CASH | 现金/货基/等待仓 | - | {cash:.1f}% | 防守 | 用于回撤低吸、半年报后再分配。 |")
    return "\n".join(lines)


def write_readme(stocks: list[StockResearch], out_dir: Path) -> None:
    latest_trade_dates = sorted({(s.metrics.get("trend") or {}).get("last_trade_date") for s in stocks if (s.metrics.get("trend") or {}).get("last_trade_date")})
    latest_trade = latest_trade_dates[-1] if latest_trade_dates else "-"
    actual_equity = sum(stock.portfolio_weight for stock in stocks)
    readme = f"""# 连续三年 ROE 大于 10% 股票财报研究

> 生成日期：{AS_OF_DATE}  
> 行情最近交易日：{latest_trade}  
> 股票来源：用户提供的同花顺自选截图，共 {len(stocks)} 只。  
> 说明：这是基于公开财务指标、公告链接与行情数据的研究记录，不构成保证收益或适合所有人的个性化投资建议。

## 默认半年组合建议

默认按“中性风险”处理：本次模型实际给出的股票仓位为 {actual_equity:.1f}%，上限控制在约 {TARGET_EQUITY_EXPOSURE:.0f}%；单股不超过 {MAX_SINGLE_WEIGHT:.0f}%，单一一级行业不超过 {MAX_INDUSTRY_WEIGHT:.0f}%，剩余资金保留为现金/货基/等待仓。若你偏保守，可把下表所有股票仓位乘以 0.6；若偏激进，也不建议单股突破 8%。

{portfolio_table(stocks)}

## 综合排序

{markdown_summary_table(stocks)}

## 评分口径

- 质量 30 分：三年年报 ROE、最新 ROE、毛利率和净利率。
- 成长 25 分：2025 年报营收/利润同比，以及 2026 一季报营收/利润同比。
- 现金负债 15 分：经营现金流/净利润、资产负债率、流动比率。
- 估值 15 分：PE(TTM)、PB，并结合最新利润增速做轻微调整。
- 走势 15 分：20/60/120 日涨跌、相对 120 日高点回撤、波动率和 60 日均线。

## 本地文件

- 每家公司：`./代码_名称/research.md`
- 原始接口响应：`./_data/raw/`
- 汇总 CSV：`./_data/summary.csv`
- 组合 CSV：`./_data/portfolio.csv`
- 统一模板：`./template.md`

## 数据来源

- [东方财富行情与 F10](https://quote.eastmoney.com/)
- [东方财富证券数据中心接口](https://datacenter.eastmoney.com/)
- [巨潮资讯公告](http://www.cninfo.com.cn/new/index)
"""
    (out_dir / "README.md").write_text(readme, encoding="utf-8")


def write_template(out_dir: Path) -> None:
    template = """# {代码} {名称} 财报研究

> 生成日期：{日期}  
> 口径：东方财富 F10 财务指标、东方财富行情 K 线、巨潮资讯公告链接；最新可得财报通常为 2026 一季报与 2025 年报。  
> 提醒：本文是研究记录，不构成保证收益或适合所有人的个性化投资建议。

## 1. 半年投资结论

固定表格：综合评分、评级、半年观点、单股建议仓位区间、默认中性组合权重、价格、估值、市值、最近交易日。

## 2. 公司概况

固定表格：公司全称、一级行业、细分行业、主营业务、收入结构、控股股东/实控人、上市日期。

## 3. 最新财报摘要

固定表格：最新季度与最新年报的营收、利润、扣非、ROE、毛利率、净利率、经营现金流和负债率。

## 4. 三年质量与成长

固定表格：最近三年年报核心财务指标。

## 5. 估值与交易状态

固定表格：价格、市值、PE、PB、20/60/120 日走势、回撤和波动率。

## 6. 财务观察

固定项目：成长、质量、现金流、估值/走势。

## 7. 半年跟踪计划

固定项目：半年报、利润质量、交易纪律。

## 8. 主要风险

固定项目：公司自身风险、行业风险、估值/趋势风险。

## 9. 数据来源

固定项目：东方财富 F10、东方财富行情、巨潮资讯公告。
"""
    (out_dir / "template.md").write_text(template, encoding="utf-8")


def cached_or_fetch(
    success_path: Path,
    error_path: Path,
    parser: Any,
    fetcher: Any,
) -> Any:
    cached = load_json(success_path)
    if cached is not None:
        return parser(cached)
    parsed, raw = fetcher()
    save_json(success_path, raw)
    if error_path.exists():
        error_path.unlink()
    return parsed


def main() -> None:
    out_dir = TARGET_DIR
    raw_dir = out_dir / "_data" / "raw"
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)

    cninfo_cache = raw_dir / "cninfo_stock_list.json"
    cached_cninfo = load_json(cninfo_cache)
    if cached_cninfo is not None:
        cninfo_lookup = cached_cninfo
    else:
        cninfo_lookup = fetch_cninfo_stock_list()
        save_json(cninfo_cache, cninfo_lookup)

    results: list[StockResearch] = []
    for idx, (code, name) in enumerate(STOCKS, 1):
        stock = StockResearch(code=code, name=name)
        print(f"[{idx:02d}/{len(STOCKS)}] fetching {code} {name}", flush=True)
        try:
            stock.finance_rows = cached_or_fetch(
                raw_dir / f"{code}_finance.json",
                raw_dir / f"{code}_finance_error.json",
                parse_finance_raw,
                lambda code=code: fetch_finance(code),
            )
        except Exception as exc:
            stock.warnings.append(f"财务主表抓取失败：{exc}")
            save_json(raw_dir / f"{code}_finance_error.json", {"error": str(exc)})
        time.sleep(0.05)

        try:
            stock.profile = cached_or_fetch(
                raw_dir / f"{code}_profile.json",
                raw_dir / f"{code}_profile_error.json",
                parse_profile_raw,
                lambda code=code: fetch_profile(code),
            )
        except Exception as exc:
            stock.warnings.append(f"公司概况抓取失败：{exc}")
            save_json(raw_dir / f"{code}_profile_error.json", {"error": str(exc)})
        time.sleep(0.05)

        try:
            stock.quote = cached_or_fetch(
                raw_dir / f"{code}_quote.json",
                raw_dir / f"{code}_quote_error.json",
                parse_quote_raw,
                lambda code=code: fetch_quote(code),
            )
        except Exception as exc:
            stock.warnings.append(f"行情估值抓取失败：{exc}")
            save_json(raw_dir / f"{code}_quote_error.json", {"error": str(exc)})
        time.sleep(0.05)

        try:
            stock.klines = cached_or_fetch(
                raw_dir / f"{code}_kline.json",
                raw_dir / f"{code}_kline_error.json",
                parse_klines_raw,
                lambda code=code: fetch_klines(code),
            )
        except Exception as exc:
            stock.warnings.append(f"K 线抓取失败：{exc}")
            save_json(raw_dir / f"{code}_kline_error.json", {"error": str(exc)})
        time.sleep(0.05)

        try:
            org_id = (cninfo_lookup.get(code) or {}).get("orgId")
            stock.announcements = cached_or_fetch(
                raw_dir / f"{code}_announcements.json",
                raw_dir / f"{code}_announcements_error.json",
                lambda data: data.get("announcements") or [],
                lambda code=code, org_id=org_id: fetch_announcements(code, org_id),
            )
        except Exception as exc:
            stock.warnings.append(f"公告链接抓取失败：{exc}")
            save_json(raw_dir / f"{code}_announcements_error.json", {"error": str(exc)})
        time.sleep(0.05)

        score_stock(stock)
        results.append(stock)

    allocate_portfolio(results)

    for stock in results:
        write_stock_markdown(stock, out_dir)

    summary_rows = [summary_row(stock) for stock in sorted(results, key=lambda s: s.score, reverse=True)]
    portfolio_rows = [row for row in summary_rows if row["portfolio_weight"] > 0]
    write_csv(out_dir / "_data" / "summary.csv", summary_rows)
    write_csv(out_dir / "_data" / "portfolio.csv", portfolio_rows)
    save_json(out_dir / "_data" / "summary.json", summary_rows)
    write_template(out_dir)
    write_readme(results, out_dir)

    print(f"done: {out_dir.resolve()}", flush=True)


if __name__ == "__main__":
    main()
