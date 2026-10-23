import logging
import re
from typing import List, Dict, Any
from playwright.async_api import async_playwright
from .utils import clean_price, classify_pc_vram, classify_ssd_capacity, is_valid_ram_16gb_ddr4

logger = logging.getLogger(__name__)

class PichauScraper:
    async def get_gaming_pcs(self) -> List[Dict[str, Any]]:
        """Busca PCs Gamers montados e certificados no catálogo oficial da Pichau."""
        results = []
        seen_links = set()
        url = "https://www.pichau.com.br/computadores/pichau-gamer"
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=['--disable-blink-features=AutomationControlled', '--no-sandbox']
            )
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                locale="pt-BR"
            )
            page = await context.new_page()
            
            try:
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
                        
                    prices_found = [clean_price(p) for p in re.findall(r'R\$\s*([\d\.,]+)', raw_text) if clean_price(p)]
                    # Ignora valores de parcelas menores (ex: 12x de R$ 300) pegando preços reais à vista >= 1500
                    cash_prices = [p for p in prices_found if p >= 1500]
                    if not cash_prices:
                        continue
                        
                    price = min(cash_prices)
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
                logger.warning(f"[Pichau PC] Erro: {e}")
                
            await browser.close()
            
        return results

    async def get_ssds(self) -> List[Dict[str, Any]]:
        """Busca SSDs de 512GB e 1TB no catálogo de hardware da Pichau."""
        results = []
        seen_links = set()
        url = "https://www.pichau.com.br/hardware/ssd"
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=['--disable-blink-features=AutomationControlled', '--no-sandbox']
            )
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                locale="pt-BR"
            )
            page = await context.new_page()
            
            try:
                # Pausa antes da requisição para evitar Cloudflare rate-limit
                await page.wait_for_timeout(3000)
                await page.goto(url, timeout=30000, wait_until="domcontentloaded")
                await page.wait_for_timeout(4000)
                
                cards = page.locator('a[href*="/ssd-"], a[data-cy*="product"]')
                count = await cards.count()
                
                for i in range(count):
                    card = cards.nth(i)
                    href = await card.get_attribute('href')
                    if not href or href.endswith('/hardware/ssd'):
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
                        
                    prices_found = [clean_price(p) for p in re.findall(r'R\$\s*([\d\.,]+)', raw_text) if clean_price(p)]
                    # Filtra preços válidos de SSD (entre R$ 80 e R$ 1500) descartando parcelas
                    valid_prices = [p for p in prices_found if 80 <= p <= 1500]
                    if not valid_prices:
                        continue
                        
                    price = min(valid_prices)
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
                logger.warning(f"[Pichau SSD] Erro: {e}")
                
            await browser.close()
            
        return results

    async def get_ram_16gb_ddr4(self) -> List[Dict[str, Any]]:
        """Busca memórias RAM 16GB DDR4 na Pichau."""
        results = []
        seen_links = set()
        url = "https://www.pichau.com.br/hardware/memorias"
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=['--disable-blink-features=AutomationControlled', '--no-sandbox']
            )
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                locale="pt-BR"
            )
            page = await context.new_page()
            
            try:
                await page.wait_for_timeout(3000)
                await page.goto(url, timeout=30000, wait_until="domcontentloaded")
                await page.wait_for_timeout(4000)
                
                cards = page.locator('a[href*="/memoria-"], a[data-cy*="product"]')
                count = await cards.count()
                
                for i in range(count):
                    card = cards.nth(i)
                    href = await card.get_attribute('href')
                    if not href or href.endswith('/hardware/memorias'):
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
                        
                    prices_found = [clean_price(p) for p in re.findall(r'R\$\s*([\d\.,]+)', raw_text) if clean_price(p)]
                    valid_prices = [p for p in prices_found if 80 <= p <= 1000]
                    if not valid_prices:
                        continue
                        
                    price = min(valid_prices)
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
                logger.warning(f"[Pichau RAM] Erro: {e}")
                
            await browser.close()
            
        return results
