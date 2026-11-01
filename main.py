import os
import sys
import re
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
    check_pichau_bundle_32gb_options,
    is_top_brand_ram,
    is_preferred_nvme_model,
    is_nvme_ssd
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

    # Ranking de Custo-Benefício para Servidores de IA (Exclusivo NVIDIA 12GB e 16GB + OBRIGATÓRIO 32GB+ MONTADO)
    logger.info("Filtrando e verificando compatibilidade de 32GB RAM montado de fábrica nos PCs de IA...")
    ai_candidates = []
    seen_ai_links = set()
    for p in (pcs_12gb + pcs_16gb):
        link = p.get('link', '')
        if link in seen_ai_links:
            continue
        seen_ai_links.add(link)
        ai_candidates.append(p)

    # Executa verificação de todos os candidatos em paralelo
    tasks = [asyncio.to_thread(enrich_ai_pc_details, p) for p in ai_candidates]
    enriched_candidates = await asyncio.gather(*tasks)

    ai_ranking = []
    for p in enriched_candidates:
        title = p.get('title', '')
        base_price = float(p.get('price', 0))
        vram_num = 16 if p.get('vram') == '16GB' else 12
        ram_info = p.get('ram_info') or {}
        site_custom = ram_info.get('site_custom') or {}
        
        # 1. Verifica se já vem com 32GB/64GB nativos de fábrica
        is_native_32gb = bool(re.search(r'\b(32|64)\s*GB\b', title.upper()) and not re.search(r'VRAM|RTX|GEFORCE|RADEON|RX', title.upper()))
        # 2. Verifica se o configurador da loja permite alterar para 32GB
        is_custom_32gb = site_custom.get('site_customization_available', False)

        # Filtro restritivo: SOMENTE PCs que venham ou possam ser alterados para 32GB+ montados
        if not (is_native_32gb or is_custom_32gb):
            continue

        if is_native_32gb:
            final_price = base_price
            custom_diff = 0.0
            ram_status_tag = "32GB Nativo de Fábrica"
        else:
            final_price = site_custom.get('site_assembled_total', base_price)
            custom_diff = site_custom.get('site_diff_price', 0.0)
            ram_status_tag = f"+R$ {custom_diff:,.2f} ({site_custom.get('site_option_title', '')[:32]}...)"

        cost_per_gb = round(final_price / vram_num, 2)
        gpu_name = extract_gpu_name(title)
        ai_recommendation = get_ai_recommendation(gpu_name, vram_num)

        ai_ranking.append({
            **p,
            'vram_num': vram_num,
            'cost_per_gb': cost_per_gb,
            'gpu_name': gpu_name,
            'ai_recommendation': ai_recommendation,
            'final_price_32gb': final_price,
            'custom_diff': custom_diff,
            'is_native_32gb': is_native_32gb,
            'ram_status_tag': ram_status_tag
        })

    # Ordena pelo melhor custo-benefício de VRAM já considerando a máquina montada com 32GB!
    ai_ranking = sorted(ai_ranking, key=lambda x: (x['cost_per_gb'], x['final_price_32gb']))

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
    
    print("\n[RANKING CUSTO-BENEFICIO: SERVIDORES DE IA (NVIDIA 12GB / 16GB + 32GB RAM MONTADO)]:")
    if not ai_ranking:
        print("  Nenhum PC com 32GB montado encontrado.")
    for rank, p in enumerate(ai_ranking[:8], 1):
        ram_info = p.get('ram_info') or {}
        final_price = p.get('final_price_32gb', p['price'])
        print(f"  #{rank} [R$ {p['cost_per_gb']:.2f}/GB] Montado c/ 32GB: {format_currency(final_price)} (Base: {format_currency(p['price'])})")
        print(f"     [{p['store']}] {p['gpu_name']} - {p['title'][:55]}...")
        print(f"     -> Placa: {ram_info.get('mobo', 'M-ATX')} ({ram_info.get('slots', 2)} slots) | Status 32GB: {p.get('ram_status_tag')}")
        print(f"     -> Recomendação IA: {p['ai_recommendation']}")

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
        'ai_ranking': ai_ranking,
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
    }

    send_email_alert(report_data)

if __name__ == "__main__":
    asyncio.run(run_radar())
