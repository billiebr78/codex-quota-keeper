# Measuring whether Codex Quota Keeper saves tokens

The goal is **fewer tokens per successfully completed coding task**, without a loss of correctness. Lower token counts alone are not a success.

## Controlled comparison (Codex VS Code)

1. Pick one short, reproducible coding task with an unambiguous pass/fail test. Start from the **same Git commit** in two separate disposable working folders.
2. Install the **same three CQK hooks** in both folders so telemetry overhead and token measurement are comparable. In the baseline folder, remove **only the CQK-managed AGENTS.md block** while leaving hooks and any other policies intact; in the optimized folder, keep the managed block. Compare final file contents to confirm that only policy differs. If other AGENTS.md files apply from parent directories, control them too.
3. Use the same extension version, model, reasoning effort, tool permissions, exact task prompt and verification criteria. Start a **fresh Codex chat** for every trial and do not reuse handoffs from prior trials.
4. Perform the task in both conditions, then run the same test suite and review the result. Record failures and manual correction separately; do not claim a win if quality is lower.
5. After each trial, run `py -m codex_quota_keeper stats --json`. Associate the new session with the trial by its recorded modification time and session hash. Record `model_tokens.input_tokens`, `cached_input_tokens`, `output_tokens`, prompt/tool counts and `token_usage_reports`. If a session cannot be identified confidently, discard that trial.
6. Repeat several times, alternating which condition runs first (AB/BA), because caching, model variability and environmental differences can affect outcomes.

## Suggested evaluation

| Trial | Conditions | Test status | Input | Cached input | Output | Total (input + output) | Human corrections |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| 1 | Baseline | pending | — | — | — | — | — |
| 1 | Optimized | pending | — | — | — | — | — |

Report token changes **only among equivalent passing results**. Show both total tokens and uncached input (`input - cached_input`), not cached input as an extra additive amount. Cached tokens are a subset of input, and reasoning tokens are a subset of output. Also report failed or incomplete runs so the result is not cherry-picked.

## Limits

- `PostModelRequest` counts **observed requests**; missing hook events or unreported token fields lead to incomplete totals.
- These are not subscription quota, token pricing, or a real-time context-window gauge.
- Any claim of efficiency improvement requires repeated measurements, equivalent outcomes and a clear note that results may not generalize.
- Do not add more instrumentation, databases or background services just to run this first benchmark.
