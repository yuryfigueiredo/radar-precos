import json
import logging
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Any
from .utils import clean_price, classify_pc_vram, classify_ssd_capacity, is_valid_ram_16gb_ddr4

logger = logging.getLogger(__name__)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept-Language': 'pt-BR,pt;q=0.9',
}

class KabumScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def _fetch_next_data(self, url: str) -> List[Dict[str, Any]]:
        try:
            r = self.session.get(url, timeout=20)
            if r.status_code != 200:
                return []
            soup = BeautifulSoup(r.text, 'html.parser')
            script = soup.find('script', id='__NEXT_DATA__')
            if not script or not script.string:
                return []
            d = json.loads(script.string)
            data_raw = d.get('props', {}).get('pageProps', {}).get('data', '{}')
            if isinstance(data_raw, str):
                catalog = json.loads(data_raw)
            else:
                catalog = data_raw
            return catalog.get('catalogServer', {}).get('data', [])
        except Exception as e:
            logger.error(f"[Kabum] Erro na busca: {e}")
            return []

    def get_gaming_pcs(self) -> List[Dict[str, Any]]:
        """Busca computadores gamers prontos na Kabum."""
        results = []
        seen_codes = set()
        queries = [
            "computador gamer rx 6600",
            "computador gamer rtx 4060",
            "computador gamer rtx 3060",
            "computador gamer rtx 4070",
            "computador gamer rx 7700",
            "computador gamer rx 7800",
            "computador gamer rx 7600 xt"
        ]
        
        for q in queries:
            url = f"https://www.kabum.com.br/busca/{q.replace(' ', '-')}?page_number=1&page_size=25&sort=price&direction=asc"
            items = self._fetch_next_data(url)
            for item in items:
                code = item.get('code')
                if not code or code in seen_codes:
                    continue
                seen_codes.add(code)
                
                name = item.get('name', '')
                desc = item.get('description', '')
                vram = classify_pc_vram(name, desc)
                if not vram:
                    continue
                    
                price = clean_price(item.get('priceWithDiscount') or item.get('price'))
                if not price or price < 1500:
                    continue
                    
                results.append({
                    'title': name,
                    'price': price,
                    'vram': vram,
                    'store': 'Kabum',
                    'warranty': item.get('warranty', 'Garantia Padrão Kabum'),
                    'link': f"https://www.kabum.com.br/produto/{code}",
                    'category': 'PC'
                })
        return results

    def get_ssds(self) -> List[Dict[str, Any]]:
        """Busca SSDs de 512GB e 1TB na Kabum."""
        results = []
        seen_codes = set()
        queries = ["ssd 512gb", "ssd 1tb"]
        
        for q in queries:
            url = f"https://www.kabum.com.br/busca/{q.replace(' ', '-')}?page_number=1&page_size=30&sort=price&direction=asc"
            items = self._fetch_next_data(url)
            for item in items:
                code = item.get('code')
                if not code or code in seen_codes:
                    continue
                seen_codes.add(code)
                
                name = item.get('name', '')
                capacity = classify_ssd_capacity(name)
                if not capacity:
                    continue
                    
                price = clean_price(item.get('priceWithDiscount') or item.get('price'))
                if not price or not (80 <= price <= 1500):
                    continue
                    
                results.append({
                    'title': name,
                    'price': price,
                    'capacity': capacity,
                    'store': 'Kabum',
                    'warranty': item.get('warranty', 'Garantia Kabum'),
                    'link': f"https://www.kabum.com.br/produto/{code}",
                    'category': 'SSD'
                })
        return results

    def get_ram_16gb_ddr4(self) -> List[Dict[str, Any]]:
        """Busca memórias RAM 16GB DDR4 mais baratas na Kabum."""
        results = []
        seen_codes = set()
        queries = ["memoria ram 16gb ddr4", "memoria 16gb ddr4"]
        
        for q in queries:
            url = f"https://www.kabum.com.br/busca/{q.replace(' ', '-')}?page_number=1&page_size=30&sort=price&direction=asc"
            items = self._fetch_next_data(url)
            for item in items:
                code = item.get('code')
                if not code or code in seen_codes:
                    continue
                seen_codes.add(code)
                
                name = item.get('name', '')
                if not is_valid_ram_16gb_ddr4(name):
                    continue
                    
                price = clean_price(item.get('priceWithDiscount') or item.get('price'))
                if not price or not (100 <= price <= 1000):
                    continue
                    
                results.append({
                    'title': name,
                    'price': price,
                    'store': 'Kabum',
                    'warranty': item.get('warranty', 'Garantia Kabum'),
                    'link': f"https://www.kabum.com.br/produto/{code}",
                    'category': 'RAM'
                })
        return results
