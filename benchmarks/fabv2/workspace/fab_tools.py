"""Evaluator-owned, key-free finance research tools for the Prime RLM.

The outer optimizer may change how these tools are described and orchestrated,
but it cannot change this capability substrate.  Every call is counted in a
per-case JSON ledger so tool behavior remains auditable outside the model.
"""

from __future__ import annotations

import argparse
import ast
import json
import math
import operator
import os
import re
import tempfile
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

MAX_END_DATE = "2026-03-01"
MAX_DOWNLOAD_BYTES = 8_000_000
USER_AGENT = "SelfHarness-FABv2/1.0 research@example.invalid"
FTS_URL = "https://efts.sec.gov/LATEST/search-index"
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_BINARY = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
}
_UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}
_FUNCTIONS = {
    "abs": abs,
    "min": min,
    "max": max,
    "sqrt": math.sqrt,
    "log": math.log,
    "log10": math.log10,
}


def _usage_path() -> Path | None:
    raw = os.environ.get("FAB_TOOLS_USAGE_FILE", "").strip()
    return Path(raw) if raw else None


def _record(name: str, *, failed: bool = False) -> None:
    path = _usage_path()
    if path is None:
        return
    try:
        payload = json.loads(path.read_text()) if path.exists() else {}
    except (OSError, ValueError):
        payload = {}
    calls = payload.setdefault("calls", {})
    calls[name] = int(calls.get(name, 0)) + 1
    if failed:
        payload["errors"] = int(payload.get("errors", 0)) + 1
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False) as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(path)


def _cache_root() -> Path:
    path = Path(os.environ.get("FAB_TOOLS_CACHE", ".fab-cache"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def _http(url: str) -> bytes:
    import hashlib

    cached = _cache_root() / hashlib.sha256(url.encode()).hexdigest()
    if cached.exists():
        return cached.read_bytes()
    request = Request(url, headers={"User-Agent": USER_AGENT})  # noqa: S310 - HTTPS checked by callers
    with urlopen(request, timeout=60) as response:  # noqa: S310 - HTTPS checked by callers
        body = response.read(MAX_DOWNLOAD_BYTES + 1)
    if len(body) > MAX_DOWNLOAD_BYTES:
        raise ValueError(f"response exceeds {MAX_DOWNLOAD_BYTES} bytes")
    cached.write_bytes(body)
    return body


def _eval_expression(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _eval_expression(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, int | float):
        return float(node.value)
    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY:
        return float(_BINARY[type(node.op)](_eval_expression(node.left), _eval_expression(node.right)))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY:
        return float(_UNARY[type(node.op)](_eval_expression(node.operand)))
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _FUNCTIONS:
        return float(_FUNCTIONS[node.func.id](*(_eval_expression(arg) for arg in node.args)))
    message = "unsupported expression"
    raise ValueError(message)


def calculate(expression: str) -> float:
    """Evaluate arithmetic without Python eval."""
    try:
        value = _eval_expression(ast.parse(expression, mode="eval"))
    except Exception:
        _record("calculator", failed=True)
        raise
    _record("calculator")
    return value


def _date(value: str) -> str:
    if not _DATE_RE.fullmatch(value):
        raise ValueError(f"invalid date {value!r}; expected YYYY-MM-DD")
    return value


def edgar_search(
    query: str,
    *,
    start_date: str = "2001-01-01",
    end_date: str = MAX_END_DATE,
    form_types: list[str] | None = None,
    top_n: int = 10,
) -> list[dict[str, Any]]:
    """Search SEC full-text filings and return stable filing metadata."""
    try:
        params: dict[str, str] = {
            "q": query,
            "dateRange": "custom",
            "startdt": _date(start_date),
            "enddt": min(_date(end_date), MAX_END_DATE),
        }
        if form_types:
            params["forms"] = ",".join(form_types)
        data = json.loads(_http(f"{FTS_URL}?{urlencode(params)}"))
        output: list[dict[str, Any]] = []
        for hit in data.get("hits", {}).get("hits", [])[: max(1, min(top_n, 50))]:
            source = hit["_source"]
            accession = source["adsh"]
            document = hit["_id"].split(":", 1)[1] if ":" in hit["_id"] else ""
            cik = str(source["ciks"][0])
            base = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}"
            output.append(
                {
                    "cik": cik,
                    "company": (source.get("display_names") or [""])[0],
                    "form_type": source.get("form") or (source.get("root_forms") or [""])[0],
                    "filed_at": source.get("file_date"),
                    "period_ending": source.get("period_ending"),
                    "document_url": f"{base}/{document}" if document else base,
                    "index_url": f"{base}/{accession.replace('-', '')}-index.htm",
                }
            )
    except Exception:
        _record("edgar_search", failed=True)
        raise
    _record("edgar_search")
    return output


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.suppressed = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag in {"script", "style", "svg"}:
            self.suppressed += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "svg"} and self.suppressed:
            self.suppressed -= 1

    def handle_data(self, data: str) -> None:
        if not self.suppressed and (cleaned := " ".join(data.split())):
            self.parts.append(cleaned)


def fetch_page_text(url: str, *, max_chars: int = 250_000) -> str:
    """Fetch an HTML filing/page and return normalized visible text."""
    try:
        parser = _TextExtractor()
        parser.feed(_http(url).decode("utf-8", errors="ignore"))
        text = "\n".join(parser.parts)
    except Exception:
        _record("fetch_page_text", failed=True)
        raise
    if not text:
        _record("fetch_page_text", failed=True)
        message = "page contains no visible text"
        raise ValueError(message)
    _record("fetch_page_text")
    return text[:max_chars]


def price_history(ticker: str, start_date: str, end_date: str) -> list[dict[str, Any]]:
    """Return unadjusted Yahoo daily closes for a public symbol."""
    try:
        start = min(_date(start_date), MAX_END_DATE)
        end = min(_date(end_date), MAX_END_DATE)
        if start > end:
            message = "start_date is later than end_date"
            raise ValueError(message)  # noqa: TRY301 - recorded by the common failure path
        period1 = int(datetime.strptime(start, "%Y-%m-%d").replace(tzinfo=UTC).timestamp())
        period2 = int(datetime.strptime(end, "%Y-%m-%d").replace(tzinfo=UTC).timestamp()) + 86400
        url = (
            f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(ticker.strip())}"
            f"?period1={period1}&period2={period2}&interval=1d&events=div%2Csplit"
        )
        result = json.loads(_http(url))["chart"]["result"][0]
        timestamps = result.get("timestamp") or []
        closes = result["indicators"]["quote"][0]["close"]
        output = [
            {
                "date": datetime.fromtimestamp(stamp, tz=UTC).strftime("%Y-%m-%d"),
                "close": round(float(close), 4),
            }
            for stamp, close in zip(timestamps, closes, strict=False)
            if close is not None
        ]
    except Exception:
        _record("price_history", failed=True)
        raise
    _record("price_history")
    return output


def _print_json(value: object) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    calc = commands.add_parser("calculate")
    calc.add_argument("expression")
    edgar = commands.add_parser("edgar-search")
    edgar.add_argument("query")
    edgar.add_argument("--start-date", default="2001-01-01")
    edgar.add_argument("--end-date", default=MAX_END_DATE)
    edgar.add_argument("--form", action="append", dest="forms")
    edgar.add_argument("--top-n", type=int, default=10)
    page = commands.add_parser("fetch-page")
    page.add_argument("url")
    page.add_argument("--max-chars", type=int, default=250_000)
    price = commands.add_parser("price-history")
    price.add_argument("ticker")
    price.add_argument("start_date")
    price.add_argument("end_date")
    args = parser.parse_args(argv)
    if args.command == "calculate":
        _print_json(calculate(args.expression))
    elif args.command == "edgar-search":
        _print_json(
            edgar_search(
                args.query,
                start_date=args.start_date,
                end_date=args.end_date,
                form_types=args.forms,
                top_n=args.top_n,
            )
        )
    elif args.command == "fetch-page":
        print(fetch_page_text(args.url, max_chars=args.max_chars))
    else:
        _print_json(price_history(args.ticker, args.start_date, args.end_date))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
