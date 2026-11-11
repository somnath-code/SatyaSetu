# Use the browser portal

Install Python 3.11 or 3.12 and Java 17 or 21 in Linux or WSL. From the extracted repository:

~~~bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[local,portal]'
satyasetu
~~~

Open [http://localhost:8080](http://localhost:8080). The default server binds to the local machine. An optional `SATYASETU_PASSWORD` of at least 16 characters enables browser authentication with username `operator`.

## Run a workflow

1. Use **Run small fixture** to see the legacy and corrected calculations match. The deliberate defect is expected to fail comparison.
2. Use **Run 2023–2024 BRFSS** to process all bundled records and codebooks. Review parity, profile results, schema drift, and the migration report. The full run uses temporary disk space for one uncompressed XPT at a time.
3. Use **Run claims review** and open **C002**. Read the cited fictional policy sections, draft a notification, and approve it with a reviewer name and evidence note. Preview the approved payload. Configure Logic Apps if you want to send it.
4. Use **Assess a migration requirement** to validate a sample or edited JSON request. Select a completed survey run if you want to check fields against its observed schema. Record reviewer decisions on the resulting tickets.

Runs and review records are kept under `out/portal/`. Choose another local state directory with `satyasetu --state PATH`. The portal uses one worker, and a second portal process cannot open the same state directory.

## Docker

Copy `.env.example` to `.env` and set a unique `SATYASETU_PASSWORD` of at least 16 characters. Leave the two callback URLs empty until their Logic Apps are configured.

~~~bash
docker compose up --build -d
docker compose logs -f portal
~~~

Docker mounts the supplied survey ZIPs read-only. The service listens at `http://localhost:8080`; sign in as `operator` with the password in `.env`. The `portal_state` volume persists run history. Keep the named volume when stopping or rebuilding.

## Verification

~~~bash
python tests/portal_smoke.py
python tests/portal_smoke.py --full
~~~

The smoke test starts a local HTTP server, runs both pipelines, checks claim citations and approval, downloads evidence, and submits a requirement linked to the survey run. The full option uses the original CDC archives.
