# Smash Arena presentation review

Work is on `design/smash-arena-theme`. The initial review preceded deployment; the subsequent user-authorized frontend release is recorded in [DEPLOYMENT.md](DEPLOYMENT.md). The working tree was clean before work began. Active application: top-level `badminton-frontend` (Vue 3, Vue Router, Vite, Tailwind); legacy nested copies were left alone.

## Existing flows inspected before editing

| Area | Existing behavior and implementation | Verification available |
| --- | --- | --- |
| Public entry | `/` and `/dashboard` redirect to `/availability`; `/poll` is a public group poll; `/bookings` has public upcoming sessions. | Router review, browser redirects, API journeys |
| Authentication | `Register.vue` owns login, register and WhatsApp password reset. `authSession.js` stores the existing JWT/member keys in localStorage or sessionStorage according to Remember me. Navbar logout clears those keys and goes to `/login`. Protected routes check `/api/auth/me` and preserve the redirect query. | Auth tests, critical journeys, before/after browser requests |
| Bookings/courts | Shared Dashboard owns creation, recurrence, editing, cancellation/deletion, court rates/maps and freeze periods. API calculates costs. | Booking/API tests and admin UI journey |
| Families/participation | Real family members, linked player accounts, individual availability statuses and individual attendance controls. Owner/member synchronization is backend-owned. | Family and linked-account tests; browser family vote and attendance |
| Attendance/invoices | Attending/participated players determine cost sharing. Existing monthly selection, all invoice columns, detail expansion, payment status, PDF download, bank/Tikkie links and admin reconciliation remain. | Invoice, rounding, cost-sharing, payment/PDF and authorization tests |
| Profiles/permissions | Account menu shows the signed-in name and logout. Family management lives on availability; member editing and roles live on admin members. There is no separate member profile route. Admin and super-admin permissions are existing API/dashboard checks. | Role/API tests, member denial in browser, admin screen inspection |
| Notifications/PWA | Existing WhatsApp settings, previews, test/group sends and logs; existing Wise integrations. No service worker, manifest, biometric/passkey UI or PWA install flow was found. | Mocked notification/Wise tests; PWA reported N/A |

Read `AGENTS.md`, the badminton skill/module notes, and the repository's mandatory `nieuwegein-badminton-regression` skill and coverage map. Existing checks: `./scripts/regression.sh fast`, `./scripts/regression.sh full`, backend pytest, production frontend build and `scripts/responsive_smoke.py`. No existing browser E2E suite/dependency was found; installed headless Chromium and its DevTools protocol were used for local browser checks without changing dependencies.

## Presentation changes

- Shared navy/orange/teal/white tokens, system typography, light canvas, white cards, restrained shadows, consistent rounding and visible focus.
- Separate original anime artwork with adult doubles players, local responsive WebP variants (approximately 64/197 kB) and JPEG fallback (288 kB); explicit image dimensions and no video or animation library.
- Public welcome content sits above the existing availability page, retaining the existing root redirect. Login/register/reset use the existing form alongside the artwork. Mobile login gets a smaller illustration.
- Member/admin screens stay compact. All controls, details, filtering, exports and tables remain; wide tables retain their own scroll containers.
- Shared lightweight SVG icons; existing navigation and account/admin menu handlers retained. Auth labels now explicitly target their inputs; other dashboard fields have accessible names derived from their existing labels and descriptions. Existing status/error messages receive live-region semantics. The page wrapper no longer creates a stacking context that could trap dialogs below navigation.
- First actual upcoming booking receives a “Next session” label; no invented session or extra request. The existing per-person family controls remain, rather than assuming exactly two players.

The dashboard controller body was moved unchanged to `dashboard/useDashboard.js`; Register’s auth body is unchanged after removing its presentation import/component registration. Routes, authSession, backend, migrations, API contracts, dependencies and build configuration have no edits. Navbar script changes concern icon rendering and class selection only.

## Verification results

| Check | Result |
| --- | --- |
| Baseline full gate | PASS — 107 tests, no failures/skips, build and structural checks pass |
| Narrow critical API journeys | PASS — 3 tests |
| New presentation interaction contracts | PASS — 11 tests; retained event handlers/models/validators, valid welcome destinations, auth/dashboard field names, decorative SVG semantics, direct prop/model forwarding and semantic controller equivalence |
| Fast gate | PASS — 19 selected tests, build and structural checks pass |
| Final full gate | PASS — 107 tests, no failures/skips, build and structural checks pass |
| Before/after auth browser journey | PASS — valid/invalid login, logout, refresh/persistence, protected redirect and denied member admin access; all 14 API request paths/methods and login payloads identical |
| Additional rendered UI journey | PASS — 16 checks: court creation, booking creation/edit/cancellation, family creation/voting/persistence/attendance, short-viewport login and dialog actions, modal stacking, focus and reduced motion; no messages sent |
| Responsive rendered pages | PASS — 56 public/member/admin page combinations at 375, 390, 768 and 1440px; no document horizontal overflow, clipped controls, JavaScript exceptions, console errors or unexpected API failures |

Run the focused tests with `cd badminton-frontend && node tests/theme-presentation.test.mjs`. These use Vue's existing compiler dependency and Node's built-in test runner; no package or build changes are needed. Baseline interaction fingerprints are intentionally explicit: future feature changes should update them only after review.

Local browser testing uses a dedicated API at port 8011, `sqlite:///:memory:`, explicit test accounts/secrets, disabled Twilio and WhatsApp messaging, and a Vite preview at 5174 proxying only to that API. No production booking, invoice, account or notification was modified. The preview runs single-threaded because concurrent requests against one in-memory SQLite connection produced connection errors in an early test setup; correcting the preview setup resolved them without application changes. The baseline initially required permission to open a local mock HTTP socket; the rerun passed. Existing SQLAlchemy deprecation/in-memory rate-limit and Vite CJS warnings remain.

## Limits and review

- No separate homepage or profile route was added. Existing availability/account/member surfaces received the theme. Family rules were retained; no hardcoded “1 player / 2 players” selector was introduced.
- No PWA caching update applies because PWA support is absent. Real device keyboards, screen-reader output, passkeys and installability are not claimed as tested. A shortened Chromium viewport checks login-action reachability; it does not emulate an actual operating-system keyboard.
- External WhatsApp delivery, Wise transfers and real payment-provider pages were not exercised; the gate uses mocked integrations. Payment/PDF calculations and linked-family synchronization are covered by existing API tests rather than a full browser payment journey.
- Screenshots use only isolated test fixtures; any court/session/person shown is preview data, not a hardcoded UI record.

## Screenshots

| Screen | Desktop | Mobile |
| --- | --- | --- |
| Public entry | [1440px](screenshots/desktop.png), [768px tablet](screenshots/tablet.png) | [390px](screenshots/mobile.png), [full page](screenshots/mobile-full.png) |
| Login | [1440px](screenshots/login-desktop.png) | [390px, full page](screenshots/login-mobile.png) |
| Booking with real fixture data | — | [Family attendance](screenshots/booking-mobile.png) |
| Admin | [Booking controls](screenshots/admin-desktop.png) | [Notification preview, short viewport](screenshots/dialog-mobile.png) |
| Invoices | — | [Monthly details](screenshots/invoices-mobile.png) |

All 56 layout captures were checked for document overflow and offscreen controls (excluding intended table scroll containers). Representative public, login, booking, member availability, invoice, admin and notification-dialog images were visually inspected for overlap and readability. Full-page screenshots show the fixed bottom navigation at its original viewport position; content below it remains reachable by scrolling. Supplemental evidence is in `verification.json`.

## Dashboard maintenance split

`Dashboard.vue` is now 1,201 lines (previously 4,036). Eight presentation components receive explicit props and existing callbacks; the shared `useDashboard.js` controller runs as the dashboard's setup function and keeps state, requests, permissions and lifecycle together. Its entire function body was copied byte-for-byte. Availability's three scalar fields forward edits immediately through named model bindings; editable day/poll/settings objects keep their existing references. No child introduces fetching or business state.

| File under `src/components/dashboard/` | Responsibility |
| --- | --- |
| `useDashboard.js` | Existing shared state, handlers, API calls, permissions and lifecycle |
| `MemberBookingsView.vue` | Member bookings, family attendance and completed history |
| `AvailabilityView.vue` | Availability, public poll and family controls |
| `MonthlyInvoiceDetails.vue` | Existing invoice totals, payment details and every table column |
| `PaymentSettingsView.vue` | Existing super-admin payment configuration form |
| `NotificationSettingsView.vue` | Existing settings, templates and logs |
| `NotificationPreviewDialog.vue` | Existing editable notification preview |
| `CostVerificationDialog.vue` | Existing cost verification dialog |
| `PublicWelcome.vue` | Theme welcome content and existing route actions |
| `TentativeIcon.js` | Existing tentative-status glyph, shared without duplication |

The remaining admin booking/court/invoice/member/diagnostic layouts stay in the dashboard and use the same controller. Repository frontend notes now point maintainers to the appropriate files.

After extraction: fast gate PASS (19 tests), full gate PASS (107 tests), focused frontend checks PASS (11 tests), and the browser creation/edit/family/vote/attendance/focus/reduced-motion/dialog journey PASS (14 checks). Rendered DOM/live-field comparisons covered all 56 page/viewport pairs: 44 were exact; 12 differed only in date/month defaults or month options because the check crossed midnight in Europe/Amsterdam. The controller body and native interaction fingerprints remain unchanged. After excluding the initial refresh of the browser's already-stored admin session, all 14 auth journey requests matched. No browser exceptions, console errors, unexpected API failures, overflow or clipped controls were detected. The extracted notification preview retained the dashboard-owned object during editing and opened/closed correctly above mobile navigation; no notification was sent. Details: `dashboard-refactor-verification.json`.

## Reference fidelity refinement

The public entry now joins the hero and white community panel into one surface, with three illustrated feature cards and a separate quick-action row. The welcome area includes the shuttlecock mascot and speech bubble. Paired adult player artwork appears on the family card and alongside the existing family form. Illustrated navy/orange/teal SVGs cover calendar/shuttle, racket/calendar, court/clipboard, receipt/euro, profile and shuttle features; compact outline icons remain on navigation and small controls. The active desktop navigation uses an orange underline. Mobile moves the booking card next to the hero and stacks the family/invoice cards in two columns; tablet cards place illustrations above labels to preserve readable text widths.

The existing club logo, route names, form handlers, controller, API requests and calculations remain. The availability entry does not load booking data, so its booking card links to the real bookings page. That page marks the actual first upcoming booking as “Next session” with a shuttle illustration. No session fixture, family-count selector, profile route or notification action was added.

Baseline fast gate: 19 passed. Final fast/full gates: 19/107 passed. Focused frontend tests: 11 passed, including decorative semantics for both icon sizes. All 56 form-state comparisons matched before/after refinement. All 14 auth journey requests (paths, methods and login payloads) matched after excluding an initial `/api/auth/me` refresh from a previously stored browser session. Browser checks covered all four requested widths with no document overflow, clipped controls, console errors or JavaScript exceptions. The isolated creation/edit/family/vote/attendance/focus/reduced-motion journey passed all 10 checks. Additional finished-layout captures cover the tablet adjustment. No notifications were sent. Existing verification limits above still apply. Supplemental evidence: `reference-refinement-verification.json`.

## Rollback

The change requires no database rollback. Before merge, if these are still the only uncommitted changes, save them with `git stash push -u -m "Smash Arena theme" -- badminton-frontend/src badminton-frontend/tests badminton-frontend/agent.md docs/smash-arena`, then `git switch main`. The stash retains the theme for later review. After merging a theme commit, `git revert <theme-commit>` and rebuild the frontend through the existing process. Do not reset unrelated work or undo backend commits.

## Artwork provenance

Built-in image-generation tool, inspected before integration. Project assets: `badminton-frontend/src/assets/arena-hero.webp`, `arena-hero-small.webp`, `arena-hero.jpg`.

Final prompt:

> Use case: stylized-concept. Asset type: website hero artwork, wide landscape 1536x1024. Create an original polished anime sports illustration for a friendly recreational badminton community. Four clearly adult players, women and men aged 25-45 with diverse skin tones, in navy sportswear with orange and teal accents, playing doubles inside a spacious indoor badminton hall. Dynamic but believable racket action, a central adult man jumping for a smash, smiling adult woman in foreground at right, other adults behind, badminton net and indoor court markings, bright overhead lights, subtle white and orange motion strokes. Crisp ink outlines, expressive faces, rich hand-painted shading. Navy blue cinematic background, warm orange light, teal court. Composition: players occupy right two thirds; left third mostly dark navy atmospheric hall with quiet negative space for HTML heading. Welcoming energetic family club mood. No text, no letters, no logos, no watermark, no interface, no cards, no childlike characters. This is separate artwork only, not a website screenshot.

Additional original cutout assets generated with the built-in image tool, inspected, and encoded as transparent WebP at 400×366: `badminton-frontend/src/assets/arena-mascot.webp` (35.85 kB) and `arena-family.webp` (48.35 kB). Feature icons are lightweight inline SVG in `ArenaFeatureIcon.vue`. Both cutouts reserve dimensions; the reference screenshot is not embedded into the UI.

Mascot final prompt:

> Use case: stylized-concept. Asset type: transparent website welcome mascot cutout. Create one adorable running badminton shuttlecock mascot, with white feather plume, white rounded cork face, bright orange headband, friendly navy eyes and smile, navy cartoon arms and legs and orange sneakers, one arm waving. Crisp expressive anime sports illustration, thick navy ink outlines, softly shaded white feathers, orange and teal accents. Slight rightward movement with two tiny orange motion strokes. Entire character visible centered with generous transparent margin. Family-friendly recreational club. No text, lettering, border, logos, UI or background. True alpha transparent background.

Paired players final prompt:

> Use case: stylized-concept. Asset type: transparent website feature-card artwork. Two friendly clearly adult recreational badminton players aged 30-40, smiling side by side, one bearded man with medium brown skin and short dark hair, one woman with light-medium skin and brown ponytail, wearing navy badminton shirts with orange collars and small teal accents. Anime sports illustration with bold clean navy ink outlines, detailed welcoming faces, soft shading. Bust portraits from waist up, shoulders together, lightly overlapping; entire silhouette visible with transparent margins. Similar to small hand-painted illustrated community avatars in a polished sports dashboard. No text, logos, frames, UI, photorealism, children or background. True alpha transparent background.
