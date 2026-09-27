# Security

Do not submit credentials, private URLs, personal data, or confidential website content in issues.

If you believe the checker has a security vulnerability, describe the affected behavior, reproduction steps, and impact without publishing secrets. Use GitHub's private vulnerability reporting feature when available; otherwise contact the repository maintainer through the GitHub profile.

The checker fetches only the robots.txt URL supplied by the user. It does not crawl discovered URLs, follow sitemap references, execute JavaScript, or require authentication. A response-size limit and request timeout reduce accidental resource consumption.
