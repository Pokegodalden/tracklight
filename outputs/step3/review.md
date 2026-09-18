# Step 3 critique and corrections

Reviewed 18 September 2026. Importer revised from 0.1.0 to **0.1.1**.
The Step 2 rule profile remains 0.1.0, unchanged. No Step 4 work was introduced.

The original implementation reconciled the supplied pack correctly, but the
passing tests did not cover several failure and identity boundaries. Five issues
were reproduced against the original code before fixing them: four failed
assertions and one unhandled exception. None changed the supplied baseline's
counts or working spans.

## Reproduced findings

| Priority | Finding and evidence | Correction |
|---|---|---|
| High | Distinct line/station combinations could produce one platform ID. Line `L` with station `X:A` and line `L:X` with station `A` both generate `PLAT:L:X:A:EB`. The importer accepted this synthetic instance with 10 locations instead of 12, causing two lines to reference the same capacity resource. | Detect collisions while constructing expected location identities. Report `location_identity_collision` and publish no model/network. Do not rename IDs or merge capacity silently. |
| Medium | Reusing one Importer object after deleting an input retained its previous file fingerprint. Its issue list was also shared with earlier returned results, and errors persisted into later runs. | Start each run with fresh state containers. A missing file leaves the combined input fingerprint unset; earlier results remain unchanged. A repaired subsequent import can succeed. |
| Medium | Failure to list the input directory escaped the library API as a PermissionError, bypassing the structured import report. | Convert directory inspection failures into an `input_directory` error with no usable model. |
| Low | A malformed CSV record beginning at physical line 3 was reported at line 2 because the source position was updated only after parsing succeeded. | Record the upcoming row's starting line before asking the CSV parser to read it. |
| Low | A third occurrence of a duplicate key claimed the second occurrence was the first. | Preserve the original source line when tracking duplicate keys and sequence values. |

Each finding now has a regression test using disposable inputs. The original
challenge files are never modified by these tests.

## Output failure guarantee clarified

The earlier documentation overstated what atomic output guarantees. A failed
input import replaces the previous bundle with a failure report **only if that
report can be written successfully**. If output publication itself fails, for
example because the destination is locked, the previous file remains unchanged.
It must not be interpreted as the current run's result.

An additional test simulates replacement failure: the previous bundle remains
byte-for-byte intact, the temporary output is cleaned up, and the error is
propagated. The CLI returns a nonzero exit status on output failure. A later UI
must respect that status and explicitly distinguish the last saved result from
the latest attempted import.

## Design choices retained after review

- Explicit endpoint topology and separate line/bound capacity are appropriate. Sector sequence numbers must not create network links.
- Unknown protection is represented by null footprints and UNVERIFIED status. Filling these with guessed buffers would exceed the current evidence.
- Exact half-unit workload accounting avoids rounding the challenge's standard/ECLO yield. This remains a declared input limitation, not a claim that all future inputs use half units.
- Reversed/platform endpoints, branching routes, shared-track capacity and external line memberships remain unsupported. Those restrictions are visible import errors and should be revisited when organiser evidence supports broader cases.
- An out-of-horizon release is preserved with a warning. Detecting scheduling infeasibility belongs to later scheduling work; import success alone is not feasibility.

The original count of passing tests was insufficient evidence of broad hidden-
instance support. The revised tests improve concrete boundary coverage, but do
not establish official validator equivalence, upload resource limits or support
for arbitrary railway networks.

## Verification and resulting status

The revised full suite has **59 tests**, including 32 importer tests. The current
run, baseline integrity check, unchanged rule-pack verification and refreshed
baseline import are captured in [review_verification.txt](review_verification.txt).
The [original verification log](verification.txt) is retained as historical evidence.

The refreshed [import result](import_result.json) records importer 0.1.1 and its
source fingerprints. Baseline reconciliation remains 54 activities, 76 locations,
192 standard-equivalent units, six dependency links and 928 matching sample
occupancy rows across 192 activity-week allocations.

Step 3 is ready for the next reviewed step within its documented input contract.
Protection semantics and official acceptance remain unresolved; Step 2's deferred
critique and the organiser questions are unchanged.
