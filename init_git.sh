#!/usr/bin/env bash
# Creates a Git history with one commit per development milestone, using YOUR git identity.
# Usage: bash init_git.sh && git remote add origin https://github.com/<you>/<repo>.git && git push -u origin main
set -e
git init -b main >/dev/null
c() { for f in "$@"; do [ -e "$f" ] && git add "$f"; done; git diff --cached --quiet || { git commit -qm "$MSG" && echo "✓ $MSG"; }; }
MSG="chore: project setup, architecture docs, env config";        c .gitignore README.md docs backend/.env.example backend/requirements.txt backend/app/__init__.py backend/app/core/config.py backend/app/core/logging.py
MSG="feat(db): SQLAlchemy models, Alembic migrations, DB session";  c backend/app/models.py backend/app/core/db.py backend/alembic backend/alembic.ini
MSG="feat(auth): password hashing, JWT, auth dependencies";        c backend/app/core/security.py backend/app/api/__init__.py backend/app/api/deps.py
MSG="feat(ai): OpenAI-compatible LLM + embedding client";          c backend/app/core/llm.py backend/app/core/__init__.py
MSG="feat(services): domain services";                              c backend/app/services backend/app/schemas.py backend/data backend/app/cli.py sample_data
MSG="feat(api): REST endpoints + FastAPI app";                       c backend/app/api backend/app/main.py
MSG="test: unit and API integration tests";                          c backend/tests
MSG="feat(frontend): React + TypeScript + Tailwind SPA";            c frontend
MSG="ci: Docker, docker-compose and GitHub Actions";                 c backend/Dockerfile docker-compose.yml .github init_git.sh
MSG="chore: remaining files";                                        git add -A && (git commit -qm "$MSG" && echo "✓ $MSG" || true)
git log --oneline
