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
- **Run logs leak the scorecard.** `report.md` content (including scorecard
  aggregates) is echoed into stage logs; checking progress with `tail` can breach
  a read-nothing rule. Grep for stage markers only, and keep scorecard rows out
  of anything a human eyeballs mid-experiment.
- **Laptop sleep kills unattended runs.** `nohup` survives the shell, not the
  OS: idle sleep freezes the process and severs every TCP connection, so all
  in-flight API calls fail together on wake — which reads as a mysterious
  "Connection error" storm that punches through per-call retries. Wrap
  multi-hour stages in `caffeinate -is`. (Cost: three dead M3 runs before the
  pattern — crash always ~2-4 iterations in, i.e. exactly when the operator
  stopped watching — gave it away.)
- **Harden the whole crash surface, not the path you were looking at.** Retries
  went onto the proposer call because that is where the first traceback pointed;
  the inner agent makes ~180 calls per M3 stage with no retry and no timeout at
  all, so the run kept dying. Count the API calls per stage per path before
  deciding where reliability work goes.
- **Any run longer than its mean time between failures needs a checkpoint.**
  Without `--resume`, a crash in iteration 3 throws away iterations 1–2, so the
  expected cost of *finishing* grows with run length — a stage can become
  unfinishable while every individual attempt looks like bad luck.
- **Read the field before hardening the method.** Every published positive
  harness-evolution result feeds execution traces to its proposer; we spent the
  whole build on selection rigor while box ② read pytest assertion text. Rigor
  around a blind diagnosis stage measures the blindness precisely.
- **A passing test suite cannot tell you the instrument is right.** 88 tests and
  a 213-line verification ladder were green throughout the entire period in which
  every sealed-split number in the repo read 0/20 against a true 17–18/20. Unit
  tests check that the code does what the code says; they cannot check that what
  the code says is what you meant to measure. Only an independent re-derivation
  from the raw evidence can, and it has to share no code with the thing it audits.
- **Never let "we failed to measure" score as "the agent failed".** A parse miss
  scored 0 exactly like a wrong answer, so an infrastructure defect was
  indistinguishable from a capability result — and biased every estimate
  downward by precisely the defect rate.
- **Grep the failure corpus before trusting a classifier.** φ(r) labelled real
  assertion failures `unbounded_retry_loop` because pytest echoes the test source
  and this suite's `@pytest.mark.timeout(420)` decorator matched a `timeout`
  rule. Text heuristics over free-form output need their inputs *looked at*, not
  imagined; the classifier was wrong in a fixed direction, which is worse than
  being silent.
- **Every ratio-plus-floor threshold has a hole between the two.** The bloat
  guard rejected the one substantive proposal at 9.92× and admitted the broken
  one at 4.76× — because the second was under the absolute floor. Pairing a ratio
  with a floor fixes the small-seed problem and creates a band where the ratio
  does not apply. Check what falls in the band.
- **Audit the artifacts of a run you are about to trust, not after.** The M3 run
  was stopped four iterations in because an audit ran *while it was going*, not
  because it crashed. Everything it had produced was inadmissible for reasons
  visible from artifacts alone, at zero rollout cost.
- **Passing a path to pytest that only sometimes exists makes rootdir drift with
  run count.** pytest keeps non-option argv tokens as rootdir candidates *if the
  file already exists*, and the values of `--junitxml` / `--evals-report-file`
  are such tokens. First run into a case directory: absent, ignored. Second run:
  present, rootdir lifts to the repo root, every nodeid changes shape, and the
  parser stops recognising its own results. Write artifacts outside the argv, or
  clear them before invoking. The symptom looked impossible — identical argv,
  identical cwd, different nodeids — which is why it survived so long.
- **Two defects that always appear together are usually one defect.** The sealed
  split was described as hit by "double evaluation" *and* "a parse bug". The
  double evaluation was the trigger *for* the parse bug, and treating them as
  independent hid the fact that `--resume` triggers it too. When two causes
  co-occur perfectly, look for the arrow between them before writing them down
  as a list.
- **A second opinion that duplicates your fix is still worth reading.** A
  parallel session fixed the same bug independently; its patch was redundant, its
  *root-cause analysis* was not — it found the pytest mechanism and the resume
  path this side had missed while writing a confident and wrong commit message.
