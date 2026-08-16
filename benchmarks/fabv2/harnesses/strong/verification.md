Before submission, run this deterministic audit:

1. Coverage: every requested output maps to a supported fact or an explicitly labelled gap.
2. Identity: company, security, geography, and fiscal period match the question.
3. Units: currency scale, percentage versus percentage-point, adjusted versus raw, and per-share versus total are explicit.
4. Arithmetic: recompute every derived value with `calculate`; preserve the expression in evidence.
5. Comparability: both sides of any comparison use compatible dates and definitions.
6. Direction and sanity: sign, ranking, magnitude, and rounding agree with the inputs.
7. Citation: each material input has a direct source URL, not merely a search result.
8. Forecast provenance: every constant projected ratio traces to the requested source period. Guidance is used only where the task explicitly requests guidance; all other carried-forward operating metrics use the latest complete actual period unless the task says otherwise.
9. Line-item taxonomy: every denominator matches the exact requested filed line. Reconcile, but do not silently combine, separately reported neighboring expenses such as SG&A and amortization.
10. Cash-flow bridge: reconcile each noncash item to the accounting line where it entered earnings. When FCFF starts from GAAP operating income, stock-based compensation and D&A have already reduced that income and must be added back exactly once; do not subtract them again as cash costs. Subtract CapEx and cash uses from working capital exactly once. Write the reconciled FCFF identity before calculating the forecast.

If an audit fails, repair the answer or clearly qualify it. Never hide a mismatch behind confident prose.
