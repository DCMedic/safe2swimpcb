# Safety evidence contract (KT-003 candidate)

## Decision-time validation

`assets/safety-state.js` and `scripts/source_evidence.py` validate timestamps and freshness at the time a decision is made. Cross-language fixtures are in `tests/fixtures/source_evidence.json`.

- Timestamps must be ISO 8601 strings with seconds and an explicit UTC offset. Missing, malformed, timezone-free or future timestamps cannot establish current evidence.
- `stale_after_hours` / secondary `freshness_hours` must be numeric, finite, positive and at most 24 hours. The exact expiry boundary is expired. No overnight polling exemption extends safety evidence.
- `observed_at` is the selected source evidence time. If present, an invalid/null value never falls through to a newer polling time. Otherwise `official_updated_at`, then legacy `last_verified_at`, is used. `last_checked_at` describes collection/reachability only.
- Direct-source adapters preserve meaningful official issuance/update times. NWS evidence ages from issuance. A direct undated current widget may use successful observation time, explicitly not the exact official issuance time.
- A combined report expires at the oldest constituent flag or Purple observation. Collection-time `fresh` booleans and saved confidence enums never confer runtime freshness.
- A current flag also requires source identity and a successful source check. The presence of environmental forecasts, current-looking labels, or source reachability alone is insufficient.

## Meaning and provenance

Red and Single Red normalize to Red. Double Red means water closed to the public. Purple is an independent dangerous-marine-life overlay, including Purple-only reports. Unknown flag tokens and malformed containers do not become colored flags.

Conflicting explicit current flags are preserved as conflict evidence, never resolved by choosing the first or least restrictive flag. Secondary disagreement does not silently override fresh primary evidence. A stale closure or Purple restriction is not relaxed by an automatic secondary gap-fill.

VisitBeaches-derived primaries and their VisitBeaches cross-checks share a lineage and cannot corroborate themselves. New secondary summaries carry `report_at`, `freshness_hours`, `source_lineage`, and report IDs. Legacy summaries missing required freshness/provenance degrade to primary-only rather than asserting confidence.

Every safety card names the actual displayed evidence source separately from official local guidance. Source confidence, heading, freshness, meaning and graphic come from one validated snapshot.

## One browser writer

`assets/safety-ui.js` is the only live writer of primary safety panels and related Eastern cards. Regional modules provide environmental content/navigation/static fallback links only. `site-ui.js` independently ages the informational Ambassador observation panel; it cannot set current flags or confidence.

The controller rejects late responses from superseded requests, clears current-looking graphics and positive confidence after failure/timeout, and revalidates time every second and on visibility/resume. Repeated unchanged states do not mutate the live region, avoiding repeated screen-reader announcements. Runtime timestamps use absolute ISO strings so observation and check times are unambiguous.

Expired evidence remains explicitly labeled last verified, with no current-looking flag graphic. Conflicting/no-explicit/unavailable states are distinct and never imply safe swimming. A no-JavaScript PCB prerender is always a conservative cached snapshot, not an assertion that it remains current after publication. Other pages begin neutral with official links.

## Validation and release boundaries

Run:

```
python -m pytest -q
node --test tests/safety_state.test.cjs
for f in assets/*.js; do node --check "$f"; done
python -m compileall -q scripts
bash -n scripts/persist_paths.sh
python scripts/validate_workflows.py
python scripts/validate_infrastructure.py
python scripts/prerender_current_status.py
python scripts/inject_social_meta.py
python scripts/generate_sitemap.py
python scripts/verify_prerender_consistency.py
python scripts/site_health_check.py
```

The deterministic browser harness is `node tests/browser_safety.cjs`, requiring Playwright and Chromium (override `CHROMIUM_PATH` if necessary). It intercepts all requests and uses fixture data, covering PCB, Western, Eastern, Southwest, narrow viewport, no JavaScript, aging, failure and accessibility attributes. It must pass in an approved environment before production readiness is claimed. In the authoring environment, Chromium launch was blocked by an OS socket restriction; no browser result is represented as passed.

No runtime JSON, immutable history, production workflows, deployment, DNS, production security or monitoring is changed by this safety candidate. Old incomplete caches intentionally fail closed until a separately authorized collector/deployment transition supplies the explicit evidence fields. Production-only guard behavior has not been removed or modified; origin integration and compatibility must be verified before release.
