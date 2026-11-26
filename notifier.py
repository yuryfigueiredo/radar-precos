import os
import smtplib
import logging
import json
import html
import tempfile
from urllib.parse import urlsplit
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from typing import Dict, List, Any
from scrapers.utils import format_currency

logger = logging.getLogger(__name__)

HISTORY_FILE = "historico_precos.json"
MONTHS_PT_BR = (
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"
)
ALLOWED_PRODUCT_HOSTS = {
    "kabum.com.br", "www.kabum.com.br",
    "terabyteshop.com.br", "www.terabyteshop.com.br",
    "pichau.com.br", "www.pichau.com.br",
    "amazon.com.br", "www.amazon.com.br",
    "mercadolivre.com.br", "www.mercadolivre.com.br",
    "produto.mercadolivre.com.br", "click1.mercadolivre.com.br",
}

def format_report_date(value: datetime) -> str:
    month = MONTHS_PT_BR[value.month - 1]
    return f"{value.day:02d} de {month} de {value.year}, {value:%H:%M}"

def history_key(item: Dict[str, Any]) -> str:
    store = str(item.get("store", "")).strip().lower()
    link = str(item.get("link", "")).strip()
    try:
        parsed = urlsplit(link)
    except ValueError:
        parsed = None
    if parsed and parsed.scheme in ("http", "https") and parsed.netloc:
        identity = f"{parsed.netloc.lower()}{parsed.path.rstrip('/')}"
    else:
        identity = " ".join(str(item.get("title", "")).upper().split())
    return f"{store}|{identity}"

def legacy_history_key(item: Dict[str, Any]) -> str:
    return f"{item.get('store', '')}_{str(item.get('title', ''))[:50]}"

def safe_product_link(value: Any) -> str:
    link = str(value or "").strip()
    try:
        parsed = urlsplit(link)
        host = (parsed.hostname or "").lower()
        if parsed.scheme != "https" or host not in ALLOWED_PRODUCT_HOSTS:
            return ""
        if parsed.username or parsed.password or not parsed.path:
            return ""
        if any(char.isspace() for char in link):
            return ""
    except ValueError:
        return ""
    return link

def load_price_history() -> Dict[str, float]:
    """Carrega o histórico de preços salvo em disco."""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Não foi possível carregar '{HISTORY_FILE}': {e}")
    return {}

def save_price_history(history: Dict[str, float]):
    """Salva o histórico de preços atualizado em disco."""
    history_path = os.path.abspath(HISTORY_FILE)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=os.path.dirname(history_path),
            prefix=".historico-",
            suffix=".tmp",
            delete=False,
        ) as f:
            temp_path = f.name
            json.dump(history, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, history_path)
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)

def calculate_variation(item: Dict[str, Any], history: Dict[str, float]) -> tuple[float, str]:
    curr_price = float(item.get("price", 0))
    key = history_key(item)
    prev_price = float(history.get(key, history.get(legacy_history_key(item), 0)))
    var = ((curr_price - prev_price) / prev_price) * 100 if prev_price > 0 else 0.0
    if abs(var) < 0.05:
        return 0.0, "0.0%"
    if var > 0:
        return var, f"+{var:.1f}%"
    return var, f"{var:.1f}%"

def get_report_items(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    sections = (
        ("rtx_3060_12gb", 8),
        ("mancer_dantalion", 2),
        ("top_brand_rams", 8),
        ("cheapest_rams", 8),
        ("nvme_top_1tb", 8),
        ("nvme_top_2tb", 8),
        ("ssds_1tb", 8),
        ("ssds_2tb", 8),
        ("ssds_512", 8),
    )
    items = []
    seen = set()
    for section, limit in sections:
        for item in data.get(section, [])[:limit]:
            key = history_key(item)
            if key not in seen:
                seen.add(key)
                items.append(item)
    return items

def save_delivered_history(data: Dict[str, Any], history: Dict[str, float]) -> None:
    for item in get_report_items(data):
        price = float(item.get("price", 0))
        if price > 0:
            history[history_key(item)] = price
    save_price_history(history)

def generate_html_report(data: Dict[str, Any], history: Dict[str, float] | None = None) -> str:
    """Gera o corpo do e-mail corporativo em HTML responsivo seguindo o padrão TechCorp."""
    now = datetime.now()
    date_str = format_report_date(now)
    history = load_price_history() if history is None else history
    
    # Cores de identificação por Loja
    store_badges = {
        'Kabum': ('#ff6500', '#ffffff'),
        'TerabyteShop': ('#1b8738', '#ffffff'),
        'Pichau': ('#e60014', '#ffffff'),
        'Amazon': ('#232f3e', '#ff9900'),
        'Mercado Livre': ('#ffe600', '#000000')
    }

    def esc(value: Any) -> str:
        return html.escape(str(value), quote=True)

    def render_link(url: Any, style: str) -> str:
        safe_url = safe_product_link(url)
        if not safe_url:
            return '<span style="color: #64748b; font-size: 11px;">Link indisponível</span>'
        return f'<a href="{esc(safe_url)}" target="_blank" rel="noopener noreferrer" style="{style}">Ver Oferta &rarr;</a>'

    def render_category_table(items: List[Dict[str, Any]], category_label: str, max_items: int = 8) -> str:
        if not items:
            return '<p style="color: #64748b; font-style: italic; padding: 10px 0; font-size: 13px;">Nenhuma oferta encontrada nesta categoria no momento.</p>'
        
        rows_html = ""
        for i, item in enumerate(items[:max_items]):
            store = item.get('store', 'Loja')
            bg_color, text_color = store_badges.get(store, ('#334155', '#ffffff'))
            
            var_num, var_str = calculate_variation(item, history)
            
            # Formatação de cores para variação
            if var_str == "0.0%":
                var_style = "color: #64748b; background-color: #f1f5f9; padding: 3px 6px; border-radius: 4px; font-weight: 600; font-size: 11px;"
            elif var_num > 0:
                var_style = "color: #dc2626; background-color: #fef2f2; padding: 3px 6px; border-radius: 4px; font-weight: 600; font-size: 11px;"
            else:
                var_style = "color: #059669; background-color: #ecfdf5; padding: 3px 6px; border-radius: 4px; font-weight: 600; font-size: 11px;"
                
            row_bg = "#ffffff" if i % 2 == 0 else "#f8fafc"
            clean_price_val = f"{item.get('price', 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            warranty = item.get('warranty', 'Garantia Oficial')
            
            sku_code = f"PROD-{i+1:03d}"
            
            rows_html += f'''
            <tr style="background-color: {row_bg}; border-bottom: 1px solid #e2e8f0;">
                <td class="radar-col-optional" style="padding: 10px 12px; font-size: 12px; color: #475569; font-family: monospace; white-space: nowrap;">
                    <span style="background-color: {bg_color}; color: {text_color}; font-size: 10px; font-weight: 700; padding: 2px 6px; border-radius: 3px; display: inline-block; margin-right: 5px;">
                        {esc(store[:4].upper())}
                    </span>
                    {sku_code}
                </td>
                <td style="padding: 10px 12px; font-size: 13px; color: #1e293b; line-height: 1.4;">
                    <div style="font-weight: 600; color: #0f172a;">{esc(item.get('title', ''))}</div>
                    <div class="radar-mobile-store" style="display: none; font-size: 10px; color: #64748b; margin-top: 2px;">{esc(store)}</div>
                    <div style="font-size: 11px; color: #64748b; margin-top: 2px;">🛡️ {esc(warranty)}</div>
                </td>
                <td class="radar-col-optional" style="padding: 10px 12px; font-size: 12px; color: #475569; white-space: nowrap;">
                    {esc(category_label)}
                </td>
                <td class="radar-col-optional" style="padding: 10px 12px; font-size: 12px; color: #64748b; text-align: center; font-weight: 500;">
                    BRL
                </td>
                <td style="padding: 10px 12px; font-size: 14px; font-weight: 700; color: #0f2942; text-align: right; white-space: nowrap;">
                    {clean_price_val}
                    <div class="radar-mobile-variation" style="display: none; margin-top: 3px;"><span style="{var_style}">{var_str}</span></div>
                </td>
                <td class="radar-col-optional" style="padding: 10px 12px; text-align: center; white-space: nowrap;">
                    <span style="{var_style}">{var_str}</span>
                </td>
                <td style="padding: 10px 12px; text-align: center; white-space: nowrap;">
                    {render_link(item.get('link'), "background-color: #0e2a47; color: #ffffff; text-decoration: none; font-size: 11px; font-weight: 600; padding: 6px 12px; border-radius: 4px; display: inline-block;")}
                </td>
            </tr>
            '''
            
        table_html = f'''
        <div style="margin-bottom: 25px; overflow-x: auto; border: 1px solid #cbd5e1; border-radius: 6px;">
            <table class="radar-product-table" style="width: 100%; border-collapse: collapse; text-align: left; background-color: #ffffff; min-width: 650px;">
                <thead>
                    <tr style="background-color: #0e2a47; color: #ffffff;">
                        <th class="radar-col-optional" style="padding: 10px 12px; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px;">SKU / LOJA</th>
                        <th style="padding: 10px 12px; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px;">DESCRIÇÃO DO PRODUTO</th>
                        <th class="radar-col-optional" style="padding: 10px 12px; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px;">CATEGORIA</th>
                        <th class="radar-col-optional" style="padding: 10px 12px; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; text-align: center;">MOEDA</th>
                        <th style="padding: 10px 12px; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; text-align: right;">PREÇO ATUAL</th>
                        <th class="radar-col-optional" style="padding: 10px 12px; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; text-align: center;">VARIAÇÃO (%)</th>
                        <th style="padding: 10px 12px; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; text-align: center;">AÇÃO</th>
                    </tr>
                </thead>
                <tbody>
                    {rows_html}
                </tbody>
            </table>
        </div>
        '''
        return table_html

    rtx_3060_12gb = data.get('rtx_3060_12gb', [])
    mancer_dantalion = data.get('mancer_dantalion', [])
    top_brand_rams = data.get('top_brand_rams', [])
    cheapest_rams = data.get('cheapest_rams', [])
    nvme_top_1tb = data.get('nvme_top_1tb', [])
    nvme_top_2tb = data.get('nvme_top_2tb', [])
    nvme_general_1tb = data.get('nvme_general_1tb', [])
    nvme_general_2tb = data.get('nvme_general_2tb', [])
    ssds_1tb = data.get('ssds_1tb', [])
    ssds_2tb = data.get('ssds_2tb', [])
    ssds_512 = data.get('ssds_512', [])

    # Destaques para o resumo da coleta
    best_top_ram = top_brand_rams[0] if top_brand_rams else None
    best_nvme_1tb = nvme_top_1tb[0] if nvme_top_1tb else (nvme_general_1tb[0] if nvme_general_1tb else None)
    best_nvme_2tb = nvme_top_2tb[0] if nvme_top_2tb else (nvme_general_2tb[0] if nvme_general_2tb else None)
    best_dantalion = mancer_dantalion[0] if mancer_dantalion else None
    best_rtx_3060_12gb = rtx_3060_12gb[0] if rtx_3060_12gb else None

    def render_source_health(source_health: Dict[str, Any]) -> str:
        status_labels = {
            "ok": "OK",
            "partial": "Parcial",
            "empty": "Sem itens",
            "error": "Erro",
            "blocked": "Bloqueada",
            "not_collected": "Não coletada",
        }
        status_styles = {
            "ok": ("#dcfce7", "#15803d"),
            "partial": ("#fef3c7", "#b45309"),
            "empty": ("#f1f5f9", "#475569"),
            "error": ("#fee2e2", "#991b1b"),
            "blocked": ("#fee2e2", "#991b1b"),
            "not_collected": ("#f1f5f9", "#475569"),
        }
        rows = []
        for store, categories in source_health.items():
            for category, health in categories.items():
                status = str(health.get("status", "not_collected"))
                bg_color, text_color = status_styles.get(status, ("#f1f5f9", "#475569"))
                detail = health.get("detail") or "Sem detalhe adicional"
                rows.append(f'''
                <tr style="border-bottom: 1px solid #e2e8f0;">
                    <td style="padding: 8px; font-size: 12px;">{esc(store)}</td>
                    <td style="padding: 8px; font-size: 12px;">{esc(category)}</td>
                    <td style="padding: 8px; font-size: 12px;">
                        <span style="background-color: {bg_color}; color: {text_color}; padding: 2px 6px; border-radius: 4px; font-weight: 700;">{esc(status_labels.get(status, status))}</span>
                        <div class="radar-mobile-health-detail" style="display: none; font-size: 10px; color: #64748b; margin-top: 3px;">{esc(detail)}</div>
                    </td>
                    <td style="padding: 8px; font-size: 12px; text-align: center;">{esc(health.get('count', 0))}</td>
                    <td class="radar-col-optional" style="padding: 8px; font-size: 12px; text-align: center;">{esc(health.get('attempted', 0))}</td>
                    <td class="radar-col-optional" style="padding: 8px; font-size: 11px; color: #475569;">{esc(detail)}</td>
                </tr>
                ''')
        if not rows:
            return ""
        return f'''
        <div style="margin-top: 30px;">
            <h3 style="margin: 0 0 10px 0; font-size: 14px; font-weight: 700; color: #0e2a47;">SAÚDE DAS FONTES DESTA COLETA</h3>
            <div style="overflow-x: auto; border: 1px solid #cbd5e1; border-radius: 6px;">
                <table class="radar-health-table" style="width: 100%; border-collapse: collapse; background-color: #ffffff; min-width: 650px;">
                    <thead>
                        <tr style="background-color: #0e2a47; color: #ffffff;">
                            <th style="padding: 8px; text-align: left; font-size: 11px;">FONTE</th>
                            <th style="padding: 8px; text-align: left; font-size: 11px;">CATEGORIA</th>
                            <th style="padding: 8px; text-align: left; font-size: 11px;">STATUS</th>
                            <th style="padding: 8px; font-size: 11px;">ITENS</th>
                            <th class="radar-col-optional" style="padding: 8px; font-size: 11px;">TENTATIVAS</th>
                            <th class="radar-col-optional" style="padding: 8px; text-align: left; font-size: 11px;">DETALHE</th>
                        </tr>
                    </thead>
                    <tbody>{''.join(rows)}</tbody>
                </table>
            </div>
        </div>
        '''

    html_content = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Relatório Diário de Preços - RTX 3060 12GB, SSDs e Memórias RAM</title>
    <style>
        @media only screen and (max-width: 600px) {{
            .radar-product-table, .radar-health-table {{ min-width: 0 !important; width: 100% !important; }}
            .radar-col-optional {{ display: none !important; }}
            .radar-mobile-store, .radar-mobile-variation, .radar-mobile-health-detail {{ display: block !important; }}
            .radar-product-table th, .radar-product-table td, .radar-health-table th, .radar-health-table td {{ padding: 8px 6px !important; }}
            .radar-product-table a {{ padding: 6px 8px !important; font-size: 10px !important; }}
        }}
    </style>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f1f5f9; margin: 0; padding: 25px 15px; color: #1e293b;">
    <div style="max-width: 860px; margin: 0 auto; background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 16px rgba(15, 23, 42, 0.08); border: 1px solid #e2e8f0;">
        
        <!-- Top Bar / Header estilo corporativo TechCorp -->
        <div style="padding: 24px 30px; border-bottom: 2px solid #e2e8f0; background-color: #ffffff;">
            <table style="width: 100%; border-collapse: collapse;">
                <tr>
                    <td style="vertical-align: top;">
                        <div style="font-size: 13px; font-weight: 700; color: #0e2a47; letter-spacing: 0.5px; text-transform: uppercase;">
                            RELATÓRIO DIÁRIO DE PREÇOS
                        </div>
                        <div style="font-size: 12px; color: #64748b; margin-top: 3px;">
                            <strong>Radar de Preços Bot</strong> &lt;notificacoes@radarprecos.global&gt;
                        </div>
                        <div style="font-size: 11px; color: #94a3b8; margin-top: 2px;">
                            {date_str}
                        </div>
                    </td>
                    <td style="vertical-align: top; text-align: right;">
                        <table style="display: inline-table; border-collapse: collapse;">
                            <tr>
                                <td style="vertical-align: middle; padding-right: 10px;">
                                    <div style="background: linear-gradient(135deg, #0e2a47 0%, #2563eb 100%); color: #ffffff; font-weight: 800; font-size: 16px; width: 38px; height: 38px; line-height: 38px; text-align: center; border-radius: 8px; box-shadow: 0 2px 6px rgba(37,99,235,0.3);">
                                        RP
                                    </div>
                                </td>
                                <td style="vertical-align: middle; text-align: left;">
                                    <div style="font-size: 16px; font-weight: 800; color: #0e2a47; line-height: 1.1;">RadarPreços</div>
                                    <div style="font-size: 10px; color: #64748b; letter-spacing: 0.3px;">RTX 3060 12GB & SSDs & RAM</div>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
            </table>
            
            <div style="margin-top: 22px;">
                <h1 style="margin: 0; font-size: 22px; font-weight: 700; color: #0e2a47;">
                    RELATÓRIO DIÁRIO DE PREÇOS - RTX 3060 12GB, SSDs & Memórias RAM
                </h1>
                <p style="margin: 6px 0 0 0; font-size: 14px; color: #475569;">
                    Olá, <strong>Yury</strong>,
                </p>
                <p style="margin: 4px 0 0 0; font-size: 13px; color: #64748b; line-height: 1.5;">
                    Abaixo está a seleção monitorada de <strong>NVIDIA GeForce RTX 3060 12GB</strong>, <strong>Memórias RAM 16GB DDR4 (Mancer Dantalion, Kingston Fury, XPG D35, Corsair, Crucial)</strong> e <strong>SSDs (Kingston NV3, WD Blue SN580, Crucial P3 Plus e demais modelos)</strong>.
                </p>
            </div>
        </div>

        <div style="padding: 25px 30px;">
            
            <div style="margin-bottom: 25px;">
                <div style="display: flex; align-items: center; margin-bottom: 10px;">
                    <h2 style="margin: 0; font-size: 16px; font-weight: 700; color: #0e2a47;">
                        NVIDIA GeForce RTX 3060 12GB — Mais Baratas
                    </h2>
                </div>
                {render_category_table(rtx_3060_12gb, "RTX 3060 12GB", max_items=8)}
            </div>

            <!-- SEÇÃO DESTAQUE FIXO: MEMÓRIA MANCER DANTALION 16GB 3200MHz -->
            {f'''
            <div style="margin-bottom: 25px;">
                <div style="display: flex; align-items: center; margin-bottom: 10px;">
                    <h2 style="margin: 0; font-size: 16px; font-weight: 700; color: #0e2a47;">
                        ⭐ Memória Destaque Fixo — Mancer Dantalion 16GB DDR4 3200MHz CL19
                    </h2>
                </div>
                {render_category_table(mancer_dantalion, "RAM Dantalion", max_items=2)}
            </div>
            ''' if mancer_dantalion else ''}

            <!-- SEÇÃO 2: Memórias RAM 16GB DDR4 — Marcas Selecionadas (Kingston Fury, XPG D35, Corsair, Crucial) -->
            <div style="margin-bottom: 25px;">
                <div style="display: flex; align-items: center; margin-bottom: 10px;">
                    <h2 style="margin: 0; font-size: 16px; font-weight: 700; color: #0e2a47;">
                        🏆 Memórias RAM 16GB DDR4 — Marcas Recomendadas (Kingston Fury Beast, XPG D35, Corsair LPX, Crucial)
                    </h2>
                </div>
                {render_category_table(top_brand_rams, "RAM Top Brand", max_items=8)}
            </div>

            <!-- SEÇÃO 3: Memórias RAM 16GB DDR4 — Mais Baratas Gerais -->
            <div style="margin-bottom: 25px;">
                <div style="display: flex; align-items: center; margin-bottom: 10px;">
                    <h2 style="margin: 0; font-size: 16px; font-weight: 700; color: #0e2a47;">
                        🧠 Memórias RAM 16GB DDR4 Gamer (Mais Baratas Gerais)
                    </h2>
                </div>
                {render_category_table(cheapest_rams, "RAM 16GB DDR4", max_items=8)}
            </div>

            <!-- SEÇÃO 4: NVMe 1TB Custo-Benefício Destaque (Kingston NV3, WD SN580, Crucial P3 Plus) -->
            <div style="margin-bottom: 25px;">
                <div style="display: flex; align-items: center; margin-bottom: 10px;">
                    <h2 style="margin: 0; font-size: 16px; font-weight: 700; color: #0e2a47;">
                        ⚡ SSDs NVMe 1TB — Melhores Custo-Benefício (Kingston NV3, WD Blue SN580, Crucial P3 Plus)
                    </h2>
                </div>
                {render_category_table(nvme_top_1tb, "NVMe 1TB Top", max_items=8)}
            </div>

            <!-- SEÇÃO 5: NVMe 2TB Custo-Benefício Destaque (Kingston NV3, WD SN580, Crucial P3 Plus) -->
            <div style="margin-bottom: 25px;">
                <div style="display: flex; align-items: center; margin-bottom: 10px;">
                    <h2 style="margin: 0; font-size: 16px; font-weight: 700; color: #0e2a47;">
                        ⚡ SSDs NVMe 2TB — Melhores Custo-Benefício (Kingston NV3, WD Blue SN580, Crucial P3 Plus)
                    </h2>
                </div>
                {render_category_table(nvme_top_2tb, "NVMe 2TB Top", max_items=8)}
            </div>

            <!-- SEÇÃO 6: SSDs 1TB Gerais Mais Baratos -->
            <div style="margin-bottom: 25px;">
                <div style="display: flex; align-items: center; margin-bottom: 10px;">
                    <h2 style="margin: 0; font-size: 16px; font-weight: 700; color: #0e2a47;">
                        💾 Armazenamento — SSDs de 1TB (Mais Baratos Gerais)
                    </h2>
                </div>
                {render_category_table(ssds_1tb, "SSD 1TB", max_items=8)}
            </div>

            <!-- SEÇÃO 7: SSDs 2TB Gerais Mais Baratos -->
            <div style="margin-bottom: 25px;">
                <div style="display: flex; align-items: center; margin-bottom: 10px;">
                    <h2 style="margin: 0; font-size: 16px; font-weight: 700; color: #0e2a47;">
                        💾 Armazenamento — SSDs de 2TB (Mais Baratos Gerais)
                    </h2>
                </div>
                {render_category_table(ssds_2tb, "SSD 2TB", max_items=8)}
            </div>

            <!-- SEÇÃO 8: SSDs 512GB Mais Baratos Gerais -->
            <div style="margin-bottom: 25px;">
                <div style="display: flex; align-items: center; margin-bottom: 10px;">
                    <h2 style="margin: 0; font-size: 16px; font-weight: 700; color: #0e2a47;">
                        💾 Armazenamento — SSDs de 512GB / 480GB (Mais Baratos Gerais)
                    </h2>
                </div>
                {render_category_table(ssds_512, "SSD 512GB", max_items=8)}
            </div>

            {render_source_health(data.get('source_health', {}))}

            <!-- RESUMO DA COLETA ATUAL -->
            <div style="margin-top: 35px; border-top: 2px solid #e2e8f0; padding-top: 22px;">
                <h3 style="margin: 0 0 12px 0; font-size: 14px; font-weight: 700; color: #0e2a47; text-transform: uppercase; letter-spacing: 0.5px;">
                    RESUMO DA COLETA ATUAL
                </h3>
                
                <ul style="margin: 0 0 18px 0; padding-left: 20px; color: #334155; font-size: 13px; line-height: 1.6;">
                    <li><strong>NVIDIA RTX 3060 12GB:</strong> {f"A placa RTX 3060 12GB mais barata está saindo a <strong>{format_currency(best_rtx_3060_12gb.get('price', 0))}</strong> ({esc(best_rtx_3060_12gb.get('store', 'Loja'))})." if best_rtx_3060_12gb else "Nenhuma oferta válida de RTX 3060 12GB foi encontrada nesta coleta."}</li>
                    <li><strong>Memória Destaque Mancer Dantalion:</strong> {f"A <strong>Mancer Dantalion 16GB DDR4 3200MHz CL19</strong> está cotada a <strong>{format_currency(best_dantalion.get('price', 0))}</strong> na {esc(best_dantalion.get('store', 'Pichau'))}." if best_dantalion else "A memória Mancer Dantalion 16GB não foi encontrada nesta coleta."}</li>
                    <li><strong>Memórias RAM Marcas Preferidas:</strong> {f"O melhor preço entre as marcas favoritas (Kingston Fury, XPG Gammix D35, Corsair Vengeance, Crucial) está saindo a <strong>{format_currency(best_top_ram.get('price', 0))}</strong> ({esc(best_top_ram.get('store', 'Loja'))})." if best_top_ram else "Nenhum preço entre as marcas favoritas foi encontrado nesta coleta."}</li>
                    <li><strong>Armazenamento NVMe Custo-Benefício:</strong> {f"Para 1TB (Kingston NV3 / WD SN580 / Crucial P3), o menor preço encontrado é <strong>{format_currency(best_nvme_1tb.get('price', 0))}</strong>. Para 2TB, temos opções a partir de <strong>{format_currency(best_nvme_2tb.get('price', 0))}</strong>." if best_nvme_1tb and best_nvme_2tb else "Não há preços suficientes de NVMe 1TB e 2TB para comparar nesta coleta."}</li>
                </ul>
            </div>

            <!-- Footer Corporativo -->
            <div style="margin-top: 35px; border-top: 1px solid #e2e8f0; padding-top: 18px;">
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="font-size: 11px; color: #64748b; vertical-align: middle;">
                            <strong>RadarPreços Global</strong><br>
                            Monitoramento Automatizado de RTX 3060 12GB, SSDs e Memórias RAM • Brasil
                        </td>
                        <td style="text-align: right; font-size: 11px; color: #64748b; vertical-align: middle;">
                            <span style="text-decoration: underline; color: #475569;">Gestão de Preferências</span> &nbsp;|&nbsp;
                            <span style="text-decoration: underline; color: #475569;">Suporte</span> &nbsp;|&nbsp;
                            <span style="text-decoration: underline; color: #475569;">Cancelar Inscrição</span>
                        </td>
                    </tr>
                </table>
            </div>

        </div>
    </div>
</body>
</html>
'''
    return html_content

def send_email_alert(data: Dict[str, Any]) -> bool:
    """Dispara o e-mail via SMTP usando variáveis de ambiente."""
    sender_email = os.getenv('SENDER_EMAIL')
    sender_password = os.getenv('SENDER_PASSWORD')
    receiver_email = os.getenv('RECEIVER_EMAIL', sender_email)
    smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
    smtp_port = int(os.getenv('SMTP_PORT', '465'))

    history = load_price_history()
    html_body = generate_html_report(data, history)
    try:
        with open("ultimo_relatorio.html", "w", encoding="utf-8") as f:
            f.write(html_body)
        logger.info("Relatório salvo localmente em 'ultimo_relatorio.html'")
    except Exception as e:
        logger.warning(f"Não foi possível salvar 'ultimo_relatorio.html': {e}")

    if not sender_email or not sender_password or not receiver_email:
        logger.warning("Credenciais de e-mail não configuradas (SENDER_EMAIL / SENDER_PASSWORD). E-mail não disparado.")
        return False

    msg = MIMEMultipart('alternative')
    msg['Subject'] = f"RADAR RTX 3060 12GB, SSDs E RAM ({datetime.now().strftime('%d/%m/%Y')})"
    msg['From'] = f"RadarPreços Bot <{sender_email}>"
    msg['To'] = receiver_email

    msg.attach(MIMEText(html_body, 'html'))

    try:
        if smtp_port == 465:
            with smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=20) as server:
                server.login(sender_email, sender_password)
                server.sendmail(sender_email, receiver_email, msg.as_string())
        else:
            with smtplib.SMTP(smtp_server, smtp_port, timeout=20) as server:
                server.starttls()
                server.login(sender_email, sender_password)
                server.sendmail(sender_email, receiver_email, msg.as_string())
                
        logger.info(f"E-mail de alerta enviado com sucesso para {receiver_email}!")
    except Exception as e:
        logger.error(f"Erro ao enviar e-mail: {e}")
        return False

    try:
        save_delivered_history(data, history)
    except Exception as e:
        logger.error(f"E-mail enviado, mas não foi possível salvar o histórico: {e}")
        return False
    return True
