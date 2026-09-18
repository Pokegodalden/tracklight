# Step 1 critique and corrections

Reviewed 18 September 2026. Scope: Step 1 implementation and its planning
documents. No scheduling rules were resolved and Step 2 has not started.

The supplied input snapshot and baseline counts were correct. The weaknesses
were in failure handling, future-pack identity and alignment of the build plan
with mandatory submission requirements.

## Findings and changes

| Finding | Evidence / consequence | Correction |
|---|---|---|
| A failed copy could leave a partial published snapshot | Simulated failure on the second file write left a `ps1-*` directory; a retry would refuse it | Write to a temporary directory, verify, compare sources again, then rename into place; ordinary failures clean up staging |
| The eight-input fingerprint actually included every file in the input folder | Adding only `notes.txt` changed the input identity | Select the eight named input paths explicitly; preserve/list extra files in the full pack |
| Verification trusted editable role metadata and ignored manifest version | A changed role with recalculated input hash, and unsupported version 999, were both accepted | Check schema/version, derive roles from paths, and derive input identity from the eight known paths |
| Missing/malformed manifests and unreadable CSVs could escape the verifier as exceptions | Missing manifest, JSON list and invalid UTF-8 caused exceptions in regression cases | Return structured failure reports; the CLI exits nonzero without a traceback for expected data errors |
| CSV parsing accepted an unterminated quoted field | A one-column unterminated CSV passed the original parser | Enable strict CSV parsing and reject blank header names |
| Capture and refresh behaviour lacked meaningful tests | Initial tests only checked the existing snapshot and four simple changes | Add capture, interruption, idempotence, changed-source, identity separation and CLI tests |
| Generic refresh documentation overpromised | The utility needs the reviewed full-pack file layout, not just eight arbitrary uploaded CSVs | Document its full-pack scope and leave the hidden-instance importer to Step 3 |
| Calendar absence was hard-coded for every future pack | A pack containing new supporting files would still claim no calendar was supplied | Return unassessed (`null`) for extended packs; preserve the original reviewed absence finding |
| The build workflow still omitted explicit submission requirements | Checklist recorded hosting/video/GitLab, but workflow.txt did not | Align workflow.txt with the four mandatory deliverables and nine scenario CSVs; protect them ahead of bonus replanning |

Additional checks reject unsafe/duplicate paths, source/destination nesting and
inconsistent extra-file inventory. Capture rechecks the source file set and bytes
before publication. The original snapshot's layout and fingerprints stay intact.

## Verification

Before fixes, the expanded regression run reproduced eight failing cases:
five failed assertions and three exceptions. After fixes, all 19 tests passed.
The 15-file original snapshot also passed the revised verifier.

Coverage includes:

- Relocating an unchanged snapshot.
- Detecting changed, missing and extra files, including same-length edits.
- Rejecting manifest identity/version/role errors, malformed JSON, missing
  manifests and path traversal.
- Rejecting malformed CSV quoting and unreadable bytes.
- Preserving exact bytes on capture and leaving the manifest unchanged on rerun.
- Keeping reference-only changes out of the eight-input identity.
- Giving changed input bytes a new pack and input identity.
- Avoiding publication after a simulated write failure or detected source change.
- Rejecting nested source/destination directories.
- Returning a structured CLI failure and nonzero exit status.

Tests modify only disposable copies. No source input, frozen payload or frozen
manifest was intentionally rewritten. No runtime package or plugin was installed.

## Limits retained

- This is integrity/inventory verification, not the future schema/domain importer
  and not the official scheduling validator.
- Fingerprints detect changes relative to a recorded manifest. They are not an
  organiser signature or protection against someone replacing both data and
  manifest deliberately.
- Publication by rename prevents ordinary interrupted copies from appearing as
  completed snapshots. Abrupt termination may leave staging folders, and no
  filesystem-level point-in-time source snapshot or crash-durability guarantee
  has been implemented. Keep the source pack static during capture.
- The full-pack utility assumes the reviewed file layout. Changed layouts must
  be reviewed explicitly rather than guessed. The original benchmark counts are
  diagnostics, not future hidden-instance restrictions.
- Official rules, scenario-specific input details and validator access remain
  open dependencies. Their absence does not invalidate Step 1's preserved bytes.

Step 1 is complete with these corrections. Proceeding to Step 2 remains a
separate user-directed action.
