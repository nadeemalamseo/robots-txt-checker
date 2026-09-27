#!/usr/bin/env python3
"""Inspect robots.txt syntax and observable crawl-control signals."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

USER_AGENT = "robots-txt-checker/1.0"
DEFAULT_TIMEOUT = 15
DEFAULT_MAX_BYTES = 512 * 1024


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
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _resolve_source(value: str) -> tuple[str, str]:
    path = Path(value)
    if path.is_file():
        return str(path), "file"
    parsed = urlparse(value)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        if parsed.path in {"", "/"}:
            return value.rstrip("/") + "/robots.txt", "url"
        return value, "url"
    raise ValueError("Input must be an existing local file or an HTTP(S) URL/domain.")


def parse_robots_text(text: str, source: str = "robots.txt") -> RobotsResult:
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
            issues.append(Issue("warning", "invalid-line", "Line is not a recognised directive.", line_number))
            continue

        name, raw_value = line.split(":", 1)
        name = name.strip().lower()
        value = _clean_value(raw_value)

        if not name:
            issues.append(Issue("warning", "empty-directive", "Directive name is empty.", line_number))
            continue

        if name == "user-agent":
            ua = value.lower()
            if not ua:
                issues.append(Issue("error", "empty-user-agent", "User-agent directive has no value.", line_number))
                current = None
                continue
            if current is None or current.directives:
                current = Group()
                groups.append(current)
            if ua in current.user_agents:
                issues.append(Issue("warning", "duplicate-user-agent", f"User-agent '{ua}' is repeated in the same group.", line_number))
            current.user_agents.append(ua)
            continue

        if current is None:
            issues.append(Issue("warning", "directive-before-user-agent", f"'{name}' appears before a User-agent group.", line_number))
            current = Group(user_agents=["*"])
            groups.append(current)

        if name == "sitemap":
            if not _valid_http_url(value):
                issues.append(Issue("error", "invalid-sitemap-url", "Sitemap value must be an absolute HTTP(S) URL.", line_number))
            elif value in seen_sitemaps:
                issues.append(Issue("warning", "duplicate-sitemap", f"Duplicate sitemap URL: {value}", line_number))
            else:
                sitemaps.append(value)
                seen_sitemaps.add(value)
        elif name in {"crawl-delay", "host"}:
            issues.append(Issue("info", "non-standard-directive", f"'{name}' is not part of the core robots.txt standard; support varies.", line_number))
        elif name not in {"allow", "disallow"}:
            issues.append(Issue("info", "unknown-directive", f"Directive '{name}' is not one of the directives checked by this tool.", line_number))

        current.directives.append({"name": name, "value": value, "line": line_number})

    if not groups:
        issues.append(Issue("warning", "no-user-agent", "No User-agent group was found."))

    summary = {
        "groups": len(groups),
        "sitemaps": len(sitemaps),
        "errors": sum(i.severity == "error" for i in issues),
        "warnings": sum(i.severity == "warning" for i in issues),
        "info": sum(i.severity == "info" for i in issues),
    }
    return RobotsResult(source, "text", None, None, None, len(text.encode("utf-8")), groups, sitemaps, issues, summary)


def load_robots(source: str, timeout: int = DEFAULT_TIMEOUT, max_bytes: int = DEFAULT_MAX_BYTES) -> RobotsResult:
    resolved, source_type = _resolve_source(source)

    if source_type == "file":
        data = Path(resolved).read_bytes()
        if len(data) > max_bytes:
            raise ValueError(f"robots.txt exceeds the {max_bytes} byte safety limit.")
        result = parse_robots_text(data.decode("utf-8-sig", errors="replace"), resolved)
        result.source_type = "file"
        result.bytes_read = len(data)
        return result

    request = Request(resolved, headers={"User-Agent": USER_AGENT, "Accept": "text/plain, text/*;q=0.9, */*;q=0.1"})
    try:
        with urlopen(request, timeout=timeout) as response:
            chunks: list[bytes] = []
            total = 0
            while True:
                chunk = response.read(min(64 * 1024, max_bytes + 1 - total))
                if not chunk:
                    break
                chunks.append(chunk)
                total += len(chunk)
                if total > max_bytes:
                    raise ValueError(f"robots.txt exceeds the {max_bytes} byte safety limit.")
            data = b"".join(chunks)
            result = parse_robots_text(data.decode("utf-8-sig", errors="replace"), resolved)
            result.source_type = "url"
            result.fetch_status = response.status
            result.final_url = response.geturl()
            result.content_type = response.headers.get("Content-Type")
            result.bytes_read = len(data)
            if response.status >= 400:
                result.issues.append(Issue("error", "http-error", f"robots.txt returned HTTP {response.status}."))
            if result.content_type and "html" in result.content_type.lower():
                result.issues.append(Issue("warning", "html-content-type", "Response is labelled as HTML rather than plain text."))
            result.summary["errors"] = sum(i.severity == "error" for i in result.issues)
            result.summary["warnings"] = sum(i.severity == "warning" for i in result.issues)
            result.summary["info"] = sum(i.severity == "info" for i in result.issues)
            return result
    except HTTPError as exc:
        return RobotsResult(resolved, "url", exc.code, exc.geturl(), exc.headers.get("Content-Type") if exc.headers else None, 0, [], [], [Issue("error", "http-error", f"robots.txt returned HTTP {exc.code}.")], {"groups": 0, "sitemaps": 0, "errors": 1, "warnings": 0, "info": 0})
    except URLError as exc:
        raise RuntimeError(f"Could not fetch robots.txt: {exc.reason}") from exc


def result_to_dict(result: RobotsResult) -> dict:
    data = asdict(result)
    data["groups"] = [asdict(g) for g in result.groups]
    data["issues"] = [asdict(i) for i in result.issues]
    return data


def exit_code(result: RobotsResult) -> int:
    return 2 if result.summary["errors"] else 1 if result.summary["warnings"] else 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Inspect a robots.txt file for common syntax and crawl-control issues.")
    parser.add_argument("source", help="robots.txt URL, site origin, or local robots.txt file")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help=f"HTTP timeout in seconds (default: {DEFAULT_TIMEOUT})")
    parser.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES, help="maximum response size (default: 524288)")
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
        print(f"Groups: {len(result.groups)}")
        print(f"Sitemaps: {len(result.sitemaps)}")
        print(f"Issues: {len(result.issues)}")
        for issue in result.issues:
            location = f" (line {issue.line})" if issue.line else ""
            print(f"- [{issue.severity}] {issue.code}{location}: {issue.message}")
    return exit_code(result)


if __name__ == "__main__":
    raise SystemExit(main())
