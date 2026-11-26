import unittest

from scrapers import utils


class PcVramClassificationTests(unittest.TestCase):
    def test_5060_ti_with_explicit_16gb_is_classified_as_16gb(self):
        title = "PC Gamer RTX 5060 Ti 16GB 32GB DDR5 SSD 1TB"

        self.assertEqual(utils.classify_pc_vram(title), "16GB")

    def test_4060_ti_with_explicit_16gb_is_classified_as_16gb(self):
        title = "PC Gamer RTX 4060 Ti 16GB 32GB DDR4 SSD 1TB"

        self.assertEqual(utils.classify_pc_vram(title), "16GB")

    def test_5060_ti_without_explicit_vram_is_not_guessed(self):
        title = "PC Gamer RTX 5060 Ti 32GB DDR5 SSD 1TB"

        self.assertIsNone(utils.classify_pc_vram(title))

    def test_5060_ti_with_explicit_8gb_is_classified_as_8gb(self):
        title = "PC Gamer RTX 5060 Ti 8GB 32GB DDR5 SSD 1TB"

        self.assertEqual(utils.classify_pc_vram(title), "8GB")

    def test_ram_capacity_does_not_change_4060_vram(self):
        title = "PC Gamer RTX 4060 8GB 32GB DDR4 SSD 1TB"

        self.assertEqual(utils.classify_pc_vram(title), "8GB")

    def test_3060_with_32gb_ram_is_classified_as_12gb(self):
        title = "PC Gamer RTX 3060 12GB 32GB DDR4"

        self.assertEqual(utils.classify_pc_vram(title), "12GB")

    def test_4090_24gb_is_outside_the_supported_vram_buckets(self):
        title = "PC Gamer RTX 4090 24GB 64GB DDR5"

        self.assertIsNone(utils.classify_pc_vram(title))

    def test_standalone_gpu_is_not_classified_as_a_pc(self):
        title = "Placa de Vídeo RTX 5060 Ti 16GB"

        self.assertIsNone(utils.classify_pc_vram(title))


class NativeRamTests(unittest.TestCase):
    def test_nvidia_title_with_32gb_ram_is_accepted(self):
        title = "PC Gamer RTX 5060 Ti 16GB 32GB DDR5 SSD 1TB"

        self.assertTrue(utils.has_native_32gb_ram(title))

    def test_nvidia_title_with_64gb_ram_is_accepted(self):
        title = "PC Gamer NVIDIA RTX 4060 8GB 64GB DDR5"

        self.assertTrue(utils.has_native_32gb_ram(title))

    def test_pc_without_32gb_ram_is_rejected(self):
        title = "PC Gamer RTX 5060 Ti 16GB SSD 1TB"

        self.assertFalse(utils.has_native_32gb_ram(title))

    def test_explicit_vram_capacity_is_not_treated_as_ram(self):
        title = "PC Gamer RTX 5090 32GB VRAM"

        self.assertFalse(utils.has_native_32gb_ram(title))

class SsdClassificationTests(unittest.TestCase):
    def test_variant_suffix_selects_1tb(self):
        title = "SSD NVMe Dahua 1TB | 2TB (1, TB)"

        self.assertEqual(utils.classify_ssd_capacity(title), "1TB")

    def test_variant_suffix_selects_2tb(self):
        title = "SSD NVMe Dahua 1TB | 2TB (2, TB)"

        self.assertEqual(utils.classify_ssd_capacity(title), "2TB")

    def test_variant_suffix_without_comma_selects_2tb(self):
        title = "SSD NVMe Dahua 1TB | 2TB (2TB)"

        self.assertEqual(utils.classify_ssd_capacity(title), "2TB")

    def test_multiple_capacities_without_variant_are_ambiguous(self):
        title = "SSD NVMe Dahua 1TB | 2TB"

        self.assertIsNone(utils.classify_ssd_capacity(title))

    def test_transport_accessory_is_not_an_ssd(self):
        title = (
            "Lacdo Maixa de Transporte Rígida para Kings ton XS1000R/XS2000/"
            "XS1000 SSD 500GB/1TB/2TB/Portátil Unidade de Estatos Sólidos "
            "Externos USB 3.2eva Saco de Armazenamento Resistente a Choces, Preto"
        )

        self.assertIsNone(utils.classify_ssd_capacity(title))

    def test_complete_pc_with_ssd_is_not_an_ssd(self):
        title = "PC Gamer RTX 4060 16GB RAM SSD 1TB"

        self.assertIsNone(utils.classify_ssd_capacity(title))

    def test_ai_computer_with_ssd_is_not_an_ssd(self):
        title = "Computador de IA RTX 4090 SSD NVMe Kingston NV3 2TB"

        self.assertIsNone(utils.classify_ssd_capacity(title))

    def test_complete_pc_without_gamer_label_is_not_an_ssd(self):
        title = "PC Intel Core i5 16GB SSD 1TB"

        self.assertIsNone(utils.classify_ssd_capacity(title))

    def test_desktop_compatibility_does_not_hide_an_ssd(self):
        title = "SSD Externo 1TB para Desktop"

        self.assertEqual(utils.classify_ssd_capacity(title), "1TB")

    def test_m2_sata_is_not_classified_as_nvme(self):
        title = "SSD M.2 SATA 1TB 2280"

        self.assertFalse(utils.is_nvme_ssd(title))

    def test_m2_pcie_is_classified_as_nvme(self):
        title = "SSD M.2 PCIe 3.0 1TB 2280"

        self.assertTrue(utils.is_nvme_ssd(title))

    def test_generic_m2_is_not_assumed_to_be_nvme(self):
        title = "SSD M.2 2280 1TB"

        self.assertFalse(utils.is_nvme_ssd(title))

    def test_explicit_nvme_is_classified_as_nvme(self):
        title = "SSD NVMe 1TB"

        self.assertTrue(utils.is_nvme_ssd(title))

    def test_wd_sn580_is_classified_as_nvme(self):
        title = "SSD WD Blue SN580 1TB"

        self.assertTrue(utils.is_nvme_ssd(title))

    def test_gen4_is_classified_as_nvme(self):
        title = "SSD Gen4 1TB"

        self.assertTrue(utils.is_nvme_ssd(title))


class RamClassificationTests(unittest.TestCase):
    def test_complete_pc_with_ram_is_not_a_memory_module(self):
        title = "PC Gamer 16GB DDR4 SSD 1TB"

        self.assertFalse(utils.is_valid_ram_16gb_ddr4(title))

    def test_complete_pc_without_gamer_label_is_not_a_memory_module(self):
        title = "PC Intel Core i5 16GB DDR4 SSD 1TB"

        self.assertFalse(utils.is_valid_ram_16gb_ddr4(title))

    def test_desktop_compatibility_does_not_hide_a_memory_module(self):
        title = "Memória Gamer 16GB DDR4 para Desktop"

        self.assertTrue(utils.is_valid_ram_16gb_ddr4(title))

    def test_32gb_kit_with_16gb_modules_is_not_a_16gb_kit(self):
        title = "Memória Gamer 32GB (2x16GB) DDR4"

        self.assertFalse(utils.is_valid_ram_16gb_ddr4(title))

    def test_32gb_advertised_with_16gb_modules_is_not_a_16gb_kit(self):
        title = "Memória 32GB DDR4 16GB por módulo"

        self.assertFalse(utils.is_valid_ram_16gb_ddr4(title))

    def test_single_16gb_module_is_valid(self):
        title = "Memória Gamer 16GB (1x16GB) DDR4"

        self.assertTrue(utils.is_valid_ram_16gb_ddr4(title))

    def test_16gb_kit_with_8gb_modules_is_valid(self):
        title = "Memória Gamer 16GB (2x8GB) DDR4"

        self.assertTrue(utils.is_valid_ram_16gb_ddr4(title))


class SearchPageHealthTests(unittest.TestCase):
    def test_unrecognized_empty_page_is_an_error(self):
        status, detail = utils.classify_search_page("Página inesperada", 0)

        self.assertEqual(status, "error")
        self.assertIn("Estrutura", detail)

    def test_legitimate_empty_search_is_empty(self):
        status, detail = utils.classify_search_page("Não encontramos resultados para a sua busca.", 0)

        self.assertIsNone(status)
        self.assertIsNone(detail)

    def test_captcha_page_is_blocked(self):
        status, detail = utils.classify_search_page("Digite os caracteres que você vê na imagem.", 0)

        self.assertEqual(status, "blocked")
        self.assertIn("CAPTCHA", detail)


class CollectionHealthTests(unittest.TestCase):
    def test_successful_collection_is_ok(self):
        health = utils.summarize_collection(3, [], 5)

        self.assertEqual(health["status"], "ok")
        self.assertEqual(health["count"], 3)

    def test_partial_failure_with_results_is_partial(self):
        health = utils.summarize_collection(3, ["timeout"], 5)

        self.assertEqual(health["status"], "partial")

    def test_no_results_and_no_errors_is_empty(self):
        health = utils.summarize_collection(0, [], 5)

        self.assertEqual(health["status"], "empty")

    def test_no_results_with_errors_is_error(self):
        health = utils.summarize_collection(0, ["timeout"], 5)

        self.assertEqual(health["status"], "error")

    def test_blocked_source_is_reported_as_blocked(self):
        health = utils.summarize_collection(0, ["account-verification"], 5, blocked=1)

        self.assertEqual(health["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
