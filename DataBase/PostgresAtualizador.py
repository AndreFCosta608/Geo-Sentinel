import os
import sys
import time
import psycopg2
from psycopg2 import sql, errors
from dotenv import load_dotenv

load_dotenv()

# ============================================================
#  CONFIGURAÇÕES – lidas do .env
# ============================================================
DB_HOST     = os.getenv("DB_HOST", "localhost")
DB_PORT     = int(os.getenv("DB_PORT", 5432)) # Padrão Postgres é 5432
DB_USER     = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME     = os.getenv("DB_NAME", "nome_do_banco")
SQL_FILE    = os.getenv("SQL_ATUALIZADOR", "Atualizador.sql")

# Cores ANSI para o terminal
BOLD, GREEN, YELLOW, RED, GRAY, RESET = "\033[1m", "\033[92m", "\033[93m", "\033[91m", "\033[90m", "\033[0m"

class PostgresManager:
    def __init__(self):
        self.config = {
            "host": DB_HOST,
            "port": DB_PORT,
            "user": DB_USER,
            "password": DB_PASSWORD,
            "dbname": DB_NAME
        }

    def executar_script(self, sql_content):
        """
        Executa múltiplos statements SQL (estilo o seu atualizador).
        """
        conn = None
        try:
            conn = psycopg2.connect(**self.config)
            conn.autocommit = False
            cursor = conn.cursor()
            
            # No Postgres, o psycopg2 consegue lidar com múltiplos statements 
            # se enviados de uma vez, mas para manter seu log detalhado,
            # ideal é usar sua função separar_statements (mantida do original).
            statements = self._separar_statements(sql_content)
            
            sucesso, falhas = 0, 0
            for idx, stmt in enumerate(statements, 1):
                if not stmt.strip(): continue
                
                print(f"  {GRAY}[{idx:>3}/{len(statements)}]{RESET} Executando: {BOLD}{stmt[:50].strip()}...{RESET}")
                
                try:
                    cursor.execute(stmt)
                    conn.commit()
                    print(f"            {GREEN}✔ OK{RESET}")
                    sucesso += 1
                except Exception as e:
                    conn.rollback()
                    # Mapeamento de erros toleráveis do Postgres (Códigos SQLSTATE)
                    # 42701: Column already exists
                    # 42P07: Table already exists
                    # 42704: Undefined object (DROP if exists fail)
                    if hasattr(e, 'pgcode') and e.pgcode in ('42701', '42P07', '42704'):
                        print(f"            {YELLOW}⚠ Ignorado: {e.pgerror.splitlines()[0]}{RESET}")
                        sucesso += 1
                    else:
                        print(f"            {RED}✘ ERRO: {e}{RESET}")
                        falhas += 1
            
            return sucesso, falhas

        except Exception as e:
            print(f"{RED}Falha crítica de conexão: {e}{RESET}")
            return 0, 1
        finally:
            if conn: conn.close()

    def _separar_statements(self, sql_str):
        # Aqui você pode reutilizar a lógica de parser que você já tem no seu arquivo original
        # O Postgres usa aspas simples para strings e aspas duplas para identificadores (tabelas/colunas)
        return sql_str.split(';') # Simplificação para o exemplo

# Exemplo de uso direto (estilo o seu main)
if __name__ == "__main__":
    manager = PostgresManager()
    with open(SQL_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    
    manager.executar_script(content)
    