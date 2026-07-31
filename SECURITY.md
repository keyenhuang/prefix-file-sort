# Security Policy

## Supported Versions

The latest release of `prefix-file-sort` receives security updates.

| Version | Supported          |
| ------- | ------------------ |
| 1.1.x   | :white_check_mark: |
| < 1.1   | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability, **please do NOT open a public issue**.

Instead, report it privately using one of the following methods:

- **GitHub Security Advisories (recommended)**: Open the repository
  **Security** tab and click **"Report a vulnerability"**. This keeps the
  report private and lets us coordinate a fix.
- **Email**: Contact the maintainer via the email listed on their GitHub profile.

Please include the following so we can reproduce and assess the issue quickly:

- A description of the vulnerability and its impact
- Steps to reproduce (minimal example)
- Affected version / commit SHA
- Any relevant logs (redact personal/sensitive paths)

You will receive an acknowledgement within **72 hours** and a fix or mitigation
plan within **14 days**. Coordinated/disclosed-after-fix is greatly appreciated.

## Security Considerations for Users

`prefix-file-sort` **moves and renames files** on your local filesystem.
Because file operations are inherently destructive, keep the following in mind:

- Always use **Preview Groups** before **Execute Move** to review exactly what
  will happen. Preview performs no filesystem changes.
- The application **never deletes files**. `Overwrite` is an explicit, opt-in
  conflict policy that must be selected manually; the default is `Skip`.
- **Undo Last Move** restores the most recent batch. Operations are tracked in
  `move_log.json` inside the source folder.
- If something looks unexpected, inspect `move_log.json` before running another
  operation.
