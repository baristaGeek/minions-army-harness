# Security Report - 2026-07-28

Whitehat Code Reviewer findings for this WorkItem. Each section below includes severity (CVSS), the relevant CWE category, and remediation recommendations.

## Whitehat Code Reviewer - 6d2131e6-67ae-4fc4-91cf-d44b6866c2b2

**Outcome:** blocked

**Executive summary:** Security findings identified; changes requested

Security review completed against the repository source and manifests. I found 28 concrete issues.

1. /workspace/repo/docker-compose.yml:25 - CWE-269, CVSS 9.8 Critical: mounting `/var/run/docker.sock` into the API container gives any API compromise full control of the host Docker daemon, which is effectively host root. Fix: remove the socket mount and use a least-privilege launcher service or remote API with strong auth.

2. /workspace/repo/minions_army/infrastructure/api/routes.py:39 - CWE-306, CVSS 8.8 High: the Slack webhook endpoint accepts unauthenticated POSTs and immediately starts work. An attacker can spam the endpoint and trigger arbitrary minion runs. Fix: verify Slack signing secrets/HMAC and reject unsigned requests.

3. /workspace/repo/minions_army/infrastructure/api/routes.py:106 - CWE-306, CVSS 8.8 High: the Web API webhook endpoint has no authentication or authorization gate before it launches work. Any internet client can submit jobs. Fix: require an API key, mTLS, or another verified identity layer.

4. /workspace/repo/minions_army/infrastructure/api/schemas.py:56 - CWE-20, CVSS 5.3 Medium: `SlackWebhookRequest` allows arbitrary extra JSON fields and stores the full raw payload. A malicious sender can smuggle unbounded or misleading data into the database and downstream processing. Fix: reject unknown fields and store only a minimal allowlisted payload.

5. /workspace/repo/minions_army/infrastructure/api/schemas.py:121 - CWE-20, CVSS 5.3 Medium: `WebAPIWebhookRequest` also accepts arbitrary extra JSON fields and persists the full request body. An attacker can inflate storage or poison downstream consumers with unexpected keys. Fix: validate a strict schema and strip everything else.

6. /workspace/repo/minions_army/infrastructure/api/middleware.py:17 - CWE-532, CVSS 5.3 Medium: the request logger records the raw query string. Secrets embedded in URLs, signed links, or tokens passed as query parameters will be written to logs. Fix: redact query strings or log only allowlisted parameters.

7. /workspace/repo/minions_army/cli/main.py:29 - CWE-200, CVSS 6.5 Medium: `show-config` dumps the resolved configuration to stdout, including environment-expanded secrets. Anyone who can run the CLI or capture its output can read API keys. Fix: redact sensitive fields or require an explicit `--include-secrets` flag.

8. /workspace/repo/minions_army/core/config/loader.py:11 - CWE-15, CVSS 6.5 Medium: the loader automatically reads `.env` from the current working directory. A malicious or repository-controlled `.env` can override runtime settings such as DB URLs and tokens. Fix: disable implicit `.env` loading or restrict it to a trusted deployment path.

9. /workspace/repo/minions_army/infrastructure/agents/loader.py:10 - CWE-94, CVSS 8.8 High: the agent provider class is imported from a config-controlled Python path. If an attacker can alter config, they can force import and execution of arbitrary module code. Fix: use a fixed allowlist of provider classes and reject arbitrary import paths.

10. /workspace/repo/minions_army/infrastructure/pipeline_steps/loader.py:10 - CWE-94, CVSS 8.8 High: the pipeline steps provider is also loaded from a config-controlled import path, creating the same arbitrary code execution risk as above. Fix: replace dynamic imports with a fixed allowlist of known step providers.

11. /workspace/repo/minions_army/core/runtime/orchestrator_runtime.py:221 - CWE-377, CVSS 6.5 Medium: the GitHub askpass helper is written to a predictable `/tmp/git-askpass` path. A local attacker can pre-create a symlink or race the file to clobber another path. Fix: create a unique secure temp file with `mkstemp`/`NamedTemporaryFile` and strict permissions.

12. /workspace/repo/minions_army/core/runtime/orchestrator_runtime.py:223 - CWE-312, CVSS 6.5 Medium: the askpass script contains the GitHub token in plaintext on disk. Any local user or backup/forensic process that can read the temp directory can recover the credential. Fix: avoid writing secrets to disk; pass tokens via process environment or an in-memory credential helper.

13. /workspace/repo/minions_army/core/runtime/orchestrator_runtime.py:206 - CWE-918, CVSS 8.6 High: `resolve_repository_url` accepts arbitrary `http(s)` and `git@` URLs. A malicious repository name can force the service to clone internal Git servers or attacker-controlled endpoints, creating SSRF and credential exposure risk. Fix: allow only approved repository hosts and schemes.

14. /workspace/repo/minions_army/core/runtime/steps/checkout_branch.py:27 - CWE-88, CVSS 7.2 High: the branch name is passed straight into `git checkout -b`. A branch name starting with `-` or containing crafted ref syntax can be parsed as an option or otherwise abuse git ref handling. Fix: validate branch names against git-safe patterns and terminate option parsing with `--`.

15. /workspace/repo/minions_army/core/runtime/steps/push.py:27 - CWE-88, CVSS 7.2 High: the same unsanitized branch name is passed into `git push`. This can be used for option injection or pushing an unintended ref. Fix: validate the ref and insert `--` before user-controlled arguments.

16. /workspace/repo/minions_army/core/runtime/steps/verify_build.py:40 - CWE-78, CVSS 8.8 High: the verification command is executed through `bash -lc`. If the command string is attacker-controlled or poisoned through config, it becomes arbitrary shell execution. Fix: execute a fixed command array without a shell, or restrict the command to an allowlist.

17. /workspace/repo/minions_army/core/runtime/steps/review_merge_deploy.py:126 - CWE-807, CVSS 8.8 High: the review stage auto-merges and deploys based on an LLM verdict produced from untrusted diff content. Prompt injection in the PR can convince the reviewer to approve malicious changes and push them to main. Fix: require deterministic human approval or a non-LLM gate before merge/deploy.

18. /workspace/repo/user_data/agent_providers/codex.py:113 - CWE-250, CVSS 9.1 Critical: Codex is launched with `--sandbox danger-full-access`. A malicious prompt or repo content can read and modify the full container filesystem and any accessible network resources. Fix: run the agent in a locked-down sandbox with minimal filesystem and network access.

19. /workspace/repo/user_data/agent_providers/claude.py:36 - CWE-250, CVSS 8.8 High: Claude is launched with `--permission-mode bypassPermissions` and Bash tool access. Prompt injection or malicious repo content can turn the agent into an arbitrary shell runner. Fix: remove bypass mode and constrain tool use to the minimum required operations.

20. /workspace/repo/user_data/agent_providers/kimi.py:77 - CWE-312, CVSS 6.5 Medium: the provider writes the API key into `~/.kimi-code/config.toml` in plaintext. That leaks credentials to any local user, container snapshot, or backup that can read the home directory. Fix: keep the key in memory or use a protected secret store.

21. /workspace/repo/minions_army/core/runtime/steps/verify_build.py:58 - CWE-532, CVSS 6.5 Medium: on failure the build tail is posted to Slack. Stack traces, file paths, and possibly secrets from the build output can leak to an external collaboration channel. Fix: send only a short error summary or redact sensitive output before posting.

22. /workspace/repo/Dockerfile:12 - CWE-494, CVSS 8.8 High: the API image installs `flyctl` via `curl | sh` with no checksum or signature verification. A compromised upstream or MITM during build can execute arbitrary code inside the image build. Fix: verify a pinned checksum/signature or install from a trusted package repository.

23. /workspace/repo/Dockerfile.minion:36 - CWE-494, CVSS 8.8 High: the minion image also installs `flyctl` via `curl | sh` without integrity verification. That is the same build-time code execution risk in the worker image. Fix: pin and verify the installer or vendor the binary from a trusted source.

24. /workspace/repo/Dockerfile.minion:39 - CWE-829, CVSS 7.5 High: global npm installation of the agent CLIs pulls and executes remote package lifecycle scripts during image build, without a lockfile or provenance pin. A compromised registry package or dependency chain can execute arbitrary build code. Fix: pin the exact package artifacts and prefer vendored or checksum-verified binaries.

25. /workspace/repo/docker-compose.yml:8 - CWE-798, CVSS 6.5 Medium: the API compose file embeds a hardcoded Postgres password. Anyone with access to the repo or compose file already knows the database credential. Fix: source the password from a secret manager or environment secret.

26. /workspace/repo/docker-compose.yml:44 - CWE-284, CVSS 6.5 Medium: the same compose file publishes Postgres on host port 5432. Any local user or adjacent process can connect to the database with the known credentials. Fix: remove the host port mapping or bind it to localhost only.

27. /workspace/repo/sample-app/docker-compose.yml:17 - CWE-798, CVSS 6.5 Medium: the sample app uses the hardcoded `finance` database password. That credential is public once the repository is visible. Fix: move the password to an external secret.

28. /workspace/repo/sample-app/docker-compose.yml:21 - CWE-284, CVSS 6.5 Medium: the sample app publishes its Postgres service on host port 5433. That exposes the database to any local user or other process on the host. Fix: do not publish the database port unless it is strictly needed.

I did not confirm any dependency CVEs locally because this review was limited to static file reading and no network-backed advisory lookup was run.

---

