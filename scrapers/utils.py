import re
import logging
from typing import Optional, Any, Dict, List

logger = logging.getLogger(__name__)

def clean_price(price_input: Any) -> Optional[float]:
    """Converte diferentes formatos de preço (float, int ou string 'R$ 1.234,56') para float."""
    if price_input is None:
        return None
    if isinstance(price_input, (int, float)):
        return float(price_input)
    
    txt = str(price_input).strip()
    txt = re.sub(r'[^\d,\.]', '', txt)
    if not txt:
        return None
    
    # Suporta formato brasileiro (1.299,90) e internacional (1,299.90)
    if ',' in txt and '.' in txt:
        if txt.rfind(',') > txt.rfind('.'):
            txt = txt.replace('.', '').replace(',', '.')
        else:
            txt = txt.replace(',', '')
    elif ',' in txt:
        txt = txt.replace(',', '.')
    
    try:
        val = float(txt)
        return val if val > 0 else None
    except ValueError:
        return None

def format_currency(value: float) -> str:
    """Formata valor em Real Brasileiro (BRL)"""
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def summarize_collection(count: int, errors: List[str], attempted: int, blocked: int = 0) -> Dict[str, Any]:
    if count > 0:
        status = "partial" if errors or blocked else "ok"
    elif blocked:
        status = "blocked"
    elif errors:
        status = "error"
    elif attempted == 0:
        status = "not_collected"
    else:
        status = "empty"

    detail = "; ".join(errors[:3])
    if len(errors) > 3:
        detail += f"; mais {len(errors) - 3} falha(s)"
    return {"status": status, "count": count, "attempted": attempted, "detail": detail}

def classify_search_page(body: str, result_count: int) -> tuple[str | None, str | None]:
    if re.search(r'captcha|robot check|security verification|verificação de segurança|digite os caracteres', body, re.I):
        return "blocked", "CAPTCHA ou verificação de segurança"
    if result_count == 0 and not re.search(
        r'não encontramos resultados|não há resultados|nenhum resultado|nenhum produto encontrado|'
        r'não foram encontrados produtos|não encontramos produtos|no results|0\s+resultados?',
        body,
        re.I,
    ):
        return "error", "Estrutura de resultados ausente ou não reconhecida"
    return None, None


def get_native_ram_capacity(text: str) -> Optional[int]:
    t = text.upper()
    t = re.sub(
        r'\b\d{1,2}\s*GB\s*(?:GDDR\d*|VRAM|DEDICADA|DE\s+MEM[OÓ]RIA\s+DE\s+V[IÍ]DEO)\b',
        ' ',
        t,
    )
    t = re.sub(r'\b(?:VRAM|DEDICADA)\s*(?:DE\s*)?\d{1,2}\s*GB\b', ' ', t)
    capacities = {int(value) for value in re.findall(r'\b(8|16|32|64)\s*GB\b', t)}
    for pattern, total in (
        (r'\b1X\s*16\s*GB\b', 16),
        (r'\b2X\s*8\s*GB\b', 16),
        (r'\b1X\s*32\s*GB\b', 32),
        (r'\b2X\s*16\s*GB\b', 32),
        (r'\b4X\s*8\s*GB\b', 32),
        (r'\b2X\s*32\s*GB\b', 64),
    ):
        if re.search(pattern, t):
            capacities.add(total)
    return max(capacities) if capacities else None

def has_native_32gb_ram(text: str) -> bool:
    return (get_native_ram_capacity(text) or 0) >= 32

def is_nvidia_gpu(text: str) -> bool:
    """Verifica se a GPU do computador é da NVIDIA (GeForce, RTX, GTX, Quadro)."""
    t = text.upper()
    return bool(re.search(r'\b(GEFORCE|RTX|GTX|NVIDIA|QUADRO)\b', t))

def extract_gpu_name(title: str, description: str = "") -> str:
    """Extrai de forma limpa o modelo exato da GPU para exibição técnica."""
    t = f"{title} {description}".upper()
    m_nv = re.search(r'\b((?:GEFORCE\s+)?RTX\s+\d{4}(?:\s*TI|\s*SUPER)*(?:\s*\d{1,2}\s*GB)?)\b', t)
    if m_nv:
        return m_nv.group(1).title()
    m_gtx = re.search(r'\b((?:GEFORCE\s+)?GTX\s+\d{4}(?:\s*TI)*(?:\s*\d{1,2}\s*GB)?)\b', t)
    if m_gtx:
        return m_gtx.group(1).title()
    m_amd = re.search(r'\b((?:RADEON\s+)?RX\s+\d{3,4}(?:\s*XT|\s*GRE)*(?:\s*\d{1,2}\s*GB)?)\b', t)
    if m_amd:
        return m_amd.group(1).title()
    return "GPU Dedicada"

def get_ai_recommendation(gpu_name: str, vram: int) -> str:
    """Gera recomendação técnica de uso para servidores de Inteligência Artificial e LLMs."""
    g = gpu_name.upper()
    if vram >= 16:
        if "4060" in g:
            return "Melhor custo 16GB VRAM: Excelente p/ Modelos 14B Q4 (Qwen 2.5), Fine-Tuning LoRA e contexto longo"
        elif any(k in g for k in ["4070", "4080", "5070", "5080"]):
            return "Alta performance Ada/Blackwell: FP8 nativo, altíssima velocidade p/ vLLM e batch inference"
        return "16GB VRAM: Ideal p/ Fine-Tuning LoRA e Modelos 14B quantizados"
    else: # 12GB
        if "3060" in g:
            return "Campeão Custo/Benefício: Roda LLaMA-3 8B, Mistral 7B e SDXL c/ folga de contexto (Q4/Q8)"
        elif any(k in g for k in ["4070", "5070"]):
            return "Tensor Cores 4ª/5ª Geração: FP8 nativo, inferência ultra-rápida de LLMs locais"
        return "12GB VRAM: Perfeito p/ Ollama, Whisper Large v3, Embeddings e LLMs 7B/8B"

def classify_pc_vram(title: str, description: str = "") -> Optional[str]:
    """Classifica a VRAM explicita ou conhecida da GPU em 8GB, 12GB ou 16GB."""
    t = re.sub(r'\s+', ' ', f"{title} {description}".upper())

    if re.search(r'^(PLACA DE V[IÍ]DEO|PLACA DE VIDEO|GPU\b|PLACA GRAFICA)', t):
        return None
    if re.search(r'\b(GABINETE|FONTE|PLACA M[AÃ]E|COOLER|WATER COOLER|TECLADO|MOUSE|MONITOR|SUPORTE)\b', t):
        if not re.search(r'\b(PC GAMER|COMPUTADOR|DESKTOP|CPU GAMER)\b', t):
            return None
    if not re.search(r'\b(PC GAMER|COMPUTADOR|DESKTOP|CPU GAMER)\b', t):
        return None

    explicit_gpu = re.search(
        r'\b(?:GEFORCE\s+)?(RTX|GTX|RX)\s*(\d{3,4})(?:\s*(TI|SUPER))?\s*(\d{1,2})\s*GB\b(?!\s*(?:DDR|RAM))',
        t
    )
    if explicit_gpu:
        capacity = int(explicit_gpu.group(4))
        return f"{capacity}GB" if capacity in (8, 12, 16) else None

    explicit_label = re.search(
        r'\b(\d{1,2})\s*GB\s*(?:VRAM|DEDICADA)\b|\b(?:VRAM|DEDICADA)\s*(?:DE\s*)?(\d{1,2})\s*GB\b',
        t
    )
    if explicit_label:
        capacity = int(explicit_label.group(1) or explicit_label.group(2))
        return f"{capacity}GB" if capacity in (8, 12, 16) else None

    model = re.search(r'\b(RTX|GTX|RX)\s*(\d{3,4})(?:\s*(TI|SUPER))?\b', t)
    if not model:
        return None

    family, number, suffix = model.groups()
    suffix = suffix or ""
    defaults = {
        ("RTX", "3050", ""): "8GB",
        ("RTX", "3060", ""): "12GB",
        ("RTX", "3070", ""): "8GB",
        ("RTX", "3080", "TI"): "12GB",
        ("RTX", "4060", ""): "8GB",
        ("RTX", "4070", ""): "12GB",
        ("RTX", "4070", "TI"): "12GB",
        ("RTX", "4070", "SUPER"): "12GB",
        ("RTX", "4080", ""): "16GB",
        ("RTX", "5050", ""): "8GB",
        ("RTX", "5060", ""): "8GB",
        ("RTX", "5070", ""): "12GB",
        ("RTX", "5070", "TI"): "16GB",
        ("RTX", "5080", ""): "16GB",
        ("GTX", "1650", ""): "4GB",
        ("GTX", "1660", ""): "6GB",
        ("GTX", "2060", "SUPER"): "8GB",
        ("RX", "6600", ""): "8GB",
        ("RX", "6650", ""): "8GB",
        ("RX", "6650", "XT"): "8GB",
        ("RX", "7600", ""): "8GB",
        ("RX", "7600", "XT"): "8GB",
        ("RX", "7650", ""): "8GB",
        ("RX", "7700", ""): "8GB",
        ("RX", "7700", "XT"): "8GB",
        ("RX", "7800", ""): "8GB",
        ("RX", "7800", "XT"): "8GB",
        ("RX", "9050", ""): "8GB",
    }
    return defaults.get((family, number, suffix))

def _is_complete_pc_title(title: str) -> bool:
    product_text = re.sub(
        r'\b(?:PARA|COMPAT[IÍ]VEL\s+COM)\s+(?:PCS?|COMPUTADOR(?:ES)?(?:\s+DESKTOP)?|DESKTOPS?)\b',
        ' ',
        title,
    )
    return bool(re.search(
        r'\b(PC|COMPUTADOR(?:ES)?|DESKTOP|CPU\s+GAMER|ALL\s+IN\s+ONE)\b',
        product_text,
    ))


def classify_ssd_capacity(title: str) -> Optional[str]:
    """Classifica a capacidade do SSD sem aceitar acessorios ou variantes ambiguas."""
    t = title.upper()

    if _is_complete_pc_title(t):
        return None

    # Exclui acessórios (cases, cabos, gavetas, adaptadores, capas) e discos rígidos mecânicos (HDs)
    if re.search(r'\b(CASE|GAVETA|ADAPTADOR|DOCK|CABO|DISSIPADOR|ENCLOSURE|CAPA|BOLSA|ESTOJO|MAIXA|TRANSPORTE|R[IÍ]GIDA|SACO)\b', t):
        return None
    if re.search(r'\b(RPM|DISCO R[ÍI]GIDO|HD INTERNO|HDD)\b', t) and not re.search(r'\bSSD\b', t):
        return None
    
    # Confirma que é SSD
    if not re.search(r'\b(SSD|NVME|M\.2)\b', t):
        return None

    variant = re.search(r'\((1|2)(?:\s*,)?\s*TB\)', t)
    if variant:
        return f"{variant.group(1)}TB"
    
    capacities = set()
    patterns = {
        '2TB': r'\b(2\s*TB|2000\s*G(?:B)?|2048\s*G(?:B)?)\b',
        '1TB': r'\b(1\s*TB|960\s*G(?:B)?|1000\s*G(?:B)?|1024\s*G(?:B)?)\b',
        '512GB': r'\b(512\s*G(?:B)?|500\s*G(?:B)?|480\s*G(?:B)?)\b',
    }
    for capacity, pattern in patterns.items():
        if re.search(pattern, t):
            capacities.add(capacity)

    return next(iter(capacities)) if len(capacities) == 1 else None

        
        

def is_nvme_ssd(title: str) -> bool:
    """Verifica se o SSD e NVMe sem tratar M.2 SATA como PCIe."""
    t = title.upper()
    if re.search(r'\bSATA\b', t) and not re.search(r'\b(NVME|PCIE)\b', t):
        return False
    return bool(re.search(r'\b(NVME|PCIE|GEN[345]|SN580|NV3|NV2|P3|P3\s*PLUS|NM620|NM790|LEGEND|REAPER|GAMMIX|FURY\s*RENEGADE)\b', t))

def is_preferred_nvme_model(title: str) -> bool:
    """Verifica se é um modelo NVMe de destaque custo-benefício (Kingston NV3, WD Blue SN580, Crucial P3 Plus)."""
    t = title.upper()
    if re.search(r'\b(NV3|NV2)\b', t) or re.search(r'\bKINGSTON\s+NV3\b', t):
        return True
    if re.search(r'\b(SN580|SN570)\b', t) or re.search(r'\bWD\s+(?:BLUE\s+)?SN580\b', t):
        return True
    if re.search(r'\b(P3\s*PLUS|P3)\b', t) or re.search(r'\bCRUCIAL\s+P3\b', t):
        return True
    return False

def is_top_brand_ram(title: str) -> bool:
    """
    Identifica as marcas e linhas de memórias preferidas do usuário:
    - Kingston Fury Beast
    - XPG Gammix D35
    - Corsair Vengeance LPX
    - Crucial / Crucial Ballistix / Crucial Pro
    """
    t = title.upper()
    if re.search(r'\b(FURY|BEAST)\b', t) or (re.search(r'\bKINGSTON\b', t) and re.search(r'\b(FURY|BEAST|RENEGADE)\b', t)):
        return True
    if re.search(r'\b(GAMMIX\s*D35|GAMMIX\s*D10|GAMMIX|D35)\b', t) or (re.search(r'\bXPG\b', t) and re.search(r'\b(D35|GAMMIX|SPECTRIX)\b', t)):
        return True
    if re.search(r'\b(VENGEANCE|LPX)\b', t) or (re.search(r'\bCORSAIR\b', t) and re.search(r'\b(VENGEANCE|LPX)\b', t)):
        return True
    if re.search(r'\bCRUCIAL\b', t):
        return True
    return False

def is_valid_ram_16gb_ddr4(title: str) -> bool:
    """
    Valida se o produto é uma memória RAM de 16GB DDR4 para Desktop/Gamer.
    Rejeita: SODIMM (notebook), DDR3, DDR5, pentes avulsos de 8GB e acessórios.
    """
    t = title.upper()

    if _is_complete_pc_title(t):
        return False

    # 1. Rejeita se for para Notebook / SODIMM / Servidor
    if re.search(r'\b(SODIMM|SO-DIMM|NOTEBOOK|LAPTOP|MACBOOK|ECC|RDIMM|LRDIMM|REGISTRADA|POWEREDGE|PROLIANT|SERVER|SERVIDOR)\b', t):
        return False
        
    # 2. Rejeita se for DDR3 ou DDR5
    if re.search(r'\b(DDR3|DDR5|DDR-3|DDR-5)\b', t):
        return False
        
    # 3. Deve ser explicitamente DDR4
    if not re.search(r'\b(DDR4|DDR-4)\b', t):
        return False
        
    # 4. Rejeita placas-mãe, processadores, kits upgrade ou acessórios avulsos
    if re.search(r'\b(PLACA\s*M[ÃA]E|MOTHERBOARD|MAINBOARD|PROCESSADOR|RYZEN|INTEL\s+CORE|KIT\s+UPGRADE|FONTE|GABINETE)\b', t):
        return False
    if re.search(r'^(DISSIPADOR|COOLER|CABO|ADAPTADOR|GAVETA|CASE)\b', t) or re.search(r'\b(DISSIPADOR\s+PARA|COOLER\s+PARA)\b', t):
        return False
        
    return get_native_ram_capacity(t) == 16

def analyze_pc_ram_upgrade(title: str, text: str = "", price: float = 0.0) -> Dict[str, Any]:
    """
    Analisa a placa-mãe e configuração de RAM para determinar a viabilidade e facilidade de upgrade para 32GB (Servidor IA).
    """
    full_text = f"{title} {text}".upper()
    
    # 1. Identificar Placa-Mãe
    m_h3 = re.search(r'PLACA\s*M[ÃA]E\s*([^<\n\r]+)', text, re.IGNORECASE)
    mobo = "M-ATX"
    if m_h3:
        raw_mobo = m_h3.group(1).strip()
        m_chip = re.search(r'\b(H510M?|A520M?|H610M?|B450M?|B550M?|B760M?|B650M?|A320M?|H310M?|B360M?|Z690|Z790|X570)\b', raw_mobo, re.IGNORECASE)
        if m_chip:
            mobo = m_chip.group(1).upper()
        else:
            mobo = raw_mobo[:20].strip()
    else:
        m_chip = re.search(r'\b(H510M?|A520M?|H610M?|B450M?|B550M?|B760M?|B650M?|A320M?|H310M?|B360M?|Z690|Z790|X570)\b', full_text, re.IGNORECASE)
        if m_chip:
            mobo = m_chip.group(1).upper()

    # 2. Slots estimados
    if any(k in mobo for k in ["B550", "B760", "B650", "Z690", "Z790", "X570"]) or "4 SLOTS" in full_text:
        slots = 4
    else:
        slots = 2

    # 3. Configuração de RAM instalada
    has_2x = bool(re.search(r'\b2\s*[xX]\s*8\s*GB\b|MEMORIA-GEN-2X|2X8GB', full_text))
    has_1x = bool(re.search(r'\b1\s*[xX]\s*16\s*GB\b|MEMORIA-PCH-GEN-1X|1X16GB', full_text))
    
    if re.search(r'\b32\s*GB\b', full_text) and not re.search(r'UPGRADE|SUPORTA', full_text):
        ram_desc = "32GB"
    elif has_1x or ("16GB" in full_text and "1X" in full_text):
        ram_desc = "1x16GB"
    elif has_2x or "2X8GB" in full_text:
        ram_desc = "2x8GB"
    elif "16GB" in full_text:
        ram_desc = "2x8GB"
    elif "8GB" in full_text:
        ram_desc = "1x8GB"
    else:
        ram_desc = "16GB"

    # 4. Status de upgrade para 32GB
    if "32GB" in ram_desc:
        status_label = "32GB Nativo"
        badge_type = "success"
        badge_bg = "#dcfce7"
        badge_color = "#15803d"
        extra_cost = 0.0
        tip = "Já vem com 32GB de fábrica. Capacidade ideal para LLMs locais sem custo adicional."
    elif ram_desc == "1x16GB":
        status_label = "Upgrade Fácil (+1x 16GB)"
        badge_type = "easy"
        badge_bg = "#dbeafe"
        badge_color = "#1d4ed8"
        extra_cost = 320.0
        tip = "Possui 1 slot livre. Basta adicionar +1 pente de 16GB avulso (~R$ 320) do radar para ter 32GB Dual Channel."
    elif slots == 4:
        status_label = "Upgrade Fácil (Placa 4 Slots)"
        badge_type = "easy"
        badge_bg = "#dbeafe"
        badge_color = "#1d4ed8"
        extra_cost = 320.0
        tip = f"Placa-mãe {mobo} tem 4 slots. Você pode adicionar pentes extras sem retirar a memória original."
    else:
        status_label = "2 Slots Ocupados (Troca p/ 2x16GB)"
        badge_type = "replace"
        badge_bg = "#fef3c7"
        badge_color = "#b45309"
        extra_cost = 600.0
        tip = f"Placa {mobo} com 2 slots ocupados por 2x8GB. Para 32GB, compre um kit 2x16GB avulso (~R$ 600) em vez de pagar R$ 777 na Pichau."

    est_total_32gb = price + extra_cost if price > 0 else 0.0

    return {
        "mobo": mobo,
        "slots": slots,
        "ram_desc": ram_desc,
        "status_label": status_label,
        "badge_type": badge_type,
        "badge_bg": badge_bg,
        "badge_color": badge_color,
        "extra_cost": extra_cost,
        "est_total_32gb": est_total_32gb,
        "tip": tip
    }

PICHAU_BUNDLE_ACTION_ID = "40d8fb501dafbbc2a3dc281d952ec724da3deffb4f"

def check_pichau_bundle_32gb_options(url: str, base_price: float = 0.0) -> Dict[str, Any]:
    """
    Consulta o configurador Server Action da Pichau para verificar se há opção de 32GB
    em estoque para vir montado direto de fábrica.
    """
    import json
    from curl_cffi import requests as cffi_requests
    
    res = {
        "status": "error",
        "detail": "",
        "site_customization_available": False,
        "site_option_title": "",
        "site_diff_price": 0.0,
        "site_assembled_total": base_price,
        "site_status_label": "Indisponível no site",
        "site_badge_bg": "#fee2e2",
        "site_badge_color": "#991b1b"
    }
    
    try:
        session = cffi_requests.Session(impersonate="chrome124")
        get_headers = {
            "Accept-Language": "pt-BR,pt;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        r_get = session.get(url, headers=get_headers, timeout=12)
        if r_get.status_code != 200:
            res["status"] = "http_error"
            res["detail"] = f"GET HTTP {r_get.status_code}"
            res["site_status_label"] = "Configurador 32GB indisponível no site"
            logger.warning(f"[Pichau] Configurador 32GB: GET HTTP {r_get.status_code}")
            return res

        m_sku = re.search(r'\b(PCM-[A-Za-z0-9_-]+)\b', r_get.text)
        if not m_sku:
            res["status"] = "sku_not_found"
            res["detail"] = "SKU PCM não encontrado"
            res["site_status_label"] = "Configurador 32GB indisponível no site"
            logger.warning("[Pichau] Configurador 32GB: SKU PCM não encontrado")
            return res
        sku = m_sku.group(1)
        
        post_headers = {
            "Accept-Language": "pt-BR,pt;q=0.9",
            "Next-Action": PICHAU_BUNDLE_ACTION_ID,
            "Accept": "text/x-component",
            "Content-Type": "text/plain;charset=UTF-8",
            "Origin": "https://www.pichau.com.br",
            "Referer": url,
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin"
        }
        r_post = session.post(url, headers=post_headers, data=json.dumps([sku]), timeout=12)
        if r_post.status_code == 409:
            res["status"] = "action_unavailable"
            res["detail"] = "POST HTTP 409: Server Action unavailable"
            res["site_status_label"] = "Configurador 32GB indisponível no site"
            logger.warning("[Pichau] Configurador 32GB: Server Action indisponível (HTTP 409)")
            return res
        if r_post.status_code != 200:
            res["status"] = "http_error"
            res["detail"] = f"POST HTTP {r_post.status_code}"
            res["site_status_label"] = "Configurador 32GB indisponível no site"
            logger.warning(f"[Pichau] Configurador 32GB: POST HTTP {r_post.status_code}")
            return res
        res["status"] = "parse_error"
        res["detail"] = "Resposta do configurador não reconhecida"
        recognized_payload = False
        for line in r_post.text.split("\n"):
            if line.startswith("1:"):
                data = json.loads(line[2:])
                recognized_payload = True
                for opt in data.get("options", []):
                    if opt.get("title") == "Memória":
                        def_item = next((v for v in opt.get("value", []) if v.get("is_default")), None)
                        def_price = float(def_item.get("price", 0)) if def_item else 0.0

                        in_stock_32gb = []
                        all_32gb = []
                        for val in opt.get("value", []):
                            val_title = val.get("title") or val.get("product", {}).get("name", "")
                            val_stock = val.get("product", {}).get("stock_status")
                            val_price = float(val.get("price", 0))

                            if "32GB" in val_title.upper() or "32 GB" in val_title.upper():
                                diff = val_price - def_price
                                item_data = {"title": val_title, "stock": val_stock, "diff": diff}
                                all_32gb.append(item_data)
                                if val_stock == "IN_STOCK":
                                    in_stock_32gb.append(item_data)

                        if in_stock_32gb:
                            best = in_stock_32gb[0]
                            diff_val = round(best["diff"], 2)
                            res["site_customization_available"] = True
                            res["site_option_title"] = best["title"]
                            res["site_diff_price"] = diff_val
                            res["site_assembled_total"] = round(base_price + diff_val, 2)
                            res["site_status_label"] = f"🟢 Disponível no Site (+R$ {diff_val:,.2f})"
                            res["site_badge_bg"] = "#dcfce7"
                            res["site_badge_color"] = "#15803d"
                        elif all_32gb:
                            res["site_status_label"] = "🔴 32GB Esgotado no Site"
                            res["site_badge_bg"] = "#fee2e2"
                            res["site_badge_color"] = "#991b1b"
                        else:
                            res["site_status_label"] = "⚪ Sem opção 32GB no site"
                            res["site_badge_bg"] = "#f1f5f9"
                            res["site_badge_color"] = "#475569"
        if not recognized_payload:
            logger.warning("[Pichau] Configurador 32GB: resposta sem payload reconhecido")
            return res
        res["status"] = "ok"
    except json.JSONDecodeError as e:
        res["status"] = "parse_error"
        res["detail"] = f"JSON inválido: {e}"
        res["site_status_label"] = "Configurador 32GB indisponível no site"
        logger.warning(f"[Pichau] JSON inválido no configurador 32GB: {e}")
    except Exception as e:
        res["status"] = "error"
        res["detail"] = str(e)
        res["site_status_label"] = "Configurador 32GB indisponível no site"
        logger.warning(f"[Pichau] Erro ao consultar configurador 32GB: {e}")

    return res


