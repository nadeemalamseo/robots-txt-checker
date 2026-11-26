#!/usr/bin/env python3
"""Inspect robots.txt syntax and observable crawl-control signals.

This tool is a diagnostic parser, not a crawler simulator or access-control system.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

USER_AGENT = "robots-txt-checker/1.1"
DEFAULT_TIMEOUT = 15
# 500 KiB: Google's documented robots.txt processing limit and the RFC 9309
# minimum parsing-limit threshold.
DEFAULT_MAX_BYTES = 500 * 1024
READ_CHUNK_SIZE = 64 * 1024


@dataclass
class Issue:
    severity: str
    code: str
    message: str
    line: int | None = None


@dataclass
class Group:
    user_agents: list[str] = field(default_factory=list)
    directives: list[dict] = field(default_factory=list)


@dataclass
class RobotsResult:
    source: str
    source_type: str
    fetch_status: int | None
    final_url: str | None
    content_type: str | None
    bytes_read: int
    groups: list[Group]
    sitemaps: list[str]
    issues: list[Issue]
    summary: dict


def _clean_value(value: str) -> str:
    return value.split("#", 1)[0].strip()


def _valid_http_url(value: str) -> bool:
    if not value or any(char.isspace() for char in value):
        return False
    parsed = urlparse(value)
    try:
        valid_port = parsed.port is None or 1 <= parsed.port <= 65535
    except ValueError:
        return False
    return (
        parsed.scheme.lower() in {"http", "https"}
        and bool(parsed.hostname)
        and valid_port
    )


def _valid_user_agent_token(value: str) -> bool:
    if value == "*":
        return True
    return bool(value) and all(
        char.isascii() and (char.isalpha() or char in {"_", "-"})
        for char in value
    )


def _resolve_source(value: str) -> tuple[str, str]:
    path = Path(value)
    if path.is_file():
        return str(path), "file"
    parsed = urlparse(value)
    if parsed.scheme.lower() in {"http", "https"} and parsed.netloc:
        if parsed.path in {"", "/"}:
            return value.rstrip("/") + "/robots.txt", "url"
        return value, "url"
    raise ValueError("Input must be an existing local file or an HTTP(S) URL/domain.")


def _summary(issues: list[Issue], groups: list[Group], sitemaps: list[str]) -> dict:
    return {
        "groups": len(groups),
        "sitemaps": len(sitemaps),
        "errors": sum(issue.severity == "error" for issue in issues),
        "warnings": sum(issue.severity == "warning" for issue in issues),
        "info": sum(issue.severity == "info" for issue in issues),
    }


def parse_robots_text(text: str, source: str = "robots.txt") -> RobotsResult:
    # A UTF-8 BOM is permitted by some editors; it must not become part of
    # the first field name.
    text = text.lstrip("\ufeff")
    groups: list[Group] = []
    current: Group | None = None
    sitemaps: list[str] = []
    issues: list[Issue] = []
    seen_sitemaps: set[str] = set()

    for line_number, raw_line in enumerate(text.splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        if ":" not in line:
            issues.append(Issue("warning", "invalid-line", "Line is not a recognised field/value record.", line_number))
            continue

        name, raw_value = line.split(":", 1)
        name = name.strip().lower()
        value = _clean_value(raw_value)

        if not name:
            issues.append(Issue("warning", "empty-field", "Field name is empty.", line_number))
            continue

        # Sitemap is an extension record, not a robots group rule. RFC 9309
        # explicitly says it must not interfere with group parsing.
        if name == "sitemap":
            if not _valid_http_url(value):
                issues.append(Issue("error", "invalid-sitemap-url", "Sitemap value must be an absolute HTTP(S) URL.", line_number))
            elif value in seen_sitemaps:
                issues.append(Issue("warning", "duplicate-sitemap", f"Duplicate sitemap URL: {value}", line_number))
            else:
                sitemaps.append(value)
                seen_sitemaps.add(value)
            continue

        if name == "user-agent":
            ua = value.lower()
            if not ua:
                issues.append(Issue("error", "empty-user-agent", "User-agent field has no value.", line_number))
                current = None
                continue
            if not _valid_user_agent_token(ua):
                issues.append(Issue(
                    "warning",
                    "invalid-user-agent-token",
                    "User-agent product tokens should contain only ASCII letters, hyphens, or underscores; '*' is also allowed.",
                    line_number,
                ))
            if current is None or current.directives:
                current = Group()
                groups.append(current)
            if ua in current.user_agents:
                issues.append(Issue("warning", "duplicate-user-agent", f"User-agent '{ua}' is repeated in the same group.", line_number))
            current.user_agents.append(ua)
            continue

        if name in {"allow", "disallow"}:
            if current is None:
                # RFC 9309 recommends that crawlers ignore Allow/Disallow
                # rules that occur outside a user-agent group.
                issues.append(Issue(
                    "warning",
                    "rule-before-user-agent",
                    f"'{name}' appears outside a User-agent group and is not assigned to a group.",
                    line_number,
                ))
                continue
            if value and not value.startswith("/"):
                issues.append(Issue(
                    "warning",
                    "invalid-rule-path",
                    f"'{name}' path should be empty or start with '/'.",
                    line_number,
                ))
            if not value:
                issues.append(Issue(
                    "info",
                    "empty-rule-path",
                    f"'{name}' has an empty path; crawler interpretation may treat it as no restriction.",
                    line_number,
                ))
            current.directives.append({"name": name, "value": value, "line": line_number})
            continue

        if name in {"crawl-delay", "host"}:
            issues.append(Issue("info", "non-standard-directive", f"'{name}' is not part of the core RFC 9309 protocol; support varies by crawler.", line_number))
        else:
            issues.append(Issue("info", "unknown-directive", f"Field '{name}' is not one of the records interpreted by this tool.", line_number))

        # Preserve non-standard records only when they occur inside a group.
        # They do not create a synthetic wildcard group.
        if current is not None:
            current.directives.append({"name": name, "value": value, "line": line_number})
        else:
            issues.append(Issue(
                "warning",
                "record-before-user-agent",
                f"'{name}' appears outside a User-agent group; it is not assigned to a group.",
                line_number,
            ))

    if not groups:
        issues.append(Issue("warning", "no-user-agent", "No User-agent group was found."))

    return RobotsResult(
        source, "text", None, None, None, len(text.encode("utf-8")),
        groups, sitemaps, issues, _summary(issues, groups, sitemaps),
    )


def _http_error_result(source: str, exc: HTTPError) -> RobotsResult:
    status = exc.code
    # RFC 9309 distinguishes unavailable (4xx) from unreachable (5xx).
    # Report the observed class; do not pretend to emulate each crawler.
    if 400 <= status < 500:
        severity = "warning"
        code = "http-unavailable"
        message = f"robots.txt returned HTTP {status} (client-error/unavailable response class)."
    else:
        severity = "error"
        code = "http-unreachable"
        message = f"robots.txt returned HTTP {status} (server-error response class)."
    issue = Issue(severity, code, message)
    issues = [issue]
    return RobotsResult(
        source, "url", status, exc.geturl(),
        exc.headers.get("Content-Type") if exc.headers else None,
        0, [], [], issues, _summary(issues, [], []),
    )


def load_robots(
    source: str,
    timeout: float = DEFAULT_TIMEOUT,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> RobotsResult:
    if timeout <= 0:
        raise ValueError("Timeout must be greater than zero.")
    if max_bytes <= 0:
        raise ValueError("Maximum byte limit must be greater than zero.")

    resolved, source_type = _resolve_source(source)

    if source_type == "file":
        with Path(resolved).open("rb") as handle:
            data = handle.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise ValueError(f"robots.txt exceeds the {max_bytes}-byte safety limit.")
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError("robots.txt is not valid UTF-8 text.") from exc
        result = parse_robots_text(text, resolved)
        result.source_type = "file"
        result.bytes_read = len(data)
        return result

    request = Request(
        resolved,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/plain, text/*;q=0.9, */*;q=0.1",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            chunks: list[bytes] = []
            total = 0
            while True:
                chunk = response.read(min(READ_CHUNK_SIZE, max_bytes + 1 - total))
                if not chunk:
                    break
                chunks.append(chunk)
                total += len(chunk)
                if total > max_bytes:
                    raise ValueError(f"robots.txt exceeds the {max_bytes}-byte safety limit.")
            data = b"".join(chunks)
            try:
                text = data.decode("utf-8-sig")
            except UnicodeDecodeError as exc:
                raise ValueError("robots.txt response is not valid UTF-8 text.") from exc

            result = parse_robots_text(text, resolved)
            result.source_type = "url"
            result.fetch_status = response.status
            result.final_url = response.geturl()
            result.content_type = response.headers.get("Content-Type")
            result.bytes_read = len(data)

            media_type = (result.content_type or "").split(";", 1)[0].strip().lower()
            if media_type and media_type != "text/plain":
                result.issues.append(Issue(
                    "warning",
                    "unexpected-content-type",
                    f"Response Content-Type is '{media_type}', not 'text/plain'.",
                ))
            if result.final_url and result.final_url != resolved:
                result.issues.append(Issue(
                    "info",
                    "redirected",
                    f"robots.txt was retrieved after redirection to {result.final_url}.",
                ))
            result.summary = _summary(result.issues, result.groups, result.sitemaps)
            return result
    except HTTPError as exc:
        return _http_error_result(resolved, exc)
    except URLError as exc:
        raise RuntimeError(f"Could not fetch robots.txt: {exc.reason}") from exc


def result_to_dict(result: RobotsResult) -> dict:
    data = asdict(result)
    data["groups"] = [asdict(group) for group in result.groups]
    data["issues"] = [asdict(issue) for issue in result.issues]
    return data


def exit_code(result: RobotsResult) -> int:
    if result.summary["errors"]:
        return 2
    if result.summary["warnings"]:
        return 1
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Inspect robots.txt syntax and observable crawl-control signals."
    )
    parser.add_argument("source", help="robots.txt URL, site origin, or local robots.txt file")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT,
                        help=f"HTTP timeout in seconds (default: {DEFAULT_TIMEOUT})")
    parser.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES,
                        help=f"maximum response size in bytes (default: {DEFAULT_MAX_BYTES})")
    args = parser.parse_args(argv)

    if args.timeout <= 0 or args.max_bytes <= 0:
        parser.error("--timeout and --max-bytes must be positive")

    try:
        result = load_robots(args.source, args.timeout, args.max_bytes)
    except (ValueError, OSError, RuntimeError) as exc:
        if args.json:
            print(json.dumps({"source": args.source, "error": str(exc)}, indent=2))
        else:
            print(f"Error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result_to_dict(result), indent=2))
    else:
        print(f"Source: {result.source}")
        if result.fetch_status is not None:
            print(f"HTTP status: {result.fetch_status}")
        if result.final_url:
            print(f"Final URL: {result.final_url}")
        if result.content_type:
            print(f"Content-Type: {result.content_type}")
        print(f"Bytes read: {result.bytes_read}")
        print(f"Groups: {len(result.groups)}")
        print(f"Sitemaps: {len(result.sitemaps)}")
        print(
            "Issues: "
            f"{result.summary['errors']} errors, "
            f"{result.summary['warnings']} warnings, "
            f"{result.summary['info']} informational"
        )
        for issue in result.issues:
            location = f" (line {issue.line})" if issue.line else ""
            print(f"- [{issue.severity}] {issue.code}{location}: {issue.message}")
    return exit_code(result)


if __name__ == "__main__":
    raise SystemExit(main())
