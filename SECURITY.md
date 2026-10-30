# Security

## Scope

Interview Bank runs locally by default. The CLI reads and writes only the bank directory you point it at. These are
the only paths that reach the network, all opt-in:

- `verify-citations` (link checks, on request) and `page-text` (saving the text of pages being cited);
- `media-transcribe --download-model`, which downloads public model weights and never uploads media;
- the Web reader started with `--ai-config`: screenshot import sends the screenshots you upload to the model
  provider you configured, the mock interview sends the answers you type, the question and its reference answer (and a
  pasted job description with the bank's question list) to it, and web research (an optional `search` section) sends questions to the search provider
  and fetches the result pages; `ai-check` sends one tiny request to each configured service.

Page fetches go only to public addresses: loopback, private, link-local and carrier-grade NAT ranges (including cloud
metadata services) are refused, also when a public page redirects there. API keys are read from a file that is not
world-readable or from an environment variable, never from the command line, and never appear in output or errors.

The `web` command binds only to `127.0.0.1` and has no option for LAN or public binding:

- every API call needs the per-process token from the launch URL, and the Host and Origin headers must match the
  loopback origin (defence against DNS rebinding and cross-site requests);
- responses use a restrictive Content-Security-Policy, question and answer text is rendered as text, and only
  HTTP(S) source links are allowed.

Do not tunnel the port. Hosting for a phone is supported only behind your own HTTPS reverse proxy with the
reader's login (`--token-file`, `--public-origin`, `--login-file`; see `tools/deploy/`): the proxy adds the fixed
token, sessions are signed HttpOnly cookies, failed logins lock out, each account sees only its own bank, and guest
reading (`--public-bank`) is a GET-only allowlist of the collections you chose to publish. Treat a local launch URL
like a password.

Source material (screenshots, transcripts, web pages) is untrusted data. The Skill and the Web import instruct models
to ignore instructions embedded in it; a prompt injection that changes a bank anyway is in scope.

## Reporting a vulnerability

Please report suspected vulnerabilities privately through [GitHub Security Advisories](https://github.com/EXIST-D/Interview-bank/security/advisories/new) rather than a public issue. If that form is unavailable, open an issue that only asks for a private contact, without details. Include the version, OS, steps to reproduce and impact. You should receive a reply within a week.
