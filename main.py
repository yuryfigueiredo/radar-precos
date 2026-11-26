import os
import sys
import asyncio
import inspect
import logging
from typing import Dict, List, Any
from dotenv import load_dotenv

# Garante suporte a UTF-8 no terminal Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Carrega variáveis locais de .env se existir
load_dotenv()

from scrapers import (
    KabumScraper,
    TerabyteScraper,
    PichauScraper,
    AmazonScraper,
    MercadoLivreScraper,
    format_currency,
    is_top_brand_ram,
    is_preferred_nvme_model,
    is_nvme_ssd,
    summarize_collection
)
from notifier import send_email_alert

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("RadarHardware")

def get_collection_health(scraper: Any, category: str, count: int) -> Dict[str, Any]:
    scraper_health = getattr(scraper, 'health', {})
    category_health = scraper_health.get(category) if isinstance(scraper_health, dict) else None
    if isinstance(category_health, dict):
        health = dict(category_health)
        health['count'] = count
        return health
    return summarize_collection(count, [], 1)

async def collect_category(store: str, category: str, scraper: Any, fetch: Any) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    try:
        items = fetch()
        if inspect.isawaitable(items):
            items = await items
        health = get_collection_health(scraper, category, len(items))
        logger.info(f"  -> {store} {category}: {len(items)} item(ns) [{health['status']}]")
        if health['status'] not in ('ok', 'empty', 'not_collected'):
            logger.warning(f"Saúde da fonte {store}/{category}: {health['detail'] or health['status']}")
        return items, health
    except Exception as e:
        logger.error(f"Erro em {store}/{category}: {e}")
        return [], summarize_collection(0, [str(e)], 1)

async def run_radar():
    logger.info("=" * 60)
    logger.info("Iniciando Radar de Precos: RTX 3060 12GB, SSDs e RAMs 16GB DDR4")
    logger.info("=" * 60)

    all_ssds: List[Dict[str, Any]] = []
    all_rams: List[Dict[str, Any]] = []
    all_rtx_3060_12gb: List[Dict[str, Any]] = []

    source_health: Dict[str, Dict[str, Dict[str, Any]]] = {}
    stores = [
        ("Kabum", KabumScraper, {"GPU": "get_rtx_3060_12gb", "SSD": "get_ssds", "RAM": "get_ram_16gb_ddr4"}),
        ("TerabyteShop", TerabyteScraper, {"GPU": "get_rtx_3060_12gb", "SSD": "get_ssds", "RAM": "get_ram_16gb_ddr4"}),
        ("Pichau", PichauScraper, {"GPU": "get_rtx_3060_12gb", "SSD": "get_ssds", "RAM": "get_ram_16gb_ddr4"}),
        ("Amazon", AmazonScraper, {"GPU": "get_rtx_3060_12gb", "SSD": "get_ssds", "RAM": "get_ram_16gb_ddr4"}),
        ("Mercado Livre", MercadoLivreScraper, {"GPU": "get_rtx_3060_12gb", "SSD": "get_ssds", "RAM": "get_ram_16gb_ddr4"}),
    ]
    category_lists = {"GPU": all_rtx_3060_12gb, "SSD": all_ssds, "RAM": all_rams}

    for index, (store, scraper_class, categories) in enumerate(stores, 1):
        logger.info(f"[{index}/5] Buscando ofertas na {store}...")
        source_health[store] = {}
        try:
            scraper = scraper_class()
        except Exception as e:
            logger.error(f"Erro ao inicializar {store}: {e}")
            for category in categories:
                source_health[store][category] = summarize_collection(0, [str(e)], 1)
            continue

        for category, method_name in categories.items():
            items, health = await collect_category(store, category, scraper, getattr(scraper, method_name))
            category_lists[category].extend(items)
            source_health[store][category] = health

    rtx_3060_12gb = sorted(all_rtx_3060_12gb, key=lambda item: item["price"])

    # Separação e categorização inteligente de Memórias RAM 16GB DDR4
    # 1. Mancer Dantalion (sempre no topo se disponível)
    mancer_dantalion = [r for r in all_rams if "DANTALION" in r.get('title', '').upper()]
    # 2. Marcas Preferidas (Kingston Fury Beast, XPG Gammix D35, Corsair Vengeance LPX, Crucial)
    top_brand_rams = sorted([r for r in all_rams if is_top_brand_ram(r.get('title', '')) and r not in mancer_dantalion], key=lambda x: x['price'])
    # 3. Mais baratas gerais
    cheapest_rams = sorted([r for r in all_rams if r not in mancer_dantalion and r not in top_brand_rams], key=lambda x: x['price'])
    # Lista combinada para exibição/histórico
    rams_16gb = (mancer_dantalion[:1] if mancer_dantalion else []) + top_brand_rams + cheapest_rams

    # Separação e categorização de Armazenamento SSD
    # 1. NVMe Custo-Benefício Destaques (1TB e 2TB: Kingston NV3, WD Blue SN580, Crucial P3 Plus)
    nvme_top_1tb = sorted([s for s in all_ssds if s.get('capacity') == '1TB' and is_preferred_nvme_model(s.get('title', ''))], key=lambda x: x['price'])
    nvme_top_2tb = sorted([s for s in all_ssds if s.get('capacity') == '2TB' and is_preferred_nvme_model(s.get('title', ''))], key=lambda x: x['price'])
    
    # 2. NVMe Gerais (1TB e 2TB)
    nvme_general_1tb = sorted([s for s in all_ssds if s.get('capacity') == '1TB' and is_nvme_ssd(s.get('title', '')) and s not in nvme_top_1tb], key=lambda x: x['price'])
    nvme_general_2tb = sorted([s for s in all_ssds if s.get('capacity') == '2TB' and is_nvme_ssd(s.get('title', '')) and s not in nvme_top_2tb], key=lambda x: x['price'])

    # 3. SSDs Mais Baratos Gerais (por capacidade)
    ssds_512 = sorted([s for s in all_ssds if s.get('capacity') == '512GB'], key=lambda x: x['price'])
    ssds_1tb = sorted([s for s in all_ssds if s.get('capacity') == '1TB'], key=lambda x: x['price'])
    ssds_2tb = sorted([s for s in all_ssds if s.get('capacity') == '2TB'], key=lambda x: x['price'])

    # Resumo no terminal
    print("\n" + "=" * 60)
    print("RESULTADOS DOS MENORES PRECOS ENCONTRADOS")
    print("=" * 60)
    
    if rtx_3060_12gb:
        print("\n[NVIDIA RTX 3060 12GB (MAIS BARATAS)]:")
        for gpu in rtx_3060_12gb[:6]:
            print(f"  [{gpu['store']}] {format_currency(gpu['price'])} - {gpu['title'][:65]}")

    if mancer_dantalion:
        print("\n[MEMORIA MANCER DANTALION 16GB (DESTAQUE FIXO)]:")
        for r in mancer_dantalion[:2]:
            print(f"  [{r['store']}] {format_currency(r['price'])} - {r['title'][:65]}")

    print("\n[MEMORIAS RAM 16GB DDR4 (MARCAS PREFERIDAS: KINGSTON FURY, XPG D35, CORSAIR LPX, CRUCIAL)]:")
    for r in top_brand_rams[:6]:
        print(f"  [{r['store']}] {format_currency(r['price'])} - {r['title'][:65]}")

    print("\n[MEMORIAS RAM 16GB DDR4 (MAIS BARATAS GERAIS)]:")
    for r in cheapest_rams[:6]:
        print(f"  [{r['store']}] {format_currency(r['price'])} - {r['title'][:65]}")

    print("\n[SSDs NVMe 1TB CUSTO-BENEFÍCIO (KINGSTON NV3, WD SN580, CRUCIAL P3)]:")
    for s in nvme_top_1tb[:6]:
        print(f"  [{s['store']}] {format_currency(s['price'])} - {s['title'][:65]}")

    print("\n[SSDs NVMe 2TB CUSTO-BENEFÍCIO (KINGSTON NV3, WD SN580, CRUCIAL P3)]:")
    for s in nvme_top_2tb[:6]:
        print(f"  [{s['store']}] {format_currency(s['price'])} - {s['title'][:65]}")

    print("\n[SSDs 1TB (MAIS BARATOS GERAIS)]:")
    for s in ssds_1tb[:6]:
        print(f"  [{s['store']}] {format_currency(s['price'])} - {s['title'][:65]}")

    print("\n[SSDs 2TB (MAIS BARATOS GERAIS)]:")
    for s in ssds_2tb[:6]:
        print(f"  [{s['store']}] {format_currency(s['price'])} - {s['title'][:65]}")

    print("\n[SSDs 512GB (MAIS BARATOS GERAIS)]:")
    for s in ssds_512[:6]:
        print(f"  [{s['store']}] {format_currency(s['price'])} - {s['title'][:65]}")
        
    print("=" * 60 + "\n")

    # Envio do e-mail e geração de relatório
    report_data = {
        'rtx_3060_12gb': rtx_3060_12gb,
        'mancer_dantalion': mancer_dantalion,
        'top_brand_rams': top_brand_rams,
        'cheapest_rams': cheapest_rams,
        'rams_16gb': rams_16gb,
        'nvme_top_1tb': nvme_top_1tb,
        'nvme_top_2tb': nvme_top_2tb,
        'nvme_general_1tb': nvme_general_1tb,
        'nvme_general_2tb': nvme_general_2tb,
        'ssds_1tb': ssds_1tb,
        'ssds_2tb': ssds_2tb,
        'ssds_512': ssds_512,
        'source_health': source_health,
    }

    report_keys = (
        'rtx_3060_12gb', 'mancer_dantalion', 'top_brand_rams', 'cheapest_rams',
        'nvme_top_1tb', 'nvme_top_2tb', 'nvme_general_1tb', 'nvme_general_2tb',
        'ssds_1tb', 'ssds_2tb', 'ssds_512'
    )
    if not any(report_data[key] for key in report_keys):
        logger.error("Nenhuma fonte retornou dados utilizáveis para o relatório.")
        raise RuntimeError("Nenhuma fonte retornou dados utilizáveis para o relatório.")

    if not send_email_alert(report_data):
        raise RuntimeError("Falha no envio do e-mail; a execução foi reprovada.")
    return report_data

if __name__ == "__main__":
    asyncio.run(run_radar())
