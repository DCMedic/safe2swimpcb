# KT-003 isolated integration candidate

This is a review candidate, not a production release. It combines the safety
evidence/controller work, release-integrity tooling, and recovery/X-preview
safeguards on the `e327b9a9d270889c56f56468f97f09d21b3b402a` baseline.
No merge, deployment, production workflow dispatch, runtime-data edit, DNS or
security-setting change, monitoring reactivation, or schedule change is part of
this preparation.

## Integration boundaries

- The public artifact allowlist includes both `assets/safety-state.js` and
  `assets/safety-ui.js`. The staging step binds their HTML references and the
  renderer's local module dependency to the actual content hashes.
- `tests/test_candidate_integration.py` builds representative PCB, Western,
  Eastern, and Southwest pages, stages the approved public files, checks safety
  script order and content identity, and loads the fingerprinted CommonJS entry.
- PR validation runs every asset's JavaScript syntax check, the safety Node
  tests, the full Python suite, workflow/infrastructure validators, build
  transforms, prerender/site-health checks, and explicit artifact staging.
- The deterministic browser harness accepts `SITE_ROOT=/absolute/artifact/path`
  to exercise the staged, fingerprinted artifact, rather than only source HTML.
  All browser requests are intercepted and use local fixtures. PR validation
  installs pinned official Playwright and its Chromium in the ephemeral runner
  and executes this harness against that job's staged artifact. It uses no
  production credentials or publishing permissions; checkout credentials are
  not persisted. Only an observed success for the exact PR head counts as a pass.
- Build transforms and artifact staging belong in a separate clean checkout.
  Do not commit generated runtime data or treat local test results as a genuine
  GitHub workflow run. Local builds cannot produce passing release attestation
  without real workflow identity and recorded per-step outcomes.

## Reproduction

Use an isolated checkout of the exact reviewed commit, Python dependencies from
`requirements.txt`, and Node. Run the checks in `.github/workflows/site-health.yml`.
The public artifact destination must be new and outside the source checkout.

For browser validation in an environment allowed to launch Chromium, install
Playwright 1.62.1 and its Chromium revision. The harness uses that browser by
default; `CHROMIUM_PATH` can explicitly select an existing approved executable:

```sh
SITE_ROOT=/absolute/artifact/path node tests/browser_safety.cjs
```

Keep source SHA, test results, staged-byte inventory, and serving-target
verification separate. A passing local build never establishes a deployed
release, current collector observations, or safe swimming conditions.

## Outstanding release gates

1. **Real browser validation.** The authoring environment previously blocked
   Chromium launch with an operating-system socket restriction. A launch failure
   is not a passing browser test. The isolated PR validation now runs deterministic
   browser assertions against the staged artifact; verify its exact-head result.
   This covers four regional pages, a narrow viewport, accessibility attributes,
   freshness aging, failed refresh, and no JavaScript. It is not a complete
   accessibility audit, cache-upgrade matrix, or production-guard compatibility
   test. Those broader release checks remain separate.
2. **Production guard compatibility.** A prior KT-002 public diagnostic at
   21:41 UTC reported VPS hosting/PCB ownership and found
   `https://knowthegulf.com/assets/ktg-status-guard.js`, SHA-256
   `fe9a3e5c79a59c4b6c50d2767f8c3038aeb725dd1807745e8cf7d334a7358416`.
   That guard was absent from the repository baseline and observed safety labels,
   freshness, meaning, and flag-pole nodes. This historical observation does not
   establish the current VPS builder or overlay. The new single-writer
   controller's compatibility with the actual serving pipeline remains
   unverified. This branch neither removes nor modifies a production guard.
3. **Hosting target decision.** The repository's `CNAME` still names
   `knowthegulf.com`. The new Pages preflight deliberately rejects a nonempty
   staged `CNAME` before upload because Pages-origin isolation is unresolved.
   Do not remove that block or change DNS merely to obtain a green deployment.
   Pages and VPS identity/cache/security checks are different release gates.
4. **VPS integration and rollout authorization.** Owner diagnostics now establish
   the active runtime builder, public-releases layout, private helper overrides,
   guard injection, collector selection, and existing recovery paths. See
   `docs/KT003_VPS_INTEGRATION.md`. The string-redacted exports are not executable
   source: the narrow remaining handoff is exact non-secret builder, guard,
   helper and public-list source. Actual builder integration, a durable pin,
   data-preserving rollback, and effective security/cache qualification remain
   release gates. No live VPS release or rollback has been attempted by this work.
5. **Review and CI.** Check the exact draft-PR commit and its required CI before
   judging merge readiness. These remaining release gates are not waived by
   Python/Node unit tests, artifact hashes, or a successful Lighthouse run.

## Draft-PR trigger audit

The audited remote `main` baseline matches the SHA above. Its production push
triggers are restricted to `main`. Only `site-health.yml` listens to
`pull_request`; it uses `contents: read` and performs validation. Its workflow
name, `Validate Know the Gulf site health`, is not in production deployment or
recovery `workflow_run` trigger lists. No workflow is manually dispatched by
opening the draft PR. Recheck the remote base and both the base/candidate
workflow definitions before publishing later revisions. A draft PR does not
authorize a merge or production action.
