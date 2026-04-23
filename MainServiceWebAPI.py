import os
import uvicorn
import Configuracores
from fastapi import Request
from fastapi import FastAPI
from datetime import datetime
from jinja2 import TemplateError
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from Controller.Geopoints_Controller import Controller_Geopoints
from starlette.exceptions import HTTPException as StarletteHTTPException

controller = None
try:
    if not os.path.exists(Configuracores.caminhologs):
        os.makedirs(Configuracores.caminhologs)
        
    controller = Controller_Geopoints()

    app = FastAPI(
        title="WebAPI.",
        debug=False,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    ALLOWED_ORIGINS = getattr(Configuracores, "ALLOWED_ORIGINS", ["http://54.39.85.217"])
    #ALLOWED_ORIGINS = ["https://encsg.com.br", "https://www.encsg.com.br"]

    app.add_middleware(
        TrustedHostMiddleware, 
        allowed_hosts=["encsg.com.br", "www.encsg.com.br", "127.0.0.1"]
    )

    app.add_middleware(
        CORSMiddleware,
        allow_credentials=True,
        allow_origins=ALLOWED_ORIGINS,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type", "HX-Request", "HX-Current-URL", "HX-Target"],
    )
    
    app.add_middleware(
        SessionMiddleware,
        secret_key=Configuracores.SECRET_KEY,
        max_age=28800,
        https_only=True,
    )
    
    templates = Jinja2Templates(directory="Public_Files")
    app.mount("/static", StaticFiles(directory="static"), name="static")

    controller.log('Inicializacao da webapi concluida...')

except Exception as e:
    print(e)
    if(controller):
        controller.log(str(e))

@app.middleware("http")
async def adiciona_headers_seguranca(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    # Server header removido para não expor stack
    response.headers["Server"] = ""
    return response

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    status_code = exc.status_code
    detalhe = exc.detail
    metodo = request.method
    url = str(request.url)
    query_params = dict(request.query_params)
    client_host = request.client.host if request.client else None
    client_port = request.client.port if request.client else None
    headers_req = dict(request.headers)

    controller.log(f"Erro HTTP {status_code} - {detalhe}")
    controller.log(f"URL: {url} | Método: {metodo}")
    controller.log(f"Query: {query_params}")
    controller.log(f"Cliente: {client_host}:{client_port}")
    controller.log(f"Headers: {headers_req}")

    if exc.status_code == 404:
        return templates.TemplateResponse("404.html", {"request": request}, status_code=404)
    return HTMLResponse(str(exc.detail), status_code=exc.status_code)

@app.exception_handler(TemplateError)
async def jinja2_exception_handler(request: Request, exc: TemplateError):
    controller.log('Falha catastrófica de template Jinja2')
    controller.log(str(exc))
    return templates.TemplateResponse("404.html", {"request": request}, status_code=404)

@app.get("/")
async def returnIndex(request: Request):
    agora = datetime.now().strftime("%d/%m %H:%M")
    return templates.TemplateResponse("index.html", {
        "request": request, 
        "data_atual": agora
    })

@app.post("/processar")
async def processar_missao(request: Request):
    # Simulação de resposta para o HTMX alimentar o log
    agora = datetime.now().strftime("%H:%M:%S")
    return HTMLResponse(f"<p class='text-green-400'>> [{agora}] Processamento manual iniciado...</p>")

@app.get("/api/camadas/alertas")
async def get_alertas(min_lat: float, min_lon: float, max_lat: float, max_lon: float, zoom: int):
    # Passamos o zoom para o controller decidir a estratégia de busca
    return controller.return_vegetal_alerts(min_lon, min_lat, max_lon, max_lat, zoom)


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000, timeout_keep_alive=30)
