Before submission, run this deterministic audit:

1. Coverage: every requested output maps to a supported fact or an explicitly labelled gap.
2. Identity: company, security, geography, and fiscal period match the question.
3. Units: currency scale, percentage versus percentage-point, adjusted versus raw, and per-share versus total are explicit.
4. Arithmetic: recompute every derived value with `calculate`; preserve the expression in evidence.
5. Comparability: both sides of any comparison use compatible dates and definitions.
6. Direction and sanity: sign, ranking, magnitude, and rounding agree with the inputs.
7. Citation: each material input has a direct source URL, not merely a search result.
8. Compute gate: every derived criterion (growth, CAGR, ratio, sum, margin, annualized value) must have a `calculate` call recorded in evidence with its expression and result. If any derived criterion in the obligation checklist lacks one, this audit fails — compute it now or label the gap explicitly. Never submit a derived figure without a calculator trace.

If an audit fails, repair the answer or clearly qualify it. Never hide a mismatch behind confident prose.
