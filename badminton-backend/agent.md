# Backend Agent Notes

## Stack

- Flask application factory in `app/__init__.py`
- SQLAlchemy models in `app/models.py`
- Main API blueprints in `app/auth.py`, `app/bookings.py`, and `app/docs.py`
- JWT auth with `PyJWT`
- Password hashing and OTP hashing with `passlib`
- Redis-backed OTP storage when `REDIS_URL` is present, in-memory fallback otherwise
- Twilio fallback helper in `app/utils.py`

## Active Paths

- `app/__init__.py`: app bootstrap, config, schema patching, seed users
- `app/models.py`: ORM models and booking cost split helpers
- `app/auth.py`: register, login, OTP, `/me`
- `app/bookings.py`: most domain logic and admin APIs
- `app/docs.py`: dynamic OpenAPI spec and Swagger UI
- `tests/`: pytest coverage for auth, bookings, and play availability

## How The Backend Works

### Startup model

`create_app()` configures Flask, SQLAlchemy, rate limiting, optional Talisman, Redis, and JWT settings, then registers the blueprints.

On startup it also:

- runs `db.create_all()`
- inspects existing tables
- applies many `ALTER TABLE` statements opportunistically for missing columns
- seeds demo admin/member users in development or mock-auth mode
- always upserts the `Anand Parasuraman` super-admin user

This means schema changes are partly model-driven and partly startup-patched. If you add a column that must work against existing databases, update both the SQLAlchemy model and the startup bootstrap logic in `app/__init__.py`.

### Auth flow

Two auth paths exist:

- OTP-based auth in `app/auth.py` via `/api/auth/send-otp` and `/api/auth/verify`
- email/password auth via `/api/auth/register` and `/api/auth/login`

`/api/auth/me` resolves the bearer token back to a `User`.

Important development behavior:

- `AUTH_MOCK=1` only exposes `mock_otp` when `FLASK_ENV=development`
- seed credentials default to `admin/admin123` and `user/user123`

### Domain model

Core models in `app/models.py`:

- `User`
- `FamilyMember`
- `Court`
- `Booking`
- `BookingParticipant`
- `PlayAvailabilityVote`
- `Invoice`
- payment-related models such as `PaymentSettings` and payment invoice records
- audit and notification models such as `AdminAuditLog`

Booking cost sharing is computed from participant statuses. Only `attending` and `participated` count toward cost split.

### Main API surface

`app/bookings.py` is the main domain module. It owns:

- play availability
- family member CRUD
- booking CRUD
- participant RSVP and admin attendance management
- court management
- freeze periods
- misc shared costs
- monthly invoice summaries
- admin users and audit logs
- WhatsApp notification settings and test sends
- Wise payment settings, invoice generation, and webhook handling

Expect most business changes to land in `app/bookings.py` plus `app/models.py`.

### API docs

`app/docs.py` walks Flask `url_map` at runtime and builds the OpenAPI document dynamically. If you add or rename an endpoint, keep `ENDPOINT_DOCS` aligned so `/api/docs` remains readable.

## External Integrations

### WhatsApp

Two patterns exist:

- direct Twilio send helper in `app/utils.py`
- bot-driven notification flow in `app/bookings.py` using `WHATSAPP_BOT_URL` and `WHATSAPP_BOT_TOKEN`

Check which path the touched feature uses before changing notification behavior.

### Wise payments

Wise integration lives in the lower half of `app/bookings.py`. It handles:

- payment settings persistence
- payment request creation
- webhook subscription creation
- incoming transfer webhook processing
- payment invoice status updates

If payment behavior changes, review both the admin endpoints and the webhook handler.

## Test And Run

Run tests:

```bash
cd badminton-backend
pytest
```

Test setup in `tests/conftest.py` uses:

- `AUTH_MOCK=1`
- `FLASK_ENV=development`
- `DATABASE_URL=sqlite:///:memory:`

For local manual runs, use the environment block documented in the repo `README.md`.

## Working Rules

- Keep changes narrow in `app/bookings.py`; it is large and cross-cutting.
- Prefer updating existing helpers over introducing parallel logic.
- When changing a response payload, search the frontend for the same endpoint and update the consumer.
- When changing model fields, check tests and seed/bootstrap code together.
