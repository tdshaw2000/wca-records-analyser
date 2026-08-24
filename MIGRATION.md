# Migrating to the personal GitLab account

Moving this repo from the corporate-linked `gitlab.com:Tim.Shaw/wca-records-analyser`
account to your personal gitlab.com account. Both are gitlab.com SaaS — this is an
account/namespace move, not a hosting change, so it's low-risk and fully reversible
(the old project can stay in place until the new one is verified working).

Three things depend on the GitLab project identity and need to move deliberately:

1. **Git history** — straightforward mirror push.
2. **The self-hosted CI runner** (`wca-analyser`, tag `wsl-docker`) — registered
   per-project, so it needs re-registering against the new project.
3. **Render.com** — currently clones via a GitLab OAuth connection tied to the
   corporate-linked account, and deploys are gated by a CI/CD variable
   (`RENDER_DEPLOY_HOOK_URL`) that lives on the GitLab project, not in git.

Nothing in `.gitlab-ci.yml`, `render.yaml`, or the Dockerfile needs to change —
they're account-agnostic. This is purely a re-plumbing exercise.

## Prerequisites

- [ ] Personal gitlab.com account exists and you can log into it.
- [ ] `~/.ssh/id_ed25519_gitlab_personal` (or equivalent) is added under
      **Personal account → Preferences → SSH Keys** on the *personal* account.
      The `gitlab-personal` alias already in `~/.ssh/config` will use this key.
- [ ] Decide the new project path (e.g. `gitlab.com:<personal-username>/wca-records-analyser`).

## Step 1 — Create the new project

On the personal account, create a new **empty** project (no README/license/gitignore
auto-created — you're pushing an existing history in).

## Step 2 — Push the full history across

```bash
cd /home/tim/apps/wca-records-analyser

# Add the new remote via the personal SSH alias (not a raw gitlab.com URL,
# so the right key is presented)
git remote add personal gitlab-personal:<personal-username>/wca-records-analyser.git

# Mirror everything: all branches, tags, and refs
git push --mirror personal
```

Verify on the new project's web UI that commit history, branches, and tags all
show up as expected before touching anything else.

## Step 3 — Repoint `origin`

Once verified:

```bash
git remote remove origin
git remote rename personal origin
git remote -v   # confirm origin now points at gitlab-personal:...
```

Leave the old corporate-linked project in place for now — don't archive or delete
it until Steps 4–6 are verified end-to-end.

## Step 4 — Recreate CI/CD variables on the new project

CI/CD variables are project-scoped and do **not** travel with git history.

On the new project: **Settings → CI/CD → Variables**, add:

- `RENDER_DEPLOY_HOOK_URL` — masked, same value as before *for now* (it'll be
  regenerated in Step 6, so this is just a placeholder to get the pipeline green
  on the test stage first).

## Step 5 — Re-register the GitLab Runner

GitLab runner registration tokens/auth tokens are tied to a specific project, so
the existing `wca-analyser` runner registration (on the WSL host, `wsl-docker` tag)
can't just be repointed — a new registration is needed.

1. On the new project: **Settings → CI/CD → Runners → New project runner**.
   - Tags: `wsl-docker` (must match what `.gitlab-ci.yml` expects).
   - Copy the generated authentication token.
2. On the WSL host, register a new runner entry in the *same* `config.toml`
   (`/home/tim/.gitlab-runner/config.toml`, owned by `tim`) alongside the other
   three unrelated runners already there (`local-laptop`, `hello-world-java-runner`,
   `wsl-local`) — don't touch those:
   ```bash
   gitlab-runner register \
     --url https://gitlab.com \
     --token <new-auth-token> \
     --executor shell \
     --tag-list wsl-docker
   ```
3. Restart the service: `sudo systemctl restart gitlab-runner`.
4. Once the new project's pipeline runs successfully (Step 7), remove the old
   runner entry for the corporate-linked project from `config.toml` and
   `gitlab-runner unregister` it.

## Step 6 — Repoint Render

Render's GitLab integration is an account-level OAuth connection, and it currently
sees the corporate-linked account's repos. Since the new repo lives under a
different GitLab identity, Render needs to be told about it explicitly — check
**Render Dashboard → Account Settings → Git Providers** for how your account's
GitLab connection is scoped before doing this, since the exact reconnect flow may
vary depending on whether Render allows multiple linked GitLab identities.

1. In Render, either:
   - Reconnect/add the personal GitLab account under Git Providers, **or**
   - Disconnect the corporate-linked GitLab connection and reconnect with the
     personal account (if only one GitLab identity can be linked at a time).
2. Create a **new Blueprint** (or edit the existing service's repo source, if
   Render allows changing it in place) pointing at the new project. Given the
   existing `render.yaml` already defines the service, using the Blueprint sync
   against the new repo is the cleanest path.
3. Set `autoDeploy: false` is already in `render.yaml` — no change needed there.
4. Once the service is connected to the new repo, go to
   **Service → Settings → Deploy Hook** and copy the (new) hook URL — this will
   differ from the old one even if the service name is unchanged.
5. Update the `RENDER_DEPLOY_HOOK_URL` CI/CD variable on the new GitLab project
   (Step 4) with this new value.

## Step 7 — Verify end-to-end

1. Push a trivial commit (or re-push `main`) to the new `origin`.
2. Confirm the pipeline runs on the new runner registration: `test` stage green,
   `deploy_render` stage fires (default branch only) and posts to the new hook.
3. Confirm Render shows a new deploy triggered by the hook, and the live site at
   `wca-records-analyser.onrender.com` (or whatever URL the new service gets)
   serves the latest change.
4. Check **Render → Settings → Auto-Deploy** still reads "No" — this is the
   single gate keeping a red pipeline off production.

## Step 8 — Clean up

Only after Step 7 is fully green:

- [x] Remove the old runner registration for the corporate-linked project
      (Step 5.4) — done 2026-08-24 (`gitlab-runner unregister`).
- [x] Decide the fate of the old GitLab project — **archived** 2026-08-24
      (Settings → General → Advanced → Archive project). Read-only, history
      preserved, reversible. Deletion can follow later at leisure.
- [ ] Update any bookmarks/links to the old project URL.

## Notes / things that do *not* need to change

- `.gitlab-ci.yml`, `render.yaml`, `Dockerfile` — all account-agnostic.
- Local commit author identity (`tim.shaw@ig.com`) — fine to leave as-is; GitLab
  account identity is separate from git commit author email. Change it only if
  you specifically want future commits attributed to a personal email.
- `~/.ssh/config`'s `gitlab.com` (corporate) entry — leave it alone; it's used
  by other projects.
