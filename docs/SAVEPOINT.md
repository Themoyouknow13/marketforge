# Save Point — 2026-08-08

**Tag:** `savepoint-2026-08-08-phase1`  
**Commit:** `5d3108e`  
**Branch:** `main`  
**Remote:** https://github.com/Themoyouknow13/marketforge  
**Pages:** https://themoyouknow13.github.io/marketforge/

## Why this save point exists

Stable checkpoint before further work, created due to limited credit availability.

## Verified at save time

- `uv run pytest -q` → **29 passed**
- Working tree clean
- `main` pushed to `origin`
- Live desk brief published on GitHub Pages

## What is included

### Core pipeline
- Live SEC + market collectors
- Fail-closed claim/evidence validation
- Monte Carlo engine
- Daily brief + dual-thesis + sandbox agent runner

### Website (Phase 1 Terminal Research)
- Meaning layer (print / context / so what)
- Mover + filing + benchmark cards
- External source chips
- Collapsed evidence drawer
- Dual thesis + hub + sandbox trace pages

### Key paths
- `src/marketforge/` — package code
- `scripts/run_live_briefing.py`
- `scripts/run_phase1_desk.py`
- `scripts/run_dual_thesis.py`
- `scripts/run_sandbox_testrun.py`
- `docs/DESIGN_LOCK.md`
- `docs/DUAL_THESIS_WORKFLOW.md`
- `site/output/index.html` — current desk brief

### Live run artifact used for the desk
- `runs/live-20260808-170443/` (local; may be gitignored under `runs/`)

## Restore commands

```bash
cd C:\Users\zackb\marketforge

# Restore code to this exact save point
git fetch origin
git checkout savepoint-2026-08-08-phase1

# Or reset main hard to the save point (destructive to later local commits)
git checkout main
git reset --hard savepoint-2026-08-08-phase1

# Reinstall + verify
uv sync --extra dev
uv run pytest -q

# Rebuild desk from last live bundle (if runs/ still present)
uv run python scripts/run_phase1_desk.py runs/live-20260808-170443/run-bundle.json
```

## Republish site from this save point

```bash
git checkout savepoint-2026-08-08-phase1
git subtree split --prefix site -b gh-pages-tmp
git push origin gh-pages-tmp:gh-pages --force
git branch -D gh-pages-tmp
```

## Live URLs at save time

- Desk: https://themoyouknow13.github.io/marketforge/output/index.html
- Hub: https://themoyouknow13.github.io/marketforge/output/hub.html
- Dual thesis: https://themoyouknow13.github.io/marketforge/output/dual-thesis.html
- Sandbox trace: https://themoyouknow13.github.io/marketforge/output/sandbox-trace.html
