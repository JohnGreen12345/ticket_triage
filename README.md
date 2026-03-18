# Support Ticket Triage Service

A deterministic API that returns ranked recommendations for incoming support tickets.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the server
uvicorn app.main:app --reload

# Run tests
pytest -v
```

## Call the Endpoint

```bash
curl -X POST http://localhost:8000/recommendations \
  -H "Content-Type: application/json" \
  -d '{"title": "Cannot log in", "description": "I reset my password but still get an error"}'
```

### Custom top_n

```bash
curl -X POST http://localhost:8000/recommendations \
  -H "Content-Type: application/json" \
  -d '{"title": "Slow dashboard", "description": "Page takes 10s to load", "top_n": 5}'
```

### Health & Metrics

```bash
curl http://localhost:8000/health
curl http://localhost:8000/metrics
```

## Project Structure

```
ticket-triage/
├── app/
│   ├── main.py       # FastAPI app, route, telemetry middleware
│   ├── models.py     # Pydantic models (shared contract)
│   └── engine.py     # Triage engine (keyword matching + ranking)
├── tests/
│   ├── test_engine.py  # Unit tests for scoring and ranking
│   └── test_api.py     # Integration tests hitting the endpoint
├── requirements.txt
└── README.md
```
