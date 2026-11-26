# Methodology

This checker reports observable properties of a robots.txt resource. It is a diagnostic aid, not a complete crawler simulator and not an access-control mechanism.

## Standards basis

The parser is informed by the Robots Exclusion Protocol in [RFC 9309](https://www.rfc-editor.org/rfc/rfc9309.html) and Google's published [robots.txt interpretation](https://developers.google.com/crawling/docs/robots-txt/robots-txt-spec).

RFC 9309 defines user-agent groups and Allow/Disallow rules. It also says other records such as Sitemap must not interfere with group parsing. Google documents its own supported fields and a 500 KiB processing limit. Different crawlers may have implementation-specific behavior.

## Input and retrieval

- Accepts an existing local file, a site origin, or a direct HTTP(S) robots.txt URL.
- A site origin is resolved to its top-level `/robots.txt` path.
- Network requests use a finite timeout and a fixed User-Agent.
- Response bytes are read incrementally and stopped at the configured byte limit.
- The default limit is 500 KiB (512,000 bytes).
- UTF-8 decoding is required; an invalid byte sequence is reported rather than silently replaced.
- Redirect final URL, response status, and Content-Type are reported when available.
- The checker does not fetch Sitemap URLs or crawl any discovered paths.

## Parsing behavior

- Field names are case-insensitive.
- A UTF-8 BOM at the beginning of a file is ignored.
- Comments beginning with `#` and blank lines are ignored.
- User-agent groups are built from User-agent records and their following records.
- Consecutive User-agent records before rules are kept in the same group.
- A new User-agent after group rules begins a new group.
- Sitemap records are collected globally. They do not create a group or terminate/split a group. Other extension/unknown records are retained separately and do not change group boundaries.
- Allow and Disallow records outside a User-agent group are reported and not assigned to an artificial wildcard group.
- Non-empty Allow/Disallow paths are expected to begin with `/`; empty values are retained as empty rules and reported informationally.
- User-agent product tokens are checked against the RFC 9309 token character set; the wildcard `*` is accepted.
- Crawl-delay and Host are reported as non-standard/implementation-dependent records.
- Unknown records are informational findings, not proof that a crawler will ignore them.

## HTTP response interpretation

RFC 9309 distinguishes unavailable 4xx responses from unreachable 5xx responses. The checker reports those observed classes separately. This is not a claim that all crawlers make identical decisions. Google documents its own handling, including its treatment of 4xx responses and redirects.

An HTTP response is evidence about the tested request at that time and from that network location. CDN, WAF, geographic routing, rate limits, and server state may change the result.

## Exit codes

- `0`: no errors or warnings
- `1`: warnings found
- `2`: an error was found or input could not be processed

Exit codes are designed for command-line and CI use. They are not indexing or ranking signals.

## Limitations

The tool does not evaluate whether a specific URL is allowed by the full ruleset, merge matching groups for a particular crawler, implement every crawler-specific extension, determine indexing status, predict rankings, authenticate to private sites, execute JavaScript, or guarantee that a crawler follows any particular rule.

robots.txt is not a security boundary. Use authentication and authorization controls to protect private resources.
