# Frontend Agent Notes

## Stack

- Vue 3
- Vue Router
- Vite
- Tailwind CSS

## Active Paths

- `src/App.vue`: app shell and route-width layout
- `src/router/index.js`: route map and auth guard
- `src/components/ArenaHero.vue`, `ArenaIcon.vue`, `ArenaFeatureIcon.vue`: shared hero artwork, compact icons and illustrated feature icons
- `src/components/Navbar.vue`: desktop/mobile nav, admin menu, auth-aware UI
- `src/components/Register.vue`: login and registration screen
- `src/components/Dashboard.vue`: main member and admin work surface
- `src/components/dashboard/useDashboard.js`: shared dashboard state, API calls, permissions, formatters, and lifecycle
- `src/components/dashboard/*.vue`: extracted member bookings, availability/poll, invoice details, payment settings, notification settings/dialogs, and public welcome presentation
- `src/authSession.js`: localStorage/sessionStorage auth state helpers

## How The Frontend Works

### Route model

Routes map into either the register/login screen or a shared `Dashboard` component with different `initialView` props.

Important route groups:

- member views: `/availability`, `/bookings`, `/costs`
- admin views: `/admin/bookings`, `/admin/courts`, `/admin/costs`, `/admin/payment-settings`, `/admin/audit-logs`, `/admin/notifications`, `/admin/members`

Protected routes rely on `router.beforeEach()`, `hasAuthSession()`, and a live `/api/auth/me` check.

### Session model

`src/authSession.js` stores:

- `auth_token`
- `member_phone`
- `member_name`
- `member_email`
- `member_role`

The "remember me" behavior picks `localStorage` or `sessionStorage`. Session changes emit a `badminton-auth-changed` browser event so `Navbar.vue` and routed screens can refresh.

### Dashboard model

`src/components/Dashboard.vue` orchestrates the UI, using `dashboard/useDashboard.js` as its setup function. The controller keeps the existing fetch logic, local state, and view switching together for:

- bookings
- admin bookings
- admin courts
- play availability
- member costs/invoices
- payment settings
- admin costs and payment invoices
- members
- admin audit logs
- notifications

Before refactoring, find the `activeView` branch in `Dashboard.vue` and its presentation component, then search the controller for the endpoint and handler. Presentation components receive explicit data and callbacks. Mutable day, poll, invoice/settings objects retain their dashboard-owned references; availability's scalar form fields use named model bindings that update the parent immediately. Do not add parallel fetching, drafts, permission checks, or state to these presentation components.

### API usage

The frontend mostly talks to:

- `/api/auth/me`
- `/api/family-members`
- `/api/play-availability`
- `/api/bookings`
- `/api/misc-costs`
- `/api/admin/courts`
- `/api/admin/freeze-periods`
- `/api/admin/users`
- `/api/admin/payment-settings`
- `/api/admin/payment-invoices/...`
- `/api/admin/whatsapp-notifications`

If an API shape changes, update both the fetch call and the rendering logic that assumes the response shape.

## Visual Structure

- `App.vue` changes page width based on route type.
- `Navbar.vue` renders separate desktop and mobile navigation patterns.
- Admin navigation appears only when stored `member_role` indicates admin access.
- `Register.vue` handles both login and registration modes in one component.

## Build

Run:

```bash
cd badminton-frontend
npm run build
```

Focused frontend regression coverage is in `tests/theme-presentation.test.mjs`. Run it with `node tests/theme-presentation.test.mjs`; it checks native interaction contracts across the extracted components, prop/model forwarding, labels, and controller equivalence. It uses the installed Vue compiler and Node test runner without new dependencies. Also run the mandatory repository regression gate.

## Working Rules

- Prefer editing the existing view component (or remaining `Dashboard.vue` branch) and its controller handler over introducing parallel state flows.
- Keep route names, nav labels, and `initialView` mappings consistent.
- When auth behavior changes, check `Register.vue`, `authSession.js`, `Navbar.vue`, and the router guard together.
- Prefer the top-level `badminton-frontend` directory; treat `badminton-frontend/badminton-frontend` as a legacy split-repo copy.
