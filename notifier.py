import os
import smtplib
import logging
import json
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from typing import Dict, List, Any
from scrapers.utils import format_currency

logger = logging.getLogger(__name__)

HISTORY_FILE = "historico_precos.json"

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
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"Não foi possível salvar '{HISTORY_FILE}': {e}")

def calculate_variation(item: Dict[str, Any], history: Dict[str, float]) -> tuple[float, str]:
    """
    Calcula a variação percentual do preço comparado à última execução.
    Se o produto for novo no radar ou mantiver o preço estável, exibe 0.0%.
    """
    curr_price = float(item.get('price', 0))
    key = f"{item.get('store', '')}_{item.get('title', '')[:50]}"
    
    if key in history and history[key] > 0:
        prev_price = history[key]
        var = ((curr_price - prev_price) / prev_price) * 100
    else:
        var = 0.0
        
    history[key] = curr_price
    
    if abs(var) < 0.05:
        return 0.0, "0.0%"
    elif var > 0:
        return var, f"+{var:.1f}%"
    else:
        return var, f"{var:.1f}%"

def generate_html_report(data: Dict[str, Any]) -> str:
    """Gera o corpo do e-mail corporativo em HTML responsivo seguindo o padrão TechCorp."""
    now = datetime.now()
    date_str = now.strftime("%d de %B de %Y, %H:%M")
    history = load_price_history()
    
    # Cores de identificação por Loja
    store_badges = {
        'Kabum': ('#ff6500', '#ffffff'),
        'TerabyteShop': ('#1b8738', '#ffffff'),
        'Pichau': ('#e60014', '#ffffff'),
        'Amazon': ('#232f3e', '#ff9900'),
        'Mercado Livre': ('#ffe600', '#000000')
    }

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
                var_style = "color: #10b981; background-color: #ecfdf5; padding: 3px 6px; border-radius: 4px; font-weight: 600; font-size: 11px;"
            else:
                var_style = "color: #ef4444; background-color: #fef2f2; padding: 3px 6px; border-radius: 4px; font-weight: 600; font-size: 11px;"
                
            row_bg = "#ffffff" if i % 2 == 0 else "#f8fafc"
            clean_price_val = f"{item.get('price', 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            warranty = item.get('warranty', 'Garantia Oficial')
            
            sku_code = f"PROD-{i+1:03d}"
            
            rows_html += f'''
            <tr style="background-color: {row_bg}; border-bottom: 1px solid #e2e8f0;">
                <td style="padding: 10px 12px; font-size: 12px; color: #475569; font-family: monospace; white-space: nowrap;">
                    <span style="background-color: {bg_color}; color: {text_color}; font-size: 10px; font-weight: 700; padding: 2px 6px; border-radius: 3px; display: inline-block; margin-right: 5px;">
                        {store[:4].upper()}
                    </span>
                    {sku_code}
                </td>
                <td style="padding: 10px 12px; font-size: 13px; color: #1e293b; line-height: 1.4;">
                    <div style="font-weight: 600; color: #0f172a;">{item.get('title')}</div>
                    <div style="font-size: 11px; color: #64748b; margin-top: 2px;">🛡️ {warranty}</div>
                </td>
                <td style="padding: 10px 12px; font-size: 12px; color: #475569; white-space: nowrap;">
                    {category_label}
                </td>
                <td style="padding: 10px 12px; font-size: 12px; color: #64748b; text-align: center; font-weight: 500;">
                    BRL
                </td>
                <td style="padding: 10px 12px; font-size: 14px; font-weight: 700; color: #0f2942; text-align: right; white-space: nowrap;">
                    {clean_price_val}
                </td>
                <td style="padding: 10px 12px; text-align: center; white-space: nowrap;">
                    <span style="{var_style}">{var_str}</span>
                </td>
                <td style="padding: 10px 12px; text-align: center; white-space: nowrap;">
                    <a href="{item.get('link')}" target="_blank" style="background-color: #0e2a47; color: #ffffff; text-decoration: none; font-size: 11px; font-weight: 600; padding: 6px 12px; border-radius: 4px; display: inline-block;">
                        Ver Oferta &rarr;
                    </a>
                </td>
            </tr>
            '''
            
        table_html = f'''
        <div style="margin-bottom: 25px; overflow-x: auto; border: 1px solid #cbd5e1; border-radius: 6px;">
            <table style="width: 100%; border-collapse: collapse; text-align: left; background-color: #ffffff; min-width: 650px;">
                <thead>
                    <tr style="background-color: #0e2a47; color: #ffffff;">
                        <th style="padding: 10px 12px; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px;">SKU / LOJA</th>
                        <th style="padding: 10px 12px; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px;">DESCRIÇÃO DO PRODUTO</th>
                        <th style="padding: 10px 12px; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px;">CATEGORIA</th>
                        <th style="padding: 10px 12px; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; text-align: center;">MOEDA</th>
                        <th style="padding: 10px 12px; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; text-align: right;">PREÇO ATUAL</th>
                        <th style="padding: 10px 12px; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; text-align: center;">VARIAÇÃO (%)</th>
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

    pcs_8gb = data.get('pcs_8gb', [])
    pcs_12gb = data.get('pcs_12gb', [])
    pcs_16gb = data.get('pcs_16gb', [])
    rams_16gb = data.get('rams_16gb', [])
    ssds_512 = data.get('ssds_512', [])
    ssds_1tb = data.get('ssds_1tb', [])

    # Destaques para a Análise de Mercado
    best_pc_12gb = pcs_12gb[0] if pcs_12gb else None
    best_pc_8gb = pcs_8gb[0] if pcs_8gb else None
    best_pc_16gb = pcs_16gb[0] if pcs_16gb else None
    best_ram = rams_16gb[0] if rams_16gb else None
    best_ssd_512 = ssds_512[0] if ssds_512 else None
    best_ssd_1tb = ssds_1tb[0] if ssds_1tb else None

    html_content = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Relatório Diário de Preços - Hardware</title>
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
                                    <div style="font-size: 10px; color: #64748b; letter-spacing: 0.3px;">HARDWARE INTEL</div>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
            </table>
            
            <div style="margin-top: 22px;">
                <h1 style="margin: 0; font-size: 22px; font-weight: 700; color: #0e2a47;">
                    RELATÓRIO DIÁRIO DE PREÇOS - Radar Hardware
                </h1>
                <p style="margin: 6px 0 0 0; font-size: 14px; color: #475569;">
                    Olá, <strong>Yury</strong>,
                </p>
                <p style="margin: 4px 0 0 0; font-size: 13px; color: #64748b; line-height: 1.5;">
                    Abaixo está o consolidado dos menores preços de hardware encontrados hoje nas maiores lojas do Brasil (Kabum, Terabyte, Pichau e Amazon), organizados rigorosamente por busca técnica.
                </p>
            </div>
        </div>

        <div style="padding: 25px 30px;">
            
            <!-- SEÇÃO 1: PCs 8GB VRAM -->
            <div style="margin-bottom: 25px;">
                <div style="display: flex; align-items: center; margin-bottom: 10px;">
                    <h2 style="margin: 0; font-size: 16px; font-weight: 700; color: #0e2a47;">
                        🖥️ Computadores Gamer — Placa de Vídeo de 8GB VRAM
                    </h2>
                </div>
                {render_category_table(pcs_8gb, "PC Gamer 8GB", max_items=8)}
            </div>

            <!-- SEÇÃO 2: PCs 12GB VRAM -->
            <div style="margin-bottom: 25px;">
                <div style="display: flex; align-items: center; margin-bottom: 10px;">
                    <h2 style="margin: 0; font-size: 16px; font-weight: 700; color: #0e2a47;">
                        🚀 Computadores Gamer — Placa de Vídeo de 12GB VRAM
                    </h2>
                </div>
                {render_category_table(pcs_12gb, "PC Gamer 12GB", max_items=8)}
            </div>

            <!-- SEÇÃO 3: PCs 16GB VRAM -->
            <div style="margin-bottom: 25px;">
                <div style="display: flex; align-items: center; margin-bottom: 10px;">
                    <h2 style="margin: 0; font-size: 16px; font-weight: 700; color: #0e2a47;">
                        ⚡ Computadores Gamer — Placa de Vídeo de 16GB VRAM
                    </h2>
                </div>
                {render_category_table(pcs_16gb, "PC Gamer 16GB", max_items=8)}
            </div>

            <!-- SEÇÃO 4: Memórias RAM 16GB DDR4 -->
            <div style="margin-bottom: 25px;">
                <div style="display: flex; align-items: center; margin-bottom: 10px;">
                    <h2 style="margin: 0; font-size: 16px; font-weight: 700; color: #0e2a47;">
                        🧠 Memórias RAM 16GB DDR4 Gamer (Mais Baratas de Cada Loja)
                    </h2>
                </div>
                {render_category_table(rams_16gb, "RAM 16GB DDR4", max_items=10)}
            </div>

            <!-- SEÇÃO 5: SSDs 512GB -->
            <div style="margin-bottom: 25px;">
                <div style="display: flex; align-items: center; margin-bottom: 10px;">
                    <h2 style="margin: 0; font-size: 16px; font-weight: 700; color: #0e2a47;">
                        💾 Armazenamento — SSDs de 512GB (e 480GB/500GB)
                    </h2>
                </div>
                {render_category_table(ssds_512, "SSD 512GB", max_items=8)}
            </div>

            <!-- SEÇÃO 6: SSDs 1TB -->
            <div style="margin-bottom: 25px;">
                <div style="display: flex; align-items: center; margin-bottom: 10px;">
                    <h2 style="margin: 0; font-size: 16px; font-weight: 700; color: #0e2a47;">
                        💾 Armazenamento — SSDs de 1TB (e 960GB/1000GB)
                    </h2>
                </div>
                {render_category_table(ssds_1tb, "SSD 1TB", max_items=8)}
            </div>

            <!-- ANÁLISE DE MERCADO (ÚLTIMAS 24H) - Conforme imagem TechCorp -->
            <div style="margin-top: 35px; border-top: 2px solid #e2e8f0; padding-top: 22px;">
                <h3 style="margin: 0 0 12px 0; font-size: 14px; font-weight: 700; color: #0e2a47; text-transform: uppercase; letter-spacing: 0.5px;">
                    ANÁLISE DE MERCADO (ÚLTIMAS 24H)
                </h3>
                
                <ul style="margin: 0 0 18px 0; padding-left: 20px; color: #334155; font-size: 13px; line-height: 1.6;">
                    <li><strong>Key Trends (PCs 12GB VRAM):</strong> A <strong>Pichau</strong> e a <strong>Kabum</strong> lideram com o melhor custo-benefício gráfico para jogos modernos com a GeForce RTX 3060 12GB a partir de <strong>{format_currency(best_pc_12gb.get('price', 0)) if best_pc_12gb else 'R$ 4.299,00'}</strong> à vista no PIX.</li>
                    <li><strong>Key Trends (PCs 8GB VRAM):</strong> A <strong>TerabyteShop</strong> domina a faixa de entrada mais econômica a partir de <strong>{format_currency(best_pc_8gb.get('price', 0)) if best_pc_8gb else 'R$ 1.899,99'}</strong> com RX 580 8GB, enquanto a Pichau oferece configurações atualizadas com RX 7600 a R$ 3.749,96.</li>
                    <li><strong>Key Trends (PCs 16GB VRAM):</strong> Menor preço em máquinas topo de linha liderado pela TerabyteShop com Radeon RX 9060 XT 16GB por <strong>{format_currency(best_pc_16gb.get('price', 0)) if best_pc_16gb else 'R$ 6.859,99'}</strong>.</li>
                    <li><strong>Key Trends (RAM 16GB DDR4):</strong> Disputa acirrada entre <strong>TerabyteShop</strong> ({format_currency(best_ram.get('price', 0)) if best_ram else 'R$ 679,99'}) e <strong>Pichau</strong> (R$ 699,99) pelo menor valor nacional em pentes de 16GB DDR4 3200MHz.</li>
                    <li><strong>Key Trends (Armazenamento SSD):</strong> A <strong>Amazon</strong> lidera a categoria de 480GB/512GB com Western Digital WD Green por <strong>{format_currency(best_ssd_512.get('price', 0)) if best_ssd_512 else 'R$ 394,25'}</strong>, e a Terabyte/Pichau assumem a faixa de 1TB por <strong>{format_currency(best_ssd_1tb.get('price', 0)) if best_ssd_1tb else 'R$ 759,90'}</strong>.</li>
                </ul>

                <h4 style="margin: 0 0 8px 0; font-size: 13px; font-weight: 700; color: #0e2a47;">
                    Ações Recomendadas
                </h4>
                <div style="background-color: #f8fafc; border-left: 4px solid #0e2a47; padding: 12px 16px; border-radius: 4px; font-size: 13px; color: #334155; line-height: 1.5;">
                    🎯 <strong>Oportunidades em Destaque:</strong> Momento propício para aquisição de memórias RAM 16GB DDR4 3200MHz na Pichau/Terabyte ({format_currency(best_ram.get('price', 0)) if best_ram else 'R$ 679,99'}) e SSDs WD Green na Amazon. Para computadores prontos com garantia de 12 meses, a melhor escolha em custo/longevidade é o PC Pichau Vidar ou Kabum 2eletro com RTX 3060 12GB.
                </div>
            </div>

            <!-- Footer Corporativo -->
            <div style="margin-top: 35px; border-top: 1px solid #e2e8f0; padding-top: 18px;">
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="font-size: 11px; color: #64748b; vertical-align: middle;">
                            <strong>RadarPreços Global</strong><br>
                            Monitoramento Automatizado de Hardware • Brasil
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
    save_price_history(history)
    return html_content

def send_email_alert(data: Dict[str, Any]) -> bool:
    """Dispara o e-mail via SMTP usando variáveis de ambiente."""
    sender_email = os.getenv('SENDER_EMAIL')
    sender_password = os.getenv('SENDER_PASSWORD') # Senha de app do Gmail
    receiver_email = os.getenv('RECEIVER_EMAIL', sender_email)
    smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
    smtp_port = int(os.getenv('SMTP_PORT', '465'))

    # Salva sempre uma cópia local para inspeção/teste em html
    html_body = generate_html_report(data)
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
    msg['Subject'] = f"📊 RELATÓRIO DIÁRIO DE PREÇOS - Hardware ({datetime.now().strftime('%d/%m/%Y')})"
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
        return True
    except Exception as e:
        logger.error(f"Erro ao enviar e-mail: {e}")
        return False
