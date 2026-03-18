# Technical Deep-Dive

This document explains the code-level details: what each piece does, how the parts connect, and why things are built this way.

---

## Architecture at a Glance

```
Request → Middleware (timer) → FastAPI route → Pydantic validation → Engine → Response
```

There are three layers, each in its own file:

- **models.py** — data shapes (Pydantic models). Imported by both other files.
- **engine.py** — pure business logic. No HTTP awareness. Takes strings, returns objects.
- **main.py** — HTTP layer. Routes, middleware, error handling. Calls the engine.

This separation matters: the engine can be tested without spinning up a web server, and swapping FastAPI for Flask (or anything else) would only touch `main.py`.

---

## models.py — The Shared Contract

Three Pydantic models define all the data flowing through the system:

**TicketInput** — what comes in:
- `title` (str, min 1 char) — required
- `description` (str, min 1 char) — required
- `top_n` (int, 1–10, default 3) — optional

Pydantic does the validation automatically. If `title` is missing or empty, FastAPI returns a 422 with a detailed error message. We didn't write any validation code — Pydantic's `Field(..., min_length=1)` handles it.

**Recommendation** — a single result:
- `action` (str) — what to do
- `confidence` (float, 0.0–1.0) — how confident the engine is
- `why` (str) — reasoning

**TriageResponse** — the wrapper:
- `recommendations` (list of Recommendation)

These models are the **integration contract**. The engine returns `list[Recommendation]`, the route wraps it in `TriageResponse`. If you change these models, both sides break immediately — which is the point. It makes mismatches impossible to miss.

---

## engine.py — The Triage Brain

### The category system

`CATEGORIES` is a Python dictionary. Each key is a category name (like `"auth"` or `"billing"`), and each value contains:
- `keywords` — a list of strings to look for in the ticket text
- `actions` — a list of pre-written recommendations (each with `action` and `why`)

There are 5 categories: auth, billing, performance, data, access. Plus a `FALLBACK_ACTIONS` list for when nothing matches.

### How scoring works

`get_recommendations()` does this:

1. **Combine** title and description into one string.
2. **For each category**, count how many of its keywords appear in the combined text (case-insensitive substring match).
3. **Sort** categories by match count, descending. Ties are broken alphabetically (for determinism).
4. **Build recommendations** from the winning categories. Each category contributes up to 3 actions. The first action gets the highest confidence, and each subsequent one drops by 15%.
5. **Confidence formula**: `matches / max_keywords_across_all_categories`, capped at 0.95, with a floor of 0.05.
6. If **nothing matched at all**, return the fallback actions with a base confidence of 0.40.

### Why it's deterministic

Same input → same keywords found → same match counts → same sort order (ties broken alphabetically) → same actions selected → same confidence scores. There's no randomness anywhere. The `sorted()` call with the `(-count, name)` key is the critical piece — without the alphabetical tiebreaker, Python's sort would be stable but the order could vary depending on dict iteration order.

### The `_count_keyword_matches` helper

A simple loop: for each keyword, check if it's a substring of the lowercased text. Returns an integer count. It's a separate function so it can be unit-tested independently.

---

## main.py — The HTTP Layer

### The FastAPI app

`app = FastAPI(...)` creates the application. The `title`, `description`, and `version` are metadata that shows up in the auto-generated docs at `/docs` (Swagger UI) and `/redoc`.

### The telemetry middleware

```python
@app.middleware("http")
async def telemetry_middleware(request, call_next):
```

This runs on **every request**, before and after the route handler:

1. Records start time with `time.perf_counter()` (high-resolution timer)
2. Calls `call_next(request)` — this runs the actual route
3. Records end time, calculates elapsed milliseconds
4. Increments `request_count`
5. If status code ≥ 400, increments `error_count`
6. Logs a structured line: `method=POST path=/recommendations status=200 latency_ms=1.2`
7. Adds elapsed time to `total_latency_ms`

The `_metrics` dict is just an in-memory Python dictionary. It resets when the server restarts. In production you'd use Prometheus counters or StatsD, but for this exercise in-memory is fine.

### The route

```python
@app.post("/recommendations", response_model=TriageResponse)
async def recommend(ticket: TicketInput) -> TriageResponse:
```

FastAPI sees `ticket: TicketInput` and automatically:
1. Parses the JSON body
2. Validates it against the Pydantic model
3. Returns 422 with error details if validation fails
4. Passes the validated object to the function if it succeeds

The function body is just two lines: call the engine, wrap the result. All the complexity is handled by the framework and the engine.

### Health and metrics

Two simple GET endpoints:
- `/health` returns `{"status": "ok"}` — useful for load balancers and container orchestration
- `/metrics` returns the in-memory counters — useful for debugging and monitoring

---

## Tests — What's Actually Being Verified

### test_engine.py (unit tests)

These test the engine in isolation. No web server, no HTTP. They import `get_recommendations` directly and call it as a Python function.

**Why this matters**: if these tests fail, the bug is in the scoring/ranking logic. If these pass but API tests fail, the bug is in the HTTP layer. This isolation speeds up debugging.

The **determinism test** is the most important one — it calls the function twice with identical input and asserts the outputs are equal. This is a hard requirement from the exercise spec.

### test_api.py (integration tests)

These use FastAPI's `TestClient`, which simulates HTTP requests without actually starting a server. It tests the full stack: JSON parsing → Pydantic validation → engine → response serialization.

The **error path tests** (422s) are critical. They verify that:
- Missing fields are caught
- Empty strings are caught
- Invalid JSON is caught  
- Out-of-range values are caught

Each of these returns a 422 status code, which is HTTP's way of saying "I understood your request format, but the data inside is invalid."

---

## Dependency Chain

```
models.py ← engine.py ← main.py
                ↑             ↑
          test_engine.py  test_api.py
```

- `models.py` imports nothing from our code (only Pydantic)
- `engine.py` imports from `models.py`
- `main.py` imports from both `models.py` and `engine.py`
- Tests import from `engine.py` and `main.py` respectively

This one-way dependency flow means changes to the engine never break the models, and changes to the HTTP layer never break the engine.

---

## Why These Libraries?

| Library | Why |
|---------|-----|
| **FastAPI** | Built-in Pydantic validation, auto-generated docs, async support, `TestClient` for integration tests. The modern Python API standard. |
| **Pydantic** | Validation with zero boilerplate. Define the shape once, get parsing + error messages + serialization for free. |
| **Uvicorn** | ASGI server that runs FastAPI. Lightweight, fast, supports `--reload` for development. |
| **Pytest** | Cleaner syntax than unittest. Class-based grouping, fixture support, detailed failure output. |
| **httpx** | Required by FastAPI's `TestClient` under the hood. Not used directly in our code. |

---

## Key Design Decisions Summary

| Decision | Choice | Why |
|----------|--------|-----|
| Engine approach | Keyword matching | Deterministic, no external deps, no API keys, fast |
| Confidence scale | 0–1 float | Industry standard, cleaner than 0–100 |
| Project layout | Flat `app/` | Simple, Docker-friendly, easy to navigate |
| Telemetry | Python logging + in-memory dict | Minimal but shows production awareness |
| Error handling | Pydantic auto-validation | Zero custom code needed for input validation |
| Test strategy | Unit + integration split | Isolates engine logic from HTTP layer |
