import os
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from typing import Dict, List, Any
from scrapers.utils import format_currency

logger = logging.getLogger(__name__)

def generate_html_report(data: Dict[str, Any]) -> str:
    """Gera o corpo do e-mail em HTML responsivo e estilizado."""
    now_str = datetime.now().strftime("%d/%m/%Y às %H:%M")
    
    # Cores por loja
    store_colors = {
        'Kabum': '#ff6500',
        'TerabyteShop': '#28a745',
        'Pichau': '#e60014',
        'Amazon': '#ff9900',
        'Mercado Livre': '#ffe600'
    }
    store_text_colors = {
        'Mercado Livre': '#000000'
    }

    def render_items(items: List[Dict[str, Any]], max_items: int = 8) -> str:
        if not items:
            return '<p style="color: #666; font-style: italic;">Nenhum produto encontrado nesta categoria no momento.</p>'
        
        html = '<table style="width: 100%; border-collapse: collapse; margin-bottom: 15px;">'
        for i, item in enumerate(items[:max_items]):
            store = item.get('store', 'Loja')
            bg_badge = store_colors.get(store, '#333333')
            txt_badge = store_text_colors.get(store, '#ffffff')
            
            html += f'''
            <tr style="border-bottom: 1px solid #e0e0e0; background-color: {'#fdfdfd' if i % 2 == 0 else '#ffffff'};">
                <td style="padding: 10px 8px; vertical-align: middle;">
                    <span style="background-color: {bg_badge}; color: {txt_badge}; font-size: 11px; font-weight: bold; padding: 3px 7px; border-radius: 4px; display: inline-block; margin-bottom: 4px;">
                        {store}
                    </span>
                    <div style="font-size: 14px; font-weight: 500; color: #222;">
                        {item.get('title')}
                    </div>
                    <div style="font-size: 11px; color: #777; margin-top: 2px;">
                        🛡️ {item.get('warranty', 'Com garantia')}
                    </div>
                </td>
                <td style="padding: 10px 8px; text-align: right; vertical-align: middle; white-space: nowrap;">
                    <div style="font-size: 16px; font-weight: bold; color: #0b8043;">
                        {format_currency(item.get('price', 0))}
                    </div>
                    <a href="{item.get('link')}" target="_blank" style="display: inline-block; background-color: #0066cc; color: #ffffff; text-decoration: none; font-size: 12px; font-weight: bold; padding: 5px 12px; border-radius: 4px; margin-top: 5px;">
                        Ver Oferta &rarr;
                    </a>
                </td>
            </tr>
            '''
        html += '</table>'
        return html

    pcs_8gb = data.get('pcs_8gb', [])
    pcs_12gb = data.get('pcs_12gb', [])
    pcs_16gb = data.get('pcs_16gb', [])
    ssds_512 = data.get('ssds_512', [])
    ssds_1tb = data.get('ssds_1tb', [])
    rams_16gb = data.get('rams_16gb', [])

    html_content = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Radar de Preços de Hardware</title>
</head>
<body style="font-family: Arial, Helvetica, sans-serif; background-color: #f4f6f8; margin: 0; padding: 20px; color: #333;">
    <div style="max-width: 720px; margin: 0 auto; background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
        
        <!-- Header -->
        <div style="background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%); color: #ffffff; padding: 25px 20px; text-align: center;">
            <h1 style="margin: 0; font-size: 24px; letter-spacing: 0.5px;">⚡ Radar de Preços: PCs, SSDs e Memórias RAM</h1>
            <p style="margin: 8px 0 0 0; font-size: 13px; opacity: 0.85;">Relatório automático atualizado em {now_str}</p>
        </div>

        <div style="padding: 20px;">
            <!-- Seção PCs Montados -->
            <div style="border-left: 4px solid #1e3c72; padding-left: 10px; margin-bottom: 20px;">
                <h2 style="margin: 0; color: #1e3c72; font-size: 20px;">🖥️ Computadores Prontos com Garantia</h2>
                <p style="margin: 3px 0 0 0; color: #666; font-size: 13px;">Pesquisados na Pichau, Kabum e Terabyte</p>
            </div>

            <!-- Bloco 8GB -->
            <div style="background-color: #fafbfc; border: 1px solid #e1e4e8; border-radius: 6px; padding: 15px; margin-bottom: 20px;">
                <h3 style="margin: 0 0 10px 0; color: #333; font-size: 16px;">🎯 Menores Preços: Placa de Vídeo de 8GB</h3>
                {render_items(pcs_8gb)}
            </div>

            <!-- Bloco 12GB -->
            <div style="background-color: #fafbfc; border: 1px solid #e1e4e8; border-radius: 6px; padding: 15px; margin-bottom: 20px;">
                <h3 style="margin: 0 0 10px 0; color: #333; font-size: 16px;">🚀 Menores Preços: Placa de Vídeo de 12GB</h3>
                {render_items(pcs_12gb)}
            </div>

            <!-- Bloco 16GB -->
            <div style="background-color: #fafbfc; border: 1px solid #e1e4e8; border-radius: 6px; padding: 15px; margin-bottom: 25px;">
                <h3 style="margin: 0 0 10px 0; color: #333; font-size: 16px;">⚡ Menores Preços: Placa de Vídeo de 16GB</h3>
                {render_items(pcs_16gb)}
            </div>

            <!-- Seção Memórias RAM -->
            <div style="border-left: 4px solid #6c5ce7; padding-left: 10px; margin-bottom: 20px;">
                <h2 style="margin: 0; color: #6c5ce7; font-size: 20px;">⚡ Peças: Memórias RAM 16GB DDR4 Gamer (Mais Baratas)</h2>
                <p style="margin: 3px 0 0 0; color: #666; font-size: 13px;">Pesquisadas na Pichau, Terabyte, Kabum, Amazon e Mercado Livre</p>
            </div>

            <!-- Bloco RAM 16GB DDR4 -->
            <div style="background-color: #fafbfc; border: 1px solid #e1e4e8; border-radius: 6px; padding: 15px; margin-bottom: 25px;">
                <h3 style="margin: 0 0 10px 0; color: #333; font-size: 16px;">🎮 Módulos e Kits 16GB DDR4 Gamer (Desktop)</h3>
                {render_items(rams_16gb, max_items=8)}
            </div>

            <!-- Seção SSDs -->
            <div style="border-left: 4px solid #0b8043; padding-left: 10px; margin-bottom: 20px;">
                <h2 style="margin: 0; color: #0b8043; font-size: 20px;">💾 Peças: SSDs Mais Baratos</h2>
                <p style="margin: 3px 0 0 0; color: #666; font-size: 13px;">Pesquisados na Pichau, Terabyte, Kabum, Amazon e Mercado Livre</p>
            </div>

            <!-- Bloco SSD 512GB -->
            <div style="background-color: #fafbfc; border: 1px solid #e1e4e8; border-radius: 6px; padding: 15px; margin-bottom: 20px;">
                <h3 style="margin: 0 0 10px 0; color: #333; font-size: 16px;">📦 SSDs de 512GB (e 480GB/500GB)</h3>
                {render_items(ssds_512)}
            </div>

            <!-- Bloco SSD 1TB -->
            <div style="background-color: #fafbfc; border: 1px solid #e1e4e8; border-radius: 6px; padding: 15px; margin-bottom: 20px;">
                <h3 style="margin: 0 0 10px 0; color: #333; font-size: 16px;">📦 SSDs de 1TB (e 960GB/1000GB)</h3>
                {render_items(ssds_1tb)}
            </div>

        </div>

        <!-- Footer -->
        <div style="background-color: #f1f3f5; padding: 15px 20px; text-align: center; font-size: 12px; color: #777; border-top: 1px solid #e0e0e0;">
            Enviado automaticamente pelo seu robô de buscas no GitHub Actions 🚀
        </div>
    </div>
</body>
</html>
'''
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
    msg['Subject'] = f"⚡ Radar de Preços: PCs, SSDs e RAM 16GB DDR4 - {datetime.now().strftime('%d/%m/%Y')}"
    msg['From'] = f"Radar de Hardware <{sender_email}>"
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
