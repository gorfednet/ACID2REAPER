# Security policy

## Credentials and repository hygiene

**Never commit** SSH private keys, API tokens or passwords to this repository. Keep keys in `~/.ssh/` (mode `600` on private keys) or your OS secret store. If a secret was ever exposed in a remote, **rotate** it (issue a new key, revoke the token), even after the repository is recreated.

## Supported versions

The **latest release** on the `main` branch is the supported version. ACID2Reaper is in its **first public beta**, and the maintainers fix pre-release builds at their discretion.

## Reporting a vulnerability

**Don't** open a public issue for a security vulnerability.

1. Open a **private security advisory** via GitHub (**Security → Advisories → Report a vulnerability**) on [ACID2Reaper](https://github.com/gorfednet/ACID2REAPER), or
2. Contact the repository owners with a description, the steps to reproduce and the impact.

We'll acknowledge your report as soon as practical and coordinate disclosure with you.

## Scope

ACID2Reaper is a **local** tool. It reads project files and writes `.rpp` output, and it doesn't expose a network service by default. Reports about malicious `.acd` or `.acd-zip` files are in scope (zip bombs and path traversal, for example); include a **safe** proof of concept or a redacted sample when you can.
