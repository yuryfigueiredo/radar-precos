import re
from typing import Optional, Any

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

def classify_pc_vram(title: str, description: str = "") -> Optional[str]:
    """
    Classifica a VRAM da GPU do PC em '8GB', '12GB' ou '16GB'.
    Mapeia rigorosamente pelos modelos de placa de vídeo do mercado,
    NUNCA confundindo memória RAM com VRAM da GPU.
    """
    t = f"{title} {description}".upper()
    
    # Rejeita se for claramente peça avulsa (placa de vídeo avulsa, gabinete, periférico)
    if re.search(r'^(PLACA DE V[IÍ]DEO|PLACA DE VIDEO|GPU\b|PLACA GRAFICA)', t):
        return None
    if re.search(r'\b(GABINETE|FONTE|PLACA M[AÃ]E|COOLER|WATER COOLER|TECLADO|MOUSE|MONITOR|SUPORTE)\b', t):
        if not re.search(r'\b(PC GAMER|COMPUTADOR|DESKTOP|CPU GAMER)\b', t):
            return None
            
    # Deve ser um computador completo
    if not re.search(r'\b(PC GAMER|COMPUTADOR|DESKTOP|CPU GAMER)\b', t):
        return None

    # Se a GPU for explicitamente de 2GB, 4GB ou 6GB (ex: RX 550, RX 560, GTX 1650, GTX 1050, GTX 1060, GTX 1660, RTX 3050 6GB), descarta
    if re.search(r'\b(RX\s*550|RX\s*560|GTX\s*1650|GTX\s*1050|GTX\s*1060|GTX\s*1660|RTX\s*3050\s*6\s*GB|RTX\s*2060\s*6\s*GB|4\s*GB\s*DEDICADA|4\s*GB\s*VRAM|6\s*GB\s*VRAM|6\s*GB\s*DEDICADA)\b', t):
        if not re.search(r'\b(RTX\s*(?:3060|3070|3080|40|50)|RX\s*(?:6600|7600|7650|7700|7800|90))\b', t):
            return None

    # 1. GPUs de 16GB VRAM
    if re.search(r'\b(RTX\s*5080|RTX\s*5070\s*TI|RTX\s*4090|RTX\s*4080|RTX\s*4070\s*TI\s*SUPER|RX\s*9070|RX\s*7900|RX\s*7800\s*XT|RX\s*7600\s*XT|RX\s*6950|RX\s*6900|RX\s*6800|ARC\s*A770\s*16\s*GB|RX\s*9060\s*XT\s*16\s*GB)\b', t):
        return '16GB'
    if re.search(r'\b(RTX\s*4060\s*TI|RTX\s*5060\s*TI)\b', t) and re.search(r'\b16\s*GB\b(?!.*(?:DDR|RAM))', t):
        return '16GB'
    if re.search(r'\b16\s*GB\s*(?:VRAM|DEDICADA)\b', t):
        return '16GB'
    if re.search(r'(?:RTX|RX|RADEON|GEFORCE|ARC)\s+[A-Z0-9\s]+?\b16\s*GB\b(?!.*(?:DDR|RAM))', t):
        return '16GB'

    # 2. GPUs de 12GB VRAM
    if re.search(r'\b(RTX\s*5070(?!\s*TI)|RTX\s*4070\s*TI(?!\s*SUPER)|RTX\s*4070\s*SUPER|RTX\s*4070(?!\s*TI)|RX\s*7700\s*XT|RX\s*6750\s*XT|RX\s*6700\s*XT|RTX\s*3080\s*TI|RTX\s*3080\s*12\s*GB|ARC\s*B580)\b', t):
        return '12GB'
    if re.search(r'\bRTX\s*3060\b', t) and not re.search(r'\bRTX\s*3060\s*8\s*GB\b', t):
        return '12GB'
    if re.search(r'\b12\s*GB\s*(?:VRAM|DEDICADA)\b', t):
        return '12GB'
    if re.search(r'(?:RTX|RX|RADEON|GEFORCE|ARC)\s+[A-Z0-9\s]+?\b12\s*GB\b(?!.*(?:DDR|RAM))', t):
        return '12GB'

    # 3. GPUs de 8GB VRAM
    if re.search(r'\b(RTX\s*5060(?!\s*TI\s*16)|RTX\s*5050|RTX\s*4060(?!\s*TI\s*16)|RTX\s*3070|RTX\s*3060\s*8\s*GB|RTX\s*3050|RTX\s*2070|RTX\s*2060\s*SUPER|RX\s*9050|RX\s*7650|RX\s*7600(?!\s*XT)|RX\s*6650|RX\s*6600|RX\s*580|RX\s*590|RX\s*570|ARC\s*A580|ARC\s*A750)\b', t):
        if re.search(r'\bRTX\s*3050\s*6\s*GB\b', t) or (re.search(r'\bRTX\s*3050\b', t) and re.search(r'\b6\s*GB\b', t)):
            return None
        return '8GB'
    if re.search(r'\b8\s*GB\s*(?:VRAM|DEDICADA)\b', t):
        return '8GB'
    if re.search(r'(?:RTX|RX|RADEON|GEFORCE|ARC)\s+[A-Z0-9\s]+?\b8\s*GB\b(?!.*(?:DDR|RAM))', t):
        return '8GB'

    return None

def classify_ssd_capacity(title: str) -> Optional[str]:
    """Classifica SSD em '512GB' ou '1TB', ignorando cases, gavetas e adaptadores."""
    t = title.upper()
    
    # Exclui acessórios (cases, cabos, gavetas, adaptadores, capas) e discos rígidos mecânicos (HDs)
    if re.search(r'\b(CASE|GAVETA|ADAPTADOR|DOCK|CABO|DISSIPADOR|ENCLOSURE|CAPA|BOLSA|ESTOJO)\b', t):
        return None
    if re.search(r'\b(RPM|DISCO R[ÍI]GIDO|HD INTERNO|HDD)\b', t) and not re.search(r'\bSSD\b', t):
        return None
    
    # Confirma que é SSD
    if not re.search(r'\b(SSD|NVME|M\.2)\b', t):
        return None
    
    # 1TB (inclui 960GB, 1000GB, 1TB, 1024GB, 960G, 1000G)
    if re.search(r'\b(1\s*TB|960\s*G(?:B)?|1000\s*G(?:B)?|1024\s*G(?:B)?)\b', t):
        return '1TB'
        
    # 512GB (inclui 480GB, 500GB, 512GB, 480G, 500G, 512G)
    if re.search(r'\b(512\s*G(?:B)?|500\s*G(?:B)?|480\s*G(?:B)?)\b', t):
        return '512GB'
        
    return None

def is_valid_ram_16gb_ddr4(title: str) -> bool:
    """
    Valida se o produto é uma memória RAM de 16GB DDR4 para Desktop/Gamer.
    Rejeita: SODIMM (notebook), DDR3, DDR5, pentes avulsos de 8GB e acessórios.
    """
    t = title.upper()
    
    # 1. Rejeita se for para Notebook / SODIMM / Servidor
    if re.search(r'\b(SODIMM|SO-DIMM|NOTEBOOK|LAPTOP|MACBOOK|ECC|RDIMM|LRDIMM|REGISTRADA|POWEREDGE|PROLIANT|SERVER|SERVIDOR)\b', t):
        return False
        
    # 2. Rejeita se for DDR3 ou DDR5
    if re.search(r'\b(DDR3|DDR5|DDR-3|DDR-5)\b', t):
        return False
        
    # 3. Deve ser explicitamente DDR4
    if not re.search(r'\b(DDR4|DDR-4)\b', t):
        return False
        
    # 4. Rejeita acessórios avulsos (dissipadores avulsos, coolers, cabos)
    if re.search(r'^(DISSIPADOR|COOLER|CABO|ADAPTADOR|GAVETA|CASE)\b', t) or re.search(r'\b(DISSIPADOR\s+PARA|COOLER\s+PARA)\b', t):
        return False
        
    # 5. Deve ser 16GB (1x16GB ou kit 2x8GB)
    has_16gb = bool(re.search(r'\b16\s*GB\b', t) or re.search(r'\b1X16\s*GB\b', t) or re.search(r'\b1X16GB\b', t))
    has_2x8gb = bool(re.search(r'\b2\s*X\s*8\s*GB\b', t) or re.search(r'\(2X8GB\)', t) or re.search(r'\b2X8GB\b', t))
    
    if not (has_16gb or has_2x8gb):
        return False
        
    # 6. Rejeita se tiver 32GB ou 64GB e não for 16GB
    if re.search(r'\b(32|64)\s*GB\b', t) and not (has_16gb or has_2x8gb):
        return False

    return True
