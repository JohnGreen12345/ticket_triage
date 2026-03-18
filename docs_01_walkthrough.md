# Walkthrough: How Everything Works

This is a plain-English explanation of the project. No jargon, just what happens and where.

---

## What is this project?

A small web service that acts like a smart helpdesk assistant. You give it a support ticket (a title and a description of a problem), and it gives you back a ranked list of "here's what you should do next" recommendations.

It's an API — meaning there's no website or buttons. You talk to it by sending data to a URL, and it sends data back.

---

## What are the files?

There are only 5 files that matter (plus 2 empty `__init__.py` files that Python needs to recognize folders as packages):

| File | What it does |
|------|-------------|
| `app/models.py` | Defines the **shape** of data going in and coming out. Like a form template — "a ticket must have a title and a description." |
| `app/engine.py` | The **brain**. Takes a ticket, looks for keywords, and decides which recommendations to return. No internet, no AI calls — just pattern matching. |
| `app/main.py` | The **front door**. Receives web requests, validates them, hands them to the engine, and sends back the response. Also tracks how fast each request was. |
| `tests/test_engine.py` | Tests for the brain — does it score keywords correctly? Does it always give the same answer for the same input? |
| `tests/test_api.py` | Tests for the front door — does the URL work? Does it reject bad requests properly? |

---

## What happens when you run `uvicorn app.main:app --reload`?

1. Uvicorn is a web server. It starts up and listens on `http://localhost:8000`.
2. `app.main:app` tells it: "go into the `app` folder, open `main.py`, and use the thing called `app`."
3. `--reload` means: if you edit any file, the server restarts automatically.
4. The server is now waiting for requests.

---

## What happens when you send a request?

When you run this curl command:

```
curl -X POST http://localhost:8000/recommendations \
  -H "Content-Type: application/json" \
  -d '{"title": "Cannot log in", "description": "I reset my password but still get an error"}'
```

Here's the journey, step by step:

1. **Curl sends a POST request** to `http://localhost:8000/recommendations` with JSON data.

2. **Uvicorn receives it** and hands it to FastAPI (our web framework inside `main.py`).

3. **Telemetry middleware fires** — it starts a timer to measure how long this request takes.

4. **FastAPI validates the input** — it checks that `title` and `description` are present and not empty (using the rules in `models.py`). If anything's wrong, it immediately sends back a 422 error and stops.

5. **The route handler runs** — the `recommend()` function in `main.py` takes the validated data and calls `get_recommendations()` from `engine.py`.

6. **The engine does its work:**
   - Combines title + description into one text string
   - Lowercases everything
   - Checks each category's keyword list (auth, billing, performance, data, access)
   - Counts how many keywords from each category appear in the text
   - The category with the most matches wins
   - Returns that category's pre-written actions with calculated confidence scores

7. **The response goes back** — FastAPI converts the result to JSON and sends it.

8. **Telemetry middleware finishes** — it stops the timer, logs the request duration and status code, and updates the counters.

---

## What does the response look like?

```json
{
  "recommendations": [
    {
      "action": "Verify account status and recent lockouts",
      "confidence": 0.19,
      "why": "Login failures after a reset often correlate with account lockouts or disabled accounts."
    },
    {
      "action": "Check auth provider error logs for this user",
      "confidence": 0.16,
      "why": "The error may originate from the identity provider rather than the application itself."
    },
    {
      "action": "Ask user for exact error code and timestamp",
      "confidence": 0.14,
      "why": "Pinpointing the time and code speeds up correlation across authentication systems."
    }
  ]
}
```

The ticket mentioned "log in", "reset", "password", and "error" — those all match the **auth** category, so you get auth-related recommendations.

---

## What happens when you run `pytest -v`?

Pytest finds every file starting with `test_` and runs every function starting with `test_`. Here's what each test checks:

### Engine tests (`test_engine.py`) — 10 tests

| Test | What it checks |
|------|---------------|
| `test_counts_single_keyword` | Does the keyword counter find "login" in "I cannot login"? |
| `test_counts_multiple_keywords` | Can it count 3 keywords in one sentence? |
| `test_case_insensitive` | Does "PASSWORD" match "password"? |
| `test_no_matches_returns_zero` | If no keywords match, does it return 0? |
| `test_auth_ticket_returns_auth_actions` | Does a login-related ticket get auth recommendations? |
| `test_billing_ticket_returns_billing_actions` | Does a billing ticket get billing recommendations? |
| `test_deterministic_same_input_same_output` | **Key requirement** — run it twice with the same input, get the exact same output? |
| `test_top_n_respected` | If you ask for 1 recommendation, do you get exactly 1? |
| `test_top_n_max` | If you ask for 10, does it handle that without crashing? |
| `test_fallback_when_no_keywords_match` | If the ticket is vague ("something unusual"), do you get generic fallback recommendations? |
| `test_confidence_descending_within_category` | Are recommendations sorted highest confidence first? |
| `test_confidence_between_zero_and_one` | Is every confidence score between 0.0 and 1.0? |
| `test_empty_after_strip_uses_fallback` | Does a super-short ticket ("Hi" / "Help") still return 3 results? |

### API tests (`test_api.py`) — 11 tests

| Test | What it checks |
|------|---------------|
| `test_valid_ticket_returns_200` | Send a good ticket → get 200 OK with 3 recommendations? |
| `test_response_shape` | Does each recommendation have `action`, `confidence`, and `why`? |
| `test_custom_top_n` | Can you request 2 recommendations instead of the default 3? |
| `test_missing_title_returns_422` | Send a ticket without a title → get 422 error? |
| `test_missing_description_returns_422` | Send a ticket without a description → get 422 error? |
| `test_empty_title_returns_422` | Send a ticket with `""` as title → get 422 error? |
| `test_empty_body_returns_422` | Send `{}` with no fields → get 422 error? |
| `test_invalid_json_returns_422` | Send garbage instead of JSON → get 422 error? |
| `test_top_n_out_of_range_returns_422` | Send `top_n: 0` → get 422 error? |
| `test_health_endpoint` | Does `/health` return `{"status": "ok"}`? |
| `test_metrics_endpoint` | Does `/metrics` return request count, error count, and latency? |

---

## The three extra endpoints

| Endpoint | Purpose |
|----------|---------|
| `POST /recommendations` | The main one — send a ticket, get recommendations |
| `GET /health` | Quick check: is the server alive? Returns `{"status": "ok"}` |
| `GET /metrics` | How many requests have been made? How many errors? What's the total latency? |

---

## What's NOT in this project (yet)

- No database — everything is in-memory
- No Docker — just run it directly with Python
- No AI/LLM calls — just keyword matching
- No UI — API only
- No authentication — anyone can call it
- No AGENTS.md or docs/ folder — that's Phase 5
