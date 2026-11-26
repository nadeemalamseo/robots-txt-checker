# Security

## Scope

This project is a local command-line diagnostic. It fetches only the robots.txt URL explicitly supplied by the operator. It does not recursively crawl a website, fetch Sitemap records, or request URLs listed in Allow/Disallow rules.

Network retrieval uses a finite timeout and a configurable response-size cap. The default cap is 500 KiB.

## Safe use

- Do not use robots.txt as an access-control mechanism.
- Do not submit credentials, private URLs, personal data, or confidential website content in public issues.
- Only inspect sites and files you are authorized to access.
- Do not increase request limits or automate repeated requests in a way that burdens a site.
- Treat fetched robots.txt content as untrusted input.

## Reporting a vulnerability

If you believe you found a security vulnerability, provide the affected version, reproduction steps, expected behavior, observed behavior, and impact. Do not publish secrets or sensitive target data in a public issue. Use GitHub private vulnerability reporting when available; otherwise contact the maintainer through the GitHub profile.
