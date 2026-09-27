import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from robots_txt_checker import exit_code, load_robots, parse_robots_text, result_to_dict


class FakeHeaders(dict):
    pass


class FakeResponse:
    def __init__(self, body, status=200, url="https://example.com/robots.txt", content_type="text/plain"):
        self._body = body.encode()
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
    def test_parse_groups_and_directives(self):
        result = parse_robots_text(
            "# comment\nUser-agent: *\nDisallow: /private/\nAllow: /private/public/\nSitemap: https://example.com/sitemap.xml\n\nUser-agent: Googlebot\nDisallow:\n"
        )
        self.assertEqual(result.summary["groups"], 2)
        self.assertEqual(result.sitemaps, ["https://example.com/sitemap.xml"])
        self.assertEqual(result.groups[0].user_agents, ["*"])
        self.assertEqual(result.groups[0].directives[0]["name"], "disallow")
        self.assertEqual(result.summary["errors"], 0)

    def test_duplicate_user_agent_and_sitemap_are_reported(self):
        result = parse_robots_text("User-agent: *\nUser-agent: *\nSitemap: https://example.com/sitemap.xml\nSitemap: https://example.com/sitemap.xml\n")
        codes = {i.code for i in result.issues}
        self.assertIn("duplicate-user-agent", codes)
        self.assertIn("duplicate-sitemap", codes)
        self.assertEqual(exit_code(result), 1)

    def test_invalid_sitemap_is_error(self):
        result = parse_robots_text("User-agent: *\nSitemap: /sitemap.xml\n")
        self.assertIn("invalid-sitemap-url", {i.code for i in result.issues})
        self.assertEqual(exit_code(result), 2)

    def test_directive_before_user_agent_is_reported(self):
        result = parse_robots_text("Disallow: /private/\n")
        self.assertIn("directive-before-user-agent", {i.code for i in result.issues})

    def test_non_standard_and_unknown_directives_are_informational(self):
        result = parse_robots_text("User-agent: *\nCrawl-delay: 10\nHost: example.com\nFoo: bar\n")
        codes = {i.code for i in result.issues}
        self.assertIn("non-standard-directive", codes)
        self.assertIn("unknown-directive", codes)
        self.assertEqual(result.summary["errors"], 0)

    def test_blank_file_has_no_group_warning(self):
        result = parse_robots_text("")
        self.assertIn("no-user-agent", {i.code for i in result.issues})
        self.assertEqual(result.summary["warnings"], 1)

    def test_local_file_loading(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "robots.txt"
            path.write_text("User-agent: *\nDisallow: /admin/\n", encoding="utf-8")
            result = load_robots(str(path))
        self.assertEqual(result.source_type, "file")
        self.assertEqual(result.groups[0].directives[0]["value"], "/admin/")

    def test_url_loading_records_http_metadata(self):
        fake = FakeResponse("User-agent: *\nDisallow: /private/\n")
        with patch("robots_txt_checker.urlopen", return_value=fake):
            result = load_robots("https://example.com")
        self.assertEqual(result.fetch_status, 200)
        self.assertEqual(result.final_url, "https://example.com/robots.txt")
        self.assertEqual(result.content_type, "text/plain")

    def test_json_output_is_serializable(self):
        result = parse_robots_text("User-agent: *\nSitemap: https://example.com/sitemap.xml\n")
        self.assertIn("sitemap.xml", json.dumps(result_to_dict(result)))


if __name__ == "__main__":
    unittest.main()
