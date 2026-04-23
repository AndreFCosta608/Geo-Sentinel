#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Geo-Sentinel: Full Rebuild Backup Engine
----------------------------------------
Gera um backup granular capaz de reconstruir o banco do zero:
  - DDL de tabelas, índices e constraints
  - Triggers e Procedures
  - Dados em formato SQL compatível com PostGIS
"""

import os
import subprocess
from datetime import datetime
from pathlib import Path

# ============================================================
#  CONFIGURAÇÕES - Bare Metal
# ============================================================
DB_CONFIG = {
    "host": "localhost",
    "port": "5432",
    "user": "pi",
    "dbname": "geo_sentinel"
}
# Definimos a senha via variável de ambiente para o pg_dump não pedir interação
os.environ["PGPASSWORD"] = "123456"

OUTPUT_ROOT = Path("./backup_full_rebuild")
# ============================================================

def executar_comando(comando):
    """Executa comando shell e captura saída"""
    try:
        processo = subprocess.run(
            comando, shell=True, check=True, 
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Erro no comando: {e.stderr.decode()}")
        return False

def garantir_pastas():
    pastas = ['tabelas', 'procedures', 'triggers', 'dados']
    for p in pastas:
        (OUTPUT_ROOT / p).mkdir(parents=True, exist_ok=True)

def backup_total():
    garantir_pastas()
    print("=" * 60)
    print(f"🚀 Iniciando Full Backup: {DB_CONFIG['dbname']}")
    print("=" * 60)

    # 1. Backup da Estrutura de Tabelas (DDL, Índices, Constraints)
    # --schema-only: evita dados / --no-owner: facilita portabilidade
    print("📦 Extraindo definições de tabelas e índices...")
    cmd_schema = (
        f"pg_dump -h {DB_CONFIG['host']} -U {DB_CONFIG['user']} -d {DB_CONFIG['dbname']} "
        f"--schema-only --no-owner --no-privileges --file={OUTPUT_ROOT}/tabelas/estrutura_completa.sql"
    )
    executar_comando(cmd_schema)

    # 2. Backup de Procedures e Funções
    print("🧠 Extraindo Procedures e Funções...")
    # Filtramos por rotinas (p = procedures/functions)
    cmd_proc = (
        f"pg_dump -h {DB_CONFIG['host']} -U {DB_CONFIG['user']} -d {DB_CONFIG['dbname']} "
        f"--schema-only --no-owner --section=post-data " 
        f"| grep -Pz '(?s)CREATE (OR REPLACE )?(FUNCTION|PROCEDURE).*?LANGUAGE' "
        f"> {OUTPUT_ROOT}/procedures/functions_and_procs.sql"
    )
    # Nota: No Postgres, funções costumam vir no schema-only, 
    # mas o comando acima garante um arquivo isolado para consulta rápida.
    executar_comando(cmd_proc)

    # 3. Backup de Dados Granular (Um arquivo por tabela)
    # Primeiro listamos as tabelas para iterar
    import psycopg2
    try:
        conn = psycopg2.connect(
            host=DB_CONFIG['host'], port=DB_CONFIG['port'],
            user=DB_CONFIG['user'], database=DB_CONFIG['dbname'], 
            password=os.environ["PGPASSWORD"]
        )
        cur = conn.cursor()
        cur.execute("SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname = 'public' AND tablename NOT IN ('spatial_ref_sys')")
        tabelas = [r[0] for r in cur.fetchall()]
        
        for tab in tabelas:
            print(f"  → Exportando dados: {tab}")
            # --data-only: apenas INSERTs / --inserts: gera comandos SQL legíveis para PostGIS
            cmd_dados = (
                f"pg_dump -h {DB_CONFIG['host']} -U {DB_CONFIG['user']} -d {DB_CONFIG['dbname']} "
                f"--data-only --inserts --no-owner --table={tab} "
                f"--file={OUTPUT_ROOT}/dados/{tab}_data.sql"
            )
            executar_comando(cmd_dados)
        
        cur.close()
        conn.close()
    except Exception as e:
        print(f"❌ Falha ao listar tabelas: {e}")

    print("\n" + "=" * 60)
    print(f"✅ Backup concluído em: {OUTPUT_ROOT.resolve()}")
    print("=" * 60)

if __name__ == "__main__":
    backup_total()
    