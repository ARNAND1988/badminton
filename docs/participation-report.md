# Participation report

Admins and super admins can open **Invoices & Payments → Participation report**.
The GET-only endpoint is `/api/admin/reports/participation`. Query parameters:
`start`, `end` (inclusive ISO dates), `status` (`all`, `paid`, `partial`,
`invoiced_unpaid`, `not_invoiced`), `family` (the option's stable ID), `view`
(`person`, `family`, `both`), and `format=csv` for download.

The default includes all bookings that have ended in Europe/Amsterdam, including
archived and past confirmed bookings, without changing their stored statuses.
Cancelled and future bookings never count. Only `attending` and `participated`
attendance counts. Linked user and family participant IDs identify the same
person, counted once per booking. The existing rounded-up court split runs over
these distinct players. Family sessions count distinct bookings; appearances
count players. All registered people, including family members with no sessions,
appear with the all-status filter. Guest identities use their recorded participant
key; guests are not merged by similar names.

Payment allocation uses non-test payment invoices and their recorded paid amount
(or full amount due when marked PAID). Stored booking line items identify court
charges and their amounts; missing bookings in a stored snapshot remain not yet
invoiced, even if they share an invoice's month. An empty snapshot is authoritative.
For legacy invoices with NULL snapshots, the fallback uses that family's recorded
bookings created no later than the invoice. Historical amounts cannot be recovered
exactly when a legacy invoice has no snapshot and bookings were subsequently edited.

Payments are allocated proportionally over the full invoice amount, including
miscellaneous charges. Largest-remainder allocation preserves cents with stable
ties. Booking line amounts and their payments are divided across that family's
players in the booking. The report shows only court amounts. Allocation occurs
before any report filters, so filtering never redistributes payments. If duplicate
invoice records cover the same family booking, the latest record takes precedence.
Legacy per-booking invoice settlement alone is not evidence of a family payment.

Apply filters to refresh the tables; CSV uses the selected filters and view. A
selected family limits every exported data row to that family. The download has
person/family section labels and monetary amounts in EUR. No report operation
creates invoices, changes attendance, records payments, or sends notifications.

Deploy both backend and frontend after merging the feature branch. No database
migration or historical data rewrite is required.
