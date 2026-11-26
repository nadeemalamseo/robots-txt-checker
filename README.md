# Robots.txt Checker

A focused Python command-line diagnostic for reviewing robots.txt syntax, user-agent groups, Allow/Disallow rules, sitemap records, HTTP responses, and common crawl-control mistakes.

## What it checks

- HTTP response status, final URL, and content type
- UTF-8 input and a bounded response size
- User-agent groups and product-token format
- Allow and Disallow rule-path structure
- Sitemap records as global records, independent of user-agent groups
- Duplicate user-agent and sitemap entries
- Rules or records appearing outside a user-agent group
- Non-standard records such as Crawl-delay and Host
- Unknown records as informational findings
- JSON output and meaningful CLI exit codes

## Requirements

- Python 3.10+
- No third-party Python packages are required.

## Usage

```bash
python robots_txt_checker.py https://example.com
python robots_txt_checker.py https://example.com/robots.txt
python robots_txt_checker.py ./robots.txt
python robots_txt_checker.py https://example.com --json
python robots_txt_checker.py https://example.com --timeout 10
python robots_txt_checker.py https://example.com --max-bytes 262144
```

The default response limit is 500 KiB (512,000 bytes), matching Google's documented robots.txt processing limit and meeting the minimum parsing-limit threshold in RFC 9309. A smaller custom limit is available for stricter local resource controls; it should not be confused with the default standards-aligned inspection limit.

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | No errors or warnings |
| 1 | Warnings were found |
| 2 | An error was found or input could not be processed |

These codes describe the checker's findings. They do not predict how every crawler will behave.

## Important interpretation notes

- robots.txt is a crawler instruction protocol, **not access control**. Do not use it to protect confidential resources.
- Sitemap records are global extension records. They do not start, end, or split a user-agent group.
- Rules outside a user-agent group are reported and not assigned to an invented wildcard group.
- RFC 9309 distinguishes HTTP 4xx "unavailable" responses from 5xx "unreachable" responses. This checker reports the observed response class; it does not emulate every search engine's policy.
- Crawl-delay and Host are not part of the core RFC 9309 protocol. Support varies by crawler.
- A syntactically valid robots.txt file does not guarantee indexing, ranking, crawling, or search visibility.

## What it does not do

The checker does not evaluate a requested URL against all robots rules, simulate a specific crawler's complete matching behavior, recursively fetch sitemap files, crawl the website, execute JavaScript, authenticate to private sites, or determine indexing status.

## Methodology

See [docs/methodology.md](docs/methodology.md) for the standards basis, parsing behavior, response handling, safety limits, and limitations.

## Development

Run the unit tests:

```bash
python -m unittest discover -s tests -v
```

GitHub Actions runs the test suite on Python 3.10, 3.11, and 3.12.

## Responsible use

Only inspect sites and local files you are authorized to access. The checker requests only the supplied robots.txt resource; it does not follow Sitemap records or crawl listed URLs. Use a reasonable timeout and response-size limit.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Security

See [SECURITY.md](SECURITY.md).

## Project links

- [Project landing page](https://nadeemalamseo.github.io/robots-txt-checker/)
- [Latest releases](https://github.com/nadeemalamseo/robots-txt-checker/releases)
- [Source repository](https://github.com/nadeemalamseo/robots-txt-checker)

## License

This repository is licensed under the MIT License. See [LICENSE](LICENSE).
