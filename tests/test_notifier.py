import json
import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from bs4 import BeautifulSoup

import notifier


def item_fixture(title="SSD NVMe Kingston NV3 1TB", price=499.0, link="https://www.kabum.com.br/produto/nv3"):
    return {
        "title": title,
        "price": price,
        "capacity": "1TB",
        "store": "Kabum",
        "warranty": "Garantia Kabum",
        "link": link,
        "category": "SSD",
    }


class NotifierTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.old_cwd = os.getcwd()
        os.chdir(self.temp_dir.name)
        self.addCleanup(os.chdir, self.old_cwd)
        self.history_path = Path(self.temp_dir.name) / "historico_precos.json"
        history_patch = patch.object(notifier, "HISTORY_FILE", str(self.history_path))
        history_patch.start()
        self.addCleanup(history_patch.stop)


class PriceHistoryTests(NotifierTestCase):
    def test_history_key_is_stable_when_title_changes(self):
        original = item_fixture()
        renamed = {**original, "title": "SSD NVMe Kingston NV3 1TB - novo nome"}

        self.assertEqual(notifier.history_key(original), notifier.history_key(renamed))

    def test_history_key_distinguishes_products_with_same_title_prefix(self):
        first = item_fixture(title="SSD NVMe modelo compartilhado 1TB", link="https://www.kabum.com.br/produto/1")
        second = item_fixture(title="SSD NVMe modelo compartilhado 1TB", link="https://www.kabum.com.br/produto/2")

        self.assertNotEqual(notifier.history_key(first), notifier.history_key(second))

    def test_variation_uses_stable_key_without_mutating_history(self):
        item = item_fixture(price=90.0)
        key = notifier.history_key(item)
        history = {key: 100.0}

        variation, label = notifier.calculate_variation(item, history)

        self.assertEqual(variation, -10.0)
        self.assertEqual(label, "-10.0%")
        self.assertEqual(history, {key: 100.0})

    def test_variation_reads_legacy_title_history(self):
        item = item_fixture(price=90.0)
        legacy_key = f"{item['store']}_{item['title'][:50]}"

        variation, label = notifier.calculate_variation(item, {legacy_key: 100.0})

        self.assertEqual(variation, -10.0)
        self.assertEqual(label, "-10.0%")

    def test_stable_key_takes_precedence_over_legacy_key(self):
        item = item_fixture(price=90.0)
        legacy_key = f"{item['store']}_{item['title'][:50]}"
        history = {notifier.history_key(item): 80.0, legacy_key: 100.0}

        variation, _ = notifier.calculate_variation(item, history)

        self.assertEqual(variation, 12.5)

    def test_report_generation_does_not_save_history(self):
        with patch.object(notifier, "save_price_history") as save:
            notifier.generate_html_report({"ssds_1tb": [item_fixture()]})

        save.assert_not_called()

    def test_pc_items_are_excluded_from_delivered_history(self):
        pc = item_fixture(title="PC Gamer RTX 5060 Ti", link="https://www.kabum.com.br/produto/pc")
        ssd = item_fixture()

        items = notifier.get_report_items({"ai_ranking": [pc], "ssds_1tb": [ssd]})

        self.assertEqual(items, [ssd])

    def test_failed_email_does_not_advance_history(self):
        server = MagicMock()
        server.sendmail.side_effect = OSError("SMTP offline")
        smtp = MagicMock()
        smtp.return_value.__enter__.return_value = server
        env = {
            "SENDER_EMAIL": "sender@example.com",
            "SENDER_PASSWORD": "fake-password",
            "RECEIVER_EMAIL": "receiver@example.com",
            "SMTP_SERVER": "smtp.example.com",
            "SMTP_PORT": "465",
        }

        with patch.dict(os.environ, env, clear=True), patch.object(notifier.smtplib, "SMTP_SSL", smtp):
            sent = notifier.send_email_alert({"ssds_1tb": [item_fixture()]})

        self.assertFalse(sent)
        self.assertFalse(self.history_path.exists())

    def test_rtx_3060_12gb_is_rendered_and_historized(self):
        gpu = item_fixture(
            title="Placa de Vídeo NVIDIA GeForce RTX 3060 12GB GDDR6",
            price=2199.99,
            link="https://www.kabum.com.br/produto/rtx-3060-12gb",
        )
        gpu.update({"vram": "12GB", "category": "GPU"})
        server = MagicMock()
        smtp = MagicMock()
        smtp.return_value.__enter__.return_value = server
        env = {
            "SENDER_EMAIL": "sender@example.com",
            "SENDER_PASSWORD": "fake-password",
            "RECEIVER_EMAIL": "receiver@example.com",
            "SMTP_SERVER": "smtp.example.com",
            "SMTP_PORT": "465",
        }

        with patch.dict(os.environ, env, clear=True), patch.object(notifier.smtplib, "SMTP_SSL", smtp):
            sent = notifier.send_email_alert({"rtx_3060_12gb": [gpu]})

        self.assertTrue(sent)
        report = Path("ultimo_relatorio.html").read_text(encoding="utf-8")
        self.assertIn("<title>Relatório Diário de Preços - RTX 3060 12GB, SSDs e Memórias RAM</title>", report)
        self.assertIn("RTX 3060 12GB", report)
        self.assertIn("R$ 2.199,99", report)
        message = server.sendmail.call_args.args[2]
        self.assertIn("Subject: RADAR RTX 3060 12GB", message)
        history = json.loads(self.history_path.read_text(encoding="utf-8"))
        self.assertEqual(history, {notifier.history_key(gpu): 2199.99})

    def test_unrendered_rtx_3060_12gb_items_do_not_enter_history(self):
        items = [
            item_fixture(
                title=f"Placa de Vídeo RTX 3060 12GB oferta {index}",
                price=2199.99 + index,
                link=f"https://www.kabum.com.br/produto/rtx-3060-12gb-{index}",
            )
            for index in range(9)
        ]

        delivered = notifier.get_report_items({"rtx_3060_12gb": items})

        self.assertEqual(delivered, items[:8])

    def test_successful_email_saves_only_rendered_items(self):
        items = [item_fixture(price=499.0), item_fixture(title="SSD NVMe extra 1TB", price=599.0, link="https://www.kabum.com.br/produto/extra")]
        server = MagicMock()
        smtp = MagicMock()
        smtp.return_value.__enter__.return_value = server
        env = {
            "SENDER_EMAIL": "sender@example.com",
            "SENDER_PASSWORD": "fake-password",
            "RECEIVER_EMAIL": "receiver@example.com",
            "SMTP_SERVER": "smtp.example.com",
            "SMTP_PORT": "465",
        }

        with patch.dict(os.environ, env, clear=True), patch.object(notifier.smtplib, "SMTP_SSL", smtp):
            sent = notifier.send_email_alert({"ssds_1tb": items[:1], "nvme_general_1tb": [items[1]]})

        self.assertTrue(sent)
        history = json.loads(self.history_path.read_text(encoding="utf-8"))
        self.assertEqual(history, {notifier.history_key(items[0]): 499.0})

    def test_missing_credentials_do_not_advance_history(self):
        with patch.dict(os.environ, {}, clear=True):
            sent = notifier.send_email_alert({"ssds_1tb": [item_fixture()]})

        self.assertFalse(sent)
        self.assertFalse(self.history_path.exists())

    def test_history_write_failure_fails_the_run_after_email(self):
        original_history = '{"legacy": 100.0}'
        self.history_path.write_text(original_history, encoding="utf-8")
        server = MagicMock()
        smtp = MagicMock()
        smtp.return_value.__enter__.return_value = server
        env = {
            "SENDER_EMAIL": "sender@example.com",
            "SENDER_PASSWORD": "fake-password",
            "RECEIVER_EMAIL": "receiver@example.com",
            "SMTP_SERVER": "smtp.example.com",
            "SMTP_PORT": "465",
        }

        with patch.dict(os.environ, env, clear=True), patch.object(
            notifier.smtplib, "SMTP_SSL", smtp
        ), patch.object(notifier.json, "dump", side_effect=OSError("disk full")):
            sent = notifier.send_email_alert({"ssds_1tb": [item_fixture()]})

        self.assertFalse(sent)
        server.sendmail.assert_called_once()
        self.assertEqual(self.history_path.read_text(encoding="utf-8"), original_history)


class HtmlReportTests(NotifierTestCase):
    def test_report_ignores_removed_pc_and_ai_sections(self):
        pc = item_fixture(title="PC Gamer RTX 5060 Ti", link="https://www.kabum.com.br/produto/pc")
        ssd = item_fixture()

        report = notifier.generate_html_report({"ai_ranking": [pc], "ssds_1tb": [ssd]})

        self.assertNotIn("PC Gamer RTX", report)
        self.assertNotIn("RANKING CUSTO-BENEFÍCIO", report)
        self.assertNotIn("Servidor de IA", report)
        self.assertIn("SSD NVMe Kingston NV3 1TB", report)

    def test_mobile_layout_keeps_price_action_and_health_status_visible(self):
        item = item_fixture()
        health = {"Kabum": {"SSD": {"status": "ok", "count": 1, "attempted": 1, "detail": "Coleta concluída."}}}
        report = notifier.generate_html_report({"ssds_1tb": [item], "source_health": health})
        soup = BeautifulSoup(report, "html.parser")

        self.assertIsNotNone(soup.style)
        self.assertIn("@media only screen and (max-width: 600px)", soup.style.string)
        product_headers = soup.select_one("table.radar-product-table thead th")
        self.assertIsNotNone(product_headers)
        product_columns = soup.select("table.radar-product-table thead th")
        self.assertIn("radar-col-optional", product_columns[0].get("class", []))
        self.assertIn("radar-col-optional", product_columns[2].get("class", []))
        self.assertIn("radar-col-optional", product_columns[3].get("class", []))
        self.assertNotIn("radar-col-optional", product_columns[4].get("class", []))
        self.assertNotIn("radar-col-optional", product_columns[6].get("class", []))
        health_columns = soup.select("table.radar-health-table thead th")
        self.assertIn("radar-col-optional", health_columns[4].get("class", []))
        self.assertIn("radar-col-optional", health_columns[5].get("class", []))
        self.assertNotIn("radar-col-optional", health_columns[2].get("class", []))

    def test_product_title_is_escaped(self):
        item = item_fixture(title="SSD <script>alert(1)</script> & 1TB")

        report = notifier.generate_html_report({"ssds_1tb": [item]})

        self.assertNotIn("<script>alert(1)</script>", report)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", report)

    def test_unsafe_link_is_not_rendered_as_href(self):
        item = item_fixture(link="javascript:alert(1)")

        report = notifier.generate_html_report({"ssds_1tb": [item]})

        self.assertNotIn('href="javascript:alert(1)"', report)
        self.assertIn("Link indisponível", report)

    def test_allowed_https_link_is_preserved(self):
        item = item_fixture(link="https://www.kabum.com.br/produto/nv3?utm_source=radar")

        report = notifier.generate_html_report({"ssds_1tb": [item]})

        self.assertIn('href="https://www.kabum.com.br/produto/nv3?utm_source=radar"', report)

    def test_product_and_source_health_fields_are_escaped(self):
        item = item_fixture(title="SSD <img src=x onerror=alert(1)>")
        health = {
            "<script>alert(9)</script>": {
                "<svg onload=alert(10)>": {
                    "status": "error",
                    "count": 0,
                    "attempted": 1,
                    "detail": "<img src=x onerror=alert(11)>",
                }
            }
        }

        report = notifier.generate_html_report({"ssds_1tb": [item], "source_health": health})

        for raw in ("<img", "<svg", "<script>alert(9)</script>", "<svg onload=alert(10)>"):
            self.assertNotIn(raw, report)
        self.assertIn("&lt;img", report)
        self.assertIn("&lt;svg", report)
        self.assertIn("&lt;script&gt;alert(9)&lt;/script&gt;", report)

    def test_malformed_product_link_does_not_break_report(self):
        item = item_fixture(link="https://[")

        report = notifier.generate_html_report({"ssds_1tb": [item]})

        self.assertIn("Link indisponível", report)

    def test_http_and_lookalike_domains_are_rejected(self):
        http_item = item_fixture(title="HTTP SSD", link="http://www.kabum.com.br/produto/nv3")
        lookalike_item = item_fixture(title="Lookalike SSD", link="https://www.kabum.com.br.evil.example/produto/nv3")

        report = notifier.generate_html_report({"ssds_1tb": [http_item, lookalike_item]})

        self.assertNotIn('href="http://www.kabum.com.br/produto/nv3"', report)
        self.assertNotIn("evil.example", report)

    def test_price_increase_is_red_and_decrease_is_green(self):
        increased = item_fixture(title="SSD aumento 1TB", price=110.0, link="https://www.kabum.com.br/produto/aumento")
        decreased = item_fixture(title="SSD queda 1TB", price=90.0, link="https://www.kabum.com.br/produto/queda")
        history = {
            notifier.history_key(increased): 100.0,
            notifier.history_key(decreased): 100.0,
        }

        report = notifier.generate_html_report({"ssds_1tb": [increased, decreased]}, history=history)
        soup = BeautifulSoup(report, "html.parser")
        increase_badge = soup.find("span", string="+10.0%")
        decrease_badge = soup.find("span", string="-10.0%")

        self.assertIn("#dc2626", increase_badge["style"])
        self.assertIn("#059669", decrease_badge["style"])

    def test_empty_report_does_not_invent_prices(self):
        report = notifier.generate_html_report({})

        self.assertNotIn("R$ 720,00", report)
        self.assertNotIn("R$ 690,00", report)
        self.assertNotIn("R$ 1.200,00", report)

    def test_report_copy_does_not_overstate_coverage_or_time_window(self):
        report = notifier.generate_html_report({})

        self.assertNotIn("ranking nacional", report)
        self.assertNotIn("ÚLTIMAS 24H", report)
        self.assertNotIn("radar completo", report)

    def test_blocked_source_is_visible_in_health_section(self):
        health = {
            "Mercado Livre": {
                "SSD": {"status": "blocked", "count": 0, "attempted": 7, "detail": "account-verification"},
                "RAM": {"status": "empty", "count": 0, "attempted": 2, "detail": ""},
            }
        }

        report = notifier.generate_html_report({"source_health": health})
        soup = BeautifulSoup(report, "html.parser")

        self.assertIn("Bloqueada", soup.get_text(" ", strip=True))
        self.assertIn("Mercado Livre", soup.get_text(" ", strip=True))

    def test_mancer_is_not_presented_as_preferred_brand(self):
        mancer = item_fixture(title="Memória Gamer Mancer Dantalion 16GB DDR4", price=189.0)

        report = notifier.generate_html_report({
            "mancer_dantalion": [mancer],
            "rams_16gb": [mancer],
        })

        self.assertNotIn("O melhor preço entre as marcas favoritas", report)
        self.assertIn("Nenhum preço entre as marcas favoritas foi encontrado", report)

    def test_sata_ssd_is_not_presented_as_nvme(self):
        sata_1tb = item_fixture(title="SSD SATA Kingston A400 1TB", price=399.0, link="https://www.kabum.com.br/produto/a400-1tb")
        sata_2tb = item_fixture(title="SSD SATA Kingston A400 2TB", price=699.0, link="https://www.kabum.com.br/produto/a400-2tb")

        report = notifier.generate_html_report({
            "ssds_1tb": [sata_1tb],
            "ssds_2tb": [sata_2tb],
        })

        self.assertIn("Não há preços suficientes de NVMe 1TB e 2TB", report)
        self.assertNotIn("Armazenamento NVMe Custo-Benefício:</strong> Para 1TB", report)

    def test_report_date_is_in_brazilian_portuguese(self):
        value = datetime(2026, 11, 25, 14, 5)

        self.assertEqual(notifier.format_report_date(value), "25 de novembro de 2026, 14:05")


if __name__ == "__main__":
    unittest.main()
