# LegalMind Tool Usage

## Pipeline Operations
*   Use `legalmind.evidence.upload` to upload files or directories.
*   Use `legalmind.evidence.ingest` for converting files.
*   Use `legalmind.prefile.run` for final document checks (includes citation & claim audit).
*   Use `legalmind.verify.claim` for specific claim verification.

## Polling
*   Long-running tools (ingest, build, verify, prefile, render) return a `run_id`.
*   Call the same tool again with `run_id` to poll for status.
*   Do not assume completion until status is "complete".
