"""FAB v2 inner-agent runner: official finance-agent loop on free tool APIs.

Frozen infrastructure (the proposer may not edit this file). The only editable
surface is prompt.txt, read at call time.

Fidelity notes (vs. the official vals-ai/finance-agent-v2 harness):
- The agent loop, hooks, tool names, tool descriptions, and parameters are
  replicated verbatim from finance_agent/get_agent.py and tools.py.
- Tools that need paid keys (sec-api.io, Tavily, Tiingo) are replaced by free
  equivalents: EDGAR official full-text search, sec.gov Archives fetch, Yahoo
  chart daily closes. web_search is a stub that returns a graceful error.
- Smoke profile: max_turns/max_time/max_tokens are reduced for cost; the
  official profile is 2h / unlimited turns / 32k tokens.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup
from model_library.agent import (
    Agent,
    AgentConfig,
    AgentHooks,
    TimeLimit,
    TurnLimit,
    TurnResult,
    default_before_query,
)
from model_library.base import LLM, LLMConfig, RawResponse
from model_library.base.input import InputItem, SystemInput, TextInput
from model_library.exceptions import MaxContextWindowExceededError
from model_library.registry_utils import get_registry_model
from simpleeval import SimpleEval

from better_harness.usage import total_tokens

MAX_END_DATE = "2026-03-01"
UA = {"User-Agent": "Fabv2Research harness-study@example.com"}
FTS_URL = "https://efts.sec.gov/LATEST/search-index?q={q}&dateRange=custom&startdt={s}&enddt={e}"
_DATE_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_CACHE = Path(os.environ.get("FABV2_CACHE", Path(__file__).resolve().parent / ".cache"))
_CACHE.mkdir(exist_ok=True)

WORKSPACE = Path(__file__).resolve().parent
QUESTION_PROMPT = "Question:\n{question}"


def _cached(url: str) -> bytes | None:
    p = _CACHE / hashlib.sha256(url.encode()).hexdigest()
    return p.read_bytes() if p.exists() else None


def _put(url: str, data: bytes) -> None:
    (_CACHE / hashlib.sha256(url.encode()).hexdigest()).write_bytes(data)


def _http(url: str) -> bytes:
    got = _cached(url)
    if got is not None:
        return got
    r = requests.get(url, headers=UA, timeout=60)
    r.raise_for_status()
    _put(url, r.content)
    return r.content


# ---- tool descriptions copied verbatim from the official harness ------------

CALC_DESC = (
    "Evaluate a mathematical expression and return the result. "
    "Use this tool for all arithmetic calculations instead of computing by hand. "
    "Supports: +, -, *, /, ** (exponentiation), % (modulo), "
    "and parentheses for grouping. "
    "Available functions: abs(), min(), max(), sqrt(), log(), log10(). "
    "Examples: '(5000 - 3200) * 0.21', '(2865507 / 1905871) ** 0.5 - 1', '14060 / 2148'."
)

SUBMIT_DESC = (
    "Submits the final answer to the user. You should include your final answer, as well as any necessary "
    "reasoning, justification, calculations, and explanation. Finally, you should provide any sources used to answer the question. "
    "You MUST use this tool to submit your final result. The user will not see your response if you do not use this tool to submit. "
    "You will not be able to continue working after this tool is called; the conversation will be ended."
)

EDGAR_DESC = (
    "Search the EDGAR Database through the SEC API. "
    "You should provide a search query. You can also optionally provide a start date, an end date, a page number, top N results, a list of form types, and/or a list of CIKs. "
    "The results are returned as a list of dictionaries, each containing the metadata for a filing. It does not contain the full text of the filing."
)

PARSE_DESC = (
    "This tool is used to parse the contents of an HTML page and save it to the agent's data storage system. "
    "The tool will retrieve the HTML page from the URL provided, then parse it from HTML to plain text. "
    "Finally, it will save it to the agent's data storage system under the key provided. "
    "You can use the retrieve_information tool to later retrieve information about the stored page."
)

RETRIEVE_DESC = (
    "This tool allows you to retrieve data from previously saved documents from the agent's data storage system, by applying an LLM prompt to the stored document.\n"
    "\n"
    "To use the tool, you will need to provide a prompt. This prompt will include both the query to be sent to the LLM, "
    "as well as the keys of files you have previously saved to the data storage system.\n"
    "\n"
    'For example, if you want to analyze data stored under the key "financial_report", your prompt should look like the following:\n'
    '"Analyze the following financial report and extract the revenue figures: {{financial_report}}"\n'
    "\n"
    "The {{key_name}} will be replaced with the full text of the document stored under that key before the query is sent.\n"
    "\n"
    "IMPORTANT: Your prompt MUST include at least one key from the data storage using this exact format: {{key_name}}. "
    "If you don't use this exact format with double braces, the tool will fail to retrieve the information.\n"
    "\n"
    "You can also optionally only pass *a portion* of each document to the LLM, rather than the entire document. This can be used to avoid token limit errors or improve efficiency. "
    "To do so, use the input_character_ranges parameter to specify which portions of documents to extract. "
    'For example, if "financial_report" contains "Annual Report 2023" and you specify:  [{"key": "financial_report", "start": 1, "end": 6}], '
    'then only "nnual" will be inserted into the prompt (characters 1 through 5, as end is exclusive).'
)

PRICE_DESC = (
    "Fetch historical daily price data for a specific asset class. "
    "Returns a CSV table with one row per day. "
    "Use asset_class='equity' or 'etf' for US-listed stocks/ETFs (e.g. AAPL, SPY), 'crypto' for pairs like btcusd (lowercase, no dash), "
    "or 'fx' for pairs like audusd. Non-US equities and most indices/futures are not covered by the pricing provider. "
    "Each row includes the raw OHLC (open/high/low/close) close price. "
    "This tool provides raw, unadjusted closing prices."
)

WEB_DESC = (
    "Search the public internet for information. Each result will contain a url, a title, and one excerpt taken directly from the page."
)


class _Tool:
    # minimal stand-in typed like model_library Tool for our needs
    name: str = ""
    description: str = ""
    parameters: dict[str, Any] = {}
    required: list[str] = []
    execution_type = "local"

    @property
    def definition(self):  # pragma: no cover - assembled by model_library
        from model_library.agent.tool import ToolDefinition

        return ToolDefinition.from_tool(self)

    async def execute(self, args, state, logger):  # pragma: no cover
        raise NotImplementedError


from model_library.agent import Tool, ToolOutput  # noqa: E402


def _validate_date(field: str, value: str) -> None:
    if not _DATE_REGEX.match(value):
        raise ValueError(f"Invalid {field} format: '{value}'. Expected YYYY-MM-DD.")


class Calculator(Tool):
    name = "calculator"
    description = CALC_DESC
    parameters: dict[str, Any] = {"expression": {"type": "string", "description": "The mathematical expression to evaluate."}}
    required = ["expression"]

    def __init__(self) -> None:
        self._evaluator = SimpleEval(
            functions={"abs": abs, "min": min, "max": max, "sqrt": math.sqrt, "log": math.log, "log10": math.log10}
        )

    async def execute(self, args, state, logger):
        expression = args.get("expression", "")
        if not expression:
            return ToolOutput(output="Error: expression must not be empty", error="empty expression")
        try:
            return ToolOutput(output=str(self._evaluator.eval(expression)))
        except Exception as e:
            msg = f"Error: invalid expression '{expression}' ({e})"
            return ToolOutput(output=msg, error=msg)


class SubmitFinalResult(Tool):
    name = "submit_final_result"
    description = SUBMIT_DESC
    parameters: dict[str, Any] = {"final_result": {"type": "string", "description": "The final result to submit to the user."}}
    required = ["final_result"]

    async def execute(self, args, state, logger):
        final_result = args.get("final_result", "")
        if not final_result:
            return ToolOutput(output="Error: final_result must not be empty", error="empty")
        return ToolOutput(output=final_result, done=True)


class EDGARSearchFree(Tool):
    name = "edgar_search"
    description = EDGAR_DESC
    parameters: dict[str, Any] = {
        "search_query": {"type": "string", "description": 'The case-insensitive search-term or phrase to search the contents of filings and their attachments. Supports wildcards (*), Boolean operators (OR, NOT), and exact phrase matching by enclosing phrases in quotation marks ("exact phrase").'},
        "form_types": {"type": "array", "items": {"type": "string"}, "description": "(optional) Limits search to specific EDGAR form types (e.g., ['8-K', '10-Q']). Default: all form types"},
        "start_date": {"type": "string", "description": "(optional) Start date for the search range in yyyy-mm-dd format.", "default": "1990-01-01"},
        "end_date": {"type": "string", "description": "(optional) End date for the search range in yyyy-mm-dd format.", "default": MAX_END_DATE},
        "top_n_results": {"type": "integer", "description": "(optional) Return only the first N results (max 100).", "default": 20},
    }
    required = ["search_query"]

    async def execute(self, args, state, logger):
        try:
            query = args["search_query"]
            start = min(args.get("start_date", "1990-01-01"), MAX_END_DATE)
            end = min(args.get("end_date", MAX_END_DATE), MAX_END_DATE)
            _validate_date("start_date", start)
            _validate_date("end_date", end)
            url = FTS_URL.format(q=quote(query), s=start, e=end)
            forms = args.get("form_types")
            if forms:
                if isinstance(forms, str):
                    forms = [forms]
                url += "&forms=" + ",".join(forms)
            top_n = int(args.get("top_n_results", 20))
            data = json.loads(_http(url))
            out = []
            for hit in data.get("hits", {}).get("hits", [])[:top_n]:
                s = hit["_source"]
                adsh = s["adsh"]
                doc = hit["_id"].split(":", 1)[1] if ":" in hit["_id"] else ""
                base = f"https://www.sec.gov/Archives/edgar/data/{int(s['ciks'][0])}/{adsh.replace('-', '')}"
                out.append(
                    {
                        "cik": s["ciks"][0],
                        "company": (s.get("display_names") or [""])[0],
                        "form_type": s.get("root_forms", [s.get("form")])[0] if s.get("root_forms") else s.get("form"),
                        "filed_at": s.get("file_date"),
                        "period_ending": s.get("period_ending"),
                        "link": f"{base}/{doc}" if doc else base,
                        "link_to_html": f"{base}/{adsh.replace('-', '')}-index.htm",
                    }
                )
            return ToolOutput(output=json.dumps(out, default=str))
        except Exception as e:
            return ToolOutput(output=f"EDGAR search failed: {e}", error=str(e))


class ParseHtmlPageFree(Tool):
    name = "parse_html_page"
    description = PARSE_DESC
    parameters: dict[str, Any] = {
        "url": {"type": "string", "description": "The URL of the HTML page to parse"},
        "key": {"type": "string", "description": "The key to use when saving the result in the conversation's data storage."},
    }
    required = ["url", "key"]

    async def execute(self, args, state, logger):
        try:
            url, key = args["url"], args["key"]
            html = _http(url).decode("utf-8", errors="ignore")
            soup = BeautifulSoup(html, "html.parser")
            for t in soup(["script", "style"]):
                t.extract()
            text = soup.get_text()
            lines = (ln.strip() for ln in text.splitlines())
            chunks = (ph.strip() for ln in lines for ph in ln.split("  "))
            plain = "\n".join(c for c in chunks if c)
            if not plain:
                raise ValueError("HTML output was empty")
            tool_result = ""
            if key in state:
                tool_result = "WARNING: The key already exists in the data storage. The new result overwrites the old one.\n"
            state[key] = plain
            tool_result += f"SUCCESS: The result has been saved to the data storage under the key: {key}.\n"
            tool_result += "The data_storage currently contains the following keys:\n" + "\n".join(state.keys())
            return ToolOutput(output=tool_result)
        except Exception as e:
            return ToolOutput(output=f"Error parsing HTML page: {e}", error=str(e))


class RetrieveInformationFree(Tool):
    name = "retrieve_information"
    description = RETRIEVE_DESC
    parameters: dict[str, Any] = {
        "prompt": {"type": "string", "description": "The prompt that will be passed to the LLM. You MUST include at least one data storage key in the format {{key_name}}."},
        "input_character_ranges": {"type": "array", "description": "(optional) Portions of documents to extract.", "items": {"type": "object"}},
    }
    required = ["prompt"]

    def __init__(self, llm: LLM, max_doc_chars: int = 120_000) -> None:
        self._llm = llm
        self._max_doc_chars = max_doc_chars

    async def execute(self, args, state, logger):
        try:
            prompt = args["prompt"]
            if not re.search(r"{{[^{}]+}}", prompt):
                raise ValueError(
                    "ERROR: Your prompt must include at least one data storage key in the format {{key_name}}."
                )
            ranges = {r.get("key"): (r.get("start"), r.get("end")) for r in args.get("input_character_ranges") or []}

            def replace(m):
                k = m.group(1)
                if k not in state:
                    raise KeyError(f"ERROR: The key '{k}' was not found in the data storage. Available: {list(state)}")
                doc = state[k]
                if k in ranges:
                    return doc[ranges[k][0] : ranges[k][1]]
                return doc

            full = re.sub(r"{{([^{}]+)}}", replace, prompt)
            note = ""
            if len(full) > self._max_doc_chars:
                # Mirrors the official harness behaviour on oversized documents:
                # the request would fail on token limits, so cap it and point
                # the agent at input_character_ranges instead of burning
                # minutes of retries on a doomed multi-MB request.
                note = (
                    f"\n\n[TOOL NOTE: the substituted documents totaled {len(full):,} characters and were "
                    f"truncated to the first {self._max_doc_chars:,}. Use input_character_ranges to read "
                    "specific sections of the stored documents.]"
                )
                full = full[: self._max_doc_chars]
            response = await self._llm.query(full)
            return ToolOutput(output=response.output_text_str + note)
        except Exception as e:
            return ToolOutput(output=f"Retrieve information failed: {e}", error=str(e))


class PriceHistoryFree(Tool):
    name = "price_history"
    description = PRICE_DESC
    parameters: dict[str, Any] = {
        "ticker": {"type": "string", "description": "Ticker symbol (e.g. AAPL)."},
        "start_date": {"type": "string", "description": "Start date YYYY-MM-DD (inclusive)."},
        "end_date": {"type": "string", "description": "End date YYYY-MM-DD (inclusive)."},
        "asset_class": {"type": "string", "enum": ["equity", "etf", "crypto", "fx"], "description": "Asset class."},
    }
    required = ["ticker", "start_date", "end_date", "asset_class"]

    async def execute(self, args, state, logger):
        try:
            ticker = str(args["ticker"]).strip()
            start, end = args["start_date"], args["end_date"]
            _validate_date("start_date", start)
            _validate_date("end_date", end)
            start, end = min(start, MAX_END_DATE), min(end, MAX_END_DATE)
            if start > end:
                raise ValueError(f"start_date '{start}' is later than end_date '{end}'.")
            from datetime import datetime

            p1 = int(datetime.strptime(start, "%Y-%m-%d").timestamp())
            p2 = int(datetime.strptime(end, "%Y-%m-%d").timestamp()) + 86400
            url = (
                f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(ticker)}"
                f"?period1={p1}&period2={p2}&interval=1d&events=div%2Csplit"
            )
            data = json.loads(_http(url))
            res = data["chart"]["result"][0]
            ts = res.get("timestamp") or []
            closes = res["indicators"]["quote"][0]["close"]
            lines = ["date,close"]
            for t, c in zip(ts, closes):
                if c is not None:
                    d = datetime.fromtimestamp(t).strftime("%Y-%m-%d")
                    lines.append(f"{d},{round(float(c), 2)}")
            if len(lines) == 1:
                return ToolOutput(output=f"No pricing data returned for {ticker} {start}..{end}")
            return ToolOutput(output="\n".join(lines))
        except Exception as e:
            return ToolOutput(output=f"Price fetch failed: {e}", error=str(e))


class WebSearchStub(Tool):
    name = "web_search"
    description = WEB_DESC
    parameters: dict[str, Any] = {"search_query": {"type": "string", "description": "The query to search for."}}
    required = ["search_query"]

    async def execute(self, args, state, logger):
        msg = (
            "web_search is temporarily unavailable in this deployment. "
            "SEC filings (edgar_search) are the authoritative source for financial data; "
            "use them directly. For prices use price_history."
        )
        return ToolOutput(output=msg, error="web_search unavailable")


def _wrap_llm_timeout(llm: LLM, timeout_s: float = 120, retries: int = 3) -> LLM:
    """Per-request timeout + retry around llm.query. Without this a single
    stuck provider request blocks forever: the agent TimeLimit only fires
    between turns, never mid-request (the self-harness MVP-2 lesson).
    """
    orig = llm.query

    async def query_with_timeout(*args, **kwargs):
        last: Exception | None = None
        for attempt in range(retries):
            try:
                return await asyncio.wait_for(orig(*args, **kwargs), timeout=timeout_s)
            except TimeoutError:
                last = TimeoutError(f"LLM request timed out after {timeout_s}s (attempt {attempt + 1}/{retries})")
            except Exception as e:
                last = e
        raise last or RuntimeError("llm query failed")

    llm.query = query_with_timeout  # type: ignore[method-assign]
    return llm


_PROXY_MODEL = "openai/deepseek-v4-flash"
_PROXY_LOADED = False
POLICY_FILES = (
    "research_policy.md",
    "verification_policy.md",
    "submission_policy.md",
)


def compose_harness_prompt(prompt_file: Path) -> str:
    """Compose independently evolvable policy surfaces into one system prompt."""
    parts = [prompt_file.read_text().strip()]
    enabled: set[str] = set()
    if variant_file := os.environ.get("BETTER_HARNESS_VARIANT_FILE"):
        try:
            enabled = set(json.loads(Path(variant_file).read_text()).get("values", {}))
        except (OSError, ValueError):
            enabled = set()
    for name in POLICY_FILES:
        if name.removesuffix(".md") not in enabled:
            continue
        path = prompt_file.parent / name
        if not path.exists():
            continue
        content = path.read_text().strip()
        if content:
            parts.append(f"## {path.stem.replace('_', ' ').title()}\n{content}")
    return "\n\n".join(parts) + "\n"


def _ensure_proxy_models() -> None:
    """Register a proxy-routed model entry (openai provider -> model name
    deepseek-v4-flash) by cloning an existing openai registry entry, so the
    standard OpenAI client picks up OPENAI_BASE_URL/OPENAI_API_KEY and the
    proxy routes by model name. Idempotent.
    """
    global _PROXY_LOADED
    if _PROXY_LOADED:
        return
    from model_library.register_models import get_model_registry

    registry = get_model_registry()
    if _PROXY_MODEL in registry:
        _PROXY_LOADED = True
        return
    donor_key = "openai/gpt-4.1-mini-2025-04-14"
    if donor_key not in registry:
        donor_key = next(k for k in registry if k.startswith("openai/gpt-4.1"))
    cfg = registry[donor_key].model_copy(
        update={
            "full_key": _PROXY_MODEL,
            "slug": "openai_deepseek-v4-flash",
            "provider_endpoint": "deepseek-v4-flash",
            "label": "DeepSeek V4 Flash (via OpenAI-compatible proxy)",
        }
    )
    registry[_PROXY_MODEL] = cfg
    _PROXY_LOADED = True


def get_agent(model_name: str, prompt_text: str, log_dir: Path, *, max_turns: int, max_time: int, max_tokens: int, temperature: float) -> Agent:
    _ensure_proxy_models()
    if model_name == _PROXY_MODEL:
        # The OpenAI-compatible proxy only serves /chat/completions (not the
        # Responses API) and hangs on streamed responses for this model, so:
        # use_completions=True and stream_completions=False.
        from model_library.providers.openai import OpenAIConfig, OpenAIModel

        llm = OpenAIModel(
            "deepseek-v4-flash",
            "openai",
            config=LLMConfig(
                max_tokens=max_tokens,
                temperature=temperature,
                supports_tools=True,  # without this flag tools are stripped from the request
                provider_config=OpenAIConfig(stream_completions=False),
            ),
            use_completions=True,
        )
        # model_library eagerly builds its default client (AiohttpTransport,
        # timeout=None) into the global client registry during __init__, and
        # assign_client is a no-op when the key is already taken. Overwrite the
        # registry entry with a standard OpenAI SDK client (default transport,
        # sane timeout) — the only combination that works against this proxy.
        import model_library.base as _ml_base
        from openai import AsyncOpenAI

        _ml_base.client_registry[llm._client_registry_key] = AsyncOpenAI(
            api_key=os.environ.get("OPENAI_API_KEY"),
            base_url=os.environ.get("OPENAI_BASE_URL") or None,
            max_retries=2,
            timeout=120.0,
        )
    else:
        llm = get_registry_model(model_name, LLMConfig(max_tokens=max_tokens, temperature=temperature))
    llm = _wrap_llm_timeout(llm)
    tools = [
        WebSearchStub(),
        RetrieveInformationFree(llm=llm),
        ParseHtmlPageFree(),
        EDGARSearchFree(),
        Calculator(),
        PriceHistoryFree(),
        SubmitFinalResult(),
    ]

    def _before_query(history: list[InputItem], last_error: Exception | None) -> list[InputItem]:
        if isinstance(last_error, MaxContextWindowExceededError):
            from model_library.agent.hooks import truncate_oldest

            return truncate_oldest(history)
        if history and isinstance(history[-1], RawResponse):
            history.append(
                TextInput(
                    text=(
                        "Your last response produced no tool call. "
                        "Call `submit_final_result` if you have a final result, "
                        "otherwise continue with the next tool call."
                    )
                )
            )
        return default_before_query(history, last_error)

    def _should_stop(turn_result: TurnResult) -> bool:
        return False

    return Agent(
        llm=llm,
        tools=tools,
        name="finance",
        log_dir=log_dir,
        config=AgentConfig(
            turn_limit=TurnLimit(max_turns=max_turns) if max_turns else None,
            time_limit=TimeLimit(max_seconds=max_time),
        ),
        hooks=AgentHooks(before_query=_before_query, should_stop=_should_stop),
    )


def run_question(
    question: str,
    *,
    model: str = "openai/deepseek-v4-flash",
    log_dir: Path,
    max_turns: int = 14,
    max_time: int = 600,
    max_tokens: int = 6000,
    temperature: float = 0.0,
    prompt_file: Path | None = None,
) -> dict[str, Any]:
    prompt_text = compose_harness_prompt(prompt_file or WORKSPACE / "prompt.txt")
    agent = get_agent(
        model,
        prompt_text,
        log_dir,
        max_turns=max_turns,
        max_time=max_time,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    started = time.monotonic()

    async def _run():
        return await agent.run(
            [SystemInput(text=prompt_text), TextInput(text=QUESTION_PROMPT.format(question=question))],
            question_id="q",
        )

    result = asyncio.run(_run())
    aggregate_tokens = total_tokens(getattr(result, "final_aggregated_metadata", None))
    compaction_tokens = total_tokens(getattr(result, "final_compaction_metadata", None))
    tokens = None
    if aggregate_tokens is not None or compaction_tokens is not None:
        tokens = (aggregate_tokens or 0) + (compaction_tokens or 0)
    return {
        "final_answer": result.final_answer or "",
        "success": bool(result.success),
        "stop_reason": str(result.stop_reason),
        "turns": result.total_turns,
        "tokens": tokens,
        "error_count": result.error_count,
        "tool_calls_count": result.tool_calls_count,
        "tool_usage": result.tool_usage,
        "duration_s": round(time.monotonic() - started, 1),
    }
