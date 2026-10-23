import logging
import re
from typing import List, Dict, Any
from playwright.async_api import async_playwright
from .utils import clean_price, classify_ssd_capacity, is_valid_ram_16gb_ddr4

logger = logging.getLogger(__name__)

class MercadoLivreScraper:
    async def get_ssds(self) -> List[Dict[str, Any]]:
        """Busca SSDs de 512GB e 1TB no Mercado Livre."""
        results = []
        queries = ["ssd-512gb", "ssd-1tb"]
        
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
            await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

            for q in queries:
                try:
                    url = f"https://lista.mercadolivre.com.br/informatica/armazenamento/discos-acessorios/ssds/{q}_OrderId_PRICE_ASC_NoIndex_True"
                    await page.goto(url, timeout=12000, wait_until="domcontentloaded")
                    await page.wait_for_timeout(2000)
                    
                    if "account-verification" in page.url:
                        logger.warning(f"[Mercado Livre SSD] Bloqueado por WAF/account-verification para {q}")
                        continue
                        
                    cards = page.locator('li.ui-search-layout__item, .poly-card')
                    count = await cards.count()
                    
                    for i in range(min(count, 15)):
                        card = cards.nth(i)
                        
                        # Título
                        title_el = card.locator('.poly-component__title, .ui-search-item__title, h2')
                        if await title_el.count() == 0:
                            continue
                        title = await title_el.first.inner_text()
                        
                        cap = classify_ssd_capacity(title)
                        if not cap:
                            continue
                            
                        # Link
                        link_el = card.locator('a.ui-search-link, a.poly-component__title')
                        if await link_el.count() == 0:
                            continue
                        href = await link_el.first.get_attribute('href')
                        if not href:
                            continue
                        # Remove parâmetros de tracking do ML
                        href = href.split('?')[0] if '?' in href else href
                        
                        # Preço
                        frac_el = card.locator('.andes-money-amount__fraction')
                        if await frac_el.count() == 0:
                            continue
                        price_str = await frac_el.first.inner_text()
                        
                        cents_el = card.locator('.andes-money-amount__cents')
                        if await cents_el.count() > 0:
                            price_str += '.' + await cents_el.first.inner_text()
                            
                        price = clean_price(price_str)
                        if not price or not (80 <= price <= 1500):
                            continue
                            
                        results.append({
                            'title': title,
                            'price': price,
                            'capacity': cap,
                            'store': 'Mercado Livre',
                            'warranty': 'Compra Garantida Mercado Livre',
                            'link': href,
                            'category': 'SSD'
                        })
                except Exception as e:
                    logger.warning(f"[Mercado Livre] Não foi possível obter dados para {q}: {e}")
                    
            await browser.close()
            
        return results

    async def get_ram_16gb_ddr4(self) -> List[Dict[str, Any]]:
        """Busca memórias RAM 16GB DDR4 mais baratas no Mercado Livre."""
        results = []
        queries = ["memoria-ram-16gb-ddr4-desktop", "memoria-ddr4-16gb"]
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
            await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

            for q in queries:
                try:
                    url = f"https://lista.mercadolivre.com.br/informatica/componentes-pc/memorias-ram/{q}_OrderId_PRICE_ASC_NoIndex_True"
                    await page.goto(url, timeout=12000, wait_until="domcontentloaded")
                    await page.wait_for_timeout(2000)
                    
                    if "account-verification" in page.url:
                        logger.warning(f"[Mercado Livre RAM] Bloqueado por WAF/account-verification para {q}")
                        continue
                        
                    cards = page.locator('li.ui-search-layout__item, .poly-card')
                    count = await cards.count()
                    
                    for i in range(min(count, 15)):
                        card = cards.nth(i)
                        
                        title_el = card.locator('.poly-component__title, .ui-search-item__title, h2')
                        if await title_el.count() == 0:
                            continue
                        title = await title_el.first.inner_text()
                        
                        if not is_valid_ram_16gb_ddr4(title):
                            continue
                            
                        link_el = card.locator('a.ui-search-link, a.poly-component__title')
                        if await link_el.count() == 0:
                            continue
                        href = await link_el.first.get_attribute('href')
                        if not href:
                            continue
                        href = href.split('?')[0] if '?' in href else href
                        
                        if href in seen_links:
                            continue
                            
                        frac_el = card.locator('.andes-money-amount__fraction')
                        if await frac_el.count() == 0:
                            continue
                        price_str = await frac_el.first.inner_text()
                        
                        cents_el = card.locator('.andes-money-amount__cents')
                        if await cents_el.count() > 0:
                            price_str += '.' + await cents_el.first.inner_text()
                            
                        price = clean_price(price_str)
                        if not price or not (100 <= price <= 1000):
                            continue
                            
                        seen_links.add(href)
                        results.append({
                            'title': title,
                            'price': price,
                            'store': 'Mercado Livre',
                            'warranty': 'Compra Garantida Mercado Livre',
                            'link': href,
                            'category': 'RAM'
                        })
                except Exception as e:
                    logger.warning(f"[Mercado Livre RAM] Não foi possível obter dados para {q}: {e}")
                    
            await browser.close()
            
        return results
