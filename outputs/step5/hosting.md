# Hosting and hidden-instance assessment

## Current boundary

The app is a Python standard-library HTTP server plus static HTML/CSS/JavaScript.
It binds only to 127.0.0.1. It requires a writable temporary directory, reads the
frozen input pack and pinned rule files, and does not need DataMall or OBU access.
Requests run synchronously. This is sufficient for a single local demo; it is not
a public hosting configuration or a tested multi-user service.

The request token, origin/Host checks, restrictive browser policy and filename
whitelist reduce local browser-request risks. They do not provide user accounts,
tenant separation or public-service authentication. Do not expose this server by
changing its bind address or placing a public tunnel in front of it.

## Upload contract tested early

Eight named CSVs are passed as base64 bytes inside a JSON request. Three schedule
files are optional but must be supplied together. Original bytes are saved in a
random per-run temporary directory, re-imported by the Step 3 importer and checked
by Step 4. No sample IDs or sample counts are required by the generator. A test
renames both line codes and an activity identifier and completes the full flow.

Local limits, chosen for this prototype rather than supplied by the organisers:

| Resource | Limit |
|---|---:|
| One CSV | 512 KiB |
| Total decoded upload | 6 MiB |
| JSON request including base64 | 9 MiB |
| Rows per input table | 2,000 |
| Activities / bookable locations / weeks | 250 / 500 / 104 |
| Schedule access / occupancy rows | 1,500 / 20,000 |
| Stored successful runs per server session | 16 |
| Conditional night search budget | 5,000 nodes per diagnostic search |

Oversized or malformed imports fail visibly. No silent truncation or row dropping
is permitted. Some inputs within the input limits can generate a schedule that
exceeds output-row limits; that operation is rejected while retaining the source
run. These limits require review against the organisers' hidden-instance contract.
Branching/ambiguous networks remain subject to the existing importer's explicit
unsupported-input policy. Larger-input runtime and memory have not been benchmarked.

## Before public deployment

Use a Python-capable container or managed backend, with the frontend served on the
same HTTPS origin. Static-only hosting cannot execute this generator/validator.
Replace the development HTTP server with a supported application server and job
workers. Add request deadlines, bounded queues, cancellation and CPU/memory limits
before larger optimisation jobs arrive in Step 6. The current synchronous API is
deliberately temporary.

Define isolated run ownership, authentication or an explicitly scoped demo-access
policy, upload retention/expiry, export persistence and storage quotas. A restart
must not silently lose a user's accepted job. Keep credentials server-side and
keep uploaded data out of logs. Package the exact rule profile and source versions
with the deployment, and retain validation evidence for each export.

Choose a hosting provider/account and repository destination at the deployment
step. Then test fresh-session upload, scheduling, download, restarts, concurrent
users and instance-size bounds on that host. No provider cost, supported quota or
deployment readiness is claimed here; those depend on the destination selected.

Local development and browser automation suffice now. Later deployment needs the
chosen host and GitLab account/CLI or connector. Notion, Outlook, Teams, SharePoint,
Figma and the OBU SDK are not needed for this slice. No new plugin was installed.
