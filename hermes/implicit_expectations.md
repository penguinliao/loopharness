# Implicit expectations PMs forget to mention

> Maintained checklist of "things the PM didn't say but expects done correctly."
> Each entry is grounded in real failures from past pipelines.
> AI must consult this in the SPEC stage and explicitly cover relevant items in acceptance criteria.

---

## Search / list / detail endpoints

- **Partial match, case-insensitive** — searching "john" should also find "johnny" and "johnson". Default to `LIKE %q%` not `=`. Real failure: AI defaulted to exact match and PM had to bug-report it.
- **Exclude sensitive fields from response** — `password_hash`, `password`, internal tokens, full email if privacy-sensitive. Walk the entire response tree, not just top level.
- **Result limit** — never return all rows. Default cap 50. If user wants more, they should paginate.
- **Empty/whitespace query handling** — return empty list or 4xx, never "all rows" by accident.
- **Case insensitive** unless PM explicitly says otherwise.

## Authentication / credentials

- **Hash passwords** — bcrypt, scrypt, or argon2. Never plaintext, never MD5/SHA-256 alone.
- **Token randomness** — use `secrets.token_urlsafe()` / `secrets.token_hex()` / `os.urandom()` / `uuid.uuid4()`. Never `random.*` (predictable).
- **Token expiration** — every reset/verification token must expire. Default 15-60 minutes.
- **Token single-use** — reset/verification tokens must be invalidated after first successful use. Re-use should return 4xx.
- **JWT secret from env** — never hardcode. Fail fast if env var missing.
- **JWT expiration** — every issued token must have `exp` claim. Default 1 hour for access tokens.

## User input validation

- **Email format** — validate before storing. Reject "abc" or strings without `@`.
- **Password strength** — minimum 8 chars, mixed letter+digit. Don't accept "123" or "password".
- **Length limits** — every text field has a max. Don't allow 1MB usernames.
- **SQL injection** — parameterized queries only. Never f-string or `%` formatting into SQL.
- **HTML escape** — if user input is rendered, escape it. Use the framework's built-in.

## State machines / flows

- **Idempotency** — payment endpoints, signup endpoints, email-send endpoints must dedupe by key.
- **Email enumeration prevention** — `/forgot-password` and similar must return identical response whether email exists or not.
- **Session invalidation on password change** — old sessions should be killed.
- **Concurrent updates** — if two users edit the same record, last-write-wins or explicit locking.

## Configuration / secrets / deployment

- **Read keys from env** — `OPENAI_API_KEY`, `STRIPE_SECRET_KEY`, etc.
- **Fail fast on missing env** — at startup, not at first request.
- **Never log secrets** — sanitize logs of API keys, passwords, tokens.
- **CORS specific origins** — never `["*"]` in production. List exact allowed origins.
- **Cookies httpOnly + secure + samesite** for sessions.

## File upload

- **MIME / extension whitelist** — block .exe, .sh, .php (or whitelist .png .jpg .pdf).
- **Size limit** — server-enforced (not just frontend). Default 10MB.
- **Path traversal** — never use user-supplied filenames in paths. Generate UUIDs.
- **Virus scan stub** — at least leave a hook for future scanning.

## Error handling

- **Don't leak internals** — 500 responses should not show stack traces in prod.
- **User-facing messages in user's language** — "邮箱格式不对" not "ValueError: invalid".
- **Distinguish client errors (4xx) from server errors (5xx)** — bad input is 400, not 500.

## Database connections / resources

- **Always close DB connections** — use `try/finally`, context manager, or framework pool. A connection leaked in the error path (e.g. inside `except IntegrityError`) will eventually exhaust SQLite locks or pool slots and the next request will hang or 500. Pattern that bites: `try: conn = sqlite3.connect(); conn.execute(...) except IntegrityError: raise HTTPException(...)` — `conn` was never closed. Fix: wrap in `with sqlite3.connect(...) as conn:` or move `conn.close()` into a `finally`. Source: v1.0 task_06 run, where the AI's IntegrityError handler caused subsequent /register requests to time out.
- **File handles, sockets, subprocesses** — same rule: always close in `finally`. Don't trust GC.

---

## How to add a new entry

1. Pipeline finishes (pass or fail) → AI proposes new entries to `.harness/proposed_skills.md`
2. PM runs `harness hermes review` → sees proposed entries with their source pipeline
3. PM approves or rejects each → approved entries get appended above with a footnote linking to the source pipeline.

## Source attribution

Each entry SHOULD eventually have a footnote naming the real pipeline that surfaced it. This makes the list auditable: "we don't add rules from nothing, we add them from observed failures."
