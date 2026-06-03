# Draft: Bug and Security Fixes for MeliOps

## 1. Constant Redefinition in `app/db/database.py`
*   **File**: `app/db/database.py`
*   **Problem**: `DATABASE_URL` is assigned inside `if` and `else`, and conditionally on line 24. uppercase naming conventions make type checkers (e.g. basedpyright) treat it as constant, throwing constant redefinition errors.
*   **Proposed Fix**: Use lowercase `database_url` for building, then assign `DATABASE_URL = database_url` once at the module level.

## 2. Type Mismatch in `app/api/v1/auth.py`
*   **File**: `app/api/v1/auth.py`
*   **Problem**: `intent_plan: str = None` type definition expects a `str`, but the default value is `None`. This raises argument type check errors.
*   **Proposed Fix**: Change definition to `intent_plan: str | None = None`.

## 3. Inefficient DB Connection Usage in `app/api/v1/router_quota.py`
*   **File**: `app/api/v1/router_quota.py`
*   **Problem**: `/quota/register` endpoint runs a loop calling `register_usage` multiple times. Each call opens and closes a connection to the PostgreSQL database from the connection pool. Highly inefficient under high usage.
*   **Proposed Fix**: Create `register_usage_batch(email: str, count: int)` in `app/db/quota.py` using a single database query with `generate_series` or similar:
    `INSERT INTO quota_usage (email) SELECT $1 FROM generate_series(1, $2)`

## 4. Security Vulnerability: Client-Side Quota Registration Bypass
*   **File**: `app/api/v1/router_extract.py`, `app/templates/index.html`
*   **Problem**: `/extract` validates quota but does not increment usage. The frontend triggers `/quota/register` on the download button. This is trivial to bypass by calling `/extract` directly or blocking the subsequent registration endpoint.
*   **Proposed Fix**: Register quota usage directly in `/extract` endpoint upon successful PDF extraction. Keep state in sync in UI by returning the updated quota status in response headers (e.g., `X-Quota-Used-Today`, `X-Quota-Used-Month`) or an associated payload, and let JavaScript parse it.

## 5. Design Smell: `valid_until` stored as `TEXT` in DB
*   **File**: `app/db/database.py`, `app/db/quota.py`
*   **Problem**: `valid_until` is stored as `TEXT` in the database, and compared using string-lexicographical comparison (`valid_until >= $2`). This is fragile to timezone offsets or changes in sub-second precision.
*   **Proposed Fix**: Change `valid_until` to `TIMESTAMP WITH TIME ZONE`. Ensure all datetime inserts use timezone-aware values and proper comparisons.

## 6. Silent OAuth Callback Failure
*   **File**: `app/api/v1/auth.py`
*   **Problem**: On login exception (state mismatch, denied access), the callback silently redirects to `/api/v1/` without indicating that login failed.
*   **Proposed Fix**: Redirect with an error query parameter (e.g., `/api/v1/?error=auth_failed`) so the UI can notify the user.

## 7. Missing DB Pool Shutdown
*   **File**: `app/main.py`, `app/db/database.py`
*   **Problem**: Database connection pool `_pool` is opened during lifespan startup but never closed. This causes connection leaks on server reload or shutdown.
*   **Proposed Fix**: Implement `close_db()` in `database.py` that calls `await _pool.close()`, and call it after the `yield` statement in FastAPI's `lifespan`.

## 8. Hardcoded Session Key Fallback
*   **File**: `app/main.py`
*   **Problem**: Session middleware uses a fallback secret `"una_clave_secreta_de_respaldo"` if `SECRET_KEY` env var is missing. Very unsafe for production.
*   **Proposed Fix**: Raise `RuntimeError` on application startup if `SECRET_KEY` is not configured.

## 9. Insecure Session Cookie Options
*   **File**: `app/main.py`
*   **Problem**: Session cookies are configured without standard security flags like `https_only` or `SameSite`, leaving them open to sniffing or CSRF.
*   **Proposed Fix**: Configure `https_only=True` (if BASE_URL starts with https), and add samesite security options.
