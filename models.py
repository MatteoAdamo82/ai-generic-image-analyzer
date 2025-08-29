"""Modelli di dati per il servizio di analisi immagini"""

from typing import Optional, Dict, Any, List, Union
from pydantic import BaseModel, Field
from datetime import datetime
from config import AIProvider, ImageType, DocumentType
import json

class AnalysisRequest(BaseModel):
    """Richiesta di analisi immagine"""
    
    # Dati immagine
    image_data: str = Field(..., description="Immagine in base64")
    image_format: str = Field(..., description="Formato immagine (jpg, png, etc.)")
    
    # Prompt personalizzato
    prompt: Optional[str] = Field(None, description="Prompt personalizzato per l'analisi")
    
    # Configurazione AI
    ai_config: Dict[str, Any] = Field(..., description="Configurazione del provider AI")
    
    # Opzioni analisi
    extract_text: bool = Field(default=True, description="Estrai testo dall'immagine")
    detect_type: bool = Field(default=True, description="Rileva il tipo di immagine")
    extract_data: bool = Field(default=True, description="Estrai dati strutturati se documento")
    
    class Config:
        json_schema_extra = {
            "example": {
                "image_data": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg==",
                "image_format": "png",
                "prompt": "Analizza questa immagine e dimmi cosa vedi",
                "ai_config": {
                    "provider": "openai",
                    "api_key": "sk-...",
                    "model": "gpt-4-vision-preview",
                    "temperature": 0.1,
                    "max_tokens": 2000
                },
                "extract_text": True,
                "detect_type": True,
                "extract_data": True
            }
        }

class PersonData(BaseModel):
    """Dati di una persona"""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    full_name: Optional[str] = None
    date_of_birth: Optional[str] = None
    place_of_birth: Optional[str] = None
    nationality: Optional[str] = None
    gender: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None

class DocumentData(BaseModel):
    """Dati di un documento"""
    document_number: Optional[str] = None
    issue_date: Optional[str] = None
    expiry_date: Optional[str] = None
    issuing_authority: Optional[str] = None
    document_type: Optional[DocumentType] = None
    
class FinancialData(BaseModel):
    """Dati finanziari"""
    amount: Optional[float] = None
    currency: Optional[str] = None
    tax_amount: Optional[float] = None
    total_amount: Optional[float] = None
    payment_method: Optional[str] = None
    transaction_date: Optional[str] = None
    
class BusinessData(BaseModel):
    """Dati aziendali"""
    company_name: Optional[str] = None
    vat_number: Optional[str] = None
    tax_code: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    
class ProductData(BaseModel):
    """Dati prodotto"""
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    currency: Optional[str] = None
    brand: Optional[str] = None
    category: Optional[str] = None
    sku: Optional[str] = None
    
class ExtractedData(BaseModel):
    """Dati estratti dall'immagine"""
    person: Optional[PersonData] = None
    document: Optional[DocumentData] = None
    financial: Optional[FinancialData] = None
    business: Optional[BusinessData] = None
    product: Optional[ProductData] = None
    text_content: Optional[str] = None
    custom_fields: Optional[Dict[str, Any]] = None
    
class TokenUsage(BaseModel):
    """Utilizzo dei token"""
    input_tokens: int = Field(..., description="Token utilizzati in input")
    output_tokens: int = Field(..., description="Token utilizzati in output")
    total_tokens: int = Field(..., description="Token totali utilizzati")
    cost_estimate: Optional[float] = Field(None, description="Stima del costo in USD")
    
class AnalysisResult(BaseModel):
    """Risultato dell'analisi"""
    success: bool = Field(..., description="Successo dell'operazione")
    image_type: Optional[ImageType] = Field(None, description="Tipo di immagine rilevato")
    confidence: Optional[float] = Field(None, description="Confidenza del rilevamento (0-1)")
    description: Optional[str] = Field(None, description="Descrizione dell'immagine")
    extracted_data: Optional[ExtractedData] = Field(None, description="Dati estratti")
    
    # Token usage
    token_usage: Optional[TokenUsage] = Field(None, description="Utilizzo dei token")
    
    # Metadati
    processing_time: Optional[float] = Field(None, description="Tempo di elaborazione in secondi")
    ai_provider: Optional[str] = Field(None, description="Provider AI utilizzato")
    ai_model_used: Optional[str] = Field(None, description="Modello AI utilizzato")
    timestamp: datetime = Field(default_factory=datetime.now, description="Timestamp dell'analisi")
    
    # Errori
    error_message: Optional[str] = Field(None, description="Messaggio di errore se presente")
    error_code: Optional[str] = Field(None, description="Codice di errore se presente")
    
    class Config:
        protected_namespaces = ()
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
    
class HealthResponse(BaseModel):
    """Risposta health check"""
    status: str = Field(..., description="Stato del servizio")
    timestamp: datetime = Field(default_factory=datetime.now)
    version: str = Field(default="1.0.0")
    uptime: Optional[float] = Field(None, description="Uptime in secondi")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
    
class ServiceInfo(BaseModel):
    """Informazioni sul servizio"""
    name: str = Field(default="Generic Image Analyzer")
    version: str = Field(default="1.0.0")
    description: str = Field(default="Servizio generico per l'analisi di immagini con AI")
    supported_providers: List[AIProvider] = Field(default_factory=lambda: list(AIProvider))
    supported_image_types: List[ImageType] = Field(default_factory=lambda: list(ImageType))
    supported_formats: List[str] = Field(default_factory=lambda: ["jpg", "jpeg", "png", "webp", "gif", "bmp"])
    max_image_size_mb: int = Field(default=10)
    
class ErrorResponse(BaseModel):
    """Risposta di errore"""
    error: bool = Field(default=True)
    message: str = Field(..., description="Messaggio di errore")
    code: Optional[str] = Field(None, description="Codice di errore")
    details: Optional[Dict[str, Any]] = Field(None, description="Dettagli aggiuntivi")
    timestamp: datetime = Field(default_factory=datetime.now)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }