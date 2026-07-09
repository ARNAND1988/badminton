# Frontend Agent Notes

## Stack

- Vue 3
- Vue Router
- Vite
- Tailwind CSS

## Active Paths

- `src/App.vue`: app shell and route-width layout
- `src/router/index.js`: route map and auth guard
- `src/components/Navbar.vue`: desktop/mobile nav, admin menu, auth-aware UI
- `src/components/Register.vue`: login and registration screen
- `src/components/Dashboard.vue`: main member and admin work surface
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

`src/components/Dashboard.vue` is the central UI module. It contains most fetch logic, local state, and view switching for:

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

Before refactoring, search for the target `activeView` branch and for the endpoint the view calls. Most behavior lives in a small number of large methods near the bottom of the file.

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

There is no dedicated frontend test suite in this repo today, so the production build is the main safety check.

## Working Rules

- Prefer editing the existing `Dashboard.vue` branch for the affected view over introducing new parallel state flows.
- Keep route names, nav labels, and `initialView` mappings consistent.
- When auth behavior changes, check `Register.vue`, `authSession.js`, `Navbar.vue`, and the router guard together.
- Prefer the top-level `badminton-frontend` directory; treat `badminton-frontend/badminton-frontend` as a legacy split-repo copy.
