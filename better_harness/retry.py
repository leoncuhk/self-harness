"""Transient-failure retry policy.

Every model call in this project crosses a third-party proxy, and that proxy has
now killed four multi-hour stages. The retry ladders written in response kept
being sized for a blip rather than for what actually happens: the first was
2s/4s, the second 5 attempts over ~50s of backoff. Both were exhausted by a
single outage while the endpoint came back a few minutes later.

So the policy is stated as a **total time budget** rather than an attempt count.
What matters for an unattended stage is "keep trying for N minutes", not "try k
times"; an attempt count silently changes meaning every time the backoff is
tuned.

Two properties this deliberately keeps:

- **Retries are visible.** Each one prints to stderr, so a stage log shows that
  the run stalled and recovered rather than appearing to have run cleanly. A
  silent retry turns a degraded provider into an invisible confound.
- **Only transport failures retry.** A model that answers with something wrong is
  a result. Retrying it would be resampling until the answer is convenient,
  which is a different experiment than the one being run.
"""

from __future__ import annotations

import sys
import time
from collections.abc import Callable

# Sized against the observed failure: outages lasting minutes, not seconds.
DEFAULT_MAX_TOTAL_S = 600.0
DEFAULT_INITIAL_S = 5.0
DEFAULT_MAX_INTERVAL_S = 60.0

TRANSIENT_TOKENS: tuple[str, ...] = (
    "overloaded",
    "overloaded_error",
    "error code: 529",
    "529 -",
    "rate limit",
    "timeout",
    "timed out",
    # The request never got a response, so retrying is safe.
    "server disconnected",
    "connection error",
    "connection reset",
    "connection aborted",
    "remoteprotocolerror",
    "apiconnectionerror",
    "error code: 502",
    "error code: 503",
    "error code: 504",
    "bad gateway",
    "service unavailable",
    "gateway timeout",
)


def is_transient(message: str) -> bool:
    """Return whether a failure is transport noise rather than an answer."""
    lowered = message.lower()
    return any(token in lowered for token in TRANSIENT_TOKENS)


def retry_transient[T](  # noqa: PLR0913 - sleep/now are injected for tests, the rest are policy
    call: Callable[[], T],
    *,
    label: str,
    max_total_s: float = DEFAULT_MAX_TOTAL_S,
    initial_s: float = DEFAULT_INITIAL_S,
    max_interval_s: float = DEFAULT_MAX_INTERVAL_S,
    sleep: Callable[[float], None] = time.sleep,
    now: Callable[[], float] = time.monotonic,
) -> T:
    """Call ``call``, retrying transport failures until the time budget is spent.

    Backoff doubles from ``initial_s`` up to ``max_interval_s``. The budget is
    checked against elapsed wall-clock, so a slow failing call consumes it rather
    than multiplying it.
    """
    started = now()
    interval = initial_s
    attempt = 0
    while True:
        attempt += 1
        try:
            return call()
        except Exception as exc:
            message = f"{type(exc).__name__}: {exc}"
            elapsed = now() - started
            if not is_transient(message) or elapsed + interval > max_total_s:
                raise
            # Deliberately stderr, not logging: a retry has to be visible in
            # the stage log, or a degraded provider becomes an invisible
            # confound in the run it degraded.
            sys.stderr.write(
                f"[retry] {label}: attempt {attempt} failed after {elapsed:.0f}s "
                f"({message.splitlines()[0][:160]}); sleeping {interval:.0f}s\n"
            )
            sys.stderr.flush()
            sleep(interval)
            interval = min(interval * 2, max_interval_s)
