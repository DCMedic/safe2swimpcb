# Recovery and X preview safety

These safeguards are development-branch changes until reviewed and deliberately
released. Preparing this branch does not authorize merging, deploying, invoking
production workflows, changing runtime data, enabling paused automation, or
changing schedules. No cron expressions are changed by this work.

## Local, non-mutating checks

Run from an isolated checkout with no publishing credentials:

```sh
python -B scripts/run_x_publisher.py --dry-run --force-slot afternoon
python -B scripts/recovery_watchdog.py --dry-run
pytest -q
python scripts/validate_workflows.py
```

Omitting a mode also selects preview for both entry points. `-B` avoids incidental
Python bytecode cache files. The X preview reads the existing data snapshot. It
does not fetch or overwrite environmental data, contact X, save posting state,
consume the flag-change baseline, advance production health, or record a failed
preview as a production failure. This holds for selected posts, no-post outcomes,
guardrail rejections, and errors. Output is labeled `PUBLISHER_PREVIEW`; live
health remains labeled `PUBLISHER_HEALTH`.

The recovery preview reads local policy and heartbeats only, even if a token is
present. It reports **recovery candidates**, not an assertion that GitHub would
permit dispatch. It does not query current workflow state, cancel runs, dispatch
workflows, or alter files. Current workflow state is checked only in apply mode.

## Workflow privilege boundaries

- Manual X dispatch defaults to `dry-run`; only a scheduled run or explicit
  `publish` dispatch on `main` enters the publishing job. Push events preview.
- Manual recovery dispatch defaults to `dry-run`; push events test and preview.
  Existing schedule and workflow-completion triggers retain their production
  behavior on `main`; explicit manual recovery requires `apply`.
- Preview jobs use read-only tokens and no persisted checkout credentials.
  X secrets and repository write permission are confined to the publishing job.
  Recovery's `actions: write` is confined to its apply job, which has no
  repository write permission.
- Preview and production jobs have separate concurrency groups so a preview
  cannot replace a pending live job. X preview verifies that `data/` is unchanged.
- X run titles identify publish and preview using the exact production-job gate.
  Recovery ignores marked previews, including completed manual previews, before
  cooldown and cancellation decisions. X preview completion cannot invoke the
  recovery workflow's live job. The independent scheduled recovery checks remain
  unchanged.
- On a development ref, selecting a live manual mode skips the live job. It
  does not silently check out `main` and perform a production action.

Manual dispatch itself is an external operation. These documented modes do not
grant permission to run a workflow. Obtain the required approval first.

## Recovery decisions

Apply mode requires an explicit `--apply`, a matching policy repository, and a
token. Within GitHub Actions it rejects a non-`main` ref. Recovery:

1. Skips any lane whose optional `enabled` value is not `true` (omission preserves
   the existing enabled behavior).
2. Checks GitHub's workflow metadata and suppresses recovery unless the workflow
   is active. It never calls the workflow-enable API.
3. Scopes runs to `main`, the expected repository and workflow ID, and production
   event types. PR and fork runs cannot become cancellation targets.
4. Queries active statuses separately from recent completed runs so old queued
   runs are not hidden by the recent-run page. Active pages have a bounded limit;
   incomplete or malformed results fail closed.
5. Leaves `waiting` runs alone because they may await a protected-environment
   approval. They suppress dispatch rather than becoming cancellation targets.
6. Confirms a canceled run is actually completed. An accepted cancellation or
   HTTP 409/422 does not prove completion. Pending cancellations defer dispatch
   until a later evaluation. A confirmed cancellation by this evaluation is
   excluded from its own failed-dispatch cooldown, allowing immediate replacement.
   Unrelated cancellations, racing successes, and newer active attempts still
   count. Cancellation attribution is not persisted across evaluations, so a
   cancellation only confirmed later retains the conservative retry delay.
7. Rechecks live state immediately before dispatch. A new run, a disabled
   workflow, remaining active runs, or a query failure prevents dispatch.

Legacy X runs without either configured title are deliberately ambiguous: old
previews also used a job called `publish`, so that job name is not proof of live
publication. Unmarked active runs suppress recovery and are never automatically
canceled. Completed legacy dispatches retain the existing bounded cooldown or
failure delay, labeled as unclassified rather than successful production. New
previews carry the explicit preview title and do not enter that fallback.

## Validation and remaining limits

Regression tests cover byte-for-byte and modification-time preservation of X
state/health, repeated flag-change previews, absent state files, successful
publishing via a stub, disabled recovery, branch/repository/event filtering,
protected approval waits, cancellation races, and workflow privilege boundaries.
Run-status, creation-time, and completed-conclusion validation also fail closed
when GitHub supplies incomplete or unsupported state.
Network mutation calls in these tests are mocked; tests do not contact GitHub or X.

GitHub's read/check/dispatch operations are not atomic. A workflow can start or
be paused after the final read. Pagination is deliberately bounded and rate
limits or uncertain API responses stop recovery rather than guess. Publisher
API success followed by a failed local persistence remains a separate
exactly-once delivery risk; these preview fixes do not claim to solve it.

Production rollout needs separate approval and validation of the exact reviewed
commit. Do not enable workflows or change schedules to test this branch.
