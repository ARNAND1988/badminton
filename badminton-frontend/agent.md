# Frontend Agent Boot Notes

## Stack

- Vue 3 single page app
- Vite 5 dev/build tooling
- Vue Router 4 with history mode
- Tailwind CSS 3 through PostCSS and Autoprefixer
- Nginx config for serving the built app in containerized deployments

## Fast Start

```bash
cd badminton-frontend
npm install
npm run dev
```

The Vite dev server listens on `http://localhost:5173`.

API calls to `/api` are proxied by `vite.config.js` to `http://127.0.0.1:8000`, so run the backend on port `8000` for local full-stack work.

## Useful Commands

```bash
npm run dev
npm run build
npm run preview
```

There is no frontend test script currently defined in `package.json`.

## Important Files

- `package.json`: scripts and npm dependencies.
- `vite.config.js`: Vue plugin, port `5173`, and `/api` proxy.
- `tailwind.config.cjs`: Tailwind content paths.
- `postcss.config.cjs`: Tailwind and Autoprefixer setup.
- `src/main.js`: Vue app bootstrap.
- `src/App.vue`: top-level shell.
- `src/router/index.js`: routes for login, verification, bookings, and member availability.
- `src/components/Register.vue`: login/registration entry screen.
- `src/components/Verify.vue`: OTP verification flow.
- `src/components/Dashboard.vue`: bookings, courts, invoices, family members, and play availability UI.
- `src/components/Navbar.vue`: app navigation.
- `nginx.conf`: frontend container web server config.

## Routes

- `/`: login/register screen.
- `/verify`: OTP verification.
- `/dashboard`: redirects to `/bookings`.
- `/bookings`: dashboard booking view.
- `/availability`: member play attendance voting view.

## Backend Contract

The app expects JSON API endpoints under `/api`, including:

- `POST /api/auth/login`
- `POST /api/auth/send-otp`
- `POST /api/auth/verify`
- `GET /api/auth/me`
- `GET /api/bookings`
- `POST /api/bookings`
- `PUT /api/bookings/:id`
- `POST /api/bookings/:id/invoice`
- `GET /api/family-members`
- `POST /api/family-members`
- `GET /api/play-availability`
- `POST /api/play-availability`
- `GET /api/admin/courts`
- `POST /api/admin/courts`

Authenticated calls use a bearer JWT from the backend. Demo accounts are created by the backend bootstrap:

- Admin: `admin` / `admin123`
- Member: `user` / `user123`

## Working Notes

- Keep API paths relative (`/api/...`) so local Vite proxy and production Nginx both work.
- Use existing Vue Options/Composition API style in nearby components before introducing a new pattern.
- Keep Tailwind utility classes consistent with the existing components and shared classes in `src/index.css`.
- If editing navigation, check both `src/router/index.js` and `Navbar.vue`.
- For production verification, run `npm run build`; Vite will catch template and bundling issues.
