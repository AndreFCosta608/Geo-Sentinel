#!/bin/bash
# Geo-Sentinel: Script de Reconstrução Total
# Este script restaura a estrutura, funções e dados na ordem correta.

# Configurações (Ajusta se necessário)
DB_NAME="geo_sentinel"
DB_USER="pi"
BACKUP_DIR="./backup_full_rebuild"

# Define a senha para não pedir interação (mesma do script Python)
export PGPASSWORD="123456"

echo "============================================================"
echo "🚜 Iniciando Restauro Total do Geo-Sentinel..."
echo "============================================================"

# 1. Criar a base de dados se não existir (opcional, requer permissão de superuser)
# psql -h localhost -U $DB_USER -c "CREATE DATABASE $DB_NAME;" 2>/dev/null

# 2. Habilitar PostGIS (Caso seja uma instalação do zero)
echo "🌍 Habilitando extensão PostGIS..."
psql -h localhost -U $DB_USER -d $DB_NAME -c "CREATE EXTENSION IF NOT EXISTS postgis;"

# 3. Restaurar Estrutura (Tabelas, Índices, Constraints)
echo "📦 Criando tabelas e índices..."
psql -h localhost -U $DB_USER -d $DB_NAME -f "$BACKUP_DIR/tabelas/estrutura_completa.sql"

# 4. Restaurar Procedures e Functions
echo "🧠 Instalando procedures e funções..."
psql -h localhost -U $DB_USER -d $DB_NAME -f "$BACKUP_DIR/procedures/functions_and_procs.sql"

# 5. Restaurar Dados (Itera sobre todos os arquivos na pasta dados)
echo "💾 Importando massa de dados..."
for f in "$BACKUP_DIR/dados/"*_data.sql; do
    [ -e "$f" ] || continue
    echo "  → Populando: $(basename "$f")"
    psql -h localhost -U $DB_USER -d $DB_NAME -f "$f"
done

echo "============================================================"
echo "✅ Geo-Sentinel reconstruído com sucesso!"
echo "============================================================"
