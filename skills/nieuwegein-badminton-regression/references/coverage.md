# Coverage map

The full gate maps the current application as follows:

- Authentication: valid/invalid login, registration, reset, token persistence/protected API access, and admin authorization in `tests/test_auth.py` and `tests/test_regression_journeys.py`.
- Members/families/roles: retrieval, updates, isolation, linked family compatibility, and permissions in booking and availability tests.
- Bookings/participation: list/create/update/delete, court/date/time, RSVP/attendance, history, and family attendance in booking tests and the critical journey.
- Invoices/admin: monthly calculation, aggregation, deduplication, payment status/history, admin CRUD, audit and payment behavior in booking tests.
- Frontend/mobile: Vite production compilation plus responsive structural checks for 390x844, 430x932, 768x1024 and desktop assumptions.
- PWA: report N/A until a manifest/service worker exists. When introduced, add manifest, service-worker lifecycle, cache-version, authenticated-update and stale-bundle tests before marking PASS.
- Backend/database: application factory startup, isolated SQLite connectivity/schema creation, middleware, API behavior, migrations/model compatibility, and unexpected response failures.

When adding a browser-capable test dependency, preserve the critical journeys' fixture-only accounts and extend them through the rendered UI without using production credentials. Never reduce the existing API end-to-end coverage while doing so.
