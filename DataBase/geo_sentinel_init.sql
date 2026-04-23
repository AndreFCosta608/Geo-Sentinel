-- 0. LIMPEZA (Cuidado: Isso apaga os dados antigos para resetar o Schema)
DROP TABLE IF EXISTS alertas_geosentinel CASCADE;
DROP TABLE IF EXISTS dados_dengue CASCADE;
DROP TABLE IF EXISTS rede_eletrica CASCADE;
DROP TABLE IF EXISTS catalogo_imagens CASCADE;
DROP TABLE IF EXISTS camadas_projeto CASCADE;
DROP TABLE IF EXISTS sitios_arqueologicos CASCADE;
DROP TABLE IF EXISTS spatial_ref_sys CASCADE;

-- 1. EXTENSÕES
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_raster;

-- 3. CATÁLOGO DE IMAGENS (Ajustado para o Downloader e GC)
CREATE TABLE catalogo_imagens (
    id SERIAL PRIMARY KEY,
    entity_id TEXT UNIQUE NOT NULL,        -- ID do satélite (ex: CBERS_4A_...)
    nuvens DOUBLE PRECISION DEFAULT 0,
    url_origem TEXT,                       -- URL para o Downloader usar
    caminho_local TEXT,                    -- Onde o arquivo .tif mora no Annunnaki
    baixado BOOLEAN DEFAULT FALSE,         -- Controle para o Downloader
    processada BOOLEAN DEFAULT FALSE,      -- Controle para o Analyzer
    criado_em TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    data_coleta TIMESTAMP WITH TIME ZONE   -- Data da foto do satélite
);

ALTER TABLE catalogo_imagens ADD COLUMN pontos_processados INTEGER DEFAULT 0;

CREATE TABLE rede_eletrica (
    id SERIAL PRIMARY KEY,
    osm_id BIGINT UNIQUE,
    tipo TEXT, -- 'transmissao', 'distribuicao'
    geometria GEOMETRY(LineString, 4326),
    ultima_sincronizacao TIMESTAMP DEFAULT NOW()
);

ALTER TABLE rede_eletrica ADD COLUMN IF NOT EXISTS fonte VARCHAR(50);

ALTER TABLE rede_eletrica ADD CONSTRAINT geo_unique UNIQUE (osm_id, geometria);

CREATE INDEX idx_rede_eletrica_gist ON rede_eletrica USING GIST(geometria);

CREATE UNIQUE INDEX IF NOT EXISTS idx_rede_unique_geom ON rede_eletrica (md5(ST_AsBinary(geometria)));

CREATE INDEX IF NOT EXISTS idx_rede_eletrica_geom_gist ON rede_eletrica USING GIST (geometria);

ALTER TABLE rede_eletrica 
  ALTER COLUMN geometria TYPE geometry(MultiLineString, 4326) 
  USING ST_Multi(geometria);
  
ALTER TABLE rede_eletrica ALTER COLUMN osm_id TYPE VARCHAR(255);


-- Garante que o PostGIS usa busca em árvore (GIST) em vez de ler linha por linha
CREATE INDEX IF NOT EXISTS idx_rede_eletrica_geometria 
ON rede_eletrica USING GIST (geometria);

-- Atualiza o mapa interno do Postgres para ele saber que o índice existe
VACUUM ANALYZE rede_eletrica;  


-- 5. INFO-DENGUE (Ajustado para os nomes que o Rust busca)
CREATE TABLE dados_dengue (
    id SERIAL PRIMARY KEY,
    codigo_municipio INT NOT NULL, 
    semana_ref TEXT NOT NULL,              -- Formato "202601"
    nivel_alerta INT,                      -- 1 a 4
    casos INT,
    temperatura_media DOUBLE PRECISION,
    nome_municipio TEXT DEFAULT 'Rio de Janeiro',
    localizacao GEOMETRY(Point, 4326),
    UNIQUE(codigo_municipio, semana_ref)
);

-- 7. ALERTAS UNIFICADOS (O "Cérebro" do Showroom)
CREATE TABLE alertas_geosentinel (
    id SERIAL PRIMARY KEY,
    camada_id INT,
    titulo TEXT,
    descricao TEXT,
    nivel_critico INT CHECK (nivel_critico BETWEEN 1 AND 5),
    ponto_gps GEOMETRY(Point, 4326),
    resolvido BOOLEAN DEFAULT FALSE,
    criado_em TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    geojson_evidencia JSONB 
);

-- 8. ÍNDICES ESPACIAIS (O motor do Annunnaki)
CREATE INDEX idx_imagens_geo ON catalogo_imagens USING GIST(ST_MakePoint(0,0)); -- Placeholder se usar area_coberta
CREATE INDEX idx_rede_geo ON rede_eletrica USING GIST(geometria);
CREATE INDEX idx_dengue_geo ON dados_dengue USING GIST(localizacao);
CREATE INDEX idx_alertas_geo ON alertas_geosentinel USING GIST(ponto_gps);
CREATE INDEX idx_arqueo_geo ON sitios_arqueologicos USING GIST(geometria);

-- 9. PERMISSÕES PARA O USUÁRIO PI
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO pi;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO pi;

