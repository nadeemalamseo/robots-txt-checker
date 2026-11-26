import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from robots_txt_checker import (
    DEFAULT_MAX_BYTES,
    exit_code,
    load_robots,
    parse_robots_text,
    result_to_dict,
)


class FakeHeaders(dict):
    pass


class FakeResponse:
    def __init__(self, body, status=200, url="https://example.com/robots.txt",
                 content_type="text/plain"):
        self._body = body if isinstance(body, bytes) else body.encode("utf-8")
        self.status = status
        self._url = url
        self.headers = FakeHeaders({"Content-Type": content_type})

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size=-1):
        if size < 0:
            size = len(self._body)
        chunk, self._body = self._body[:size], self._body[size:]
        return chunk

    def geturl(self):
        return self._url


class RobotsCheckerTests(unittest.TestCase):
    def test_default_limit_is_google_500_kib(self):
        self.assertEqual(DEFAULT_MAX_BYTES, 500 * 1024)

    def test_parse_groups_and_directives(self):
        result = parse_robots_text(
            "User-agent: *\nDisallow: /private/\nAllow: /private/public/\n"
            "Sitemap: https://example.com/sitemap.xml\n\n"
            "User-agent: Googlebot\nDisallow:\n"
        )
        self.assertEqual(result.summary["groups"], 2)
        self.assertEqual(result.sitemaps, ["https://example.com/sitemap.xml"])
        self.assertEqual(result.groups[0].user_agents, ["*"])
        self.assertEqual(result.groups[0].directives[0]["name"], "disallow")
        self.assertEqual(result.summary["errors"], 0)

    def test_sitemap_before_user_agent_is_global_and_does_not_create_group(self):
        result = parse_robots_text(
            "Sitemap: https://example.com/sitemap.xml\n"
            "User-agent: *\nDisallow: /private/\n"
        )
        self.assertEqual(len(result.groups), 1)
        self.assertEqual(result.sitemaps, ["https://example.com/sitemap.xml"])
        self.assertNotIn("directive-before-user-agent", {i.code for i in result.issues})

    def test_sitemap_between_groups_does_not_terminate_or_split_group(self):
        result = parse_robots_text(
            "User-agent: ExampleBot\n"
            "Sitemap: https://example.com/sitemap.xml\n"
            "User-agent: OtherBot\n"
            "Disallow: /private/\n"
        )
        self.assertEqual(len(result.groups), 1)
        self.assertEqual(result.groups[0].user_agents, ["examplebot", "otherbot"])

    def test_nonstandard_records_do_not_split_user_agent_group(self):
        result = parse_robots_text(
            "User-agent: FirstBot\\n"
            "Crawl-delay: 10\\n"
            "User-agent: SecondBot\\n"
            "Disallow: /private/\\n"
        )
        self.assertEqual(len(result.groups), 1)
        self.assertEqual(result.groups[0].user_agents, ["firstbot", "secondbot"])
        self.assertEqual(result.groups[0].other_records[0]["name"], "crawl-delay")

    def test_multiple_sitemaps_are_global_and_duplicates_reported(self):
        result = parse_robots_text(
            "Sitemap: https://example.com/a.xml\n"
            "Sitemap: https://example.com/b.xml\n"
            "Sitemap: https://example.com/a.xml\n"
        )
        self.assertEqual(result.sitemaps, [
            "https://example.com/a.xml", "https://example.com/b.xml"
        ])
        self.assertIn("duplicate-sitemap", {i.code for i in result.issues})
        self.assertEqual(len(result.groups), 0)

    def test_directives_before_user_agent_are_not_promoted_to_wildcard(self):
        result = parse_robots_text("Disallow: /private/\n")
        self.assertEqual(result.groups, [])
        self.assertIn("rule-before-user-agent", {i.code for i in result.issues})
        self.assertNotIn("*", [ua for group in result.groups for ua in group.user_agents])

    def test_duplicate_user_agent_and_sitemap_are_reported(self):
        result = parse_robots_text(
            "User-agent: *\nUser-agent: *\n"
            "Sitemap: https://example.com/sitemap.xml\n"
            "Sitemap: https://example.com/sitemap.xml\n"
        )
        codes = {issue.code for issue in result.issues}
        self.assertIn("duplicate-user-agent", codes)
        self.assertIn("duplicate-sitemap", codes)
        self.assertEqual(exit_code(result), 1)

    def test_invalid_sitemap_urls_are_errors(self):
        for url in ("/sitemap.xml", "//example.com/sitemap.xml",
                    "ftp://example.com/sitemap.xml", "https://example.com:99999/sitemap.xml"):
            with self.subTest(url=url):
                result = parse_robots_text(f"User-agent: *\nSitemap: {url}\n")
                self.assertIn("invalid-sitemap-url", {issue.code for issue in result.issues})
                self.assertEqual(exit_code(result), 2)

    def test_sitemap_url_scheme_is_case_insensitive(self):
        result = parse_robots_text("Sitemap: HTTPS://example.com/sitemap.xml\n")
        self.assertEqual(result.sitemaps, ["HTTPS://example.com/sitemap.xml"])

    def test_invalid_rule_path_is_reported(self):
        result = parse_robots_text("User-agent: *\nDisallow: private\n")
        self.assertIn("invalid-rule-path", {issue.code for issue in result.issues})

    def test_empty_allow_disallow_is_not_a_syntax_error(self):
        result = parse_robots_text("User-agent: *\nDisallow:\nAllow:\n")
        self.assertEqual(result.summary["errors"], 0)
        self.assertEqual(result.summary["info"], 2)

    def test_invalid_user_agent_token_is_reported(self):
        result = parse_robots_text("User-agent: Google Bot\nDisallow: /private/\n")
        self.assertIn("invalid-user-agent-token", {issue.code for issue in result.issues})

    def test_non_standard_and_unknown_directives_are_informational(self):
        result = parse_robots_text(
            "User-agent: *\nCrawl-delay: 10\nHost: example.com\nFoo: bar\n"
        )
        codes = {issue.code for issue in result.issues}
        self.assertIn("non-standard-directive", codes)
        self.assertIn("unknown-directive", codes)
        self.assertEqual(result.summary["errors"], 0)

    def test_unknown_record_before_user_agent_does_not_create_group(self):
        result = parse_robots_text("Custom-Field: value\n")
        self.assertEqual(result.groups, [])
        self.assertIn("record-before-user-agent", {issue.code for issue in result.issues})

    def test_blank_file_has_no_group_warning(self):
        result = parse_robots_text("")
        self.assertIn("no-user-agent", {issue.code for issue in result.issues})
        self.assertEqual(result.summary["warnings"], 1)

    def test_utf8_bom_is_ignored(self):
        result = parse_robots_text("\ufeffUser-agent: *\nDisallow: /private/\n")
        self.assertEqual(result.groups[0].user_agents, ["*"])

    def test_local_file_loading(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "robots.txt"
            path.write_text("User-agent: *\nDisallow: /admin/\n", encoding="utf-8")
            result = load_robots(str(path))
        self.assertEqual(result.source_type, "file")
        self.assertEqual(result.groups[0].directives[0]["value"], "/admin/")

    def test_local_file_size_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "robots.txt"
            path.write_bytes(b"x" * 20)
            with self.assertRaisesRegex(ValueError, "safety limit"):
                load_robots(str(path), max_bytes=10)

    def test_invalid_utf8_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "robots.txt"
            path.write_bytes(b"User-agent: *\n\xff")
            with self.assertRaisesRegex(ValueError, "valid UTF-8"):
                load_robots(str(path))

    def test_url_loading_records_http_metadata(self):
        fake = FakeResponse("User-agent: *\nDisallow: /private/\n")
        with patch("robots_txt_checker.urlopen", return_value=fake):
            result = load_robots("https://example.com")
        self.assertEqual(result.fetch_status, 200)
        self.assertEqual(result.final_url, "https://example.com/robots.txt")
        self.assertEqual(result.content_type, "text/plain")

    def test_non_text_plain_content_type_is_reported(self):
        fake = FakeResponse("User-agent: *\n", content_type="text/html; charset=utf-8")
        with patch("robots_txt_checker.urlopen", return_value=fake):
            result = load_robots("https://example.com")
        self.assertIn("unexpected-content-type", {issue.code for issue in result.issues})

    def test_redirect_is_reported_as_information(self):
        fake = FakeResponse(
            "User-agent: *\n",
            url="https://cdn.example.com/robots.txt",
        )
        with patch("robots_txt_checker.urlopen", return_value=fake):
            result = load_robots("https://example.com")
        self.assertIn("redirected", {issue.code for issue in result.issues})

    def test_http_404_is_unavailable_warning(self):
        exc = HTTPError(
            "https://example.com/robots.txt", 404, "Not Found",
            {"Content-Type": "text/plain"}, None,
        )
        with patch("robots_txt_checker.urlopen", side_effect=exc):
            result = load_robots("https://example.com")
        self.assertEqual(result.fetch_status, 404)
        self.assertIn("http-unavailable", {issue.code for issue in result.issues})
        self.assertEqual(exit_code(result), 1)

    def test_http_503_is_unreachable_error(self):
        exc = HTTPError(
            "https://example.com/robots.txt", 503, "Unavailable",
            {"Content-Type": "text/plain"}, None,
        )
        with patch("robots_txt_checker.urlopen", side_effect=exc):
            result = load_robots("https://example.com")
        self.assertIn("http-unreachable", {issue.code for issue in result.issues})
        self.assertEqual(exit_code(result), 2)

    def test_json_output_is_serializable(self):
        result = parse_robots_text(
            "User-agent: *\nSitemap: https://example.com/sitemap.xml\n"
        )
        self.assertIn("sitemap.xml", json.dumps(result_to_dict(result)))


if __name__ == "__main__":
    unittest.main()
