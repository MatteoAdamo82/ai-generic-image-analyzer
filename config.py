"""Configurazione per il servizio generico di analisi immagini"""

from typing import List, Dict, Any, Optional
from pydantic import Field, validator
from pydantic_settings import BaseSettings
from enum import Enum

class AIProvider(str, Enum):
    """Provider AI supportati"""
    OPENAI = "openai"
    CLAUDE = "claude"
    OLLAMA = "ollama"
    OPENROUTER = "openrouter"
    GEMINI = "gemini"

class ImageType(str, Enum):
    """Tipi di media riconosciuti"""
    PHOTO = "photo"
    SELFIE = "selfie"
    DOCUMENT = "document"
    RECEIPT = "receipt"
    INVOICE = "invoice"
    ID_CARD = "id_card"
    PASSPORT = "passport"
    DRIVING_LICENSE = "driving_license"
    BUSINESS_CARD = "business_card"
    MENU = "menu"
    SCREENSHOT = "screenshot"
    PRODUCT = "product"
    TEXT = "text"
    PDF = "pdf"
    OTHER = "other"

class DocumentType(str, Enum):
    """Tipi di documento"""
    IDENTITY_DOCUMENT = "identity_document"
    FINANCIAL_DOCUMENT = "financial_document"
    BUSINESS_DOCUMENT = "business_document"
    LEGAL_DOCUMENT = "legal_document"
    MEDICAL_DOCUMENT = "medical_document"
    EDUCATIONAL_DOCUMENT = "educational_document"
    OTHER = "other"

class ServiceConfig(BaseSettings):
    """Configurazione del servizio generico di analisi immagini"""
    
    # Server
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8002, env="PORT")
    debug: bool = Field(default=False, env="DEBUG")
    
    # Sicurezza
    # SERVICE_JWT_SECRET: secret condiviso con whatsagent per autenticazione M2M (JWT HS256).
    # Deve corrispondere a IMAGE_ANALYZER_SERVICE_JWT_SECRET nel .env di whatsagent.
    # Se non impostato l'autenticazione è disabilitata (solo per sviluppo!).
    api_key: Optional[str] = Field(default=None, env="API_KEY")
    service_jwt_secret: Optional[str] = Field(default=None, env="SERVICE_JWT_SECRET")
    allowed_origins: str = Field(default="*", env="ALLOWED_ORIGINS")
    ollama_model: Optional[str] = Field(default=None, env="OLLAMA_MODEL")
    ollama_base_url: Optional[str] = Field(default=None, env="OLLAMA_BASE_URL")
    
    # Logging
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_dir: str = Field(default="logs", env="LOG_DIR")
    
    # Limiti immagini
    max_image_size_mb: int = Field(default=10, env="MAX_IMAGE_SIZE_MB")
    min_image_width: int = Field(default=32, env="MIN_IMAGE_WIDTH")
    min_image_height: int = Field(default=32, env="MIN_IMAGE_HEIGHT")
    max_image_width: int = Field(default=4096, env="MAX_IMAGE_WIDTH")
    max_image_height: int = Field(default=4096, env="MAX_IMAGE_HEIGHT")

    # Limiti PDF
    max_pdf_size_mb: int = Field(default=20, env="MAX_PDF_SIZE_MB")
    max_pdf_pages: int = Field(default=10, env="MAX_PDF_PAGES")

    # Formati supportati
    supported_formats: str = Field(default="jpg,jpeg,png,webp,gif,bmp,pdf", env="SUPPORTED_FORMATS")
    
    # Timeout e performance
    analysis_timeout: int = Field(default=60, env="ANALYSIS_TIMEOUT")
    max_concurrent_requests: int = Field(default=5, env="MAX_CONCURRENT_REQUESTS")
    
    # Rate limiting
    rate_limit_requests: int = Field(default=100, env="RATE_LIMIT_REQUESTS")
    rate_limit_window: int = Field(default=3600, env="RATE_LIMIT_WINDOW")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
    
    @validator("log_level")
    def validate_log_level(cls, v):
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level deve essere uno di: {', '.join(valid_levels)}")
        return v.upper()
    
    @validator("max_image_size_mb")
    def validate_max_image_size(cls, v):
        if v <= 0 or v > 100:
            raise ValueError("La dimensione massima dell'immagine deve essere tra 1 e 100 MB")
        return v
    
    @validator("port")
    def validate_port(cls, v):
        if v < 1 or v > 65535:
            raise ValueError("La porta deve essere tra 1 e 65535")
        return v
    
    @property
    def max_image_size_bytes(self) -> int:
        """Dimensione massima immagine in bytes"""
        return self.max_image_size_mb * 1024 * 1024

    @property
    def max_pdf_size_bytes(self) -> int:
        """Dimensione massima PDF in bytes"""
        return self.max_pdf_size_mb * 1024 * 1024
    
    @property
    def supported_formats_list(self) -> List[str]:
        """Lista dei formati supportati"""
        return [fmt.strip().lower() for fmt in self.supported_formats.split(",")]
    
    @property
    def allowed_origins_list(self) -> List[str]:
        """Lista delle origini consentite"""
        if self.allowed_origins == "*":
            return ["*"]
        return [origin.strip() for origin in self.allowed_origins.split(",")]

class AIProviderConfig:
    """Configurazione per un provider AI"""
    
    def __init__(
        self,
        provider: AIProvider,
        api_key: str,
        model: str,
        base_url: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 2000,
        **kwargs
    ):
        self.provider = provider
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.extra_params = kwargs
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte la configurazione in dizionario"""
        config = {
            "provider": self.provider,
            "api_key": self.api_key,
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens
        }
        
        if self.base_url:
            config["base_url"] = self.base_url
        
        config.update(self.extra_params)
        return config
