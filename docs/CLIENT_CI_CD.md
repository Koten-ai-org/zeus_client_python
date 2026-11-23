# Zeus client CI/CD

Instructions for an agent adding the `zeus_client_python` release flow to another Zeus client repository. Go exists today. Node.js, Java, and .NET will use the same flow later.

The reference implementation is this repository: `.github/workflows/ci.yml`, `.github/workflows/release.yml`, `scripts/check_version_clocks.py`, `Makefile`, `.pre-commit-config.yaml`, and `.github/CODEOWNERS`. Read those files. Translate the tools. Do not paste Python commands into another language.

## Outcome

1. **Commit** on a `feat/` or `fix/` branch. A hook rejects unlinted or unformatted files. A format command fixes them. `make ci` is the full local gate the author runs before pushing.
2. **Pull request** into `main`. GitHub Actions is the merge gate: lint, typecheck, tests with a coverage floor, a package build check, and version clocks. A person approves. Paths that hold domain rules, security, and the public API also need a code owner.
3. **Merge** only when those checks are green and the branch is up to date with `main`. The merge does not publish.
4. **Release** is a second pull request that moves every version clock to the same `X.Y.Z`. After that pull request is on `main` and CI is green, a person pushes an annotated tag. The tag workflow checks the tag, re-runs the offline suite, builds, opens a GitHub Release from the changelog, and publishes to that language's registry.

## Before editing

Work in the target client repository.

- Read the Makefile, workflows, version constant, `CHANGELOG.md`, and `sdk_bootstrap.pins.json`. Extend a working `make ci`. Do not replace it with a shorter suite.
- Resolve the GitHub repository with `gh repo view --json nameWithOwner`. A 307 from `koten-ai/<repo>` means the canonical name is `Koten-ai-org/<repo>`. Call the API on the URL in that redirect.
- List collaborators with `gh api repos/<owner>/<repo>/collaborators`. `CODEOWNERS` may name only those logins. Include every account with write or admin so the pull request author is not the only code owner. An author cannot approve their own pull request.
- Find the domain, security, and public API directories by reading the tree. Use those paths in `CODEOWNERS`. Do not copy `src/zeus_client/domain` into a repository that lays packages out differently.
- Read the supported language versions from the manifest (`requires-python`, the `go` line, `engines`, the Java toolchain, `TargetFramework`). Test those versions. Do not add a runtime the manifest does not support.
- Keep an existing coverage floor. If the repository has none, run the suite once, set the floor a few points under that baseline, and write the number in a workflow comment.
- If `sdk_bootstrap.pins.json` has no `zeus_1_0_client.available_tag`, add that field set to the current `vX.Y.Z`. Do not invent other pin fields.

## Tools by language

Use a tool the repository already depends on when one exists. Otherwise use the row below.

| Gate | Python (reference) | Go | Node.js | Java | .NET |
| --- | --- | --- | --- | --- | --- |
| Lint and format check | `ruff check`, `ruff format --check` | `gofmt -l` must be empty. Add `golangci-lint` only when the repo already runs it. | The formatter already chosen (`biome check` or `eslint` plus `prettier --check`). Do not add both. | The formatter already wired (`spotlessCheck` or equivalent). | `dotnet format --verify-no-changes` |
| Typecheck | `mypy` | `go vet` | `tsc --noEmit` when the package is TypeScript. Skip as its own job when the compiler is `tsc` during build and there is no separate typecheck. | Compiler in `mvn -B -DskipTests compile` or `gradle compileJava` | Compiler inside `dotnet build` |
| Tests | `pytest -m "not integration"` plus coverage, floor in CI | `go test -race -cover ./...`. Keep `-race` when the Makefile already requires it. | The existing test runner with coverage | JUnit via Maven or Gradle, with a coverage report | `dotnet test` with coverage |
| Package check | `python -m build` and `twine check` | `go build ./...` | `npm pack --dry-run` | `mvn -B -DskipTests package` or `gradle assemble` | `dotnet pack` without pushing |
| Advisory audit | `pip-audit`, `continue-on-error: true` | `govulncheck` | `npm audit` | The dependency checker already on the build, otherwise OWASP dependency-check | `dotnet list package --vulnerable` |
| Version constant | `pyproject.toml` `version` and `src/zeus_client/_version.py` | `version.go` `const Version`. `go.mod` has no package version. | `package.json` `version` and the exported version constant | Build-file version (`pom.xml` or `build.gradle`) and a public version constant when one exists | `Version` in the project file or `Directory.Build.props`, plus the public version constant when one exists |
| Publish | PyPI Trusted Publishing (`id-token: write`) | Annotated tag and GitHub Release. The module proxy indexes a public tag. No upload token. | npm Trusted Publishing with provenance | Maven Central trusted publishing for the coordinates already in the build. Stop and ask if there is no `groupId`. | NuGet Trusted Publishing |

The audit job stays `continue-on-error: true`. It is not a required status check.

Lab integration tests stay out of the merge gate. A manual workflow may exist and stay off until real tests and secrets exist.

## Version clocks

One version `X.Y.Z` must appear in every clock. The tag is `vX.Y.Z`.

1. Manifest version, from the table above.
2. Importable version constant, when that language has one.
3. A `CHANGELOG.md` heading `## X.Y.Z` at the start of a line, optionally followed by a space and a date. `## Unreleased` does not count. `## 1.2.30` does not satisfy `1.2.3`.
4. `sdk_bootstrap.pins.json` → `zeus_1_0_client.available_tag` equals `vX.Y.Z`.

Add `scripts/check_version_clocks` in the repository language, or a small Python script if the runner is `ubuntu-latest`. Flags:

- `--root` repository root, default the working directory.
- `--tag vX.Y.Z` optional. The tag must start with `v` and the rest must equal the manifest version.

Exit 0 and print `version clocks match X.Y.Z` when every clock agrees. Exit 1 and print one line per mismatch on stderr. A missing file is a mismatch. Do not treat a missing changelog section as success.

Tests, using temp directories plus one test against the real tree:

- Matching clocks pass.
- `--tag` of the same version passes. A different tag fails.
- A wrong constant, a missing changelog heading, and a wrong `available_tag` each fail in one run.
- The repository as checked out passes.

CI calls the script with no tag from the build job. The release workflow calls it with `--tag`.

## Local commands

Keep `make ci` aligned with the CI workflow. Expected targets:

| Target | Behavior |
| --- | --- |
| `install` | Install the dev toolchain the CI job installs. |
| `hooks` | Install the commit hook. |
| `lint` | Check only. Non-zero when the tree is dirty. |
| `format` | Write the formatting fixes. |
| `typecheck` | The typecheck command. Omit the target when the language has no separate typechecker. |
| `test` | Offline tests, integration excluded. |
| `cov` | Same tests with the coverage floor. |
| `build` | Produce the package and run the package check. Do not publish. |
| `audit` | The advisory scanner. `make ci` does not call it. |
| `ci` | `lint`, `typecheck`, `cov`, and `build`. |

The commit hook runs the same check commands as `lint`, not `format`. Document `make hooks` and `make ci` in the README.

Go already has `make ci` as `fmt vet race test`, and `fmt` runs `gofmt -w`. Leave race and vet in `make ci`. Point `lint` at `gofmt -l` so CI fails without rewriting files. Keep `format` as the writer.

## CI workflow

File: `.github/workflows/ci.yml`.

- Workflow name `CI`.
- `permissions: contents: read`.
- Triggers: `push` to `main`, `pull_request` to `main`, `workflow_dispatch`.
- Concurrency group `ci-${{ github.workflow }}-${{ github.ref }}` with `cancel-in-progress: true`.
- Jobs, each with a stable `name` that is the status-check context. Prefer `lint`, `typecheck`, `test`, and `build`. A test matrix must use a name that expands to a concrete string, such as `test (go1.25)`. The ruleset lists every expansion, not the template.
- The build job runs the version-clock script before packaging.
- `ubuntu-latest`. Cache the language toolchain the way that language's setup action supports.
- When the conformance suite needs the private `zeus_client_design` checkout, use `secrets.KOTEN_CI_PAT` and `continue-on-error: true` on that checkout. Skip the suite when the clone is absent. A missing secret must not fail the merge gate.

If you split an existing single job, the old job name stops being a check. Update the ruleset to the new names. Go's current check is `make ci (fmt · vet · race · test)`.

## Release workflow

File: `.github/workflows/release.yml`. Keep it separate from `ci.yml` so the CI token stays read-only.

- `permissions`: `contents: write`, `id-token: write`.
- Triggers: `push` of tags `v*`, and `workflow_dispatch` with a required string input `tag` (an existing tag, for example `v1.2.3`).
- Concurrency group `release-${{ github.ref }}` with `cancel-in-progress: false`.
- Checkout `fetch-depth: 0`. On `workflow_dispatch`, checkout `inputs.tag`. Otherwise checkout `github.ref`.
- Resolve the tag: `inputs.tag` on dispatch, otherwise `GITHUB_REF_NAME`. It must start with `v`. Run the clock script with `--tag`.
- Then require an annotated tag whose commit is on `main`:

```bash
set -euo pipefail
TAG="${TAG}"
git fetch origin "refs/tags/${TAG}:refs/tags/${TAG}"
git fetch origin main:refs/remotes/origin/main
TYPE=$(git cat-file -t "refs/tags/${TAG}")
test "$TYPE" = "tag"
git merge-base --is-ancestor "refs/tags/${TAG}^{commit}" refs/remotes/origin/main
```

`git cat-file -t` prints `tag` for an annotated tag and `commit` for a lightweight tag. A lightweight tag fails the job.

- Run the offline suite, build, and the package check.
- Take the changelog body from the `## X.Y.Z` section through the next `## ` heading. Publish a GitHub Release on that tag with that body and the built artifacts.
- Publish to the registry in the table. Trusted publishing uses the workflow's OIDC token. Do not store a registry password. Go stops after the GitHub Release.
- The workflow does not create or push the tag.

README release text:

```bash
git tag -a vX.Y.Z -m "vX.Y.Z" && git push origin vX.Y.Z
```

State that the pull request updates every clock, and that the tag is pushed only after CI is green on `main`.

## Ruleset

Apply this after the workflow file is on `main` and one run has reported the check names. Read the names from `gh api repos/<owner>/<repo>/commits/<sha>/check-runs`. The context is the job `name` when that name is unique. Copy it exactly, including a middle dot (`·`, U+00B7) when the job name has one.

Create one active ruleset named `main` on `refs/heads/main`:

- Pull request required, one approving review, code-owner review required.
- Stale-review dismissal off, last-push approval off, thread resolution off, extra approval for unattributed changes off.
- Required status checks: every concrete CI job name except the audit job. Strict policy on, so the branch must be up to date with `main`.
- Bypass actor: repository role admin, `actor_id` 5, `actor_type` `RepositoryRole`, `bypass_mode` `pull_request`. Admins can merge a pull request past the rules. A direct push to `main` stays blocked.

`POST /repos/<owner>/<repo>/rulesets`. On HTTP 307, `POST` the same body to `repositories/<id>/rulesets` from the response URL. On HTTP 404, the token is not an admin. Stop and say so.

If the created ruleset sets `require_extra_approval_for_unattributed_changes` to true, `PUT` it back with false.

`CODEOWNERS` is read from the default branch. Code-owner review has no owners until that file is on `main`.

## Done when

- `make ci` passes locally.
- The clock script passes on the tree and fails on a bad tag.
- `ci.yml` runs on pull requests and on pushes to `main`, and its job names match the ruleset.
- `release.yml` rejects a lightweight tag and a tag that is not on `main`.
- The README shows `make hooks`, `make ci`, and the annotated-tag command.
- The ruleset is active, or you reported that the token cannot administer the repository.
- You did not publish on merge, did not create a tag from CI, did not make audit a required check, and did not put integration tests on the merge gate.
