# Security

## Scope

Interview Bank runs locally. The CLI reads and writes only the bank directory you point it at and never makes network requests (the optional `media-transcribe --download-model` downloads public model weights; it never uploads media).

The optional `web` command starts a personal helper, not an Internet service:

- it binds only to `127.0.0.1` and has no option for LAN or public binding;
- every API call needs the per-process token from the launch URL, and the Host and Origin headers must match the loopback origin (defence against DNS rebinding and cross-site requests);
- responses use a restrictive Content-Security-Policy, question and answer text is rendered as text, and only HTTP(S) source links are allowed.

Do not tunnel, proxy or host it publicly. Treat the launch URL like a password.

Source material (screenshots, transcripts, web pages) is untrusted data. The Skill instructs agents to ignore instructions embedded in it; a prompt-injection that changes a bank anyway is in scope.

## Reporting a vulnerability

Please report suspected vulnerabilities privately through [GitHub Security Advisories](https://github.com/EXIST-D/Interview-bank/security/advisories/new) rather than a public issue. If that form is unavailable, open an issue that only asks for a private contact, without details. Include the version, OS, steps to reproduce and impact. You should receive a reply within a week.
