The evaluator-owned `fab_tools.py` is the stable data plane. Inspect its exact CLI with:

`<python> fab_tools.py --help`

Core calls are `calculate`, `sec-filings`, `edgar-search`, `fetch-page`, `search-page`, and `price-history`. Use the Python executable supplied in the task message. Quote multi-word expressions and queries. Examples:

- `<python> fab_tools.py calculate '(2865507 / 1905871) ** 0.5 - 1'`
- `<python> fab_tools.py sec-filings CZR --form 10-K --start-date 2022-01-01 --end-date 2025-12-31`
- `<python> fab_tools.py edgar-search 'company phrase' --form 10-K --top-n 5`
- `<python> fab_tools.py fetch-page 'https://www.sec.gov/Archives/...'`
- `<python> fab_tools.py search-page 'https://www.sec.gov/Archives/...' 'adjusted EBITDAR' 'rent obligations' --context-chars 1200`
- `<python> fab_tools.py price-history AAPL 2024-01-01 2024-01-31`

Use `sec-filings` to enumerate an issuer's exact filings by ticker and period; use `edgar-search` only when the issuer or filing is unknown. Use `search-page` first for long filings because it scans the entire visible document while returning bounded context; `fetch-page` intentionally returns only a prefix. Search metric-name variants together, then fetch or reuse only what is needed. Do not repeatedly download or reread the same document. Use the calculator for every reported derived number, including ratios, growth, annualization, averages, and percentage changes.
