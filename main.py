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
    format_currency,
    extract_gpu_name,
    get_ai_recommendation,
    analyze_pc_ram_upgrade,
    check_pichau_bundle_32gb_options
)
from notifier import send_email_alert

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("RadarHardware")

def enrich_ai_pc_details(item: Dict[str, Any]) -> Dict[str, Any]:
    """Enriquece informações de placa-mãe, slots e verifica se o configurador da loja permite vir montado com 32GB."""
    import re
    url = item.get('link', '')
    title = item.get('title', '')
    price = float(item.get('price', 0))
    desc_detail = ""
    
    if url and item.get('store') == 'Pichau':
        try:
            from curl_cffi import requests as cffi_requests
            from bs4 import BeautifulSoup
            session = cffi_requests.Session(impersonate="chrome124")
            headers = {"Accept-Language": "pt-BR,pt;q=0.9"}
            r = session.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                html = r.text
                soup = BeautifulSoup(html, "html.parser")
                m_h3 = re.search(r'<h3[^>]*>\s*PLACA\s*M[ÃA]E\s*([^<]+)</h3>', html, re.IGNORECASE)
                mobo = ""
                if m_h3:
                    mobo = m_h3.group(1).strip()
                else:
                    m_chip = re.search(r'\b(H510M?|A520M?|H610M?|B450M?|B550M?|B760M?|B650M?|A320M?|H310M?|B360M?|Z690|Z790)\b', html, re.IGNORECASE)
                    if m_chip:
                        mobo = m_chip.group(1).upper()
                imgs = [img.get('src', '') for img in soup.find_all('img')]
                has_2x = any('2x' in img.lower() and 'memoria' in img.lower() for img in imgs)
                has_1x = any(('1x' in img.lower() or '-1x' in img.lower()) and 'memoria' in img.lower() for img in imgs)
                if mobo:
                    desc_detail += f"PLACA MÃE {mobo} "
                if has_1x:
                    desc_detail += "1x16GB "
                elif has_2x:
                    desc_detail += "2x8GB "
        except Exception:
            pass

    ram_info = analyze_pc_ram_upgrade(title, desc_detail, price)
    
    # Consulta se o configurador da loja permite vir montado de fábrica com 32GB
    if url and item.get('store') == 'Pichau':
        site_custom = check_pichau_bundle_32gb_options(url, price)
        ram_info['site_custom'] = site_custom

    item['ram_info'] = ram_info
    return item

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

    # Ranking de Custo-Benefício para Servidores de IA (Exclusivo NVIDIA 12GB e 16GB)
    ai_pcs = []
    seen_ai_links = set()
    for p in (pcs_12gb + pcs_16gb):
        link = p.get('link', '')
        if link in seen_ai_links:
            continue
        seen_ai_links.add(link)
        vram_num = 16 if p.get('vram') == '16GB' else 12
        price = float(p.get('price', 0))
        cost_per_gb = round(price / vram_num, 2)
        gpu_name = extract_gpu_name(p['title'])
        ai_recommendation = get_ai_recommendation(gpu_name, vram_num)
        ai_pcs.append({
            **p,
            'vram_num': vram_num,
            'cost_per_gb': cost_per_gb,
            'gpu_name': gpu_name,
            'ai_recommendation': ai_recommendation
        })
    ai_ranking = sorted(ai_pcs, key=lambda x: (x['cost_per_gb'], x['price']))

    # Enriquecimento assíncrono dos melhores PCs de IA com análise de upgrade de RAM para 32GB
    if ai_ranking:
        logger.info("Analisando especificações de placa-mãe e upgrade para 32GB nos melhores PCs de IA...")
        ai_top = ai_ranking[:8]
        tasks = [asyncio.to_thread(enrich_ai_pc_details, p) for p in ai_top]
        enriched_top = await asyncio.gather(*tasks)
        ai_ranking = enriched_top + ai_ranking[8:]

    ssds_512 = sorted([s for s in all_ssds if s.get('capacity') == '512GB'], key=lambda x: x['price'])
    ssds_1tb = sorted([s for s in all_ssds if s.get('capacity') == '1TB'], key=lambda x: x['price'])

    rams_16gb = sorted(all_rams, key=lambda x: x['price'])

    # Resumo no terminal
    print("\n" + "=" * 60)
    print("RESULTADOS DOS MENORES PRECOS ENCONTRADOS")
    print("=" * 60)
    
    print("\n[RANKING CUSTO-BENEFICIO: SERVIDORES DE IA (NVIDIA 12GB / 16GB)]:")
    for rank, p in enumerate(ai_ranking[:6], 1):
        ram_info = p.get('ram_info') or {}
        site_custom = ram_info.get('site_custom') or {}
        est_tot = ram_info.get('est_total_32gb', p['price'])
        print(f"  #{rank} [R$ {p['cost_per_gb']:.2f}/GB] {format_currency(p['price'])} - [{p['store']}] {p['gpu_name']} ({p['title'][:45]}...)")
        print(f"     -> Placa: {ram_info.get('mobo', 'M-ATX')} ({ram_info.get('slots', 2)} slots) | RAM Padrão: {ram_info.get('ram_desc', '16GB')}")
        if site_custom:
            site_status = site_custom.get('site_status_label', 'Indisponível no site')
            site_tot = site_custom.get('site_assembled_total', p['price'])
            print(f"     -> Montado de Fábrica no Site: {site_status} (Total: {format_currency(site_tot)})")
        print(f"     -> Upgrade Manual: {ram_info.get('status_label', 'N/D')} [Total Estimado: {format_currency(est_tot)}]")
        print(f"     -> Recomendação IA: {p['ai_recommendation']}")

    print("\n[PCs COM 12GB VRAM - EXCLUSIVO NVIDIA]:")
    for p in pcs_12gb[:8]:
        print(f"  [{p['store']}] {format_currency(p['price'])} - {p['title'][:65]}")

    print("\n[PCs COM 16GB VRAM - EXCLUSIVO NVIDIA]:")
    for p in pcs_16gb[:8]:
        print(f"  [{p['store']}] {format_currency(p['price'])} - {p['title'][:65]}")

    print("\n[PCs COM 8GB VRAM - NVIDIA E AMD]:")
    for p in pcs_8gb[:8]:
        print(f"  [{p['store']}] {format_currency(p['price'])} - {p['title'][:65]}")

    print("\n[MEMORIAS RAM 16GB DDR4 GAMER]:")
    for r in rams_16gb[:10]:
        print(f"  [{r['store']}] {format_currency(r['price'])} - {r['title'][:65]}")

    print("\n[SSDs 512GB]:")
    for s in ssds_512[:8]:
        print(f"  [{s['store']}] {format_currency(s['price'])} - {s['title'][:65]}")

    print("\n[SSDs 1TB]:")
    for s in ssds_1tb[:8]:
        print(f"  [{s['store']}] {format_currency(s['price'])} - {s['title'][:65]}")
        
    print("=" * 60 + "\n")

    # Envio do e-mail e geração de relatório
    report_data = {
        'ai_ranking': ai_ranking,
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
