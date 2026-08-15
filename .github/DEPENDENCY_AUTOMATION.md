# Dependabot automation

Dependabot groups minor and patch updates by ecosystem.  After the existing
`CI quality gates` workflow finishes, `dependabot-automation.yml` performs the
following in a trusted default-branch workflow:

1. It accepts only open, non-draft Dependabot pull requests targeting `main`
   from this repository and rejects any change outside the dependency manifests,
   generated lock files, and GitHub Actions workflows.
2. For Python and npm updates, it recreates the generated lock file without npm
   lifecycle scripts, and pushes a lock-only commit when needed.
3. It waits for the CI run for that exact commit to succeed, then queues only
   minor and patch updates for squash merge. Major updates and PRs that report
   maintainer changes always remain for manual review.

## One-time repository setup

Create a dedicated fine-grained personal access token restricted to this
repository. Store it as the repository Actions secret
`DEPENDENCY_AUTOMATION_TOKEN`. Grant only:

- **Contents:** Read and write (to commit generated lock files to Dependabot
  branches)
- **Pull requests:** Read and write (to queue the squash merge)
- **Workflows:** Read and write (required when a Dependabot update changes a
  workflow file)

Do not use a personal all-repository token. The standard `GITHUB_TOKEN` cannot
be used for this job: commits it creates do not start the follow-up CI run that
must validate regenerated locks.

Repository auto-merge must also be enabled. The workflow uses a full SHA pin for
the metadata action and intentionally runs from `workflow_run`, rather than a
PR-triggered write workflow, so a Dependabot PR never receives write credentials
or repository secrets.

## Operations

If the token is added after a Dependabot PR already exists, rerun its `CI quality
gates` workflow once. If the workflow rejects a path, a major version, or a
maintainer-change update, review and merge it manually. The lock-file check in
CI remains the final protection against merging stale generated dependencies.
