# KT-003 VPS integration checkpoint

This is engineering preparation, not a release approval. PR #58 remains a draft.
No merge, deployment, service/timer/configuration change, or live-data mutation
is authorized by this document. The owner operates Termius; direct assistant SSH
setup and attempts are out of scope.

## Established operator evidence

The owner supplied read-only diagnostics on 2026-11-11 between 22:57 and 23:43
UTC. Reuse them rather than repeat the architecture investigation:

- Caddy was active. The enabled deployment timer invoked its service about every
  two minutes, with scheduling accuracy/jitter. PCB and Destin shadow collectors
  had independent enabled timers and successful recent service exits.
- The current symlink targeted a directory under `public-releases`, not the
  older documented `releases` directory. The observed application SHA and
  `.deployed-sha` both identified
  `e327b9a9d270889c56f56468f97f09d21b3b402a`.
- The deployment wrapper invokes a private controller. The selected engine was
  RUNTIME, not LEGACY. Its `deploy.py` hash was
  `ca876be6b44806e787466272fca4c2a939a30d20a5efcee75f5ddc0b3ad4c133`.
- The runtime engine selects collector input, obtains a remote source SHA,
  checks its checkout identity, builds and validates a public release, switches
  the current symlink, smoke-tests, and updates its deployed marker. The shown
  `promote` branch immediately raises, so it is not an available promotion API.
- Private `public_release.py` copies helper overrides into the source checkout,
  executes build helpers, applies its own public-file list, rerenders safety
  panels, injects `ktg-status-guard.js`, and writes its own release marker.
- The active guard was 5,127 bytes with SHA-256
  `fe9a3e5c79a59c4b6c50d2767f8c3038aeb725dd1807745e8cf7d334a7358416`.
  `safety-ui.js` and `safety-state.js` were absent from that observed release.
- Runtime selection has per-lane locking, payload/report validation, a previous
  release fallback, non-regression checks, and independent secondary-evidence
  aging. The build overlays selected payloads before rendering and checks that
  output payloads match. These protections must survive integration.
- The controller and engine contain rollback/recovery paths. The inspected
  paths switch to a saved release and restore a marker. That alone does not
  prove that newer observations survive application rollback. The inspected
  engine does not show the required durable application/builder approval pin.
- Both controller and engine run recovery before their normal prepare path.
  Do not execute them, even with a preparation flag, as read-only diagnostics.

These are timestamped observations, not a claim that production cannot change.
The separate source files in a handoff are individually checked for changes
during read; the handoff is not an atomic, multi-file snapshot.
Different controller and engine lock paths do not, by themselves, prove a bug.
Their complete acquisition ordering and all promotion callers must be checked
from source before modifying the locking protocol.

## Exact-source handoff, not another architecture survey

The existing exported functions replaced string constants with `<REDACTED>` or
`<STRING_...>`. Consequently their DOM selectors, JSON keys, helper paths,
command arguments, lock names, marker fields and public-list contents are not
reconstructible executable source. Neither those exports nor unit tests of an
invented substitute qualify the actual builder.

The remaining input is the known controller and runtime builder module set,
guard, referenced public-file list, and helper overrides with non-secret
constants intact. `scripts/export_vps_builder_source.py` supports this narrow
handoff. It only reads fixed source modules and the two literal dependency
locations found statically in `public_release.py`; it does not import source,
execute deployment commands, read environment files or runtime observations,
make network requests, or write output files. It rejects symlinks, unsupported
dependency expressions, nonregular/oversized files and detected changing reads.

Run it through a reviewed Python stdin block with `-I -B`; do not install it on
the VPS merely to collect source. Its credential-pattern screen withholds whole
suspect files, but is not a guarantee. The owner must review output before
sharing. Output is JSON with source text and hashes, not executable shell output.
An incomplete result means a specific source item is missing/withheld, not that
another broad diagnostic pass is needed. File reads may affect filesystem access
times, and the terminal may retain history/output; there are no intentional
application, configuration, runtime-data or service changes to roll back.

Do not publish private source to this public repository before inspecting it for
secrets and separating machine-specific configuration. The source handoff is
first for private engineering review.

## Implementation decisions and acceptance gates

1. **Version the real builder.** Record source and builder identities separately.
   Bring its actual helper transformations, input contracts, public-file list,
   guard and tests into the isolated integration. Remove no live guard. Compare
   each override against the candidate so an old helper cannot silently replace
   the new safety contract. Choose one final renderer and validate the actual
   post-overlay, post-transform artifact, including browser and no-JS output.
2. **Pin application and builder, not observations.** Use an explicit immutable
   source SHA and builder digest in a persistent, fail-closed policy. Read the
   policy before build and again under the promotion lock immediately before
   switch. The pin setter must use that same lock. Re-fetching moving `main`
   must never override the pin. Continue validating fresh collector snapshots
   independently; freezing an old public directory is not a sufficient pin.
3. **Preserve data on rollback.** Recompose the approved application/builder
   pair with the newest compatible validated observations, preserving their
   original timestamps, lineage and digests. Keep a durable last-good snapshot
   independent of whichever public release the symlink currently names. Never
   overwrite collector state with old bundled JSON. Retain incompatible newer
   snapshots without interpreting them; present qualified stale/unavailable
   output rather than silently falling back to a supposedly current old flag.
4. **Serialize and recover.** Establish one consistent controller-to-engine lock
   order. Persist the rollback/pin transaction and fsync its directory before a
   switch. Make interrupted recovery idempotent. Pin the approved rollback pair
   before another timer invocation can repromote the rejected pair. Do not alter
   existing service privileges, timers or production lock files in this phase.
5. **Qualify the real path.** Isolated tests must cover a pin change during an
   in-flight build, malformed/missing policy, concurrent promotions, interruption
   at each durable step, reboot recovery, newer/older/incompatible snapshots,
   unavailable collectors, guard interaction and denied public files. Validate
   exact staged bytes, manifest provenance and cache generation behavior. A
   mocked policy test is not a tested deployment pin or production rollback.
6. **Prepare approval-specific rollout.** After source integration passes, name
   the exact commit, builder/artifact digests, target, installation and switch
   commands, effects, failure behavior and data-preserving rollback commands.
   Keep production-changing commands separate from read-only verification.
   Obtain separate approval before any production action. Verify the release and
   two subsequent normal scheduled updates after any approved rollout.

The repository's custom-domain Pages preflight remains fail-closed. VPS-first
production is the working design; source integration does not authorize a Pages
or DNS change. Hosting checks and source/builder qualification remain separate.

## Validation scope

The source exporter has isolated tests for exact source/hash preservation,
nonexecution, no intentional file mutation, credential withholding, symlinks,
size limits, unapproved JSON, dependency traversal and escaped terminal controls.
These tests qualify only the handoff utility. Actual VPS builder integration,
deployment-pin behavior and data-preserving rollback remain untested until the
unredacted non-secret source is available and integrated.
