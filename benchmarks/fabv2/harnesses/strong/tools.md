The evaluator-owned `fab_tools.py` is the stable data plane. Inspect its exact CLI with:

`<python> fab_tools.py --help`

Core calls are `calculate`, `edgar-search`, `fetch-page`, and `price-history`. Use the Python executable supplied in the task message. Quote multi-word expressions and queries. Examples:

- `<python> fab_tools.py calculate '(2865507 / 1905871) ** 0.5 - 1'`
- `<python> fab_tools.py edgar-search 'company phrase' --form 10-K --top-n 5`
- `<python> fab_tools.py fetch-page 'https://www.sec.gov/Archives/...'`
- `<python> fab_tools.py price-history AAPL 2024-01-01 2024-01-31`

Load large page text into a Python variable once, then search it locally with case-insensitive keywords and nearby context. Do not repeatedly download or reread the same document. Use the calculator for every reported derived number, including ratios, growth, annualization, averages, and percentage changes.
