import os
import sys
import asyncio
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
    format_currency
)
from notifier import send_email_alert

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("RadarHardware")

async def run_radar():
    logger.info("=" * 60)
    logger.info("Iniciando Radar de Precos: PCs, SSDs e RAMs 16GB DDR4")
    logger.info("=" * 60)

    all_pcs: List[Dict[str, Any]] = []
    all_ssds: List[Dict[str, Any]] = []
    all_rams: List[Dict[str, Any]] = []

    # 1. Kabum (Requests / Next.js)
    try:
        logger.info("[1/5] Buscando ofertas na Kabum...")
        kabum = KabumScraper()
        kabum_pcs = kabum.get_gaming_pcs()
        kabum_ssds = kabum.get_ssds()
        kabum_rams = kabum.get_ram_16gb_ddr4()
        all_pcs.extend(kabum_pcs)
        all_ssds.extend(kabum_ssds)
        all_rams.extend(kabum_rams)
        logger.info(f"  -> Kabum: {len(kabum_pcs)} PCs, {len(kabum_ssds)} SSDs, {len(kabum_rams)} RAMs 16GB DDR4")
    except Exception as e:
        logger.error(f"Erro na Kabum: {e}")

    # 2. Terabyte (Requests / HTML)
    try:
        logger.info("[2/5] Buscando ofertas na TerabyteShop...")
        terabyte = TerabyteScraper()
        tb_pcs = terabyte.get_gaming_pcs()
        tb_ssds = terabyte.get_ssds()
        tb_rams = terabyte.get_ram_16gb_ddr4()
        all_pcs.extend(tb_pcs)
        all_ssds.extend(tb_ssds)
        all_rams.extend(tb_rams)
        logger.info(f"  -> Terabyte: {len(tb_pcs)} PCs, {len(tb_ssds)} SSDs, {len(tb_rams)} RAMs 16GB DDR4")
    except Exception as e:
        logger.error(f"Erro na Terabyte: {e}")

    # 3. Pichau (Playwright)
    try:
        logger.info("[3/5] Buscando ofertas na Pichau...")
        pichau = PichauScraper()
        pichau_pcs = await pichau.get_gaming_pcs()
        pichau_ssds = await pichau.get_ssds()
        pichau_rams = await pichau.get_ram_16gb_ddr4()
        all_pcs.extend(pichau_pcs)
        all_ssds.extend(pichau_ssds)
        all_rams.extend(pichau_rams)
        logger.info(f"  -> Pichau: {len(pichau_pcs)} PCs, {len(pichau_ssds)} SSDs, {len(pichau_rams)} RAMs 16GB DDR4")
    except Exception as e:
        logger.error(f"Erro na Pichau: {e}")

    # 4. Amazon (Playwright)
    try:
        logger.info("[4/5] Buscando ofertas na Amazon...")
        amazon = AmazonScraper()
        amz_ssds = await amazon.get_ssds()
        amz_rams = await amazon.get_ram_16gb_ddr4()
        all_ssds.extend(amz_ssds)
        all_rams.extend(amz_rams)
        logger.info(f"  -> Amazon: {len(amz_ssds)} SSDs, {len(amz_rams)} RAMs 16GB DDR4")
    except Exception as e:
        logger.error(f"Erro na Amazon: {e}")

    # 5. Mercado Livre (Playwright)
    try:
        logger.info("[5/5] Buscando ofertas no Mercado Livre...")
        ml = MercadoLivreScraper()
        ml_ssds = await ml.get_ssds()
        ml_rams = await ml.get_ram_16gb_ddr4()
        all_ssds.extend(ml_ssds)
        all_rams.extend(ml_rams)
        logger.info(f"  -> Mercado Livre: {len(ml_ssds)} SSDs, {len(ml_rams)} RAMs 16GB DDR4")
    except Exception as e:
        logger.error(f"Erro no Mercado Livre: {e}")

    # Organização e Ordenação por Menor Preço
    pcs_8gb = sorted([p for p in all_pcs if p.get('vram') == '8GB'], key=lambda x: x['price'])
    pcs_12gb = sorted([p for p in all_pcs if p.get('vram') == '12GB'], key=lambda x: x['price'])
    pcs_16gb = sorted([p for p in all_pcs if p.get('vram') == '16GB'], key=lambda x: x['price'])

    ssds_512 = sorted([s for s in all_ssds if s.get('capacity') == '512GB'], key=lambda x: x['price'])
    ssds_1tb = sorted([s for s in all_ssds if s.get('capacity') == '1TB'], key=lambda x: x['price'])

    rams_16gb = sorted(all_rams, key=lambda x: x['price'])

    # Resumo no terminal
    print("\n" + "=" * 60)
    print("RESULTADOS DOS MENORES PRECOS ENCONTRADOS")
    print("=" * 60)
    
    print("\n[PCs COM 8GB VRAM]:")
    for p in pcs_8gb[:5]:
        print(f"  [{p['store']}] {format_currency(p['price'])} - {p['title'][:65]}")
        
    print("\n[PCs COM 12GB VRAM]:")
    for p in pcs_12gb[:5]:
        print(f"  [{p['store']}] {format_currency(p['price'])} - {p['title'][:65]}")

    print("\n[PCs COM 16GB VRAM]:")
    for p in pcs_16gb[:5]:
        print(f"  [{p['store']}] {format_currency(p['price'])} - {p['title'][:65]}")

    print("\n[MEMORIAS RAM 16GB DDR4 GAMER]:")
    for r in rams_16gb[:8]:
        print(f"  [{r['store']}] {format_currency(r['price'])} - {r['title'][:65]}")

    print("\n[SSDs 512GB]:")
    for s in ssds_512[:5]:
        print(f"  [{s['store']}] {format_currency(s['price'])} - {s['title'][:65]}")

    print("\n[SSDs 1TB]:")
    for s in ssds_1tb[:5]:
        print(f"  [{s['store']}] {format_currency(s['price'])} - {s['title'][:65]}")
        
    print("=" * 60 + "\n")

    # Envio do e-mail e geração de relatório
    report_data = {
        'pcs_8gb': pcs_8gb,
        'pcs_12gb': pcs_12gb,
        'pcs_16gb': pcs_16gb,
        'rams_16gb': rams_16gb,
        'ssds_512': ssds_512,
        'ssds_1tb': ssds_1tb,
    }

    send_email_alert(report_data)

if __name__ == "__main__":
    asyncio.run(run_radar())
