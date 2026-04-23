import os
import time
import json
import requests
import rasterio
import numpy as np
from pathlib import Path
from datetime import datetime
from pyproj import Transformer
from Controller.Master_Controller import Controller_Master

class Controller_Vegetal(Controller_Master):
    
    def __init__(self):
        super().__init__()
        # 🇪🇺 NOVO ENDPOINT: AWS Earth Search (Catálogo ultra estável do Sentinel-2)
        self.stac_url = "https://earth-search.aws.element84.com/v1/search"
        self.bbox_rj = [-43.80, -23.08, -43.10, -22.74]
        self.pasta_tifs = Path("data/tifs")
        self.pasta_tifs.mkdir(parents=True, exist_ok=True)

    def catalogar_novas_cenas(self):
        self.log("🛰️ Iniciando varredura no catálogo ESA (Sentinel-2)...")
        
        params = {
            "bbox": self.bbox_rj,
            "collections": ["sentinel-2-l2a"], # Coleção Nível 2A (Correção Atmosférica já aplicada)
            "limit": 5,
            "query": {"eo:cloud_cover": {"lt": 20}} # Filtro de nuvens < 20%
        }
        
        try:
            response = requests.post(self.stac_url, json=params, timeout=60)
            response.raise_for_status() # Força o erro se não for 200 OK
            
            itens = response.json().get('features', [])
            self.log(f"📊 Encontradas {len(itens)} cenas correspondentes aos critérios.")

            for item in itens:
                # No Sentinel-2 via AWS, as chaves já são amigáveis
                assets_links = {
                    "green": item['assets'].get('green', {}).get('href'),
                    "red": item['assets'].get('red', {}).get('href'),
                    "nir": item['assets'].get('nir', {}).get('href')
                }
                
                sql = """
                    INSERT INTO catalogo_imagens 
                    (entity_id, nuvens, url_origem, data_coleta, baixado, processada)
                    VALUES (%s, %s, %s, %s, FALSE, FALSE)
                    ON CONFLICT (entity_id) DO NOTHING;
                """
                args = (
                    item['id'], 
                    item['properties'].get('eo:cloud_cover'),
                    json.dumps(assets_links),
                    item['properties'].get('datetime')
                )
                
                linhas = self.objDB.insert(sql, args)
                if linhas > 0:
                    self.log(f"✅ Nova cena catalogada: {item['id']}")
                    
        except requests.exceptions.RequestException as e:
            self.log(f"❌ Erro de rede ao catalogar na ESA: {str(e)}")
        except Exception as e:
            self.log(f"❌ Erro genérico ao catalogar: {str(e)}")
            
    def listar_pendentes_download(self):
        sql = """
            SELECT id, entity_id, url_origem 
            FROM catalogo_imagens 
            WHERE baixado = FALSE 
            ORDER BY data_coleta DESC LIMIT 3;
        """
        return self.objDB.select(sql)
    
    def _executar_download(self, url, destino):
        # --- NOVO: VERIFICAÇÃO DE SOBERANIA LOCAL ---
        if destino.exists() and destino.stat().st_size > 1000000: # Se tem + de 1MB
            self.log(f"↪️ Arquivo {destino.name} já identificado no disco. Pulando para o próximo.")
            return True

        tentativas = 3
        timeout_segundos = 300
        headers = {'User-Agent': 'GeoSentinel/1.0'}
    
        for i in range(tentativas):
            try:
                self.log('')
                self.log(f"⏳ Tentativa {i+1}/{tentativas}: {destino.name}")
                
                with requests.get(url, stream=True, timeout=timeout_segundos, headers=headers) as r:
                    r.raise_for_status()
                    total_size = int(r.headers.get('content-length', 0))
                    downloaded = 0
                    
                    with open(destino, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=1024*1024):
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                if total_size > 0:
                                    percent = int(100 * downloaded / total_size)
                                    bar = '█' * (percent // 2) + '-' * (50 - percent // 2)
                                    print(f"\r   |{bar}| {percent}% ({downloaded/(1024*1024):.1f}MB)", end="")
                    print() 
                    return True
            except Exception as e:
                self.log(f"\n⚠️ Falha na tentativa {i+1}: {e}")
                if i < tentativas - 1:
                    time.sleep(10)
                else:
                    if os.path.exists(destino): os.remove(destino)
        return False

    def processar_fila_download(self):
        pendentes = self.listar_pendentes_download()
        
        if not pendentes:
            self.log("💾 Nada pendente para download no momento.")
            return

        for registro in pendentes:
            id_db = registro['id']
            eid = registro['entity_id']
            links = json.loads(registro['url_origem'])
            
            caminhos_sucesso = {}
            houve_erro = False
            
            self.log(f"📂 Iniciando fluxo de download da cena: {eid}")
            
            for banda, url in links.items():
                if not url: 
                    self.log(f"⚠️ URL ausente para a banda {banda} na cena {eid}.")
                    continue
                
                nome_arquivo = f"{eid}_{banda}.tif"
                caminho_final = self.pasta_tifs / nome_arquivo
                
                if self._executar_download(url, caminho_final):
                    caminhos_sucesso[banda] = str(caminho_final)
                else:
                    houve_erro = True
                    break # Se uma banda falha, aborta a cena inteira para não calcular NDVI furado

            if not houve_erro and caminhos_sucesso:
                sql_upd = "UPDATE catalogo_imagens SET baixado = TRUE, caminho_local = %s WHERE id = %s"
                self.objDB.update(sql_upd, (json.dumps(caminhos_sucesso), id_db))
                self.log(f"🎉 Cena {eid} baixada 100% e cravada no banco de dados!")
    
    def _executar_deteccao(self, id_imagem, eid, path_red, path_nir, path_green):
        try:
            with rasterio.open(path_red) as src_red, \
                 rasterio.open(path_nir) as src_nir, \
                 rasterio.open(path_green) as src_green:
                
                self.log(f"🧠 Lendo matrizes e calculando índices para {eid}...")
                
                # Leitura das bandas (Sentinel-2: B04, B08, B03)
                red = src_red.read(1).astype('float32')
                nir = src_nir.read(1).astype('float32')
                green = src_green.read(1).astype('float32')

                # Cálculo do NDVI (Índice de Vegetação)
                # Fórmula: (NIR - RED) / (NIR + RED)
                ndvi = np.divide((nir - red), (nir + red), out=np.zeros_like(nir), where=(nir + red) != 0)

                # Cálculo do NDWI (Índice de Água - para filtrar ruído de corpos d'água)
                ndwi = np.divide((green - nir), (green + nir), out=np.zeros_like(green), where=(green + nir) != 0)

                # Criando a máscara: Onde é vegetação (NDVI > 0.4) e NÃO é água (NDWI < 0)
                mask = (ndvi > 0.4) & (ndwi < 0)
                
                # O "Salto" para performance no i3
                indices = np.argwhere(mask)[::50] 
                total_pontos = len(indices)
                
                # --- BLOCO DE AUDITORIA (Inserir aqui) ---
                if total_pontos > 0:
                    r_t, c_t = indices[0]
                    lon_t, lat_t = src_red.xy(r_t, c_t)
                    print(f"\n🌍 AUDITORIA GEOGRÁFICA:")
                    print(f"   > Coordenada Bruta: {lon_t}, {lat_t}")
                    print(f"   > CRS da Imagem:    {src_red.crs}")
                    
                    if str(src_red.crs) != "EPSG:4326":
                        print(f"   ⚠️ ALERTA: Imagem em METROS ({src_red.crs}). Banco em GRAUS (4326)!")
                # ------------------------------------------

                # --- 1. RECUPERAR CHECKPOINT ---
                sql_check = "SELECT pontos_processados FROM catalogo_imagens WHERE id = %s"
                res = self.objDB.select(sql_check, (id_imagem,))
                inicio = res[0]['pontos_processados'] if res and res[0]['pontos_processados'] else 0

                if inicio >= total_pontos:
                    self.log(f"✅ Cena {eid} já estava 100% concluída.")
                    return True

                # --- 2. BENCHMARK ---
                self.log(f"🧪 Benchmark de hardware no annunnaki...")
                t0 = time.time()
                amostra = min(10, total_pontos)
                for i in range(amostra):
                    lon, lat = src_red.xy(indices[i][0], indices[i][1])
                    self.objDB.select("SELECT ST_SetSRID(ST_MakePoint(%s, %s), 4326)", (float(lon), float(lat)))
                
                tempo_medio = (time.time() - t0) / amostra
                est_seg = (total_pontos - inicio) * tempo_medio
                
                horas = int(est_seg // 3600)
                minutos = int((est_seg % 3600) // 60)
                segundos = int(est_seg % 60)
                
                print(f"\n📊 --- RELATÓRIO DE CAPACIDADE ---")
                print(f"   > Pontos Pendentes: {total_pontos - inicio}")
                if horas > 0:
                    print(f"   > Estimativa Pragmática: {horas}h {minutos}m {segundos}s")
                else:
                    print(f"   > Estimativa Pragmática: {minutos}m {segundos}s")
                
                print(f"\n⚠️  NOTA DE PERFORMANCE:")
                print(f"   Acreditamos que o tempo total de processamento não deverá passar de alguns minutos.")
                print(f"   Porém, como é impossível prever o comportamento exato do GIS dentro da base de dados")
                print(f"   devido às dezenas de variações de versões existentes, a estimativa acima reflete")
                print(f"   um cenário conservador e pragmático para o hardware atual.")
                
                confirmar = input("\n🚀 Iniciar processamento PAGINADO? (s/n): ")
                if confirmar.lower() != 's': return False
                
                # --- MARCA DE INÍCIO ---
                agora_inicio = datetime.now()
                t_inicio_real = time.time() # Para cálculo de duração
                
                print(f"\n🟢 Início do Processamento: {agora_inicio.strftime('%d/%m - %H:%M:%S')}")
                self.log(f"🛰️ Vigilância iniciada em {eid} (Checkpoint: {inicio})")

                # --- 3. PAGINAÇÃO ---
                tamanho_pagina = 500
                lista_batch = []
                t_inicio_real = time.time()

                # Criamos o tradutor: De Metros (32723) para Graus (4326)
                transformer = Transformer.from_crs(src_red.crs, "EPSG:4326", always_xy=True)
                for i in range(inicio, total_pontos):
                    r, c = indices[i]
                    
                    x_metr, y_metr = src_red.xy(r, c)
                    
                    # CONVERSÃO REAL: Transforma metros em Longitude/Latitude
                    lon, lat = transformer.transform(x_metr, y_metr)
                    
                    val_ndvi = float(ndvi[r, c])
                    nivel = 5 if val_ndvi > 0.7 else 3 if val_ndvi > 0.6 else 1
                    
                    lista_batch.append((f"Risco {eid}", nivel, float(lon), float(lat)))
                    #lista_batch.append((f"Risco {eid}", nivel, float(lon), float(lat), float(lon), float(lat)))

                    if len(lista_batch) >= tamanho_pagina or i == total_pontos - 1:
                        valores_list = []
                        for item in lista_batch:
                            # item: (titulo, nivel, lon, lat, lon_ref, lat_ref)
                            valores_list.append(f"('{item[0]}', {item[1]}, {item[2]}, {item[3]})")
                        
                        valores_str = ",".join(valores_list)
                            
                        sql_batch = f"""
                            INSERT INTO alertas_geosentinel (camada_id, titulo, nivel_critico, ponto_gps)
                            SELECT 0, val.t, val.n, ST_SetSRID(ST_MakePoint(val.lo, val.la), 4326)
                            FROM (VALUES {valores_str}) AS val(t, n, lo, la)
                            WHERE EXISTS (
                                SELECT 1 FROM rede_eletrica r 
                                WHERE ST_DWithin(
                                    ST_SetSRID(ST_MakePoint(val.lo, val.la), 4326), 
                                    r.geometria, 
                                    0.0005
                                )
                            )
                        """
                        
                        self.objDB.insert(sql_batch, ()) 
                        
                        # Checkpoint
                        self.objDB.update("UPDATE catalogo_imagens SET pontos_processados = %s WHERE id = %s", (i, id_imagem))
                        
                        lista_batch = []

                        # Gauge
                        percent = int(100 * (i + 1) / total_pontos)
                        passado = time.time() - t_inicio_real
                        vel = (i - inicio + 1) / passado if passado > 0 else 0
                        restante = (total_pontos - i) / vel if vel > 0 else 0
                        
                        bar = '█' * (percent // 5) + '░' * (20 - percent // 5)
                        print(f"\r   |{bar}| {percent}% - {vel:.1f} pts/s - Faltam: {int(restante//60)}m{int(restante%60)}s", end="")

                
                # --- MARCA DE CONCLUSÃO ---
                agora_fim = datetime.now()
                t_fim_real = time.time()
                
                # Cálculo da duração formatada
                duracao_total = t_fim_real - t_inicio_real
                horas_gastas = int(duracao_total // 3600)
                minutos_gastos = int((duracao_total % 3600) // 60)
                segundos_gastos = int(duracao_total % 60)

                print(f"\n\n🏁 Finalizado em: {agora_fim.strftime('%d/%m - %H:%M:%S')}")
                
                # Exibe a diferença de tempo real
                if horas_gastas > 0:
                    tempo_total_str = f"{horas_gastas}h {minutos_gastos}m {segundos_gastos}s"
                else:
                    tempo_total_str = f"{minutos_gastos}m {segundos_gastos}s"

                print(f"⏱️ Tempo total gasto: {tempo_total_str}")
                print(f"✅ Concluído!")
                return True

        except Exception as e:
            self.log(f"❌ Erro crítico: {e}")
            return False

    def processar_novas_cenas(self):
        self.log("🧠 Iniciando processamento de matrizes...")
        
        sql = """
            SELECT id, entity_id, caminho_local 
            FROM catalogo_imagens 
            WHERE baixado = TRUE AND processada = FALSE 
            LIMIT 1;
        """
        cenas = self.objDB.select(sql)
        
        if not cenas:
            self.log("📭 Nenhuma cena pendente de processamento.")
            return

        for cena in cenas:
            id_db, eid, caminhos = cena['id'], cena['entity_id'], json.loads(cena['caminho_local'])
            
            self.log(f"🧹 Limpando alertas antigos da cena {eid}...")
            sql_limpeza = "DELETE FROM alertas_geosentinel WHERE titulo LIKE %s AND camada_id = 0"
            self.objDB.delete(sql_limpeza, (f"%{eid}%",))
            
            sucesso = self._executar_deteccao(id_db, eid, caminhos.get('red'), caminhos.get('nir'), caminhos.get('green'))
            
            if sucesso:
                self.objDB.update("UPDATE catalogo_imagens SET processada = TRUE WHERE id = %s", (id_db,))
                self.log(f"✅ Matrizes da cena {eid} analisadas com sucesso.")
                
                self.log("♻️ Removendo .tifs pesados do disco...")
                for banda, path_arquivo in caminhos.items():
                    if path_arquivo and os.path.exists(path_arquivo):
                        try:
                            os.remove(path_arquivo)
                        except Exception as e:
                            self.log(f"⚠️ Falha ao deletar {path_arquivo}: {e}")
                self.log(f"✅ Disco liberado para a próxima rodada.")

if __name__ == "__main__":
    worker = Controller_Vegetal()
    worker.catalogar_novas_cenas()
    worker.processar_fila_download()
    worker.processar_novas_cenas()
    print('Concluido...')
    