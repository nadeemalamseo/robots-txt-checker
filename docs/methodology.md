# Methodology

This checker focuses on observable properties of a robots.txt resource. It is a review aid, not a complete implementation of every crawler's robots.txt processing.

## Checks

- local-file or HTTP(S) input
- HTTP status and final URL for fetched resources
- response content type
- UTF-8 text parsing
- response-size safety limit
- user-agent groups
- Allow and Disallow directives
- absolute HTTP(S) sitemap references
- duplicate user-agent entries in a group
- duplicate sitemap references
- missing user-agent groups
- directives before a user-agent group
- common non-standard directives such as Crawl-delay and Host
- unknown directives as informational findings

## Interpretation

The tool reports syntax and observable response conditions. It does not determine:

- whether a URL is indexed by a search engine;
- whether a crawler will fetch a URL in every situation;
- which crawler-specific implementation will be used;
- whether a robots rule improves rankings;
- whether a site is eligible for a search feature.

An HTTP error is an observable response condition, not a prediction about search-engine behavior.

## Safety limits

Network mode sends requests only to the supplied robots.txt URL, uses a finite timeout, and limits the response body to 512 KiB by default. It does not recursively crawl discovered URLs or sitemap files.

Local mode reads only the file explicitly supplied to the command.

## Exit codes

- 0: no errors or warnings
- 1: warnings found
- 2: an error was found or input could not be processed

Exit codes are for scripts and CI checks. They are not statements about indexing or ranking.
