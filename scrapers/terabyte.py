import logging
import re
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Any
from .utils import clean_price, classify_pc_vram, classify_ssd_capacity, is_valid_ram_16gb_ddr4

logger = logging.getLogger(__name__)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept-Language': 'pt-BR,pt;q=0.9',
}

class TerabyteScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def _parse_products_from_soup(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        items = []
        cards = soup.select('.product-item, .pbox')
        for card in cards:
            name_el = card.select_one('.product-item__name, .prod-name, a[title]')
            title = name_el.get('title') if name_el and name_el.has_attr('title') else (name_el.get_text().strip() if name_el else '')
            if not title:
                continue

            link_el = card.select_one('a[href*="/produto/"]')
            href = link_el.get('href') if link_el else ''
            if not href:
                continue
            if not href.startswith('http'):
                href = f"https://www.terabyteshop.com.br{href}"

            price_el = card.select_one('.product-item__new-price, .prod-new-price, [class*="new-price"]')
            price_text = price_el.get_text() if price_el else card.get_text()
            m = re.search(r'R\$\s*([\d\.,]+)', price_text)
            price = clean_price(m.group(1)) if m else None

            if price:
                items.append({
                    'title': title,
                    'price': price,
                    'link': href,
                    'store': 'TerabyteShop',
                    'warranty': '12 Meses de Garantia Terabyte'
                })
        return items

    def get_gaming_pcs(self) -> List[Dict[str, Any]]:
        """Busca PCs Gamer completos na Terabyte com foco em GPUs de 8GB, 12GB e 16GB."""
        results = []
        queries = [
            "computador gamer rx 6600",
            "computador gamer rtx 4060",
            "pc gamer rtx 3060",
            "pc gamer rtx 4070",
            "pc gamer rx 6750 xt",
            "pc gamer rx 7700 xt",
            "pc gamer rx 7600 xt",
            "pc gamer rx 7800 xt",
            "pc gamer rtx 4070 ti super",
            "pc gamer rtx 4080"
        ]
        seen_links = set()
        
        for q in queries:
            url = f"https://www.terabyteshop.com.br/busca?str={q.replace(' ', '+')}"
            try:
                r = self.session.get(url, timeout=20)
                if r.status_code == 200:
                    soup = BeautifulSoup(r.text, 'html.parser')
                    products = self._parse_products_from_soup(soup)
                    for p in products:
                        if p['link'] in seen_links:
                            continue
                        seen_links.add(p['link'])
                        vram = classify_pc_vram(p['title'])
                        if vram and p['price'] >= 1800:
                            p['vram'] = vram
                            p['category'] = 'PC'
                            results.append(p)
            except Exception as e:
                logger.error(f"[Terabyte] Erro ao buscar PCs para {q}: {e}")
        return results

    def get_ssds(self) -> List[Dict[str, Any]]:
        """Busca SSDs de 512GB, 1TB e 2TB na Terabyte."""
        results = []
        queries = ["ssd 512gb", "ssd 1tb", "ssd 2tb", "ssd nvme 1tb", "ssd nvme 2tb", "kingston nv3", "wd sn580", "crucial p3"]
        seen_links = set()

        for q in queries:
            url = f"https://www.terabyteshop.com.br/busca?str={q.replace(' ', '+')}"
            try:
                r = self.session.get(url, timeout=20)
                if r.status_code == 200:
                    soup = BeautifulSoup(r.text, 'html.parser')
                    products = self._parse_products_from_soup(soup)
                    for p in products:
                        if p['link'] in seen_links:
                            continue
                        seen_links.add(p['link'])
                        cap = classify_ssd_capacity(p['title'])
                        if cap and 80 <= p['price'] <= 3000:
                            p['capacity'] = cap
                            p['category'] = 'SSD'
                            results.append(p)
            except Exception as e:
                logger.error(f"[Terabyte] Erro ao buscar SSDs para {q}: {e}")
        return results

    def get_ram_16gb_ddr4(self) -> List[Dict[str, Any]]:
        """Busca memórias RAM 16GB DDR4 na TerabyteShop (incluindo marcas preferidas)."""
        results = []
        queries = [
            "memoria ddr4 16gb",
            "memoria ram ddr4 16gb",
            "fury beast 16gb ddr4",
            "xpg gammix d35 16gb",
            "corsair vengeance 16gb ddr4",
            "crucial 16gb ddr4"
        ]
        seen_links = set()

        for q in queries:
            url = f"https://www.terabyteshop.com.br/busca?str={q.replace(' ', '+')}"
            try:
                r = self.session.get(url, timeout=20)
                if r.status_code == 200:
                    soup = BeautifulSoup(r.text, 'html.parser')
                    products = self._parse_products_from_soup(soup)
                    for p in products:
                        if p['link'] in seen_links:
                            continue
                        seen_links.add(p['link'])
                        if is_valid_ram_16gb_ddr4(p['title']) and 100 <= p['price'] <= 1800:
                            p['category'] = 'RAM'
                            results.append(p)
            except Exception as e:
                logger.error(f"[Terabyte] Erro ao buscar RAMs para {q}: {e}")
        return results
