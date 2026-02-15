Split repository into standalone backend and frontend repositories

Two supported approaches are provided:

- Quick: `git subtree split` — creates branches containing only the subtree history.
- Recommended: `git-filter-repo` — creates clean repositories preserving history for the selected paths.

Scripts included

- `scripts/split_subrepos.sh` — uses `git subtree split` to create `split-backend` and `split-frontend` branches and optionally push them to remotes.
- `scripts/split_with_filterrepo.sh` — uses `git filter-repo` (recommended) to produce separate repositories or archives. Requires `git-filter-repo` installed.

Subtree quick steps (local)

```bash
# create subtree branches
git subtree split -P backend -b split-backend
git subtree split -P frontend -b split-frontend

# push to new remotes (replace URLs)
git remote add backend-remote git@github.com:yourorg/badminton-backend.git 2>/dev/null || true
git remote add frontend-remote git@github.com:yourorg/badminton-frontend.git 2>/dev/null || true

git push backend-remote split-backend:main
git push frontend-remote split-frontend:main
```

Filter-repo recommended steps

1. Install `git-filter-repo`: https://github.com/newren/git-filter-repo
2. Operate from a fresh clone (safer):

```bash
git clone /path/to/monorepo repo-backend-work
cd repo-backend-work
git filter-repo --path backend/ --path-rename backend/:/ --force
git remote add origin-backend git@github.com:yourorg/badminton-backend.git
git push origin-backend main
```

Repeat from a fresh clone for `frontend` replacing `backend/` with `frontend/`.

Automated helper

Use the provided helper to push directly (run in repository root):

```bash
BACKEND_REMOTE=git@github.com:yourorg/badminton-backend.git \
FRONTEND_REMOTE=git@github.com:yourorg/badminton-frontend.git \
./scripts/split_with_filterrepo.sh
```

Notes

- Always test the resulting repos before removing the monorepo.
- `git-filter-repo` rewrites history; be careful when force-pushing to remote repositories.
- If you prefer I can run the split for you, provide either (a) a `git bundle` containing the repo history, or (b) add a remote I can push to and give me access.
