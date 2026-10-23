import asyncio
import logging
import re
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from curl_cffi import requests
from playwright.async_api import async_playwright
from .utils import clean_price, classify_pc_vram, classify_ssd_capacity, is_valid_ram_16gb_ddr4

logger = logging.getLogger(__name__)

class PichauScraper:
    def __init__(self):
        self.headers = {
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
        }

    def _get_session(self) -> requests.Session:
        return requests.Session(impersonate="chrome124")

    # -------------------------------------------------------------
    # 1. COMPUTADORES GAMER
    # -------------------------------------------------------------
    def _fetch_pcs_sync(self) -> List[Dict[str, Any]]:
        results = []
        seen_links = set()
        urls = [
            "https://www.pichau.com.br/computadores/pichau-gamer?rgpu=6359&sort=price-asc",
            "https://www.pichau.com.br/computadores/pichau-gamer?rgpu=611&sort=price-asc",
            "https://www.pichau.com.br/computadores/pichau-gamer?sort=price-asc",
            "https://www.pichau.com.br/computadores/pichau-gamer",
        ]
        s = self._get_session()
        for url in urls:
            try:
                resp = s.get(url, headers=self.headers, timeout=20)
                if resp.status_code != 200:
                    logger.warning(f"[Pichau PC] Status {resp.status_code} ao buscar {url}")
                    continue
                    
                soup = BeautifulSoup(resp.text, "html.parser")
                cards = soup.select('a[data-cy*="product"], a[href*="/pc-gamer-"], a[href*="/computador-"]')
                
                for card in cards:
                    href = card.get('href')
                    if not href or href.endswith('/computadores/pichau-gamer'):
                        continue
                    if not href.startswith('http'):
                        href = f"https://www.pichau.com.br{href}"
                    if href in seen_links:
                        continue
                        
                    raw_text = card.get_text(separator="\n")
                    lines = [l.strip() for l in raw_text.split('\n') if l.strip()]
                    
                    title = ""
                    for l in lines:
                        if any(k in l.upper() for k in ["PC GAMER", "COMPUTADOR", "MANCER", "PICHAU"]):
                            title = l
                            break
                    if not title and lines:
                        title = lines[0]
                        
                    vram = classify_pc_vram(title, raw_text)
                    if not vram:
                        continue
                        
                    # Preço à vista no PIX prioritário da Pichau
                    price = None
                    price_vista_el = card.select_one('div[class*="price_vista"]')
                    if price_vista_el:
                        price = clean_price(price_vista_el.get_text())
                        
                    if not price:
                        m_pix = re.search(r'R\$\s*([\d\.,]+)\s*(?:a partir de\s*)?(?:[0-9]+%\s*de\s*desconto\s*no\s*PIX|no\s*PIX|à\s*vista)', raw_text, re.IGNORECASE)
                        if m_pix:
                            price = clean_price(m_pix.group(1))
                            
                    if not price:
                        prices_found = [clean_price(p) for p in re.findall(r'R\$\s*([\d\.,]+)', raw_text) if clean_price(p)]
                        cash_prices = [p for p in prices_found if p >= 1500]
                        if cash_prices:
                            price = min(cash_prices)
                            
                    if not price or price < 1500:
                        continue
                        
                    seen_links.add(href)
                    results.append({
                        'title': title,
                        'price': price,
                        'vram': vram,
                        'store': 'Pichau',
                        'warranty': '12 Meses - Montado e Certificado',
                        'link': href,
                        'category': 'PC'
                    })
            except Exception as e:
                logger.warning(f"[Pichau PC] Erro ao buscar {url}: {e}")
                
        return results

    async def get_gaming_pcs(self) -> List[Dict[str, Any]]:
        """Busca PCs Gamers com curl-impersonate (evitando bloqueios Cloudflare WAF/Turnstile)."""
        try:
            pcs = await asyncio.to_thread(self._fetch_pcs_sync)
            if pcs:
                return pcs
        except Exception as e:
            logger.warning(f"[Pichau PC] curl_cffi falhou, tentando fallback: {e}")
            
        # Fallback via Playwright se necessário
        return await self._get_gaming_pcs_playwright()

    async def _get_gaming_pcs_playwright(self) -> List[Dict[str, Any]]:
        results = []
        seen_links = set()
        urls = [
            "https://www.pichau.com.br/computadores/pichau-gamer?rgpu=6359&sort=price-asc",
            "https://www.pichau.com.br/computadores/pichau-gamer",
        ]
        async with async_playwright() as p:
            for url in urls:
                try:
                    browser = await p.chromium.launch(
                        headless=True,
                        args=['--disable-blink-features=AutomationControlled', '--no-sandbox']
                    )
                    context = await browser.new_context(
                        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                        locale="pt-BR"
                    )
                    page = await context.new_page()
                    await page.goto(url, timeout=30000, wait_until="domcontentloaded")
                    await page.wait_for_timeout(4000)
                    
                    cards = page.locator('a[data-cy*="product"], a[href*="/pc-gamer-"], a[href*="/computador-"]')
                    count = await cards.count()
                    for i in range(count):
                        card = cards.nth(i)
                        href = await card.get_attribute('href')
                        if not href or href.endswith('/computadores/pichau-gamer'):
                            continue
                        if not href.startswith('http'):
                            href = f"https://www.pichau.com.br{href}"
                        if href in seen_links:
                            continue
                        raw_text = await card.inner_text()
                        lines = [l.strip() for l in raw_text.split('\n') if l.strip()]
                        title = ""
                        for l in lines:
                            if any(k in l.upper() for k in ["PC GAMER", "COMPUTADOR", "MANCER", "PICHAU"]):
                                title = l
                                break
                        if not title and lines:
                            title = lines[0]
                        vram = classify_pc_vram(title, raw_text)
                        if not vram:
                            continue
                        price = None
                        price_vista_el = card.locator('div[class*="price_vista"]')
                        if await price_vista_el.count() > 0:
                            price = clean_price(await price_vista_el.first.inner_text())
                        if not price:
                            m_pix = re.search(r'R\$\s*([\d\.,]+)\s*(?:a partir de\s*)?(?:[0-9]+%\s*de\s*desconto\s*no\s*PIX|no\s*PIX|à\s*vista)', raw_text, re.IGNORECASE)
                            if m_pix:
                                price = clean_price(m_pix.group(1))
                        if not price or price < 1500:
                            continue
                        seen_links.add(href)
                        results.append({
                            'title': title,
                            'price': price,
                            'vram': vram,
                            'store': 'Pichau',
                            'warranty': '12 Meses - Montado e Certificado',
                            'link': href,
                            'category': 'PC'
                        })
                    await browser.close()
                    await asyncio.sleep(2)
                except Exception as e:
                    logger.warning(f"[Pichau Playwright Fallback] Erro: {e}")
        return results

    # -------------------------------------------------------------
    # 2. SSDs (512GB e 1TB)
    # -------------------------------------------------------------
    def _fetch_ssds_sync(self) -> List[Dict[str, Any]]:
        results = []
        seen_links = set()
        urls = [
            "https://www.pichau.com.br/hardware/ssd?sort=price-asc",
            "https://www.pichau.com.br/search?q=ssd+512gb",
            "https://www.pichau.com.br/search?q=ssd+1tb",
        ]
        s = self._get_session()
        for url in urls:
            try:
                resp = s.get(url, headers=self.headers, timeout=20)
                if resp.status_code != 200:
                    continue
                soup = BeautifulSoup(resp.text, "html.parser")
                cards = soup.select('a[href*="/ssd-"], a[data-cy*="product"]')
                for card in cards:
                    href = card.get('href')
                    if not href or href.endswith('/hardware/ssd'):
                        continue
                    if not href.startswith('http'):
                        href = f"https://www.pichau.com.br{href}"
                    if href in seen_links:
                        continue
                    raw_text = card.get_text(separator="\n")
                    if "Esgotado" in raw_text:
                        continue
                    lines = [l.strip() for l in raw_text.split('\n') if l.strip()]
                    title = ""
                    for l in lines:
                        if "SSD" in l.upper():
                            title = l
                            break
                    if not title and lines:
                        title = lines[0]
                    cap = classify_ssd_capacity(title)
                    if not cap:
                        continue
                    price = None
                    price_vista_el = card.select_one('div[class*="price_vista"]')
                    if price_vista_el:
                        price = clean_price(price_vista_el.get_text())
                    if not price:
                        m_pix = re.search(r'R\$\s*([\d\.,]+)\s*(?:a partir de\s*)?(?:[0-9]+%\s*de\s*desconto\s*no\s*PIX|no\s*PIX|à\s*vista)', raw_text, re.IGNORECASE)
                        if m_pix:
                            price = clean_price(m_pix.group(1))
                    if not price:
                        prices_found = [clean_price(p) for p in re.findall(r'R\$\s*([\d\.,]+)', raw_text) if clean_price(p)]
                        valid_prices = [p for p in prices_found if 80 <= p <= 1500]
                        if valid_prices:
                            price = min(valid_prices)
                    if not price or not (80 <= price <= 1500):
                        continue
                    seen_links.add(href)
                    results.append({
                        'title': title,
                        'price': price,
                        'capacity': cap,
                        'store': 'Pichau',
                        'warranty': 'Garantia Pichau',
                        'link': href,
                        'category': 'SSD'
                    })
            except Exception as e:
                logger.warning(f"[Pichau SSD] Erro em {url}: {e}")
        return results

    async def get_ssds(self) -> List[Dict[str, Any]]:
        return await asyncio.to_thread(self._fetch_ssds_sync)

    # -------------------------------------------------------------
    # 3. MEMÓRIA RAM 16GB DDR4
    # -------------------------------------------------------------
    def _fetch_rams_sync(self) -> List[Dict[str, Any]]:
        results = []
        seen_links = set()
        urls = [
            "https://www.pichau.com.br/search?q=memoria+ddr4+16gb&sort=price-asc",
            "https://www.pichau.com.br/hardware/memorias?capacidade=5645",
            "https://www.pichau.com.br/hardware/memorias",
        ]
        s = self._get_session()
        for url in urls:
            try:
                resp = s.get(url, headers=self.headers, timeout=20)
                if resp.status_code != 200:
                    continue
                soup = BeautifulSoup(resp.text, "html.parser")
                cards = soup.select('a[href*="/memoria-"], a[data-cy*="product"]')
                for card in cards:
                    href = card.get('href')
                    if not href or href.endswith('/hardware/memorias'):
                        continue
                    if not href.startswith('http'):
                        href = f"https://www.pichau.com.br{href}"
                    if href in seen_links:
                        continue
                    raw_text = card.get_text(separator="\n")
                    if "Esgotado" in raw_text:
                        continue
                    lines = [l.strip() for l in raw_text.split('\n') if l.strip()]
                    title = ""
                    for l in lines:
                        if "MEMORIA" in l.upper() or "DDR4" in l.upper():
                            title = l
                            break
                    if not title and lines:
                        title = lines[0]
                    if not is_valid_ram_16gb_ddr4(title):
                        continue
                    price = None
                    price_vista_el = card.select_one('div[class*="price_vista"]')
                    if price_vista_el:
                        price = clean_price(price_vista_el.get_text())
                    if not price:
                        m_pix = re.search(r'R\$\s*([\d\.,]+)\s*(?:a partir de\s*)?(?:[0-9]+%\s*de\s*desconto\s*no\s*PIX|no\s*PIX|à\s*vista)', raw_text, re.IGNORECASE)
                        if m_pix:
                            price = clean_price(m_pix.group(1))
                    if not price:
                        prices_found = [clean_price(p) for p in re.findall(r'R\$\s*([\d\.,]+)', raw_text) if clean_price(p)]
                        valid = [p for p in prices_found if 80 <= p <= 1000]
                        if valid:
                            price = min(valid)
                    if not price or not (80 <= price <= 1000):
                        continue
                    seen_links.add(href)
                    results.append({
                        'title': title,
                        'price': price,
                        'store': 'Pichau',
                        'warranty': 'Garantia Pichau',
                        'link': href,
                        'category': 'RAM'
                    })
            except Exception as e:
                logger.warning(f"[Pichau RAM] Erro em {url}: {e}")
        return results

    async def get_ram_16gb_ddr4(self) -> List[Dict[str, Any]]:
        return await asyncio.to_thread(self._fetch_rams_sync)
