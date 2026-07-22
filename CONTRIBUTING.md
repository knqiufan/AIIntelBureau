# Contributing

Use a branch and pull request; do not push directly to protected `main`. Run `python -m pytest` in `backend`, then `npm ci`, `npm test`, and `npm run build` in `web`. Do not commit `.env`, logs, database files, browser recordings, or real user data.

Changes that affect data retention, access controls, dependencies, deployment, or runbooks must update their tests and documentation. The CI jobs are required checks; obtain code-owner review for security, runtime, or deployment changes.
