import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from scrapers.amazon import AmazonScraper
from scrapers.kabum import KabumScraper
from scrapers.mercadolivre import MercadoLivreScraper
from scrapers.pichau import PichauScraper
from scrapers.terabyte import TerabyteScraper
from scrapers.utils import check_pichau_bundle_32gb_options


class FakeLocator:
    def __init__(self):
        self.count = AsyncMock(return_value=0)


class FakePage:
    def __init__(self, blocked=False, status_code=200, body=""):
        self.url = "https://www.mercadolivre.com.br/"
        self.blocked = blocked
        self.status_code = status_code
        self.add_init_script = AsyncMock()
        self.wait_for_timeout = AsyncMock()
        self.content = AsyncMock(return_value=body)
        self.locator = Mock(return_value=FakeLocator())

    async def goto(self, url, **kwargs):
        if self.blocked:
            self.url = "https://account.mercadolivre.com/account-verification"
        return SimpleNamespace(status=self.status_code)


def playwright_manager(page):
    browser = MagicMock()
    browser.close = AsyncMock()
    context = MagicMock()
    context.new_page = AsyncMock(return_value=page)
    browser.new_context = AsyncMock(return_value=context)
    playwright = MagicMock()
    playwright.chromium.launch = AsyncMock(return_value=browser)
    manager = MagicMock()
    manager.__aenter__ = AsyncMock(return_value=playwright)
    manager.__aexit__ = AsyncMock(return_value=False)
    return manager


class ScraperHealthTests(unittest.IsolatedAsyncioTestCase):
    def test_kabum_http_failure_is_reported(self):
        scraper = KabumScraper()
        scraper.session = Mock()
        scraper.session.get.return_value = Mock(status_code=503, text="")

        items = scraper.get_ssds()

        self.assertEqual(items, [])
        self.assertEqual(scraper.health["SSD"]["status"], "error")
        self.assertEqual(scraper.health["SSD"]["attempted"], 8)
        self.assertIn("HTTP 503", scraper.health["SSD"]["detail"])

    def test_terabyte_http_failure_is_reported(self):
        scraper = TerabyteScraper()
        scraper.session = Mock()
        scraper.session.get.return_value = Mock(status_code=403, text="")

        items = scraper.get_ram_16gb_ddr4()

        self.assertEqual(items, [])
        self.assertEqual(scraper.health["RAM"]["status"], "blocked")
        self.assertEqual(scraper.health["RAM"]["attempted"], 6)
        self.assertIn("HTTP 403", scraper.health["RAM"]["detail"])

    def test_terabyte_missing_search_structure_is_an_error(self):
        scraper = TerabyteScraper()
        scraper.session = Mock()
        scraper.session.get.return_value = Mock(
            status_code=200, text="<html><body>Página inesperada</body></html>"
        )

        items = scraper.get_ssds()

        self.assertEqual(items, [])
        self.assertEqual(scraper.health["SSD"]["status"], "error")
        self.assertEqual(scraper.health["SSD"]["attempted"], 8)
        self.assertIn("Estrutura", scraper.health["SSD"]["detail"])

    async def test_amazon_http_failure_is_reported(self):
        scraper = AmazonScraper()
        page = FakePage(status_code=503)
        manager = playwright_manager(page)

        with patch("scrapers.amazon.async_playwright", return_value=manager):
            items = await scraper.get_ram_16gb_ddr4()

        self.assertEqual(items, [])
        self.assertEqual(scraper.health["RAM"]["status"], "error")
        self.assertEqual(scraper.health["RAM"]["attempted"], 6)
        self.assertIn("HTTP 503", scraper.health["RAM"]["detail"])

    async def test_amazon_captcha_is_reported_as_blocked(self):
        scraper = AmazonScraper()
        page = FakePage(body="<title>Amazon CAPTCHA</title>Digite os caracteres que você vê na imagem.")
        manager = playwright_manager(page)

        with patch("scrapers.amazon.async_playwright", return_value=manager):
            items = await scraper.get_ssds()

        self.assertEqual(items, [])
        self.assertEqual(scraper.health["SSD"]["status"], "blocked")
        self.assertIn("CAPTCHA", scraper.health["SSD"]["detail"])

    async def test_amazon_missing_search_structure_is_an_error(self):
        scraper = AmazonScraper()
        page = FakePage(body="<html><body>Página inesperada</body></html>")
        manager = playwright_manager(page)

        with patch("scrapers.amazon.async_playwright", return_value=manager):
            items = await scraper.get_ssds()

        self.assertEqual(items, [])
        self.assertEqual(scraper.health["SSD"]["status"], "error")
        self.assertIn("Estrutura", scraper.health["SSD"]["detail"])

    async def test_amazon_legitimate_empty_search_is_empty(self):
        scraper = AmazonScraper()
        page = FakePage(body="Não encontramos resultados para a sua busca.")
        manager = playwright_manager(page)

        with patch("scrapers.amazon.async_playwright", return_value=manager):
            items = await scraper.get_ram_16gb_ddr4()

        self.assertEqual(items, [])
        self.assertEqual(scraper.health["RAM"]["status"], "empty")

    async def test_pichau_http_failure_is_reported(self):
        scraper = PichauScraper()
        session = Mock()
        session.get.return_value = Mock(status_code=503, text="")
        scraper._get_session = Mock(return_value=session)

        items = await scraper.get_ssds()

        self.assertEqual(items, [])
        self.assertEqual(scraper.health["SSD"]["status"], "error")
        self.assertEqual(scraper.health["SSD"]["attempted"], 7)
        self.assertIn("HTTP 503", scraper.health["SSD"]["detail"])

    async def test_pichau_missing_search_structure_is_an_error(self):
        scraper = PichauScraper()
        session = Mock()
        session.get.return_value = Mock(
            status_code=200, text="<html><body>Página inesperada</body></html>"
        )
        scraper._get_session = Mock(return_value=session)

        items = await scraper.get_ssds()

        self.assertEqual(items, [])
        self.assertEqual(scraper.health["SSD"]["status"], "error")
        self.assertEqual(scraper.health["SSD"]["attempted"], 7)
        self.assertIn("Estrutura", scraper.health["SSD"]["detail"])

    async def test_mercadolivre_account_verification_is_blocked(self):
        scraper = MercadoLivreScraper()
        manager = playwright_manager(FakePage(blocked=True))

        with patch("scrapers.mercadolivre.async_playwright", return_value=manager):
            items = await scraper.get_ssds()

        self.assertEqual(items, [])
        self.assertEqual(scraper.health["SSD"]["status"], "blocked")
        self.assertEqual(scraper.health["SSD"]["attempted"], 5)
        self.assertIn("account-verification", scraper.health["SSD"]["detail"])

    async def test_mercadolivre_http_failure_is_reported(self):
        for method_name, category, attempted in (
            ("get_ssds", "SSD", 5),
            ("get_ram_16gb_ddr4", "RAM", 2),
        ):
            with self.subTest(category=category):
                scraper = MercadoLivreScraper()
                manager = playwright_manager(FakePage(status_code=503))

                with patch("scrapers.mercadolivre.async_playwright", return_value=manager):
                    items = await getattr(scraper, method_name)()

                self.assertEqual(items, [])
                self.assertEqual(scraper.health[category]["status"], "error")
                self.assertEqual(scraper.health[category]["attempted"], attempted)
                self.assertIn("HTTP 503", scraper.health[category]["detail"])

    async def test_mercadolivre_missing_search_structure_is_an_error(self):
        scraper = MercadoLivreScraper()
        page = FakePage(body="<html><body>Página inesperada</body></html>")
        manager = playwright_manager(page)

        with patch("scrapers.mercadolivre.async_playwright", return_value=manager):
            items = await scraper.get_ssds()

        self.assertEqual(items, [])
        self.assertEqual(scraper.health["SSD"]["status"], "error")
        self.assertEqual(scraper.health["SSD"]["attempted"], 5)
        self.assertIn("Estrutura", scraper.health["SSD"]["detail"])


class PichauBundleDiagnosticTests(unittest.TestCase):
    def test_invalid_json_is_a_parse_error(self):
        session = Mock()
        session.get.return_value = Mock(status_code=200, text="PCM-TEST123")
        session.post.return_value = Mock(status_code=200, text="1:{invalid-json}")

        with patch("curl_cffi.requests.Session", return_value=session):
            result = check_pichau_bundle_32gb_options(
                "https://www.pichau.com.br/pc-gamer-teste", 3500.0
            )

        self.assertEqual(result["status"], "parse_error")
        self.assertIn("JSON", result["detail"])
        self.assertFalse(result["site_customization_available"])

    def test_unrecognized_success_body_is_a_parse_error(self):
        session = Mock()
        session.get.return_value = Mock(status_code=200, text="PCM-TEST123")
        session.post.return_value = Mock(status_code=200, text='0:{"unexpected":true}')

        with patch("curl_cffi.requests.Session", return_value=session):
            result = check_pichau_bundle_32gb_options(
                "https://www.pichau.com.br/pc-gamer-teste", 3500.0
            )

        self.assertEqual(result["status"], "parse_error")
        self.assertIn("reconhecid", result["detail"].lower())
        self.assertFalse(result["site_customization_available"])

    def test_server_action_409_is_explicit(self):
        session = Mock()
        session.get.return_value = Mock(status_code=200, text="PCM-TEST123")
        session.post.return_value = Mock(status_code=409, text="Server Action unavailable.")

        with patch("curl_cffi.requests.Session", return_value=session):
            result = check_pichau_bundle_32gb_options(
                "https://www.pichau.com.br/pc-gamer-teste", 3500.0
            )

        self.assertEqual(result["status"], "action_unavailable")
        self.assertIn("indisponível", result["site_status_label"].lower())
        self.assertFalse(result["site_customization_available"])


if __name__ == "__main__":
    unittest.main()
