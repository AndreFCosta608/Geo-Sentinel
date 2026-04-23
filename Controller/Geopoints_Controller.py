import json
import Configuracores
import DataBase.DB_PostGres
from decimal import Decimal
from datetime import datetime
from Controller.Master_Controller import Controller_Master

class Controller_Geopoints(Controller_Master):

    def return_vegetal_alerts(self, min_lon, min_lat, max_lon, max_lat, zoom):
        # Determinamos o tamanho do grid de agrupamento baseado no zoom
        # Quanto menor o zoom, maior o grid (mais pontos agrupados)
        if zoom < 10:
            grid_size = 0.1  # Aprox 11km
        elif zoom < 13:
            grid_size = 0.01 # Aprox 1.1km
        else:
            grid_size = 0    # Sem agrupamento (zoom alto)

        if grid_size > 0:
            # SQL para Agrupamento (Clusters)
            query = f"""
                SELECT 
                    count(*) as total,
                    MAX(nivel_critico) as nivel_critico,
                    'Cluster de Alertas' as titulo,
                    concat(count(*), ' alertas nesta região') as descricao,
                    ST_AsGeoJSON(ST_Centroid(ST_Collect(ponto_gps)))::json as geometria
                FROM alertas_geosentinel
                WHERE ponto_gps && ST_MakeEnvelope(%s, %s, %s, %s, 4326)
                  AND resolvido = FALSE
                GROUP BY ST_SnapToGrid(ponto_gps, {grid_size})
                LIMIT 1000
            """
        else:
            # SQL para Pontos Reais (Bounding Box simples)
            query = """
                SELECT id, titulo, descricao, nivel_critico,
                       ST_AsGeoJSON(ponto_gps)::json as geometria
                FROM alertas_geosentinel
                WHERE ponto_gps && ST_MakeEnvelope(%s, %s, %s, %s, 4326)
                  AND resolvido = FALSE
                ORDER BY nivel_critico DESC
                LIMIT 1000
            """
        
        params = (min_lon, min_lat, max_lon, max_lat)
        results = self.objDB.select(query, params)
        
        # Converte o retorno do banco para o formato FeatureCollection esperado pelo Leaflet
        geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": r['geometria'],
                    "properties": {
                        "id": r.get('id'),
                        "titulo": r['titulo'],
                        "nivel": r['nivel_critico'],
                        "descricao": r['descricao'],
                        "total": r.get('total', 1) # 1 se for ponto real, N se for cluster
                    }
                } for r in results
            ]
        }
        return geojson
