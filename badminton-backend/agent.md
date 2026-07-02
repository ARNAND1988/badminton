# Backend Agent Boot Notes

## Stack

- Python Flask application factory in `app/__init__.py`
- Flask-SQLAlchemy models
- Alembic migrations
- JWT auth with `PyJWT`
- OTP hashing with `passlib`
- Optional Redis-backed OTP storage
- Optional Twilio WhatsApp delivery
- Flask-Limiter for rate limiting
- Flask-Talisman enabled outside testing/development
- Gunicorn production entrypoint through `wsgi.py`
- Pytest test suite

## Fast Start

```bash
cd badminton-backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL="sqlite:///db.sqlite"
export SECRET_KEY="dev-secret"
export JWT_SECRET="dev-jwt-secret"
export FLASK_ENV=development
export AUTH_MOCK=1
flask --app app:create_app run --port=8000
```

The app serves API routes on `http://localhost:8000/api`.

## Useful Commands

```bash
pytest -q
pytest --cov=app
gunicorn wsgi:app -w 2 -b 0.0.0.0:8000
alembic -c alembic.ini upgrade head
alembic -c alembic.ini revision --autogenerate -m "describe change"
```

## Environment Variables

- `DATABASE_URL`: SQLAlchemy database URL. Local quick start can use `sqlite:///db.sqlite`; production should use Postgres.
- `SECRET_KEY`: Flask secret key.
- `JWT_SECRET`: JWT signing secret. Falls back to `SECRET_KEY` when unset.
- `JWT_EXP_SECONDS`: token lifetime in seconds, default `3600`.
- `REDIS_URL`: optional Redis URL for OTP storage, for example `redis://localhost:6379/0`.
- `AUTH_MOCK`: set to `1`, `true`, or `yes` only in development to return OTPs in API responses.
- `FLASK_ENV`: set to `development` locally. Talisman is skipped in development/testing.
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `WHATSAPP_FROM`: optional production WhatsApp OTP delivery settings.

## Important Files

- `app/__init__.py`: app factory, extensions, blueprints, default seed data, health route.
- `app/models.py`: `User`, `FamilyMember`, `PlayAvailabilityVote`, `Court`, `Booking`, `BookingParticipant`, `Invoice`.
- `app/auth.py`: OTP auth, demo username/password login, JWT issuance, current-user endpoint.
- `app/bookings.py`: booking, court admin, invoice, family member, and play availability endpoints.
- `app/utils.py`: WhatsApp/Twilio helper.
- `wsgi.py`: Gunicorn entrypoint.
- `requirements.txt`: Python dependencies.
- `alembic.ini`, `alembic/`: database migrations.
- `tests/`: pytest coverage for auth, bookings, and play availability.

## API Overview

Health:

- `GET /api/health`

Auth:

- `POST /api/auth/send-otp`
- `POST /api/auth/verify`
- `POST /api/auth/login`
- `GET /api/auth/me`

Bookings and courts:

- `GET /api/bookings/availability?date=YYYY-MM-DD`
- `GET /api/bookings`
- `POST /api/bookings` admin only
- `PUT /api/bookings/:id` admin only
- `POST /api/bookings/:id/invoice` admin only
- `GET /api/admin/courts` admin only
- `POST /api/admin/courts` admin only

Member availability:

- `GET /api/family-members`
- `POST /api/family-members`
- `GET /api/play-availability`
- `POST /api/play-availability`

Admin users:

- `GET /api/admin/users` admin only
- `POST /api/admin/users` admin only

## Demo Accounts

The app seeds these users if missing:

- Admin: `admin` / `admin123`, phone `+10000000000`

## Database Notes

- `create_app()` currently calls `db.create_all()` and seeds default court/user records on startup.
- Alembic migrations exist and should be used for schema changes that need repeatable deployment.
- Dates and times in booking models are stored as strings (`YYYY-MM-DD`, `HH:MM`), so preserve that format in API clients and tests.

## Working Notes

- Admin-only endpoints require a bearer JWT for a user with `role == "admin"`.
- Development OTP mock mode only works when `AUTH_MOCK=1` and `FLASK_ENV=development`.
- Redis is optional; without `REDIS_URL`, OTPs are kept in process memory.
- When changing models, update `models.py`, add or adjust Alembic migrations, and run `pytest -q`.
- Tests use SQLite-friendly setup from `tests/conftest.py`; avoid adding production-only database assumptions without test coverage.
