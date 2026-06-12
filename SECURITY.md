# Security Policy

## Reporting a vulnerability

Please report security issues privately via GitHub's
[private vulnerability reporting](https://github.com/drew0716/ragcli/security/advisories/new)
rather than opening a public issue. You should receive a response within a week.

## Deployment model and expectations

`rag serve` is designed to run as a **local, single-user tool** bound to
`127.0.0.1`. The API has no authentication layer. Binding to a non-loopback
address requires an explicit `--allow-remote` flag and is **not recommended**:
anyone who can reach the port can query your documents, manage collections,
and change settings.

If you need to expose ragcli over a network, put it behind a reverse proxy
that handles authentication (e.g. nginx with basic auth, Tailscale, or an
authenticated tunnel).

Filesystem access from the API (uploads, ingest paths, the folder browser) is
confined to the project directory the server was started in.
