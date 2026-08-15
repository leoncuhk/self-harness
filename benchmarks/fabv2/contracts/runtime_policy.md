The file must be strict JSON with `schema_version: 1`; unknown keys are forbidden.

- `filing_index.forms`: non-empty subset of `10-K`, `10-Q`, `8-K`; dates use `YYYY-MM-DD`; `top_n_per_form` 1-10; `max_tickers` 1-6.
- `search_page.context_chars`: 100-5000; `max_results_per_query`: 1-100; `max_calls_per_document`: 1-20.
- `tool_output.enabled`: boolean; `max_chars`: 1000-50000; `tail_chars`: 0-10000 and smaller than `max_chars`; `tools`: unique non-empty subset of the Prime middleware tool names `bash`, `ipython`, `read`.

`fab_tools.py` subcommands such as `search_page_text` are not middleware tool names and must not appear in `tool_output.tools`.
