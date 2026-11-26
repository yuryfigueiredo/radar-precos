import unittest
from unittest.mock import AsyncMock, Mock, patch

import main


def ssd_fixture():
    return {
        "title": "SSD NVMe Kingston NV3 1TB",
        "price": 499.0,
        "capacity": "1TB",
        "store": "Kabum",
        "warranty": "Garantia Kabum",
        "link": "https://www.kabum.com.br/produto/test-nv3",
        "category": "SSD",
    }


class RunRadarTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.kabum = Mock()
        self.kabum.health = {}
        self.kabum.get_gaming_pcs.return_value = []
        self.kabum.get_ssds.return_value = []
        self.kabum.get_ram_16gb_ddr4.return_value = []

        self.terabyte = Mock()
        self.terabyte.health = {}
        self.terabyte.get_gaming_pcs.return_value = []
        self.terabyte.get_ssds.return_value = []
        self.terabyte.get_ram_16gb_ddr4.return_value = []

        self.pichau = Mock()
        self.pichau.health = {}
        self.pichau.get_gaming_pcs = AsyncMock(return_value=[])
        self.pichau.get_ssds = AsyncMock(return_value=[])
        self.pichau.get_ram_16gb_ddr4 = AsyncMock(return_value=[])

        self.amazon = Mock()
        self.amazon.health = {}
        self.amazon.get_ssds = AsyncMock(return_value=[])
        self.amazon.get_ram_16gb_ddr4 = AsyncMock(return_value=[])

        self.mercadolivre = Mock()
        self.mercadolivre.health = {}
        self.mercadolivre.get_ssds = AsyncMock(return_value=[])
        self.mercadolivre.get_ram_16gb_ddr4 = AsyncMock(return_value=[])

        patches = [
            patch.object(main, "KabumScraper", return_value=self.kabum),
            patch.object(main, "TerabyteScraper", return_value=self.terabyte),
            patch.object(main, "PichauScraper", return_value=self.pichau),
            patch.object(main, "AmazonScraper", return_value=self.amazon),
            patch.object(main, "MercadoLivreScraper", return_value=self.mercadolivre),
            patch("builtins.print"),
        ]
        for patcher in patches:
            patcher.start()
            self.addCleanup(patcher.stop)

    async def test_pc_collection_is_not_requested(self):
        self.kabum.get_ssds.return_value = [ssd_fixture()]
        sender = Mock(return_value=True)
        with patch.object(main, "send_email_alert", sender):
            await main.run_radar()

        self.kabum.get_gaming_pcs.assert_not_called()
        self.terabyte.get_gaming_pcs.assert_not_called()
        self.pichau.get_gaming_pcs.assert_not_called()
        report_data = sender.call_args.args[0]
        self.assertNotIn("ai_ranking", report_data)
        self.assertNotIn("PC", report_data["source_health"]["Kabum"])

    async def test_email_failure_fails_the_run(self):
        self.kabum.get_ssds.return_value = [ssd_fixture()]
        with patch.object(main, "send_email_alert", Mock(return_value=False)):
            with self.assertRaisesRegex(RuntimeError, "e-mail"):
                await main.run_radar()

    async def test_no_usable_data_fails_before_sending_email(self):
        sender = Mock(return_value=True)
        with patch.object(main, "send_email_alert", sender):
            with self.assertRaisesRegex(RuntimeError, "Nenhuma fonte"):
                await main.run_radar()
        sender.assert_not_called()

    async def test_blocked_source_health_is_included_in_report(self):
        self.kabum.get_ssds.return_value = [ssd_fixture()]
        self.amazon.health = {
            "SSD": {
                "status": "blocked",
                "count": 0,
                "attempted": 7,
                "detail": "account-verification",
            }
        }
        sender = Mock(return_value=True)
        with patch.object(main, "send_email_alert", sender):
            await main.run_radar()

        report_data = sender.call_args.args[0]
        self.assertEqual(report_data["source_health"]["Amazon"]["SSD"]["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
