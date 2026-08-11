# Lessons learned

Practice notes from building and running MVP-1/MVP-2. Each lesson earned its place
by costing something. Append-only.

## Experimental method

- **Pre-registration only works if it can hurt you.** MVP-1's stop rule fired
  against the experiment's own momentum — the single most valuable event of the
  project. A rule you would renegotiate after seeing data is not a rule.
- **Tier labels track price, not capability on your distribution.** deepseek-v4-
  "flash" saturated an authored task suite twice (0.917 baseline, holdout at
  ceiling). Calibrate models against *your* tasks; never trust the tier name.
- **Model selection is instrument calibration, not quality preference** — legal
  when it uses baseline numbers only (never evolution results) and every probe is
  reported. gpt-4.1-nano was chosen for being weak-but-tool-capable.
- **Designer=runner bias is real and measurable**: two consecutive failures to
  author tasks with headroom for a specific model is that bias in data form.
  Third-party benchmarks (TB2.1) dodge the whole failure class.
- **A B5-style check is a saturation alarm**: stock-prompt baseline == minimal-seed
  baseline means the suite can't see the surface you plan to edit.
- **Determinism must be measured, not assumed**: deepseek at temperature=0 was
  0-flaky over 20 repeats/case; gpt-4.1-nano at the same setting is genuinely
  flaky (0.33 pass fractions). Same endpoint, same config, different physics.
- **Schema-check before writing analysis code** — the repeats.json reader was
  written against an imagined schema (`cases`) instead of the real one
  (`per_case`) and failed on first contact. Read one real artifact first.

## Engineering the loop

- **Serialize runs that share a workspace.** Surface overrides are written into
  the live workspace during eval (`workspace_override_context`); two concurrent
  runs would clobber each other's harness. One experiment at a time per workspace.
- **Long runs: `nohup … & disown` + a Monitor watching for a DONE marker.** The
  sandboxed foreground shell caps at 10 minutes; backgrounded harness tasks are
  killed at the cap too. Print explicit `STAGE_DONE exit=$?` markers — greppable,
  and silence stays distinguishable from success.
- **Absolute paths in generated configs**: relative paths resolve against the
  config file's directory and silently double up (`runs/x/runs/x/...`).
- **Guards need absolute floors, not just ratios** — a 3× bloat ratio against a
  78-byte seed rejects any real edit; a latency ratio over sub-second runs is
  machine noise. Pair every ratio with an absolute floor.
- **Protocol promises need implementation audits**: "log `system_fingerprint`
  per rollout" lived in the pre-registration for four full campaigns before
  anyone noticed no code wrote it. Grep the code for every promise the protocol
  makes.
- **Intentional weird bytes (NBSP) beat lint**: write them as ` ` escapes —
  visible in review, and RUF001 stays quiet.

## Reading results

- **Liveness ≠ efficacy.** A loop that runs cleanly and promotes something looks
  identical to a loop that works, until an equal-budget baseline exists. M1's
  prediction precision 1.0 on a toy whose failure messages contain the answers is
  liveness only.
- **Papers without an equal-budget arm can't attribute gains to their method**
  (see [paper-study.md](paper-study.md) on 2606.09498): evolution is itself
  test-time compute; seed-vs-evolved comparisons conflate search spend with
  method value.
- **Read the ledger before the pass rate** — prediction accuracy is readable
  after one iteration; pass-rate curves on small task sets are noise for many.
