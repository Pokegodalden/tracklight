# Tracklight judging deployment

Step 10 adds a WSGI service using pinned Waitress 3.0.2. The original
`ps1.webapp` remains a loopback development server; do not expose it through a
public tunnel. The new service reuses the same Workspace, solver and checker.

## Local verification

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-hosted.txt
.\.venv\Scripts\python.exe -m ps1.hosted --local --port 8780 --data-dir .tracklight
```

On Linux/macOS use `.venv/bin/python`. Browse http://127.0.0.1:8780. No external
API keys are required. Step 9 enrichment remains skipped.

## Host configuration

Use **one container replica**, one persistent volume mounted at `/data`, and a
TLS-terminating reverse proxy. The service itself uses HTTP behind that proxy.
Dockerfile runs as UID 10001; the mounted directory must be writable by that UID.
Set secrets using the hosting provider's secret configuration, not committed files:

| Environment variable | Value |
| --- | --- |
| `TRACKLIGHT_ORIGIN` | Exact external HTTPS origin, e.g. `https://tracklight.example.org`, without trailing slash/path |
| `TRACKLIGHT_DEMO_PASSWORD` | Chosen nonempty judging access password, shared privately with authorised reviewers |
| `TRACKLIGHT_DATA_DIR` | `/data` in the supplied image |
| `PORT` | `8080`, or the provider's injected port |

The browser's HTTP Basic prompt accepts any username and the configured demo
password. This shared gate is not individual reviewer authentication. Each browser
receives a separate random HttpOnly, SameSite cookie, marked Secure in hosted
mode. Job IDs and run IDs never grant access to another session. The app checks
Host, Origin and session CSRF tokens; it does not trust forwarded headers.
Configure the reverse proxy to preserve the external Host exactly.

Example container test after selecting a host and providing the secrets:

```sh
docker build -t tracklight .
docker run --rm --cpus=1 --memory=1g --pids-limit=128 \
  -p 8080:8080 -v tracklight-data:/data \
  -e TRACKLIGHT_ORIGIN -e TRACKLIGHT_DEMO_PASSWORD tracklight
```

**These CPU/memory values are proposed deployment limits, not organiser-confirmed
limits or a measured guarantee.** Docker is unavailable in the current workspace,
so this container build has not been executed here. Test the image and resource
envelope on the selected host before publishing its URL. The WSGI service has
been executed and tested locally on Windows/Python 3.12.

## Persistence, queue and retention

- One worker process runs at a time, with one OR-Tools thread. At most eight jobs
  are queued/running globally and one per session. Each session permits 100 jobs
  and the existing 16-run limit; at most 32 sessions are retained.
- Search limits remain 1–60 seconds. A 120-second wall deadline also covers model
  construction, the optional lock diagnostic and validation. Expiry or cancellation
  terminates the worker and withholds unpublished decisions. This is separate from
  an ordinary solver timeout with a retained complete incumbent.
- Mutations return job IDs immediately. The UI polls, offers cancellation and
  resumes a pending job after refresh. Duplicate request IDs cannot create duplicate
  mutations or be reused with a different body.
- Completed run checkpoints, input/schedule bytes, reviews and job outcomes are
  written on the persistent volume. A clean restart restores completed runs.
  Interrupted jobs are explicitly labelled and require resubmission; they are not
  silently treated as completed. Run export still re-imports the exact decisions.
- Sessions expire 24 hours after creation, not after last use. Expired session
  storage is reclaimed when a new page/session is opened. Export before expiry.
  Losing the browser cookie also loses access to that session; there is no account
  recovery system. A code/rule upgrade can invalidate source provenance and require
  a new session/import; persistence is not automatic migration between builds.
- A 512 MiB application storage admission/checkpoint quota rejects new work when
  full; temporary data can briefly exceed it while a job is executing. Configure
  an actual disk quota on the host. Container memory/CPU/disk controls are external
  to the Python app. Stop/restart the whole container, not only its parent process.
- Request bodies and candidates are reclaimed after execution. Uploaded contents,
  passwords and request bodies are not logged. No DataMall/OBU credentials are used.

## Verification before publishing

Run the test suite and frozen-data/rule checks. Then, on the selected deployed URL:

1. Confirm HTTPS, expected access prompt, health endpoint and Secure cookie.
2. Upload the eight files in `outputs/step10/final-release/hidden-style-inputs`.
   This is a synthetic renamed benchmark, **not an official hidden instance**.
3. Solve A, inspect the timeline, export, and independently revalidate the bytes.
4. In another browser session, verify that the first session's runs/jobs/exports
   cannot be opened. Queue two jobs from separate sessions; confirm serial work.
5. Refresh while solving; cancel a test job; confirm the parent is unchanged.
6. Restart the container and verify completed plans/reviews are restored.
7. Measure wall time and peak CPU/memory under the selected host's real limits.

`.gitlab-ci.yml` installs pinned dependencies and runs the checks/tests. The
pipeline is prepared but cannot be claimed passed on GitLab until the repository
exists and the runner executes it. No public host, GitLab project or YouTube
publication is configured yet.

Implementation references: [Waitress documentation](https://docs.pylonsproject.org/projects/waitress/en/stable/)
and its [server arguments](https://docs.pylonsproject.org/projects/waitress/en/stable/arguments.html).
