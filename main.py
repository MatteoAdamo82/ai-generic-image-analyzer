"""Servizio generico di analisi immagini - Applicazione FastAPI"""

from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt as pyjwt
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import logging
import time
from functools import lru_cache

from config import ServiceConfig, AIProvider
from models import AnalysisRequest, AnalysisResult
from analyzer import ImageAnalyzer

# Configurazione logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Variabili globali
analyzer: Optional[ImageAnalyzer] = None
SUPPORTED_PROVIDERS = [provider.value for provider in AIProvider]

@lru_cache()
def get_config() -> ServiceConfig:
    """Ottieni la configurazione del servizio"""
    return ServiceConfig()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestisce il ciclo di vita dell'applicazione"""
    global analyzer
    
    try:
        # Startup
        service_config = get_config()
        analyzer = ImageAnalyzer(service_config)
        
        logger.info(f"Servizio generico di analisi media avviato")
        logger.info(f"Host: {service_config.host}:{service_config.port}")
        logger.info(f"Debug: {service_config.debug}")
        logger.info(f"Formati supportati: {', '.join(service_config.supported_formats_list)}")
        logger.info(f"Dimensione massima immagine: {service_config.max_image_size_mb}MB")
        logger.info(f"Dimensione massima PDF: {service_config.max_pdf_size_mb}MB (max {service_config.max_pdf_pages} pagine)")
        
        yield
        
    except Exception as e:
        logger.error(f"Errore durante l'avvio: {e}")
        raise
    
    # Shutdown
    try:
        logger.info("Arresto servizio di analisi immagini")
    except Exception as e:
        logger.error(f"Errore durante l'arresto: {e}")

# Creazione app FastAPI
app = FastAPI(
    title="Generic Media Analyzer",
    description="Servizio generico per l'analisi di immagini e PDF con AI",
    version="2.0.0",
    lifespan=lifespan
)

# Configurazione CORS
config_temp = get_config()
app.add_middleware(
    CORSMiddleware,
    allow_origins=config_temp.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middleware per logging delle richieste
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    
    # Log della richiesta
    logger.info(f"Richiesta: {request.method} {request.url.path}")
    
    response = await call_next(request)
    
    # Log della risposta
    process_time = time.time() - start_time
    logger.info(f"Risposta: {response.status_code} - Tempo: {process_time:.3f}s")
    
    return response

# ── Autenticazione inter-servizio (JWT HS256) ─────────────────────────────────

_bearer = HTTPBearer(auto_error=True)

async def validate_service_jwt(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> bool:
    """Valida il JWT di servizio emesso da whatsagent.

    Il token deve:
      - essere firmato con SERVICE_JWT_SECRET
      - avere iss = "whatsagent"
      - non essere scaduto

    Se SERVICE_JWT_SECRET non è configurato emette un warning e lascia passare
    (utile in fase di sviluppo; in produzione il secret deve sempre essere impostato).
    """
    svc_config = get_config()
    secret = svc_config.service_jwt_secret

    if not secret:
        logger.warning(
            "[ServiceAuth] SERVICE_JWT_SECRET non configurato: "
            "richiesta accettata senza verifica JWT."
        )
        return True

    try:
        payload = pyjwt.decode(
            credentials.credentials,
            secret,
            algorithms=["HS256"],
            options={"require": ["iss", "sub", "exp"]},
        )
        if payload.get("iss") != "whatsagent":
            raise pyjwt.InvalidIssuerError("Issuer non valido")
        logger.debug(f"[ServiceAuth] Token valido — sub={payload.get('sub')}")
        return True
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token di servizio scaduto",
        )
    except pyjwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token di servizio non valido: {exc}",
        )

# Exception handler personalizzato
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Errore non gestito: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={
            "message": "Errore interno del server",
            "code": "INTERNAL_ERROR",
            "details": {"path": str(request.url.path)}
        }
    )

# Endpoint principale

@app.get("/health")
async def health_check():
    """Endpoint per il controllo dello stato del servizio"""
    return {
        "status": "healthy",
        "service": "generic-media-analyzer",
        "version": "2.0.0",
        "analyzer_ready": analyzer is not None
    }

@app.post("/analyze", response_model=AnalysisResult)
async def analyze_image(
    request: AnalysisRequest,
    _: bool = Depends(validate_service_jwt),
):
    """Analizza un'immagine o un PDF"""
    if not analyzer:
        raise HTTPException(status_code=503, detail="Servizio non inizializzato")
    
    try:
        # Validazione della configurazione AI
        if not request.ai_config:
            raise HTTPException(
                status_code=400, 
                detail="Configurazione AI richiesta"
            )
        
        request_ai_config = dict(request.ai_config)

        # Validazione del provider
        provider = request_ai_config.get('provider')
        if not provider or provider not in SUPPORTED_PROVIDERS:
            raise HTTPException(
                status_code=400,
                detail=f"Provider non supportato: {provider}. Supportati: {SUPPORTED_PROVIDERS}"
            )

        service_config = get_config()
        if provider == AIProvider.OLLAMA.value:
            configured_ollama_model = service_config.ollama_model
            configured_ollama_base_url = service_config.ollama_base_url

            if not configured_ollama_model:
                raise HTTPException(
                    status_code=400,
                    detail="OLLAMA_MODEL non configurato nel file .env"
                )
            if not configured_ollama_base_url:
                raise HTTPException(
                    status_code=400,
                    detail="OLLAMA_BASE_URL non configurato nel file .env"
                )

            # Override silenzioso: per Ollama usa sempre model/base_url dal .env del servizio
            request_ai_config['model'] = configured_ollama_model
            request_ai_config['base_url'] = configured_ollama_base_url
            request_ai_config['api_key'] = ""

        # Validazione API key del provider
        if provider != AIProvider.OLLAMA.value and not request_ai_config.get('api_key'):
            raise HTTPException(
                status_code=400,
                detail="API key del provider AI richiesta"
            )
        
        # Validazione modello
        if not request_ai_config.get('model'):
            raise HTTPException(
                status_code=400,
                detail="Modello AI richiesto"
            )

        prepared_request = request.model_copy(update={"ai_config": request_ai_config})
        
        # Esegui l'analisi
        result = await analyzer.analyze_image(prepared_request)
        
        if not result.success:
            raise HTTPException(
                status_code=500,
                detail=f"Errore nell'analisi: {result.error_message}"
            )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Errore nell'endpoint analyze: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Errore interno: {str(e)}"
        )



if __name__ == "__main__":
    config = get_config()
    uvicorn.run(
        "main:app",
        host=config.host,
        port=config.port,
        reload=config.debug,
        log_level=config.log_level.lower()
    )
