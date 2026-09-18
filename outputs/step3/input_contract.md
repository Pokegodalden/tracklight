# Step 3 input contract — importer version 0.1.1

This document describes the importer implemented for the provisional Step 2
profile. Its supported-input restrictions are implementation boundaries, not
new claims about the organiser's hidden instances. Step 2's files remain unchanged.

## Files and record identity

Supply a directory containing these eight UTF-8 CSVs. A UTF-8 byte-order mark is
accepted. Column order may vary; the exact named column set is required. Extra
columns, duplicate headings, malformed quoting, missing cells and blank rows
are errors. Extra files are reported as unconsumed warnings.

| File | Unique record key | Main checks |
|---|---|---|
| 01_LINES.csv | line_code | Nonblank identifiers and names |
| 02_STATIONS.csv | line_code + station_id | Existing line; unique positive station order within line; interchange membership |
| 03_SECTORS.csv | sector_id | Both endpoint stations on the same line; structured ID; unique positive sector order within line |
| 04_LOCATION_SUPPLY.csv | location_id | Kind, line and bound agree with the referenced entity; explicit nonnegative capacity |
| 05_BUFFER_LOCATION.csv | nature_of_works | The three supported nature categories; nonnegative buffer counts; Live-only opposite-bound flag |
| 06_PARAMETERS.csv | key | Exactly horizon_start and horizon_weeks; ISO date and positive integer horizon |
| 07_PROJECT_DETAILS.csv | contract_number + activity_type | Nature lookup; PM/PC/C access type; priorities, dates, workfronts and allocation |
| 08_ACTIVITY_DETAILS.csv | activity_id | Exact contract/type lookup; existing endpoints; release date; workload; predecessor and priority |

`activity_type` is an extensible, nonblank label joined exactly to the project
table. It is kept distinct from `access_type` and `nature_of_activity`, which
joins to `nature_of_works`. A contract may have several activity-type rows, but
its award date, planned/contractual completion dates and contract priority must
agree across those rows. Ambiguous contract-wide values are errors.

The three supported nature labels are `Live`, `Non-live (Consist)` and
`Non-live (Others)`, preserving the source spelling. Buffer counts come from
the input table. Only Live may require opposite-bound effects; Others must have
zero buffer. This imports parameters without inventing a geometry algorithm.

## Values and dates

- Identifiers are case-sensitive, nonblank and contain no whitespace. Text is not trimmed or silently corrected; leading/trailing whitespace and control characters are rejected.
- Integer fields accept ordinary unsigned base-10 notation without leading zeroes. Priorities are 1–3 and flags are 0/1.
- Supply capacity, contract allocation and workfront counts may be zero. Zero contract resources generate a warning, not an invented replacement.
- Positive workload is supported in exact half-unit increments under the profile's scale of two. The supplied pack uses whole units. Other fractions, exponents and nonfinite values are rejected as unsupported. The original workload string is retained alongside an exact integer count.
- Dates use YYYY-MM-DD and must be real calendar dates. Completion dates before award are rejected. A planned target later than the contractual deadline is preserved with a warning.
- Release dates before the horizon retain their calculated release week, with earliest in-horizon week set to 1. Release dates after the horizon are preserved with a warning. Neither changes the source date or proves a schedule feasible.
- Dates before award generate a review warning. A horizon that cannot fit in the supported ISO date range fails visibly.

The calendar uses seven-day buckets anchored at `horizon_start`, as in provisional
R19. This is not a dated operational access calendar. The module does not create
night assignments, decide deadline feasibility or extend the horizon.

## Supported network and routes

Line and station identifiers are not restricted to ALP/BET or the sample names.
Counts are not fixed to the sample. Structured sector and location IDs must
agree with the endpoint and line records supplied.
Different entity combinations must not generate the same location ID. Such
collisions are rejected with their conflicting identities; they cannot merge
line or bound capacity.

Each line must be one connected, unbranched, acyclic chain containing all its
station memberships. Explicit `from_station_id` / `to_station_id` edges establish
the chain. Endpoints must follow increasing station order. Sector sequence
numbers are checked for uniqueness within each line but never create adjacency;
gaps and different row ordering are supported.

Every supplied station and tunnel must have an explicit EB and WB supply row.
Missing rows are errors, even when the activity list does not currently use
that location. A zero-capacity row is different from an absent row.

Each location is its own capacity resource. Interchange membership does not
merge ALP/BET capacity or add a travel edge between their tunnels. `is_shared=1`
is explicitly unsupported under the current separate-capacity profile.

Activity endpoints currently support SEC-to-SEC spans on the same line/bound,
in increasing spatial order, including the same sector at both ends. Expansion
includes each intervening tunnel and every incident platform once. This spatial
ordering also applies to WB; the importer does not infer train movement direction.
Platform endpoints, reversed endpoints, cross-line/bound spans, branches and
disconnected routes are rejected with a specific explanation. They require
reviewed semantics before support can be added.

`is_interchange` must agree with membership in more than one supplied line.
External, unmodelled lines are outside this version's supported network.

## Dependencies

An activity may reference one predecessor activity or leave the cell blank.
Unknown IDs, self-dependencies and cycles fail. Lists of predecessors are not
part of this input schema. Cross-contract dependencies are supported.

The model contains predecessor/successor edges, source rows and a topological
order. Cycle errors include a concrete chain following predecessor links.
No scheduling order is enforced yet; the model records provisional R18 for the
future solver/checker to apply.

## Separate meanings in the model

| Object | What is populated now | What remains unset |
|---|---|---|
| working_span | Ordered location IDs under R04 | Official expander equivalence |
| protection | Nature, buffer parameter, opposite-bound flag, source and unresolved rule IDs | Exact protected locations, affected lines and timing verdict |
| supply_demand | Work locations and the distinct-group/location/week accounting unit | Actual consumption, because no schedule or sharing groups exist |

Protection location lists are `null`, never an empty list implying no protection.
R12, R15 and R17 remain UNVERIFIED. A successful import is not a successful
schedule validation. None of the source sample's allocations are loaded by the
importer; the sample is used separately for span regression tests.

## Errors, provenance and output

Each finding includes severity, code, filename, source line and field when those
can be identified. Cross-file omissions may have no individual source row.
Independent row errors are collected together. Later validation phases run only
after earlier prerequisites pass, so one report is not guaranteed to list every
possible downstream problem at once.

The output is one JSON bundle containing a report, provenance, normalized model
and network. If any error exists, the model and network are both null. Warnings
remain visible on a successful import. A successful report says
`IMPORTED_WITH_UNVERIFIED_RULES`; schedule feasibility is `NOT_EVALUATED` and
official validation is `NOT_RUN`.

The bundle records hashes of the exact eight input byte sequences, their combined
identity using Step 1's algorithm, the pinned profile and importer source files.
It distinguishes the actual input identity from the profile's reference input
identity, allowing a different supported instance without pretending it is the
baseline. Each normalized source record carries its CSV filename and physical
starting line.
Each run uses fresh state even when an Importer object is reused. Earlier
returned results do not change, and missing inputs cannot inherit old hashes.

The CLI writes the bundle atomically. When publication succeeds, a failed input
import replaces any prior bundle with a failure report and null model/network.
If publication itself fails, the old file remains unchanged and the operation
fails; callers must not treat that old file as the latest attempted import.
Ordinary exceptions clean up temporary output files. An abrupt process termination
may leave a temporary file; it is not a published bundle. Output inside the selected
input directory, frozen baselines or rule specifications is refused. Exit status
is zero for a successful import and one for a failed import/output operation.

This local importer does not yet impose web-upload quotas or solve-time limits.
Those limits remain part of later hosted-application work and organiser
clarification. No network access, API keys or additional Python packages are used.
