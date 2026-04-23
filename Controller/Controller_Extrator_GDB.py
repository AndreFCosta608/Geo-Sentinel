import os
import fiona
import geopandas as gpd
from pathlib import Path
from sqlalchemy import text
from sqlalchemy import create_engine
from shapely.geometry import LineString
from shapely.geometry import MultiLineString
from geoalchemy2 import Geometry as GeoGeneric
from Controller.Master_Controller import Controller_Master

class Controller_Extrator_GDB(Controller_Master):
    
    def __init__(self):
        super().__init__()
        self.engine = create_engine('postgresql://pi:123456@localhost:5432/geo_sentinel')

    def varrer_e_processar(self, diretorio_raiz):
        """Varre o diretório em busca de PASTAS .gdb"""
        self.log(f"🔎 Iniciando varredura em: {diretorio_raiz}")
        
        path_raiz = Path(diretorio_raiz)
        
        # Ajuste: Buscamos qualquer item que seja um diretório e termine com .gdb
        gdbs_encontrados = [
            p for p in path_raiz.glob("**/*") 
            if p.is_dir() and p.suffix.lower() == '.gdb'
        ]
        
        if not gdbs_encontrados:
            self.log(f"📭 Nenhum File Geodatabase (.gdb) encontrado em {diretorio_raiz}.")
            # Dica: Verifique se o caminho passado no main está correto
            return

        for gdb_path in gdbs_encontrados:
            self.log(f"📦 Localizado: {gdb_path.name}")
            # No Linux, o fiona/geopandas precisa do caminho absoluto ou string da pasta
            self._extrair_linhas_gdb(str(gdb_path))

    def _extrair_linhas_gdb(self, gdb_path_str):
        """
        Lê as camadas vetoriais dentro do GDB e popula a tabela rede_eletrica no PostGIS.
        """
        gdb_path = Path(gdb_path_str)
        
        try:
            # 1. Lista as camadas (fiona lê o diretório .gdb no Unix/Linux)
            layers = fiona.listlayers(gdb_path_str)
            
            for layer in layers:
                self.log(f"  ∟ Lendo camada: {layer}...")
                
                # 2. Carrega a camada via GeoPandas
                gdf = gpd.read_file(gdb_path_str, layer=layer)
                
                # 3. Trava para tabelas alfanuméricas
                if not isinstance(gdf, gpd.GeoDataFrame) or not hasattr(gdf, 'geometry'):
                    self.log(f"  ⚠️ Camada '{layer}' é alfanumérica. Pulando...")
                    continue
    
                # 4. Filtro de tipo: Apenas linhas
                gdf = gdf[gdf.geometry.type.isin(['LineString', 'MultiLineString'])]
                
                if gdf.empty:
                    self.log(f"  ℹ️ Camada '{layer}' sem trechos de rede aérea. Pulando...")
                    continue
    
                # 5. Normalização para WGS84 (EPSG:4326)
                if gdf.crs != "EPSG:4326":
                    gdf = gdf.to_crs("EPSG:4326")
    
                # 6. Conversão para MultiLineString (Garante compatibilidade total)
                gdf['geometry'] = [
                    MultiLineString([g]) if isinstance(g, LineString) else g 
                    for g in gdf.geometry
                ]
    
                # 7. Preparação para o banco
                df_final = gdf[['geometry']].copy()
                df_final.rename_geometry('geometria', inplace=True)
                
                # O osm_id agora é uma string identificando a fonte/camada/index
                df_final['osm_id'] = [f"gdb_{layer}_{i}" for i in range(len(df_final))]
                df_final['tipo'] = f"ArcGIS_{layer}"
                df_final['fonte'] = gdb_path.name
    
                # 8. INGESTÃO VIA STAGING (Para ignorar duplicatas no PostGIS)
                total = len(df_final)
                self.log(f"  🚀 Carregando {total} trechos na tabela de staging...")
                
                # 8.1 - Injeta rápido na tabela temporária (replace limpa a tabela anterior)
                df_final.to_postgis(
                    'rede_eletrica_staging', 
                    self.engine, 
                    if_exists='replace', 
                    index=False,
                    dtype={'geometria': GeoGeneric(geometry_type='MULTILINESTRING', srid=4326)}
                )
                
                self.log("  🔄 Transferindo para a principal (descartando duplicatas)...")
                
                # 8.2 - Transfere os dados ignorando a trava (ON CONFLICT DO NOTHING)
                sql_transferencia = text("""
                    INSERT INTO rede_eletrica (geometria, osm_id, tipo, fonte)
                    SELECT geometria, osm_id, tipo, fonte 
                    FROM rede_eletrica_staging
                    ON CONFLICT (md5(st_asbinary(geometria))) DO NOTHING;
                """)
                
                with self.engine.begin() as conn:
                    result = conn.execute(sql_transferencia)
                    linhas_inseridas = result.rowcount
                    
                self.log(f"  ✅ Camada {layer} concluída: {linhas_inseridas} trechos novos salvos ({(total - linhas_inseridas)} duplicatas ignoradas).")
    
        except Exception as e:
            self.log(f"❌ Erro crítico ao processar {gdb_path.name}: {str(e)}")

if __name__ == "__main__":
    DIRETORIO_DATA = "/home/pi/Deposito/Projetos/Meus/Geo-Sentinel/Linhas"
    extractor = Controller_Extrator_GDB()
    extractor.varrer_e_processar(DIRETORIO_DATA)
    print("\n🚀 Carga de infraestrutura concluída. O banco está pronto para o Showroom!")
    