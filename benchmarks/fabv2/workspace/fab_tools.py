"""Evaluator-owned, key-free finance research tools for FAB inner runtimes.

The outer optimizer may change how these tools are described and orchestrated,
but it cannot change this capability substrate.  Every call is counted in a
per-case JSON ledger so tool behavior remains auditable outside the model.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import operator
import os
import re
import tempfile
import time
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from self_harness.fab_policy import load_fab_policy

MAX_END_DATE = "2026-03-01"
MAX_DOWNLOAD_BYTES = 8_000_000
USER_AGENT = "SelfHarness-FABv2/1.0 research@example.invalid"
FTS_URL = "https://efts.sec.gov/LATEST/search-index"
TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions"
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


def _runtime_policy() -> dict[str, Any]:
    path = Path(__file__).with_name("runtime_policy.json")
    return load_fab_policy(path) if path.is_file() else {"schema_version": 1}


def _scope_key(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:20]


def _scoped_count(name: str, scope: str) -> int:
    path = _usage_path()
    if path is None or not path.exists():
        return 0
    try:
        payload = json.loads(path.read_text())
    except (OSError, ValueError):
        return 0
    return int((payload.get("scoped_calls") or {}).get(name, {}).get(scope, 0))


def _record(name: str, *, failed: bool = False, scope: str | None = None) -> None:
    path = _usage_path()
    if path is None:
        return
    try:
        payload = json.loads(path.read_text()) if path.exists() else {}
    except (OSError, ValueError):
        payload = {}
    calls = payload.setdefault("calls", {})
    calls[name] = int(calls.get(name, 0)) + 1
    if scope is not None:
        scoped = payload.setdefault("scoped_calls", {}).setdefault(name, {})
        scoped[scope] = int(scoped.get(scope, 0)) + 1
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


def _sec_data() -> dict[str, Any]:
    path = Path(os.environ.get("FAB_SEC_DATA", Path(__file__).with_name("sec_data.json")))
    if not path.is_file():
        return {"schema_version": 1}
    payload = json.loads(path.read_text())
    if payload.get("schema_version") != 1:
        message = "unsupported SEC-data schema"
        raise ValueError(message)
    return payload


def _frozen_document(url: str) -> bytes | None:
    for document in _sec_data().get("document_extracts", []):
        if document.get("url") == url:
            return str(document["body"]).encode()
    return None


def _offline() -> bool:
    return os.environ.get("FAB_TOOLS_OFFLINE", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _http(url: str) -> bytes:
    if (frozen := _frozen_document(url)) is not None:
        return frozen
    cached = _cache_root() / hashlib.sha256(url.encode()).hexdigest()
    if cached.exists():
        return cached.read_bytes()
    if _offline():
        raise RuntimeError(f"offline cache miss for {url}")
    request = Request(url, headers={"User-Agent": USER_AGENT})  # noqa: S310 - tool allows HTTPS
    body: bytes | None = None
    for attempt in range(4):
        try:
            with urlopen(request, timeout=60) as response:  # noqa: S310 - tool allows HTTPS
                body = response.read(MAX_DOWNLOAD_BYTES + 1)
            break
        except HTTPError as exc:
            if exc.code not in {429, 500, 502, 503, 504} or attempt == 3:
                raise
        except URLError:
            if attempt == 3:
                raise
        time.sleep(0.5 * (2**attempt))
    if body is None:  # pragma: no cover - loop either returns data or raises
        message = "HTTP retry loop ended without data"
        raise RuntimeError(message)
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


def sec_filings(
    ticker: str,
    *,
    form_type: str = "10-K",
    start_date: str = "2001-01-01",
    end_date: str = MAX_END_DATE,
    top_n: int = 10,
) -> list[dict[str, Any]]:
    """List a company's recent SEC filings without relying on keyword search."""
    try:
        symbol = ticker.strip().upper()
        if not symbol or not re.fullmatch(r"[A-Z0-9.-]+", symbol):
            raise ValueError(f"invalid ticker {ticker!r}")  # noqa: TRY301 - common audit path
        start = _date(start_date)
        end = min(_date(end_date), MAX_END_DATE)
        for coverage in _sec_data().get("filing_coverage", []):
            if (
                str(coverage.get("ticker", "")).upper() == symbol
                and coverage.get("form_type") == form_type
                and str(coverage.get("coverage_start", "")) <= start
                and end <= str(coverage.get("coverage_end", ""))
            ):
                limit = max(1, min(top_n, 50))
                rows = [
                    {
                        "ticker": symbol,
                        "company": coverage["company"],
                        "cik": coverage["cik"],
                        "form_type": form_type,
                        "filed_at": filing["filed_at"],
                        "period_ending": filing["period_ending"],
                        "document_url": filing["document_url"],
                        "index_url": filing["index_url"],
                        "source_type": "evaluator_frozen_sec_index",
                    }
                    for filing in coverage.get("filings", [])
                    if start <= filing["filed_at"] <= end
                ][:limit]
                _record("sec_filings")
                return rows
        tickers = json.loads(_http(TICKERS_URL))
        company = next(
            (
                item
                for item in tickers.values()
                if str(item.get("ticker", "")).upper() == symbol
            ),
            None,
        )
        if company is None:
            raise ValueError(  # noqa: TRY301 - common audit path
                f"ticker {symbol!r} not found in SEC company tickers"
            )
        cik = str(int(company["cik_str"])).zfill(10)
        payload = json.loads(_http(f"{SUBMISSIONS_URL}/CIK{cik}.json"))
        recent = payload.get("filings", {}).get("recent", {})
        rows: list[dict[str, Any]] = []
        for form, filed, period, accession, document in zip(
            recent.get("form", []),
            recent.get("filingDate", []),
            recent.get("reportDate", []),
            recent.get("accessionNumber", []),
            recent.get("primaryDocument", []),
            strict=False,
        ):
            if form != form_type or not start <= filed <= end:
                continue
            accession_slug = accession.replace("-", "")
            base = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession_slug}"
            rows.append(
                {
                    "ticker": symbol,
                    "company": payload.get("name") or company.get("title"),
                    "cik": cik,
                    "form_type": form,
                    "filed_at": filed,
                    "period_ending": period,
                    "document_url": f"{base}/{document}",
                    "index_url": f"{base}/{accession_slug}-index.html",
                }
            )
            if len(rows) >= max(1, min(top_n, 50)):
                break
    except Exception:
        _record("sec_filings", failed=True)
        raise
    _record("sec_filings")
    return rows


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.suppressed = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag in {"script", "style", "svg", "ix:header", "ix:hidden", "xbrli:context"}:
            self.suppressed += 1

    def handle_endtag(self, tag: str) -> None:
        if (
            tag in {"script", "style", "svg", "ix:header", "ix:hidden", "xbrli:context"}
            and self.suppressed
        ):
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


def search_page_text(
    url: str,
    queries: list[str],
    *,
    context_chars: int = 800,
    max_matches: int = 20,
) -> list[dict[str, Any]]:
    """Search all visible page text and return bounded contextual windows."""
    search_policy = _runtime_policy().get("search_page") or {}
    scope = _scope_key(url)
    max_calls = int(search_policy.get("max_calls_per_document", 20))
    if _scoped_count("search_page_text", scope) >= max_calls:
        _record("search_page_text", failed=True, scope=scope)
        message = f"runtime policy blocks more than {max_calls} searches of one document"
        raise RuntimeError(message)
    needles = [query.strip() for query in queries if query.strip()]
    if not needles:
        _record("search_page_text", failed=True, scope=scope)
        message = "at least one non-empty query is required"
        raise ValueError(message)
    try:
        parser = _TextExtractor()
        parser.feed(_http(url).decode("utf-8", errors="ignore"))
        text = "\n".join(parser.parts)
        lowered = text.casefold()
        policy_radius = int(search_policy.get("context_chars", 5_000))
        radius = max(100, min(context_chars, policy_radius, 5_000))
        limit = max(1, min(max_matches, 100))
        per_query_limit = int(search_policy.get("max_results_per_query", 100))
        matches: list[dict[str, Any]] = []
        for query in needles:
            start = 0
            query_matches = 0
            folded = query.casefold()
            while (
                len(matches) < limit
                and query_matches < per_query_limit
                and (offset := lowered.find(folded, start)) >= 0
            ):
                left = max(0, offset - radius)
                right = min(len(text), offset + len(query) + radius)
                matches.append(
                    {"query": query, "offset": offset, "snippet": text[left:right]}
                )
                query_matches += 1
                start = offset + max(1, len(folded))
            if len(matches) >= limit:
                break
    except Exception:
        _record("search_page_text", failed=True, scope=scope)
        raise
    _record("search_page_text", scope=scope)
    return matches


def _frozen_prices(ticker: str, start: str, end: str) -> list[dict[str, Any]] | None:
    """Return a complete evaluator-owned slice, never a misleading partial slice."""
    path = Path(os.environ.get("FAB_MARKET_DATA", Path(__file__).with_name("market_data.json")))
    if not path.is_file():
        return None
    payload = json.loads(path.read_text())
    if payload.get("schema_version") != 1:
        message = "unsupported market-data schema"
        raise ValueError(message)
    symbol = ticker.strip().upper()
    for series in payload.get("series", []):
        if (
            str(series.get("ticker", "")).upper() != symbol
            or series.get("field") != "unadjusted_close"
            or start < str(series.get("coverage_start", ""))
            or end > str(series.get("coverage_end", ""))
        ):
            continue
        source = str(series["source_url"])
        currency = str(series.get("currency", "USD"))
        return [
            {
                "date": str(row["date"]),
                "close": round(float(row["close"]), 4),
                "currency": currency,
                "source_url": source,
                "source_type": str(series.get("source_type", "frozen_snapshot")),
            }
            for row in series.get("rows", [])
            if start <= str(row["date"]) <= end
        ]
    return None


def price_history(ticker: str, start_date: str, end_date: str) -> list[dict[str, Any]]:
    """Return auditable unadjusted daily closes, preferring frozen official facts."""
    try:
        start = min(_date(start_date), MAX_END_DATE)
        end = min(_date(end_date), MAX_END_DATE)
        if start > end:
            message = "start_date is later than end_date"
            raise ValueError(message)  # noqa: TRY301 - recorded by the common failure path
        if (frozen := _frozen_prices(ticker, start, end)) is not None:
            _record("price_history")
            return frozen
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
                "currency": result.get("meta", {}).get("currency") or "USD",
                "source_url": url,
                "source_type": "live_yahoo_chart",
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
    filings = commands.add_parser("sec-filings")
    filings.add_argument("ticker")
    filings.add_argument("--form", default="10-K")
    filings.add_argument("--start-date", default="2001-01-01")
    filings.add_argument("--end-date", default=MAX_END_DATE)
    filings.add_argument("--top-n", type=int, default=10)
    page = commands.add_parser("fetch-page")
    page.add_argument("url")
    page.add_argument("--max-chars", type=int, default=250_000)
    search_page = commands.add_parser("search-page")
    search_page.add_argument("url")
    search_page.add_argument("query", nargs="+")
    search_page.add_argument("--context-chars", type=int, default=800)
    search_page.add_argument("--max-matches", type=int, default=20)
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
    elif args.command == "sec-filings":
        _print_json(
            sec_filings(
                args.ticker,
                form_type=args.form,
                start_date=args.start_date,
                end_date=args.end_date,
                top_n=args.top_n,
            )
        )
    elif args.command == "fetch-page":
        print(fetch_page_text(args.url, max_chars=args.max_chars))
    elif args.command == "search-page":
        _print_json(
            search_page_text(
                args.url,
                args.query,
                context_chars=args.context_chars,
                max_matches=args.max_matches,
            )
        )
    else:
        _print_json(price_history(args.ticker, args.start_date, args.end_date))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
