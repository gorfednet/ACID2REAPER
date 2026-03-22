# Security policy

## Credentials and repository hygiene

**Never commit** SSH private keys, API tokens, or passwords to this repository. Keep keys in `~/.ssh/` (mode `600` on private keys) or your OS secret store. If a secret was ever exposed in a remote, **rotate** it (new key, revoke token) even after the repository is recreated.

## Supported versions

We aim to support the **latest release** on the `main` branch. This project is currently in its **first public beta**; pre-release builds may receive fixes at maintainers’ discretion.

## Reporting a vulnerability

Please **do not** open a public issue for security vulnerabilities.

1. Open a **private security advisory** via GitHub (**Security → Advisories → Report a vulnerability**) on [ACID2Reaper](https://github.com/gorfednet/ACID2REAPER), or
2. Contact the repository owners with a clear description, steps to reproduce, and impact.

We will acknowledge receipt as soon as practical and coordinate disclosure.

## Scope

ACID2Reaper is a **local** tool: it reads project files and writes `.rpp` output. It does not expose a network service by default. Reports about malicious `.acd` / `.acd-zip` files are in scope (e.g., zip bombs, path traversal); please include a **safe** proof of concept or redacted sample when possible.
