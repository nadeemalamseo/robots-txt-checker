# robots-txt-checker

A practical robots.txt checking tool for reviewing syntax, directives, user-agent rules, sitemap references, and common crawl-control mistakes.

## What it does

This small Python command-line utility inspects a robots.txt resource from a local file, site origin, or direct HTTP(S) URL.

It reports observable conditions including:

- HTTP response status and final URL
- response content type
- user-agent groups
- Allow and Disallow directives
- sitemap references
- duplicate user-agent and sitemap entries
- directives before a user-agent group
- invalid sitemap URLs
- common non-standard directives such as Crawl-delay and Host
- unknown directives as informational findings

JSON output is available for scripts and CI workflows.

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

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | No errors or warnings |
| 1 | Warnings were found |
| 2 | An error occurred or an error finding was detected |

These codes describe checker findings, not search-engine indexing or ranking outcomes.

## Important limitations

The checker reports observable syntax and HTTP conditions. It does not reproduce every crawler's implementation.

It does not:

- determine search-engine indexing status;
- predict rankings or guarantee search visibility;
- guarantee that a crawler will obey a rule in every context;
- validate crawler-specific semantics for every search engine;
- recursively fetch sitemap files;
- execute JavaScript;
- authenticate to private sites.

Crawl-delay and Host are reported as non-standard or implementation-dependent directives rather than treated as universally supported rules.

## Methodology

See [the methodology](docs/methodology.md) for the checking model, safety limits, interpretation guidance, and exit-code definitions.

## Development

Run:

```bash
python -m unittest discover -s tests -v
```

GitHub Actions runs the unit tests across Python 3.10, 3.11, and 3.12.

## Responsible use

Use the checker only against sites and files you are authorized to inspect. Avoid excessive automated requests and respect the target site's operational constraints.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Security

See [SECURITY.md](SECURITY.md).

## Project links

- [Project landing page](https://nadeemalamseo.github.io/robots-txt-checker/)
- [v0.1.0 release](https://github.com/nadeemalamseo/robots-txt-checker/releases/tag/v0.1.0)
- [Download v0.1.0 ZIP](https://github.com/nadeemalamseo/robots-txt-checker/archive/refs/tags/v0.1.0.zip)

## License

This repository is licensed under the MIT License. See [LICENSE](LICENSE).

