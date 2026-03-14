"""Servizio principale per l'analisi delle immagini"""

import json
import time
import base64
import asyncio
from io import BytesIO
from PIL import Image
from typing import Optional, Dict, Any
import logging

from config import AIProviderConfig, ServiceConfig, ImageType, DocumentType, AIProvider
from models import (
    AnalysisRequest, AnalysisResult, TokenUsage, ExtractedData,
    PersonData, DocumentData, FinancialData, BusinessData, ProductData
)
from ai_providers import create_ai_provider

logger = logging.getLogger(__name__)

class ImageAnalyzer:
    """Servizio principale per l'analisi delle immagini"""
    
    def __init__(self, config: ServiceConfig):
        self.config = config
        
    async def analyze_image(self, request: AnalysisRequest) -> AnalysisResult:
        """Analizza un'immagine o un PDF e restituisce i risultati strutturati"""
        start_time = time.time()

        try:
            # Valida il media (immagine o PDF)
            await self._validate_media(request.image_data, request.image_format)

            # Crea il provider AI
            ai_config = AIProviderConfig(**request.ai_config)
            provider = create_ai_provider(ai_config)

            # Esegui l'analisi
            prompt = request.prompt or provider._get_default_prompt()
            raw_result, token_usage = await provider.analyze_image(
                request.image_data,
                request.image_format,
                prompt
            )

            # Parsing del risultato JSON
            parsed_result = await self._parse_ai_response(raw_result)

            # Costruisci il risultato finale
            processing_time = time.time() - start_time

            result = AnalysisResult(
                success=True,
                image_type=self._parse_image_type(parsed_result.get('image_type')),
                confidence=parsed_result.get('confidence'),
                description=parsed_result.get('description'),
                extracted_data=self._parse_extracted_data(parsed_result.get('extracted_data', {})),
                token_usage=token_usage,
                processing_time=processing_time,
                ai_provider=ai_config.provider,
                ai_model_used=ai_config.model
            )

            logger.info(f"Analisi completata in {processing_time:.2f}s - Tipo: {result.image_type} - Formato: {request.image_format}")
            return result

        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"Errore nell'analisi: {e}", exc_info=True)

            return AnalysisResult(
                success=False,
                error_message=str(e),
                error_code="ANALYSIS_ERROR",
                processing_time=processing_time
            )
    
    async def _validate_media(self, image_data: str, image_format: str) -> None:
        """Valida un media (immagine o PDF) prima dell'analisi"""
        fmt = image_format.lower()

        # Verifica formato supportato
        if fmt not in self.config.supported_formats_list:
            raise ValueError(f"Formato non supportato: {image_format}")

        # Normalizza base64
        if image_data.startswith('data:'):
            image_data = image_data.split(',')[1]

        try:
            media_bytes = base64.b64decode(image_data)
        except Exception as e:
            raise ValueError(f"Dati base64 non validi: {e}")

        if fmt == "pdf":
            await self._validate_pdf(media_bytes)
        else:
            await self._validate_image(media_bytes)

    async def _validate_pdf(self, pdf_bytes: bytes) -> None:
        """Valida un PDF"""
        if len(pdf_bytes) > self.config.max_pdf_size_bytes:
            raise ValueError(
                f"PDF troppo grande: {len(pdf_bytes)} bytes (max: {self.config.max_pdf_size_bytes})"
            )
        if not pdf_bytes.startswith(b'%PDF'):
            raise ValueError("Il file non sembra un PDF valido (header mancante)")

    async def _validate_image(self, image_bytes: bytes) -> None:
        """Valida un'immagine tramite PIL"""
        if len(image_bytes) > self.config.max_image_size_bytes:
            raise ValueError(
                f"Immagine troppo grande: {len(image_bytes)} bytes (max: {self.config.max_image_size_bytes})"
            )
        try:
            with Image.open(BytesIO(image_bytes)) as img:
                width, height = img.size
                if width < self.config.min_image_width or height < self.config.min_image_height:
                    raise ValueError(f"Immagine troppo piccola: {width}x{height}")
                if width > self.config.max_image_width or height > self.config.max_image_height:
                    raise ValueError(f"Immagine troppo grande: {width}x{height}")
        except Exception as e:
            raise ValueError(f"Immagine non valida: {e}")
    
    async def _parse_ai_response(self, raw_response: str) -> Dict[str, Any]:
        """Parsing della risposta AI in formato JSON"""
        try:
            # Rimuovi eventuali caratteri di formattazione markdown
            cleaned_response = raw_response.strip()
            if cleaned_response.startswith('```json'):
                cleaned_response = cleaned_response[7:]
            if cleaned_response.endswith('```'):
                cleaned_response = cleaned_response[:-3]
            
            cleaned_response = cleaned_response.strip()
            
            # Parsing JSON
            parsed = json.loads(cleaned_response)
            return parsed
            
        except json.JSONDecodeError as e:
            logger.warning(f"Errore nel parsing JSON: {e}. Risposta raw: {raw_response[:500]}...")
            
            # Fallback: estrai informazioni base dalla risposta testuale
            return {
                "image_type": "other",
                "confidence": 0.5,
                "description": raw_response[:500],
                "extracted_data": {
                    "text_content": raw_response
                }
            }
    
    def _parse_image_type(self, image_type_str: Optional[str]) -> Optional[ImageType]:
        """Parsing del tipo di immagine"""
        if not image_type_str:
            return None
        
        try:
            return ImageType(image_type_str.lower())
        except ValueError:
            logger.warning(f"Tipo di immagine non riconosciuto: {image_type_str}")
            return ImageType.OTHER
    
    def _parse_document_type(self, doc_data: Dict[str, Any]) -> Optional[DocumentType]:
        """Determina il tipo di documento dai dati estratti"""
        if not doc_data:
            return None
        
        # Logica per determinare il tipo di documento
        if any(key in doc_data for key in ['first_name', 'last_name', 'date_of_birth']):
            return DocumentType.IDENTITY_DOCUMENT
        elif any(key in doc_data for key in ['amount', 'total_amount', 'tax_amount']):
            return DocumentType.FINANCIAL_DOCUMENT
        elif any(key in doc_data for key in ['company_name', 'vat_number']):
            return DocumentType.BUSINESS_DOCUMENT
        else:
            return DocumentType.OTHER
    
    def _parse_extracted_data(self, data: Dict[str, Any]) -> Optional[ExtractedData]:
        """Parsing dei dati estratti"""
        if not data:
            return None
        
        try:
            extracted = ExtractedData()
            
            # Testo generale
            if 'text_content' in data:
                extracted.text_content = data['text_content']
            
            # Dati persona
            if 'person' in data and data['person']:
                extracted.person = PersonData(**data['person'])
            
            # Dati documento
            if 'document' in data and data['document']:
                doc_data = data['document']
                # Determina il tipo di documento se non specificato
                if 'document_type' not in doc_data:
                    doc_data['document_type'] = self._parse_document_type(doc_data)
                extracted.document = DocumentData(**doc_data)
            
            # Dati finanziari
            if 'financial' in data and data['financial']:
                extracted.financial = FinancialData(**data['financial'])
            
            # Dati aziendali
            if 'business' in data and data['business']:
                extracted.business = BusinessData(**data['business'])
            
            # Dati prodotto
            if 'product' in data and data['product']:
                extracted.product = ProductData(**data['product'])
            
            # Campi personalizzati
            custom_fields = {k: v for k, v in data.items() 
                           if k not in ['text_content', 'person', 'document', 'financial', 'business', 'product']}
            if custom_fields:
                extracted.custom_fields = custom_fields
            
            return extracted
            
        except Exception as e:
            logger.error(f"Errore nel parsing dei dati estratti: {e}")
            # Fallback: salva tutto come campi personalizzati
            return ExtractedData(
                text_content=str(data),
                custom_fields=data
            )
    
    async def get_service_info(self) -> Dict[str, Any]:
        """Restituisce informazioni sul servizio"""
        return {
            "name": "Generic Image Analyzer",
            "version": "1.0.0",
            "description": "Servizio generico per l'analisi di immagini con AI",
            "supported_providers": [provider.value for provider in list(AIProvider)],
            "supported_image_types": [img_type.value for img_type in list(ImageType)],
            "supported_formats": self.config.supported_formats_list,
            "max_image_size_mb": self.config.max_image_size_mb,
            "limits": {
                "max_image_width": self.config.max_image_width,
                "max_image_height": self.config.max_image_height,
                "min_image_width": self.config.min_image_width,
                "min_image_height": self.config.min_image_height,
                "analysis_timeout": self.config.analysis_timeout,
                "max_concurrent_requests": self.config.max_concurrent_requests
            }
        }