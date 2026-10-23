import logging
import re
from typing import List, Dict, Any
from playwright.async_api import async_playwright
from .utils import clean_price, classify_ssd_capacity, is_valid_ram_16gb_ddr4

logger = logging.getLogger(__name__)

class AmazonScraper:
    async def get_ssds(self) -> List[Dict[str, Any]]:
        """Busca SSDs de 512GB e 1TB na Amazon Brasil."""
        results = []
        queries = ["ssd 480gb", "ssd 512gb", "ssd 1tb"]
        seen_links = set()
        
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
            
            for q in queries:
                try:
                    url = f"https://www.amazon.com.br/s?k={q.replace(' ', '+')}"
                    await page.goto(url, timeout=30000, wait_until="domcontentloaded")
                    await page.wait_for_timeout(2500)
                    
                    cards = page.locator('div[data-component-type="s-search-result"]')
                    count = await cards.count()
                    
                    for i in range(min(count, 35)):
                        card = cards.nth(i)
                        
                        # Título
                        title_el = card.locator('h2 span, h2')
                        if await title_el.count() == 0:
                            continue
                        title = await title_el.first.inner_text()
                        
                        cap = classify_ssd_capacity(title)
                        if not cap:
                            continue
                            
                        # Link (o título no Amazon é envolvido pela tag <a> pai ou tem link com /dp/)
                        link_el = card.locator('a:has(h2), a[href*="/dp/"], h2 a')
                        if await link_el.count() == 0:
                            continue
                        href = await link_el.first.get_attribute('href')
                        if not href:
                            continue
                        if not href.startswith('http'):
                            href = f"https://www.amazon.com.br{href}"
                        href = href.split('/ref=')[0] if '/ref=' in href else href
                        
                        if href in seen_links:
                            continue
                            
                        # Preço
                        price_el = card.locator('.a-price .a-offscreen')
                        if await price_el.count() > 0:
                            price_raw = await price_el.first.inner_text()
                        else:
                            price_raw = await card.inner_text()
                            
                        m = re.search(r'R\$\s*([\d\.,]+)', price_raw)
                        if not m:
                            continue
                            
                        price = clean_price(m.group(1))
                        if not price or not (80 <= price <= 1500):
                            continue
                            
                        seen_links.add(href)
                        results.append({
                            'title': title,
                            'price': price,
                            'capacity': cap,
                            'store': 'Amazon',
                            'warranty': 'Garantia de Compra Protegida Amazon',
                            'link': href,
                            'category': 'SSD'
                        })
                except Exception as e:
                    logger.error(f"[Amazon SSD] Erro ao buscar {q}: {e}")
                    
            await browser.close()
            
        return results

    async def get_ram_16gb_ddr4(self) -> List[Dict[str, Any]]:
        """Busca memórias RAM 16GB DDR4 mais baratas na Amazon Brasil."""
        results = []
        queries = ["memoria ddr4 16gb", "memoria ram ddr4 16gb"]
        seen_links = set()
        
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
            
            for q in queries:
                try:
                    url = f"https://www.amazon.com.br/s?k={q.replace(' ', '+')}"
                    await page.goto(url, timeout=30000, wait_until="domcontentloaded")
                    await page.wait_for_timeout(2500)
                    
                    cards = page.locator('div[data-component-type="s-search-result"]')
                    count = await cards.count()
                    
                    for i in range(min(count, 35)):
                        card = cards.nth(i)
                        
                        title_el = card.locator('h2 span, h2')
                        if await title_el.count() == 0:
                            continue
                        title = await title_el.first.inner_text()
                        
                        if not is_valid_ram_16gb_ddr4(title):
                            continue
                            
                        link_el = card.locator('a:has(h2), a[href*="/dp/"], h2 a')
                        if await link_el.count() == 0:
                            continue
                        href = await link_el.first.get_attribute('href')
                        if not href:
                            continue
                        if not href.startswith('http'):
                            href = f"https://www.amazon.com.br{href}"
                        href = href.split('/ref=')[0] if '/ref=' in href else href
                        
                        if href in seen_links:
                            continue
                            
                        price_el = card.locator('.a-price .a-offscreen')
                        if await price_el.count() > 0:
                            price_raw = await price_el.first.inner_text()
                        else:
                            price_raw = await card.inner_text()
                            
                        m = re.search(r'R\$\s*([\d\.,]+)', price_raw)
                        if not m:
                            continue
                            
                        price = clean_price(m.group(1))
                        if not price or not (80 <= price <= 1000):
                            continue
                            
                        seen_links.add(href)
                        results.append({
                            'title': title,
                            'price': price,
                            'store': 'Amazon',
                            'warranty': 'Garantia de Compra Protegida Amazon',
                            'link': href,
                            'category': 'RAM'
                        })
                except Exception as e:
                    logger.error(f"[Amazon RAM] Erro ao buscar {q}: {e}")
                    
            await browser.close()
            
        return results
