#!/usr/bin/env python3
"""
Geo-Sentinel: Motor de Detecção de Riscos Vegetais
Script de ponto de entrada para processamento de imagens CBERS-4A e PostGIS.
"""

import sys
from pathlib import Path

# 1. Ajuste de Rota: Garante que o Python localize a pasta 'fontes'
ROOT_DIR = Path(__file__).resolve().parent
sys.path.append(str(ROOT_DIR / "fontes"))

try:
    from Controller.Vegetal_Controller import Controller_Vegetal
except ImportError as e:
    print(f"❌ Erro ao importar o Controller Vegetal: {e}")
    sys.exit(1)

def main():
    print("=" * 60)
    print("🛰️  GEO-SENTINEL: INICIANDO VIGILÂNCIA VEGETAL")
    print("=" * 60)
    
    worker = Controller_Vegetal()

    # Estágio 1: Busca no INPE
    print("\n[Passo 1/3] Consultando novas imagens no catálogo...")
    worker.catalogar_novas_cenas()

    # Estágio 2: Download das Bandas (Com o novo sistema de retentativas)
    print("\n[Passo 2/3] Verificando fila de download (Imagens -> Disco)...")
    worker.processar_fila_download()

    # Estágio 3: Processamento NDVI e PostGIS
    print("\n[Passo 3/3] Cruzando vegetação com rede elétrica...")
    worker.processar_novas_cenas()

    print("\n" + "=" * 60)
    print("✅ CICLO DE VIGILÂNCIA CONCLUÍDO")
    print("=" * 60)

if __name__ == "__main__":
    main()
    