import asyncio
import logging
import re
from typing import List, Dict, Any
import requests as http_requests
from bs4 import BeautifulSoup
from curl_cffi import requests
from playwright.async_api import async_playwright
from .utils import clean_price, classify_pc_vram, classify_search_page, classify_ssd_capacity, is_rtx_3060_12gb, is_valid_ram_16gb_ddr4, summarize_collection

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
        self.health = {}

    def _get_session(self) -> requests.Session:
        return requests.Session(impersonate="chrome124")

    # -------------------------------------------------------------
    # 1. COMPUTADORES GAMER
    # -------------------------------------------------------------
    def _fetch_pcs_sync(self) -> List[Dict[str, Any]]:
        results = []
        seen_links = set()
        errors = []
        blocked = 0
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
                    error = f"HTTP {resp.status_code}"
                    errors.append(error)
                    if resp.status_code in (401, 403, 429):
                        blocked += 1
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
                errors.append(str(e))
                logger.warning(f"[Pichau PC] Erro ao buscar {url}: {e}")

        self.health['PC'] = summarize_collection(len(results), errors, len(urls), blocked)
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
        previous = self.health.get('PC', {})
        errors = [previous['detail']] if previous.get('detail') else []
        blocked = 1 if previous.get('status') == 'blocked' else 0
        attempted = previous.get('attempted', 0)
        urls = [
            "https://www.pichau.com.br/computadores/pichau-gamer?rgpu=6359&sort=price-asc",
            "https://www.pichau.com.br/computadores/pichau-gamer",
        ]
        async with async_playwright() as p:
            for url in urls:
                attempted += 1
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
                    response = await page.goto(url, timeout=30000, wait_until="domcontentloaded")
                    if response.status_code != 200:
                        errors.append(f"HTTP {response.status_code}")
                        if response.status_code in (401, 403, 429):
                            blocked += 1
                        await browser.close()
                        continue
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
                    errors.append(str(e))
                    logger.warning(f"[Pichau Playwright Fallback] Erro: {e}")
        self.health['PC'] = summarize_collection(len(results), errors, attempted, blocked)
        return results

    def _fetch_rtx_3060_12gb_sync(self) -> List[Dict[str, Any]]:
        results = []
        seen_links = set()
        errors = []
        blocked = 0
        urls = [
            "https://www.pichau.com.br/search?q=placa+de+video+rtx+3060+12gb&sort=price-asc",
            "https://www.pichau.com.br/search?q=geforce+rtx+3060+12gb&sort=price-asc",
        ]
        session = http_requests.Session()
        for url in urls:
            try:
                response = session.get(
                    url,
                    headers={"Accept-Language": "pt-BR,pt;q=0.9"},
                    timeout=20,
                )
                if response.status_code != 200:
                    errors.append(f"HTTP {response.status_code}")
                    if response.status_code in (401, 403, 429):
                        blocked += 1
                    continue
                soup = BeautifulSoup(response.text, "html.parser")
                cards = soup.select('a[data-cy*="product"], a[href*="/placa-de-video-"]')
                status, detail = classify_search_page(soup.get_text(" ", strip=True), len(cards))
                if status:
                    errors.append(f"{url}: {detail}")
                    if status == "blocked":
                        blocked += 1
                    continue
                for card in cards:
                    href = card.get("href")
                    if not href:
                        continue
                    if not href.startswith("http"):
                        href = f"https://www.pichau.com.br{href}"
                    if href in seen_links:
                        continue
                    raw_text = card.get_text(separator="\n")
                    if "Esgotado" in raw_text:
                        continue
                    lines = [line.strip() for line in raw_text.split("\n") if line.strip()]
                    title = next(
                        (line for line in lines if "RTX" in line.upper() or "3060" in line),
                        lines[0] if lines else "",
                    )
                    if not is_rtx_3060_12gb(title):
                        continue
                    price = None
                    price_el = card.select_one('div[class*="price_vista"]')
                    if price_el:
                        price = clean_price(price_el.get_text())
                    if not price:
                        match = re.search(
                            r'R\$\s*([\d\.,]+)\s*(?:a partir de\s*)?'
                            r'(?:[0-9]+%\s*de\s*desconto\s+no\s+PIX|no\s+PIX|à\s+vista)',
                            raw_text,
                            re.IGNORECASE,
                        )
                        if match:
                            price = clean_price(match.group(1))
                    if not price or not (1000 <= price <= 15000):
                        continue
                    seen_links.add(href)
                    results.append({
                        "title": title,
                        "price": price,
                        "vram": "12GB",
                        "store": "Pichau",
                        "warranty": "Garantia Pichau",
                        "link": href,
                        "category": "GPU",
                    })
            except Exception as error:
                errors.append(str(error))
                logger.warning(f"[Pichau GPU] Erro em {url}: {error}")

        self.health["GPU"] = summarize_collection(len(results), errors, len(urls), blocked)
        return results

    async def get_rtx_3060_12gb(self) -> List[Dict[str, Any]]:
        return await asyncio.to_thread(self._fetch_rtx_3060_12gb_sync)

    # -------------------------------------------------------------
    # 2. SSDs (512GB, 1TB e 2TB)
    # -------------------------------------------------------------
    def _fetch_ssds_sync(self) -> List[Dict[str, Any]]:
        results = []
        seen_links = set()
        errors = []
        blocked = 0
        urls = [
            "https://www.pichau.com.br/hardware/ssd?sort=price-asc",
            "https://www.pichau.com.br/search?q=ssd+512gb",
            "https://www.pichau.com.br/search?q=ssd+1tb",
            "https://www.pichau.com.br/search?q=ssd+2tb",
            "https://www.pichau.com.br/search?q=kingston+nv3",
            "https://www.pichau.com.br/search?q=wd+sn580",
            "https://www.pichau.com.br/search?q=crucial+p3",
        ]
        s = self._get_session()
        for url in urls:
            try:
                resp = s.get(url, headers=self.headers, timeout=20)
                if resp.status_code != 200:
                    errors.append(f"HTTP {resp.status_code}")
                    if resp.status_code in (401, 403, 429):
                        blocked += 1
                    continue
                soup = BeautifulSoup(resp.text, "html.parser")
                cards = soup.select('a[href*="/ssd-"], a[data-cy*="product"]')
                status, detail = classify_search_page(soup.get_text(" ", strip=True), len(cards))
                if status:
                    errors.append(f"{url}: {detail}")
                    if status == "blocked":
                        blocked += 1
                    continue
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
                        valid_prices = [p for p in prices_found if 80 <= p <= 3000]
                        if valid_prices:
                            price = min(valid_prices)
                    if not price or not (80 <= price <= 3000):
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
                errors.append(str(e))
                logger.warning(f"[Pichau SSD] Erro em {url}: {e}")
        self.health['SSD'] = summarize_collection(len(results), errors, len(urls), blocked)
        return results

    async def get_ssds(self) -> List[Dict[str, Any]]:
        return await asyncio.to_thread(self._fetch_ssds_sync)

    # -------------------------------------------------------------
    # 3. MEMÓRIA RAM 16GB DDR4
    # -------------------------------------------------------------
    def _fetch_rams_sync(self) -> List[Dict[str, Any]]:
        results = []
        seen_links = set()
        errors = []
        blocked = 0
        urls = [
            "https://www.pichau.com.br/memoria-mancer-dantalion-16gb-1x16gb-ddr4-3200mhz-cl19-preta-e-branca-mcr-dtl3200-16gb",
            "https://www.pichau.com.br/search?q=memoria+ddr4+16gb&sort=price-asc",
            "https://www.pichau.com.br/search?q=fury+beast+16gb+ddr4",
            "https://www.pichau.com.br/search?q=gammix+d35+16gb",
            "https://www.pichau.com.br/search?q=corsair+vengeance+16gb+ddr4",
            "https://www.pichau.com.br/search?q=crucial+16gb+ddr4",
            "https://www.pichau.com.br/hardware/memorias?capacidade=5645",
            "https://www.pichau.com.br/hardware/memorias",
        ]
        s = self._get_session()
        for url in urls:
            try:
                resp = s.get(url, headers=self.headers, timeout=20)
                if resp.status_code != 200:
                    errors.append(f"HTTP {resp.status_code}")
                    if resp.status_code in (401, 403, 429):
                        blocked += 1
                    continue
                soup = BeautifulSoup(resp.text, "html.parser")
                
                # Se for a página individual do produto (ex: Mancer Dantalion)
                if "/memoria-mancer-dantalion-" in url:
                    title_el = soup.find("h1")
                    title = title_el.get_text().strip() if title_el else "Memoria Mancer Dantalion, 16GB (1x16GB), DDR4, 3200MHz, CL19, Preta e Branca, MCR-DTL3200-16GB"
                    price = None
                    price_vista_el = soup.select_one('div[class*="price_vista"]')
                    if price_vista_el:
                        price = clean_price(price_vista_el.get_text())
                    if not price:
                        m_pix = re.search(r'R\$\s*([\d\.,]+)', resp.text)
                        if m_pix:
                            price = clean_price(m_pix.group(1))
                    if price and 100 <= price <= 1800:
                        seen_links.add(url)
                        results.append({
                            'title': title,
                            'price': price,
                            'store': 'Pichau',
                            'warranty': 'Garantia Pichau',
                            'link': url,
                            'category': 'RAM'
                        })
                    continue

                cards = soup.select('a[href*="/memoria-"], a[data-cy*="product"]')
                status, detail = classify_search_page(soup.get_text(" ", strip=True), len(cards))
                if status:
                    errors.append(f"{url}: {detail}")
                    if status == "blocked":
                        blocked += 1
                    continue
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
                        valid = [p for p in prices_found if 80 <= p <= 1800]
                        if valid:
                            price = min(valid)
                    if not price or not (80 <= price <= 1800):
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
                errors.append(str(e))
                logger.warning(f"[Pichau RAM] Erro em {url}: {e}")
        self.health['RAM'] = summarize_collection(len(results), errors, len(urls), blocked)
        return results

    async def get_ram_16gb_ddr4(self) -> List[Dict[str, Any]]:
        return await asyncio.to_thread(self._fetch_rams_sync)
