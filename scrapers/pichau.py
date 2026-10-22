import logging
import re
from typing import List, Dict, Any
from playwright.async_api import async_playwright
from .utils import clean_price, classify_pc_vram, classify_ssd_capacity, is_valid_ram_16gb_ddr4

logger = logging.getLogger(__name__)

class PichauScraper:
    async def get_gaming_pcs(self) -> List[Dict[str, Any]]:
        """Busca PCs Gamers montados e certificados na Pichau."""
        results = []
        seen_links = set()
        urls = [
            "https://www.pichau.com.br/computadores/pichau-gamer?sort=price-asc",
            "https://www.pichau.com.br/search?q=computador+gamer+rx+6600&sort=price-asc",
            "https://www.pichau.com.br/search?q=computador+gamer+rtx+4060&sort=price-asc",
            "https://www.pichau.com.br/search?q=computador+gamer+rtx+3060&sort=price-asc"
        ]
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=['--disable-blink-features=AutomationControlled', '--no-sandbox']
            )
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            
            for url in urls:
                try:
                    await page.goto(url, timeout=30000, wait_until="domcontentloaded")
                    await page.wait_for_timeout(3000)
                    
                    cards = page.locator('a[href*="/computador-"]')
                    count = await cards.count()
                    
                    for i in range(min(count, 15)):
                        card = cards.nth(i)
                        href = await card.get_attribute('href')
                        if not href:
                            continue
                        if not href.startswith('http'):
                            href = f"https://www.pichau.com.br{href}"
                        if href in seen_links:
                            continue
                            
                        raw_text = await card.inner_text()
                        lines = [l.strip() for l in raw_text.split('\n') if l.strip()]
                        
                        title = ""
                        for l in lines:
                            if "PC" in l or "Gamer" in l or "Intel" in l or "AMD" in l or "Ryzen" in l:
                                title = l
                                break
                        if not title and lines:
                            title = lines[0]
                            
                        vram = classify_pc_vram(title, raw_text)
                        if not vram:
                            continue
                            
                        prices_found = re.findall(r'R\$\s*([\d\.,]+)', raw_text)
                        parsed_prices = [clean_price(p) for p in prices_found if clean_price(p)]
                        if not parsed_prices:
                            continue
                            
                        price = min(parsed_prices)
                        if price < 1500:
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
                    logger.warning(f"[Pichau] Aviso ao acessar {url}: {e}")
                    
            await browser.close()
            
        return results

    async def get_ssds(self) -> List[Dict[str, Any]]:
        """Busca SSDs de 512GB e 1TB na Pichau."""
        results = []
        seen_links = set()
        urls = [
            "https://www.pichau.com.br/hardware/ssd?sort=price-asc",
            "https://www.pichau.com.br/search?q=ssd+1tb&sort=price-asc"
        ]
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=['--disable-blink-features=AutomationControlled', '--no-sandbox']
            )
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            
            for url in urls:
                try:
                    await page.goto(url, timeout=30000, wait_until="domcontentloaded")
                    await page.wait_for_timeout(3000)
                    
                    cards = page.locator('a[href*="/ssd-"]')
                    count = await cards.count()
                    
                    for i in range(min(count, 20)):
                        card = cards.nth(i)
                        href = await card.get_attribute('href')
                        if not href:
                            continue
                        if not href.startswith('http'):
                            href = f"https://www.pichau.com.br{href}"
                        if href in seen_links:
                            continue
                            
                        raw_text = await card.inner_text()
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
                            
                        prices_found = re.findall(r'R\$\s*([\d\.,]+)', raw_text)
                        parsed_prices = [clean_price(p) for p in prices_found if clean_price(p)]
                        if not parsed_prices:
                            continue
                            
                        price = min(parsed_prices)
                        if not (80 <= price <= 1500):
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
                    logger.warning(f"[Pichau SSD] Aviso ao acessar {url}: {e}")
                    
            await browser.close()
            
        return results

    async def get_ram_16gb_ddr4(self) -> List[Dict[str, Any]]:
        """Busca memórias RAM 16GB DDR4 na Pichau."""
        results = []
        seen_links = set()
        urls = [
            "https://www.pichau.com.br/hardware/memorias?order=price_asc",
            "https://www.pichau.com.br/search?q=memoria+ddr4+16gb&sort=price-asc"
        ]
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=['--disable-blink-features=AutomationControlled', '--no-sandbox']
            )
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            
            for url in urls:
                try:
                    await page.goto(url, timeout=30000, wait_until="domcontentloaded")
                    await page.wait_for_timeout(3000)
                    
                    cards = page.locator('a[href*="/memoria-"], a[href*="/produto/"]')
                    count = await cards.count()
                    
                    for i in range(min(count, 20)):
                        card = cards.nth(i)
                        href = await card.get_attribute('href')
                        if not href:
                            continue
                        if not href.startswith('http'):
                            href = f"https://www.pichau.com.br{href}"
                        if href in seen_links:
                            continue
                            
                        raw_text = await card.inner_text()
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
                            
                        prices_found = re.findall(r'R\$\s*([\d\.,]+)', raw_text)
                        parsed_prices = [clean_price(p) for p in prices_found if clean_price(p)]
                        if not parsed_prices:
                            continue
                            
                        price = min(parsed_prices)
                        if not (100 <= price <= 1000):
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
                    logger.warning(f"[Pichau RAM] Aviso ao acessar {url}: {e}")
                    
            await browser.close()
            
        return results
