# Robots.txt Checker

A practical command-line checker for reviewing robots.txt syntax, user-agent groups, crawl directives, sitemap references, and common crawl-control mistakes.

## Quick start

```bash
python robots_txt_checker.py https://example.com
python robots_txt_checker.py https://example.com/robots.txt
python robots_txt_checker.py ./robots.txt
```

For machine-readable output:

```bash
python robots_txt_checker.py https://example.com --json
```

## What the results mean

The checker reports observable syntax and HTTP conditions. A finding does not by itself establish how a particular search engine will crawl, index, or rank a URL.

## Related resource

For broader guidance on technical SEO implementation and site-level diagnostics, see [MarketLatch SEO Services](https://marketlatch.com/seo-services/).
