#!/usr/bin/env python3
"""
Geo-Sentinel: Importador de Malha Elétrica (ArcGIS GDB)
Script de ponto de entrada para facilitar o uso no Hugging Face.
"""

import sys
from pathlib import Path


DIRETORIO_DATA = "/home/pi/Deposito/Projetos/Meus/Geo-Sentinel/Linhas"

# 1. Ajuste de Rota: Garante que o Python ache a pasta 'fontes' a partir da raiz
ROOT_DIR = Path(__file__).resolve().parent
#pasta_fontes = ROOT_DIR / "fontes"
pasta_fontes = ROOT_DIR
sys.path.append(str(pasta_fontes))

# 2. Importa o seu controller blindado
try:
    from Controller.Controller_Extrator_GDB import Controller_Extrator_GDB
except ImportError as e:
    print(f"❌ Erro de importação. Verifique se a estrutura de pastas está correta.\nDetalhe: {e}")
    sys.exit(1)

def main():
    print("🌍 [Geo-Sentinel] Iniciando importação da malha elétrica...")
    
    try:
        # Liga o motor e inicia a varredura
        extrator = Controller_Extrator_GDB()
        extrator.varrer_e_processar(str(DIRETORIO_DATA))
        
        print("\n✅ Carga de infraestrutura concluída com sucesso!")
        print("🌱 O banco de dados está pronto para o motor de detecção vegetal.")
        
    except Exception as e:
        print(f"\n❌ Falha na execução: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # Garante que o script rode apenas se for o processo principal
    main()
    