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


class FakeElement:
    def __init__(self, text="", href=None, count=1):
        self.text_value = text
        self.href = href
        self.count = AsyncMock(return_value=count)

    @property
    def first(self):
        return self

    async def inner_text(self):
        return self.text_value

    async def get_attribute(self, name):
        return self.href if name == "href" else None


class FakeCards:
    def __init__(self, cards):
        self.cards = cards
        self.count = AsyncMock(return_value=len(cards))

    def nth(self, index):
        return self.cards[index]


class FakeProductCard:
    def __init__(self, elements):
        self.elements = elements

    def locator(self, selector):
        return self.elements.get(selector, FakeLocator())


class FakeProductPage(FakePage):
    def __init__(self, cards_selector, cards):
        super().__init__(body="<html><body>Resultados da busca</body></html>")
        self.cards_selector = cards_selector
        self.cards = cards
        self.locator = self._locator

    def _locator(self, selector):
        if selector == self.cards_selector:
            return FakeCards(self.cards)
        return FakeLocator()


class Rtx3060ScraperTests(unittest.IsolatedAsyncioTestCase):
    def test_kabum_rtx_3060_12gb_http_failure_is_reported(self):
        scraper = KabumScraper()
        scraper.session = Mock()
        scraper.session.get.return_value = Mock(status_code=429, text="")
        session = MagicMock()
        session.__enter__.return_value = session
        session.get.return_value = Mock(status_code=429, text="")

        with patch("scrapers.kabum.requests.Session", return_value=session):
            items = scraper.get_rtx_3060_12gb()

        self.assertEqual(items, [])
        self.assertEqual(scraper.health["GPU"]["status"], "blocked")
        self.assertEqual(scraper.health["GPU"]["attempted"], 2)

    def test_kabum_rtx_3060_12gb_uses_standard_http_session(self):
        scraper = KabumScraper()
        shared_session = Mock()
        shared_session.get.return_value = Mock(status_code=503, text="")
        scraper.session = shared_session
        session = MagicMock()
        session.__enter__.return_value = session
        session.get.return_value = Mock(status_code=503, text="")

        with patch("scrapers.kabum.requests.Session", return_value=session) as session_factory:
            scraper.get_rtx_3060_12gb()

        session_factory.assert_called_once_with()
        shared_session.get.assert_not_called()
        self.assertNotIn("headers", session.get.call_args.kwargs)

    def test_kabum_rtx_3060_12gb_results_are_filtered(self):
        valid = {
            "code": "GPU3060",
            "name": "Placa de Vídeo NVIDIA GeForce RTX 3060 12GB GDDR6",
            "price": 2199.99,
            "warranty": "12 meses",
        }
        scraper = KabumScraper()
        scraper._fetch_next_data = Mock(
            side_effect=[
                [
                    valid,
                    {"code": "GPU8", "name": "Placa de Vídeo RTX 3060 8GB GDDR6", "price": 1499.0},
                    {"code": "PC", "name": "PC Gamer RTX 3060 12GB 16GB DDR4", "price": 2999.0},
                    {"code": "OTHER", "name": "Placa de Vídeo RTX 4070 12GB GDDR6X", "price": 3999.0},
                    valid,
                ],
                [valid],
            ]
        )

        with patch("scrapers.kabum.requests.Session", return_value=MagicMock()):
            items = scraper.get_rtx_3060_12gb()

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], valid["name"])
        self.assertEqual(items[0]["category"], "GPU")
        self.assertEqual(items[0]["vram"], "12GB")
        self.assertEqual(scraper.health["GPU"]["status"], "ok")
        self.assertEqual(scraper.health["GPU"]["attempted"], 2)

    def test_kabum_changed_next_data_schema_is_reported(self):
        scraper = KabumScraper()
        scraper.session = Mock()
        scraper.session.get.return_value = Mock(
            status_code=200,
            text='<script id="__NEXT_DATA__" type="application/json">{"props":{"pageProps":{"data":"{}"}}}</script>',
        )
        session = MagicMock()
        session.__enter__.return_value = session
        session.get.return_value = Mock(
            status_code=200,
            text='<script id="__NEXT_DATA__" type="application/json">{"props":{"pageProps":{"data":"{}"}}}</script>',
        )

        with patch("scrapers.kabum.requests.Session", return_value=session):
            items = scraper.get_rtx_3060_12gb()

        self.assertEqual(items, [])
        self.assertEqual(scraper.health["GPU"]["status"], "error")
        self.assertIn("catalogServer/data", scraper.health["GPU"]["detail"])

    def test_terabyte_rtx_3060_12gb_http_failure_is_reported(self):
        scraper = TerabyteScraper()
        scraper.session = Mock()
        scraper.session.get.return_value = Mock(status_code=403, text="")
        session = MagicMock()
        session.__enter__.return_value = session
        session.get.return_value = Mock(status_code=403, text="")

        with patch("scrapers.terabyte.requests.Session", return_value=session):
            items = scraper.get_rtx_3060_12gb()

        self.assertEqual(items, [])
        self.assertEqual(scraper.health["GPU"]["status"], "blocked")
        self.assertEqual(scraper.health["GPU"]["attempted"], 2)

    def test_terabyte_rtx_3060_12gb_uses_standard_http_session(self):
        scraper = TerabyteScraper()
        shared_session = Mock()
        shared_session.get.return_value = Mock(status_code=503, text="")
        scraper.session = shared_session
        session = MagicMock()
        session.__enter__.return_value = session
        session.get.return_value = Mock(status_code=503, text="")

        with patch("scrapers.terabyte.requests.Session", return_value=session) as session_factory:
            scraper.get_rtx_3060_12gb()

        session_factory.assert_called_once_with()
        shared_session.get.assert_not_called()
        self.assertNotIn("headers", session.get.call_args.kwargs)

    def test_terabyte_rtx_3060_12gb_results_are_filtered(self):
        valid = {
            "title": "Placa de Vídeo NVIDIA GeForce RTX 3060 12GB GDDR6",
            "price": 2199.99,
            "link": "https://www.terabyteshop.com.br/produto/gpu-3060-12gb",
            "store": "TerabyteShop",
        }
        scraper = TerabyteScraper()
        scraper.session = Mock()
        scraper.session.get.return_value = Mock(status_code=200, text="<html>Resultados</html>")
        session = MagicMock()
        session.__enter__.return_value = session
        session.get.return_value = Mock(status_code=200, text="<html>Resultados</html>")
        scraper._parse_products_from_soup = Mock(return_value=[valid])

        with patch("scrapers.terabyte.requests.Session", return_value=session):
            items = scraper.get_rtx_3060_12gb()

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["category"], "GPU")
        self.assertEqual(items[0]["vram"], "12GB")
        self.assertEqual(scraper.health["GPU"]["status"], "ok")
        self.assertEqual(scraper.health["GPU"]["attempted"], 2)

    def test_terabyte_rtx_3060_12gb_ignores_old_price_fallback(self):
        html = """
        <div class="product-item">
            <a class="product-item__name" title="Placa de Vídeo RTX 3060 12GB GDDR6" href="/produto/gpu-3060-12gb"></a>
            <span>De R$ 2.499,99</span>
        </div>
        """
        scraper = TerabyteScraper()
        scraper.session = Mock()
        scraper.session.get.return_value = Mock(status_code=200, text=html)
        session = MagicMock()
        session.__enter__.return_value = session
        session.get.return_value = Mock(status_code=200, text=html)

        with patch("scrapers.terabyte.requests.Session", return_value=session):
            items = scraper.get_rtx_3060_12gb()

        self.assertEqual(items, [])

    def test_terabyte_ssd_and_ram_accept_current_price_legacy_classes(self):
        cases = (
            (
                "get_ssds",
                "SSD",
                "SSD NVMe Kingston NV3 1TB",
                "prod-price",
                299.99,
            ),
            (
                "get_ram_16gb_ddr4",
                "RAM",
                "Memória Gamer Kingston Fury Beast 16GB DDR4",
                "product-item__current-price",
                699.9,
            ),
        )

        for method_name, category, title, price_class, expected_price in cases:
            with self.subTest(method=method_name):
                html = f"""
                <div class="product-item">
                    <a class="product-item__name" title="{title}" href="/produto/{category.lower()}-test"></a>
                    <span class="{price_class}">R$ {expected_price:.2f}</span>
                </div>
                """
                scraper = TerabyteScraper()
                scraper.session = Mock()
                scraper.session.get.return_value = Mock(status_code=200, text=html)

                items = getattr(scraper, method_name)()

                self.assertEqual(len(items), 1, scraper.health)
                self.assertEqual(items[0]["price"], expected_price)
                self.assertEqual(items[0]["category"], category)

    async def test_pichau_rtx_3060_12gb_http_failure_is_reported(self):
        scraper = PichauScraper()
        session = Mock()
        session.get.return_value = Mock(status_code=503, text="")
        with patch("scrapers.pichau.http_requests.Session", return_value=session):
            items = await scraper.get_rtx_3060_12gb()

        self.assertEqual(items, [])
        self.assertEqual(scraper.health["GPU"]["status"], "error")
        self.assertEqual(scraper.health["GPU"]["attempted"], 2)

    async def test_pichau_rtx_3060_12gb_results_are_filtered(self):
        html = """
        <a data-cy="product" href="/placa-de-video-rtx-3060-12gb">Placa de Vídeo RTX 3060 12GB<div class="price_vista">R$ 2.199,99</div></a>
        <a data-cy="product" href="/placa-de-video-rtx-3060-8gb">Placa de Vídeo RTX 3060 8GB<div class="price_vista">R$ 1.499,99</div></a>
        <a data-cy="product" href="/pc-gamer-rtx-3060">PC Gamer RTX 3060 12GB<div class="price_vista">R$ 2.999,99</div></a>
        """
        scraper = PichauScraper()
        session = Mock()
        session.get.return_value = Mock(status_code=200, text=html)
        with patch("scrapers.pichau.http_requests.Session", return_value=session):
            items = await scraper.get_rtx_3060_12gb()

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "Placa de Vídeo RTX 3060 12GB")
        self.assertEqual(items[0]["category"], "GPU")
        self.assertEqual(scraper.health["GPU"]["status"], "ok")
        self.assertEqual(scraper.health["GPU"]["attempted"], 2)

    async def test_pichau_rtx_3060_12gb_uses_standard_http_session(self):
        scraper = PichauScraper()
        session = Mock()
        session.get.return_value = Mock(status_code=503, text="")
        with patch("scrapers.pichau.http_requests.Session", return_value=session) as session_factory:
            await scraper.get_rtx_3060_12gb()

        session_factory.assert_called_once_with()
        headers = session.get.call_args.kwargs["headers"]
        self.assertNotIn("sec-ch-ua", {name.lower() for name in headers})

    async def test_pichau_rtx_3060_12gb_ignores_installment_only_price(self):
        html = """
        <a data-cy="product" href="/placa-de-video-rtx-3060-12gb-pix">Placa de Vídeo RTX 3060 12GB<span>De R$ 2.499,99 por R$ 2.199,99 no PIX</span></a>
        <a data-cy="product" href="/placa-de-video-rtx-3060-12gb-parcelado">Placa de Vídeo RTX 3060 12GB<span>R$ 2.199,99 em 10x de R$ 219,99</span></a>
        """
        scraper = PichauScraper()
        session = Mock()
        session.get.return_value = Mock(status_code=200, text=html)
        with patch("scrapers.pichau.http_requests.Session", return_value=session):
            items = await scraper.get_rtx_3060_12gb()

        self.assertEqual(len(items), 1, scraper.health)
        self.assertEqual(items[0]["price"], 2199.99)
        self.assertEqual(items[0]["link"], "https://www.pichau.com.br/placa-de-video-rtx-3060-12gb-pix")

    async def test_amazon_rtx_3060_12gb_http_failure_is_reported(self):
        scraper = AmazonScraper()
        manager = playwright_manager(FakePage(status_code=503))

        with patch("scrapers.amazon.async_playwright", return_value=manager):
            items = await scraper.get_rtx_3060_12gb()

        self.assertEqual(items, [])
        self.assertEqual(scraper.health["GPU"]["status"], "error")
        self.assertEqual(scraper.health["GPU"]["attempted"], 2)

    async def test_amazon_rtx_3060_12gb_uses_default_browser_identity(self):
        scraper = AmazonScraper()
        manager = playwright_manager(FakePage(status_code=503))

        with patch("scrapers.amazon.async_playwright", return_value=manager):
            await scraper.get_rtx_3060_12gb()

        playwright = manager.__aenter__.return_value
        launch_args = playwright.chromium.launch.call_args.kwargs.get("args", [])
        context_kwargs = playwright.chromium.launch.return_value.new_context.call_args.kwargs
        self.assertNotIn("--disable-blink-features=AutomationControlled", launch_args)
        self.assertNotIn("user_agent", context_kwargs)

    async def test_amazon_rtx_3060_12gb_results_are_filtered(self):
        current_price_selector = '.a-price[data-a-strike="false"] .a-offscreen, .a-price:not([data-a-strike="true"]) .a-offscreen'

        def card(title, href, price):
            return FakeProductCard({
                "h2 span, h2": FakeElement(text=title),
                "a:has(h2), a[href*=\"/dp/\"], h2 a": FakeElement(href=href),
                current_price_selector: FakeElement(text=price),
            })

        page = FakeProductPage(
            "div[data-component-type=\"s-search-result\"]",
            [
                card("Placa de Vídeo NVIDIA GeForce RTX 3060 12GB GDDR6", "/dp/B0VALID", "R$ 2.199,99"),
                card("Placa de Vídeo RTX 3060 8GB GDDR6", "/dp/B0INVALID", "R$ 1.499,99"),
                card("PC Gamer RTX 3060 12GB 16GB DDR4", "/dp/B0PC", "R$ 2.999,99"),
            ],
        )
        scraper = AmazonScraper()
        manager = playwright_manager(page)

        with patch("scrapers.amazon.async_playwright", return_value=manager):
            items = await scraper.get_rtx_3060_12gb()

        self.assertEqual(len(items), 1, scraper.health)
        self.assertEqual(items[0]["category"], "GPU")
        self.assertEqual(items[0]["price"], 2199.99)
        self.assertEqual(scraper.health["GPU"]["status"], "ok")

    async def test_amazon_rtx_3060_12gb_ignores_struck_through_price(self):
        card = FakeProductCard({
            "h2 span, h2": FakeElement(text="Placa de Vídeo RTX 3060 12GB GDDR6"),
            "a:has(h2), a[href*=\"/dp/\"], h2 a": FakeElement(href="/dp/B0OLD"),
            ".a-price .a-offscreen": FakeElement(text="R$ 2.499,99"),
        })
        page = FakeProductPage(
            'div[data-component-type="s-search-result"]',
            [card],
        )
        scraper = AmazonScraper()
        manager = playwright_manager(page)

        with patch("scrapers.amazon.async_playwright", return_value=manager):
            items = await scraper.get_rtx_3060_12gb()

        self.assertEqual(items, [])

    async def test_mercadolivre_rtx_3060_12gb_http_failure_is_reported(self):
        scraper = MercadoLivreScraper()
        manager = playwright_manager(FakePage(status_code=503))

        with patch("scrapers.mercadolivre.async_playwright", return_value=manager):
            items = await scraper.get_rtx_3060_12gb()

        self.assertEqual(items, [])
        self.assertEqual(scraper.health["GPU"]["status"], "error")
        self.assertEqual(scraper.health["GPU"]["attempted"], 2)

    async def test_mercadolivre_rtx_3060_12gb_results_are_filtered(self):
        def card(title, href, fraction, cents):
            return FakeProductCard({
                ".poly-component__title, .ui-search-item__title, h2": FakeElement(text=title),
                "a.ui-search-link, a.poly-component__title": FakeElement(href=href),
                ".andes-money-amount--current .andes-money-amount__fraction": FakeElement(text=fraction),
                ".andes-money-amount--current .andes-money-amount__cents": FakeElement(text=cents),
            })

        page = FakeProductPage(
            "li.ui-search-layout__item, .poly-card",
            [
                card("Placa de Vídeo Nvidia RTX 3060 12GB", "https://produto.mercadolivre.com.br/gpu-3060-12gb", "2.199", "99"),
                card("Placa de Vídeo RTX 3060 8GB", "https://produto.mercadolivre.com.br/gpu-3060-8gb", "1.499", "99"),
            ],
        )
        scraper = MercadoLivreScraper()
        manager = playwright_manager(page)

        with patch("scrapers.mercadolivre.async_playwright", return_value=manager):
            items = await scraper.get_rtx_3060_12gb()

        self.assertEqual(len(items), 1, scraper.health)
        self.assertEqual(items[0]["category"], "GPU")
        self.assertEqual(items[0]["price"], 2199.99)
        self.assertEqual(scraper.health["GPU"]["status"], "ok")

    async def test_mercadolivre_rtx_3060_12gb_uses_current_price(self):
        card = FakeProductCard({
            ".poly-component__title, .ui-search-item__title, h2": FakeElement(
                text="Placa de Vídeo Nvidia RTX 3060 12GB"
            ),
            "a.ui-search-link, a.poly-component__title": FakeElement(
                href="https://produto.mercadolivre.com.br/gpu-3060-12gb"
            ),
            ".andes-money-amount--previous .andes-money-amount__fraction": FakeElement(text="2.499"),
            ".andes-money-amount--previous .andes-money-amount__cents": FakeElement(text="99"),
            ".andes-money-amount--current .andes-money-amount__fraction": FakeElement(text="2.199"),
            ".andes-money-amount--current .andes-money-amount__cents": FakeElement(text="99"),
        })
        page = FakeProductPage("li.ui-search-layout__item, .poly-card", [card])
        scraper = MercadoLivreScraper()
        manager = playwright_manager(page)

        with patch("scrapers.mercadolivre.async_playwright", return_value=manager):
            items = await scraper.get_rtx_3060_12gb()

        self.assertEqual(len(items), 1, scraper.health)
        self.assertEqual(items[0]["price"], 2199.99)

    async def test_mercadolivre_rtx_3060_12gb_ignores_previous_price_without_current_price(self):
        card = FakeProductCard({
            ".poly-component__title, .ui-search-item__title, h2": FakeElement(
                text="Placa de Vídeo Nvidia RTX 3060 12GB"
            ),
            "a.ui-search-link, a.poly-component__title": FakeElement(
                href="https://produto.mercadolivre.com.br/gpu-3060-12gb"
            ),
            ".andes-money-amount--previous .andes-money-amount__fraction": FakeElement(text="2.499"),
            ".andes-money-amount--previous .andes-money-amount__cents": FakeElement(text="99"),
        })
        page = FakeProductPage("li.ui-search-layout__item, .poly-card", [card])
        scraper = MercadoLivreScraper()
        manager = playwright_manager(page)

        with patch("scrapers.mercadolivre.async_playwright", return_value=manager):
            items = await scraper.get_rtx_3060_12gb()

        self.assertEqual(items, [])

    async def test_mercadolivre_rtx_3060_12gb_uses_default_browser_identity(self):
        scraper = MercadoLivreScraper()
        page = FakePage(status_code=503)
        manager = playwright_manager(page)

        with patch("scrapers.mercadolivre.async_playwright", return_value=manager):
            await scraper.get_rtx_3060_12gb()

        playwright = manager.__aenter__.return_value
        launch_args = playwright.chromium.launch.call_args.kwargs.get("args", [])
        context_kwargs = playwright.chromium.launch.return_value.new_context.call_args.kwargs
        self.assertNotIn("--disable-blink-features=AutomationControlled", launch_args)
        self.assertNotIn("user_agent", context_kwargs)
        page.add_init_script.assert_not_awaited()

    async def test_mercadolivre_ssd_and_ram_prices_keep_thousands_and_cents(self):
        def card(title, href, fraction, cents):
            return FakeProductCard({
                ".poly-component__title, .ui-search-item__title, h2": FakeElement(text=title),
                "a.ui-search-link, a.poly-component__title": FakeElement(href=href),
                ".andes-money-amount--current .andes-money-amount__fraction": FakeElement(text=fraction),
                ".andes-money-amount--current .andes-money-amount__cents": FakeElement(text=cents or "", count=0 if cents is None else 1),
            })

        cases = (
            ("get_ssds", "SSD", "SSD NVMe Kingston NV3 1TB", "1.299", "90", 1299.9),
            ("get_ssds", "SSD", "SSD NVMe Kingston NV3 1TB", "599", None, 599.0),
            ("get_ram_16gb_ddr4", "RAM", "Memória Gamer Kingston Fury Beast 16GB DDR4", "699", "90", 699.9),
            ("get_ram_16gb_ddr4", "RAM", "Memória Gamer Kingston Fury Beast 16GB DDR4", "1.000", None, 1000.0),
        )

        for method_name, category, title, fraction, cents, expected in cases:
            with self.subTest(category=category, fraction=fraction, cents=cents):
                page = FakeProductPage(
                    "li.ui-search-layout__item, .poly-card",
                    [card(title, "https://produto.mercadolivre.com.br/item", fraction, cents)],
                )
                scraper = MercadoLivreScraper()
                manager = playwright_manager(page)

                with patch("scrapers.mercadolivre.async_playwright", return_value=manager):
                    items = await getattr(scraper, method_name)()

                self.assertTrue(items, scraper.health)
                self.assertTrue(all(item["price"] == expected for item in items))
                self.assertEqual(scraper.health[category]["status"], "ok")

    async def test_mercadolivre_ssd_and_ram_use_current_price(self):
        cases = (
            (
                "get_ssds",
                "SSD",
                "SSD NVMe Kingston NV3 1TB",
                "1.299",
                "90",
                "999",
                "90",
                999.9,
            ),
            (
                "get_ram_16gb_ddr4",
                "RAM",
                "Memória Gamer Kingston Fury Beast 16GB DDR4",
                "899",
                "90",
                "699",
                "90",
                699.9,
            ),
        )

        for method_name, category, title, old_fraction, old_cents, fraction, cents, expected in cases:
            with self.subTest(category=category):
                card = FakeProductCard({
                    ".poly-component__title, .ui-search-item__title, h2": FakeElement(text=title),
                    "a.ui-search-link, a.poly-component__title": FakeElement(
                        href=f"https://produto.mercadolivre.com.br/{category.lower()}-current"
                    ),
                    ".andes-money-amount__fraction": FakeElement(text=old_fraction),
                    ".andes-money-amount__cents": FakeElement(text=old_cents),
                    ".andes-money-amount--current .andes-money-amount__fraction": FakeElement(text=fraction),
                    ".andes-money-amount--current .andes-money-amount__cents": FakeElement(text=cents),
                })
                page = FakeProductPage("li.ui-search-layout__item, .poly-card", [card])
                scraper = MercadoLivreScraper()
                manager = playwright_manager(page)

                with patch("scrapers.mercadolivre.async_playwright", return_value=manager):
                    items = await getattr(scraper, method_name)()

                self.assertTrue(items, scraper.health)
                self.assertTrue(all(item["price"] == expected for item in items))


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
