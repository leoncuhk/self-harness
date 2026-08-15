#!/usr/bin/env python3
"""免费工具链：用公共 API 模拟官方 harness 的四个外部工具。

- edgar_search   → EDGAR 官方全文检索 (efts.sec.gov)，免费无 key，等价 sec-api.io 的核心能力
- filing/fetch   → sec.gov Archives 取 filing 文档并解析为纯文本（等价 parse_html_page）
- prices         → Yahoo chart API 原始收盘价（等价 price_history 的日线 close，未复权）
- 缓存           → .cache/ 按 URL 哈希落盘，重复实验零成本

用法（用 finance-agent venv 的 python 以获得 bs4）:
  py tools_local.py search '"Charles D. Young"' --forms 8-K --start 2025-07-01 --end 2025-07-31
  py tools_local.py docs 0000912593-25-000199            # 列出 filing 内文档
  py tools_local.py fetch https://www.sec.gov/Archives/... # 取文转纯文本
  py tools_local.py price SUI 2025-07-01 2025-09-01
作为库:
  from tools_local import edgar_search, fetch_text, filing_index, prices
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote

import aiohttp

CACHE = Path(__file__).resolve().parent / ".cache"
CACHE.mkdir(exist_ok=True)
UA = {"User-Agent": "Independent Research fabv2-study contact@example.com"}
FTS_URL = "https://efts.sec.gov/LATEST/search-index?q={q}&dateRange=custom&startdt={s}&enddt={e}"


def _cache_get(url: str) -> bytes | None:
    p = CACHE / hashlib.sha256(url.encode()).hexdigest()
    return p.read_bytes() if p.exists() else None


def _cache_put(url: str, data: bytes) -> None:
    (CACHE / hashlib.sha256(url.encode()).hexdigest()).write_bytes(data)


def http_get(url: str, headers: dict | None = None, binary: bool = False) -> bytes:
    import requests

    cached = _cache_get(url)
    if cached is not None:
        return cached
    for attempt in range(3):
        try:
            r = requests.get(url, headers={**UA, **(headers or {})}, timeout=60)
            r.raise_for_status()
            data = r.content if binary else r.content
            _cache_put(url, data)
            return data
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2 * (attempt + 1))


def edgar_search(
    query: str,
    forms: str | None = None,
    ciks: list[str] | None = None,
    start: str = "1990-01-01",
    end: str = "2026-03-01",
) -> list[dict]:
    """EDGAR 全文检索。返回 [{adsh, cik, name, form, file_date, period, doc_url}]。

    doc_url 直指命中文档（可能是主文档或 exhibit）；加 forms=8-K&form=... 语法:
    query 里引号短语、AND/OR、通配符均支持。
    """
    url = FTS_URL.format(q=quote(query), s=start, e=end)
    if forms:
        url += f"&forms={forms}"
    data = json.loads(http_get(url))
    out = []
    for hit in data.get("hits", {}).get("hits", []):
        s = hit["_source"]
        adsh = s["adsh"]
        doc = hit["_id"].split(":", 1)[1] if ":" in hit["_id"] else ""
        base = f"https://www.sec.gov/Archives/edgar/data/{int(s['ciks'][0])}/{adsh.replace('-', '')}"
        out.append(
            {
                "adsh": adsh,
                "cik": s["ciks"][0],
                "name": s.get("display_names", [""])[0],
                "form": s.get("form"),
                "file_date": s.get("file_date"),
                "period": s.get("period_ending"),
                "doc_url": f"{base}/{doc}" if doc else base,
                "index_url": f"{base}/{adsh.replace('-', '')}-index.htm",
            }
        )
    return out


def filing_index(adsh: str) -> list[dict]:
    """列出一个 filing 的全部文档（含 exhibit）。adsh 如 0000912593-25-000199。"""
    cik_dir = None
    # 从任一缓存/搜索拿 cik 不现实，直接要求传入完整信息时用 docs 命令的 --cik
    raise NotImplementedError("用 filing_docs(cik, adsh)")


def filing_docs(cik: str, adsh: str) -> list[dict]:
    """ filing 文档清单: [{name, size, url}]"""
    base = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{adsh.replace('-', '')}"
    idx = json.loads(http_get(f"{base}/index.json"))
    return [
        {"name": it["name"], "size": it.get("size", 0), "url": f"{base}/{it['name']}"}
        for it in idx["directory"]["item"]
    ]


def html_to_text(html: bytes) -> str:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style"]):
        t.extract()
    text = soup.get_text()
    lines = (ln.strip() for ln in text.splitlines())
    chunks = (ph.strip() for ln in lines for ph in ln.split("  "))
    return "\n".join(c for c in chunks if c)


def fetch_text(url: str) -> str:
    return html_to_text(http_get(url))


def prices(symbol: str, start: str, end: str) -> list[dict]:
    """Yahoo chart 日线，未复权 close（与官方 price_history 的 raw close 对齐）。"""
    from datetime import datetime

    p1 = int(datetime.strptime(start, "%Y-%m-%d").timestamp())
    p2 = int(datetime.strptime(end, "%Y-%m-%d").timestamp()) + 86400
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(symbol)}"
        f"?period1={p1}&period2={p2}&interval=1d&events=div%2Csplit"
    )
    data = json.loads(http_get(url, headers={"User-Agent": "Mozilla/5.0"}))
    res = data["chart"]["result"][0]
    ts = res["timestamp"]
    q = res["indicators"]["quote"][0]
    out = []
    for i, t in enumerate(ts):
        d = datetime.fromtimestamp(t).strftime("%Y-%m-%d")
        if q["close"][i] is not None:
            out.append({"date": d, "close": round(q["close"][i], 2)})
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search")
    s.add_argument("query")
    s.add_argument("--forms")
    s.add_argument("--start", default="1990-01-01")
    s.add_argument("--end", default="2026-03-01")
    d = sub.add_parser("docs")
    d.add_argument("adsh")
    d.add_argument("--cik", required=True)
    f = sub.add_parser("fetch")
    f.add_argument("url")
    f.add_argument("--grep", help="过滤含关键词的行（大小写不敏感）")
    f.add_argument("--ctx", type=int, default=1, help="grep 命中行的上下文行数")
    p = sub.add_parser("price")
    p.add_argument("symbol")
    p.add_argument("start")
    p.add_argument("end")
    a = ap.parse_args()

    if a.cmd == "search":
        for r in edgar_search(a.query, a.forms, start=a.start, end=a.end):
            print(json.dumps(r, ensure_ascii=False))
    elif a.cmd == "docs":
        for r in filing_docs(a.cik, a.adsh):
            print(json.dumps(r, ensure_ascii=False))
    elif a.cmd == "fetch":
        text = fetch_text(a.url)
        if a.grep:
            lines = text.splitlines()
            pat = re.compile(a.grep, re.I)
            hits = [i for i, ln in enumerate(lines) if pat.search(ln)]
            shown = set()
            for i in hits:
                for j in range(max(0, i - a.ctx), min(len(lines), i + a.ctx + 1)):
                    if j not in shown:
                        print(f"{j:6d}| {lines[j][:200]}")
                        shown.add(j)
            print(f"-- {len(hits)} 命中 / 全文 {len(text)} 字符")
        else:
            print(text)
    elif a.cmd == "price":
        for r in prices(a.symbol, a.start, a.end):
            print(r["date"], r["close"])


if __name__ == "__main__":
    main()
