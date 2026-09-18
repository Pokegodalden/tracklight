# Step 3 — importer and network model

Implemented 18 September 2026. Scope: Step 3 only. The Step 2 rule profile and
frozen source files are unchanged; their critique remains deferred pending
organiser information, as requested.

Reviewed and corrected to importer **0.1.1**; see the [critique and corrections](review.md).

The importer reads the eight input CSVs, checks their structure and relationships,
and produces normalized records, a line/bound-aware network and an import report.
The supplied pack imports successfully with no input errors or warnings.
Protection remains explicitly **UNVERIFIED**.

## Deliverables

- [Import result](import_result.json): one bundle containing normalized data, network, provenance and findings.
- [Supported input contract](input_contract.md): keys, validation behaviour, supported routes and limitations.
- [Current verification log](review_verification.txt): regression tests and checks of the preserved baseline/rule pack.
- [Critique and corrections](review.md): reproduced problems, fixes and retained limitations.
- [Importer](../../ps1/importer.py), [network model](../../ps1/network.py) and [schemas](../../ps1/schema.py): reusable Python modules using only the standard library.

## Reconciliation

| Measure | Imported result |
|---|---:|
| Lines | 2 |
| Station/line memberships | 20 |
| Distinct station IDs | 18 |
| Tunnel sectors | 18 |
| Bookable locations | 76 |
| Contracts / contract-type rows | 14 / 14 |
| Activities | 54 |
| Standard-equivalent work units | 192 |
| Exact scaled work units, scale 2 | 384 |
| Predecessor links | 6 |
| Tunnel-to-platform incidence links | 72 |

The input fingerprint matches Step 1's eight-file identity:
`2c66b645033c6949c8262e974333663abef18ade8a7f151e0210d290f0baf64e`.
The horizon remains 4 January–1 August 2027, in 30 weekly buckets.

Every derived working span matches the supplied sample's locations across
**192 activity-week allocations and 928 occupancy rows**. This tests span
expansion only; it does not validate the sample schedule's sharing, workfront,
capacity, protection, ECLO or scoring rules.

## What this enables

Every activity now links to its exact contract/type record, nature and access
type, earliest start week, exact workload and derived work locations. Source
filename/line information follows each record so later conflicts can point back
to the input that caused them.

The model keeps working locations, protection requirements and supply demand
separate. For example, A074's current working span is:

1. PLAT:ALP:H01:EB
2. SEC:ALP:H01_H02:EB
3. PLAT:ALP:H02:EB

Its Live parameters are retained, but its additional protected locations and
affected lines remain unset. No Beta capacity is merged into Alpha's work span.

Malformed inputs fail with specific source-aware findings. A dependency cycle
includes an actual cycle chain. Missing supply is an error; zero supply is kept
as zero. Work released after the horizon remains visible with a warning instead
of being dropped or moved automatically.

## Verification

The regression suite covers baseline counts, sample-span reconciliation, line
and bound separation, missing/duplicate records, bad dates/numbers/categories,
unknown references, dependency cycles, contradictory contract dates and unsupported
routes. It also exercises changed IDs, an additional contract/type and activity,
a smaller one-line instance, reordered columns, and shuffled/gapped sector orders.

All 59 tests pass, including identity collision detection, reusable-importer
isolation, directory access failures and accurate error locations. A changed
profile is rejected. A failed re-import replaces the prior model when output
publication succeeds; publication failure preserves the previous bundle and
returns an error. The complete test suite and frozen baseline/rule-pack
verification are recorded in the current log.

## Run it

From the project root with Python 3.12:

```text
python -m ps1.importer data/baselines/ps1-0dfd901f97bf579f/PS1/01_data --output outputs/step3/import_result.json
python -m unittest discover -s tests -v
```

For another instance, replace the input directory with a folder containing the
same eight CSV filenames. The importer accepts supported identifiers/counts
beyond the sample; it does not require READMEs, diagrams or sample schedules.

## Scope and next boundary

This version supports connected, unbranched lines and same-line/bound SEC
endpoints in spatial order. Platform/reversed endpoints, branching routes,
shared-track capacity and other unsupported structures fail visibly. These
are declared implementation boundaries, not assertions about all hidden tests.

Step 3's gate is met for the supplied pack and the supported input contract.
R12/R15/R17 remain unresolved; no protection footprint or night assignment is
invented. Step 4's scheduling validator and physical-night diagnostic have not
been started. No additional plugin, account connection, API credential or
third-party package was needed.
