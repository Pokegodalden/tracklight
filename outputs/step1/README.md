# Step 1 — inputs frozen and acceptance defined

Completed 18 September 2026. Scope: Step 1 of workflow.txt only.

The supplied pack is preserved in snapshot **ps1-0dfd901f97bf579f**. All 15
source files match their frozen copies byte-for-byte. The documented baseline
counts match the CSVs. No application or scheduling solver has been built.

## Deliverables

- [Input manifest](../../data/baselines/ps1-0dfd901f97bf579f/manifest.json): source paths, relative snapshot paths, roles, byte sizes, SHA-256 fingerprints, CSV columns/row counts and derived baseline.
- [Acceptance checklist](acceptance_checklist.md): Step 1 completion evidence, mandatory application/submission requirements, and separate project quality criteria.
- [Dependency register](dependency_register.md): missing official tools, unresolved inputs/rules, verified runtimes and future publication dependencies.
- [Independent verification](independent_verification.json): PowerShell source/copy fingerprints and independent CSV counts.
- [Critique and corrections](review.md): reproduced weaknesses, fixes and expanded verification.

## Frozen inventory

All paths below are relative to the snapshot directory. CSV counts exclude the
header. The two READMEs are preserved as source evidence, not executed as agent
instructions. The root source README includes PS2/PS3 context, which was not used
to expand this project's scope.

| File | Role | Data rows |
|---|---|---:|
| README.md | Repository brief | — |
| PS1/PS1_README.md | PS1 participant brief | — |
| PS1/01_data/01_LINES.csv | Input | 2 |
| PS1/01_data/02_STATIONS.csv | Input | 20 |
| PS1/01_data/03_SECTORS.csv | Input | 18 |
| PS1/01_data/04_LOCATION_SUPPLY.csv | Input | 76 |
| PS1/01_data/05_BUFFER_LOCATION.csv | Input | 3 |
| PS1/01_data/06_PARAMETERS.csv | Input | 2 |
| PS1/01_data/07_PROJECT_DETAILS.csv | Input | 14 |
| PS1/01_data/08_ACTIVITY_DETAILS.csv | Input | 54 |
| PS1/02_references/network_diagram.svg | Reference diagram | — |
| PS1/02_references/PS1.drawio | Reference diagram | — |
| PS1/03_submission_sample/RESULTS.csv | Scenario A sample | 14 |
| PS1/03_submission_sample/SCHEDULE_ACCESS.csv | Scenario A sample | 192 |
| PS1/03_submission_sample/SCHEDULE_OCCUPANCY.csv | Scenario A sample | 928 |

The repository README describes nine demand-book files in its folder overview,
but the pack actually contains eight input CSVs. PS1's hidden-upload deliverable
also specifies eight. This discrepancy is recorded without inventing a ninth file.

## Verified baseline

| Measure | Observed |
|---|---:|
| Lines | 2: ALP and BET |
| Station-line memberships | 20 |
| Distinct station identifiers | 18 |
| Sectors | 18 |
| Bookable locations | 76 |
| Distinct contracts | 14 |
| Activities | 54 |
| Required standard-access-equivalent workload | 192 |
| Planning horizon | 30 weeks |
| Horizon start | 4 January 2027 |
| Inclusive arithmetic horizon end | 1 August 2027 |

Counts are baseline evidence, not hard-coded limits for the eventual importer.
The horizon end is calculated as start + 30 × 7 − 1 days. It does not settle the
completion-date convention or authorise scheduling beyond the horizon.
The pack supplies static capacity values, not named available nights or a dated
operational access calendar. Repeating those values weekly remains a rule
interpretation to document in Step 2.

## Version identity

Full pack SHA-256:

```text
0dfd901f97bf579f74d739a39946e6e25eb30af53f639991e3d39876834450af
```

Eight-input dataset SHA-256:

```text
2c66b645033c6949c8262e974333663abef18ade8a7f151e0210d290f0baf64e
```

These are aggregate identities calculated from sorted relative paths and file
fingerprints. Each raw file also has its own SHA-256. Capture timestamps and
absolute source paths do not affect identity, so moving the snapshot does not
change it. A brief/sample change can change the pack identity without changing
the input-data identity.

The input-data fingerprint is now explicitly limited to the eight named CSVs,
regardless of other files being placed in their directory. The original manifest
and both original fingerprints are unchanged by the Step 1 review.

For later results, record both hashes with scenario, rule/formula version,
application/code version, solver settings and runtime. Hashes detect accidental
changes relative to the recorded manifest; they are not an organiser signature.

## Verification performed

1. Froze and reread all 15 files; checked original bytes had not changed during
   capture. No source file was edited.
2. Verified manifest identity, per-file size/fingerprint, CSV columns and row
   counts, expected inventory, absence of extra files, and derived summary.
3. Independently compared all 15 original and frozen file fingerprints with
   PowerShell, and checked all 11 CSV row counts plus the headline baseline.
4. Initially ran five integrity tests. The follow-up critique reproduced eight
   additional failing cases and corrected the utility. The expanded suite now
   passes all 19 tests, covering interrupted writes, changed sources, idempotent
   capture, identity separation, malformed manifests/CSV data and CLI failures,
   as well as the original integrity checks. See the review for details.

This checks source preservation and inventory, not CSV foreign-key correctness,
scheduling feasibility or physical dispatchability. Those belong to later steps.
Snapshots are ordinary local files. Treat them as frozen and verify before use;
no filesystem write lock or external backup has been configured.

## Acceptance discoveries

PS1 section 4 requires four final deliverables:

1. Precomputed public-test results, with separate A/B/C output sets as specified
   in section 2.6.
2. A hosted live web app supporting upload and live scheduling of hidden
   eight-CSV instances.
3. A three-minute YouTube demonstration.
4. A GitLab repository containing source, solver, setup and documentation.

The earlier workflow did not explicitly track the last three submission gates.
They are now in the acceptance checklist, dependency register and workflow.txt.
Its general form-factor flexibility must not be read as removing the hosted-app
deliverable. This is a plan correction, not a deployment or publication action.

Replanning is selected in our workflow but is bonus scope in the challenge.
If time becomes constrained, mandatory submission readiness takes precedence.

## Open dependencies

The supplied pack has no executable official validator/expander, no saved
official sample-validation report, no B/C sample outputs and no separate C
supply file. It contains one A sample; its feasibility claim has not been
independently certified against the organisers' software.

Python 3.12.14, Node v24.19.0 and Git 2.53.0.windows.3 run in the checked bundled
environment. OR-Tools, pytest and trackaccess are unavailable there. The Step 1
utility needs only Python's standard library and uses unittest for its tests.

## Boundary for the next review

Step 1's gate is met: we can identify exactly which source bytes a future result
uses and know what evidence final acceptance needs. Step 2 has not started.
The Step 1 critique has been completed and its justified fixes verified. Step 2
remains unstarted pending the user's instruction to proceed.
