"""Servizio principale per l'analisi delle immagini"""

import json
import time
import base64
from io import BytesIO
from PIL import Image
from typing import Optional, Dict, Any
import logging

from config import AIProviderConfig, ServiceConfig, ImageType, DocumentType
from models import (
    AnalysisRequest, AnalysisResult, ExtractedData,
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

            # Resize immagini (non PDF) per velocizzare l'inferenza
            image_data = request.image_data
            if request.image_format.lower() != 'pdf':
                image_data = self._resize_for_analysis(image_data)

            # Crea il provider AI
            ai_config = AIProviderConfig(**request.ai_config)
            provider = create_ai_provider(ai_config)

            # Esegui l'analisi
            prompt = request.prompt or provider._get_default_prompt()
            raw_result, token_usage = await provider.analyze_image(
                image_data,
                request.image_format,
                prompt
            )

            # Parsing del risultato JSON
            parsed_result = await self._parse_ai_response(raw_result)

            # Inferisci image_type dalla descrizione se il modello non lo ha impostato
            raw_type = parsed_result.get('image_type')
            if not raw_type or raw_type in ('unknown', 'other', 'null', 'none'):
                raw_type = self._infer_image_type(parsed_result.get('description', ''))
                parsed_result['image_type'] = raw_type

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
    
    def _resize_for_analysis(self, image_data_b64: str) -> str:
        """Ridimensiona l'immagine se supera resize_max_side px sul lato lungo."""
        raw = image_data_b64
        if raw.startswith('data:'):
            raw = raw.split(',', 1)[1]

        try:
            img_bytes = base64.b64decode(raw)
            with Image.open(BytesIO(img_bytes)) as img:
                w, h = img.size
                max_side = max(w, h)
                if max_side <= self.config.resize_max_side:
                    return image_data_b64  # già piccola

                ratio = self.config.resize_max_side / max_side
                new_w, new_h = int(w * ratio), int(h * ratio)
                resized = img.resize((new_w, new_h), Image.LANCZOS)

                buf = BytesIO()
                fmt = img.format or 'JPEG'
                resized.save(buf, format=fmt, quality=self.config.resize_quality)
                result_b64 = base64.b64encode(buf.getvalue()).decode()
                logger.info(f"Immagine ridimensionata da {w}x{h} a {new_w}x{new_h} ({len(image_data_b64)//1024}KB → {len(result_b64)//1024}KB)")
                return result_b64
        except Exception as e:
            logger.warning(f"Resize fallito, uso immagine originale: {e}")
            return image_data_b64

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
    
    # Mappa nomi campi alternativi (modelli piccoli usano nomi diversi)
    _FIELD_ALIASES: Dict[str, str] = {
        "descrizione": "description",
        "tipo_immagine": "image_type", "tipo": "image_type", "type": "image_type",
        "confidenza": "confidence",
        "dati_estratti": "extracted_data", "dati": "extracted_data",
        "testo_contenuto": "text_content", "contenuto_testo": "text_content",
        "testo": "text_content",
    }

    async def _parse_ai_response(self, raw_response: str) -> Dict[str, Any]:
        """Parsing della risposta AI in formato JSON con sanitizzazione robusta"""
        cleaned = raw_response.strip()

        # Rimuovi wrapper markdown
        if cleaned.startswith('```json'):
            cleaned = cleaned[7:]
        if cleaned.startswith('```'):
            cleaned = cleaned[3:]
        if cleaned.endswith('```'):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        # Sanitizza newline/tab letterali dentro stringhe JSON
        cleaned = self._sanitize_json_strings(cleaned)

        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.warning(f"Errore nel parsing JSON: {e}. Risposta raw: {raw_response[:500]}...")
            return {
                "image_type": "other",
                "confidence": 0.5,
                "description": raw_response[:500],
                "extracted_data": {"text_content": raw_response}
            }

        # Normalizza nomi campi alternativi → nomi standard
        parsed = self._normalize_field_names(parsed)
        return parsed

    def _sanitize_json_strings(self, text: str) -> str:
        """Escapa newline/tab letterali dentro i valori stringa JSON."""
        result = []
        in_string = False
        escape_next = False
        for ch in text:
            if escape_next:
                result.append(ch)
                escape_next = False
                continue
            if ch == '\\':
                result.append(ch)
                escape_next = True
                continue
            if ch == '"':
                in_string = not in_string
                result.append(ch)
                continue
            if in_string:
                if ch == '\n':
                    result.append('\\n')
                    continue
                if ch == '\r':
                    result.append('\\r')
                    continue
                if ch == '\t':
                    result.append('\\t')
                    continue
            result.append(ch)
        return ''.join(result)

    def _normalize_field_names(self, data: Any) -> Any:
        """Rinomina ricorsivamente campi con alias noti ai nomi standard."""
        if isinstance(data, dict):
            normalized = {}
            for key, value in data.items():
                std_key = self._FIELD_ALIASES.get(key.lower(), key)
                normalized[std_key] = self._normalize_field_names(value)
            return normalized
        if isinstance(data, list):
            return [self._normalize_field_names(item) for item in data]
        return data
    
    def _infer_image_type(self, description: str) -> str:
        """Inferisce il tipo di immagine dalla descrizione quando il modello non lo fornisce."""
        desc = description.lower()
        keywords_map = {
            'id_card': ['carta d\'identità', 'carta di identita', 'identity card', 'id card', 'carta d\'identita'],
            'passport': ['passaporto', 'passport'],
            'driving_license': ['patente', 'driving license', 'driver\'s license'],
            'receipt': ['scontrino', 'ricevuta', 'receipt', 'ticket'],
            'invoice': ['fattura', 'invoice', 'bolletta'],
            'document': ['documento', 'document', 'contratto', 'contract', 'certificato', 'certificate',
                        'permesso di soggiorno', 'residence permit', 'codice fiscale', 'tessera sanitaria'],
            'business_card': ['biglietto da visita', 'business card'],
            'menu': ['menu', 'menù', 'listino'],
            'product': ['prodotto', 'product', 'articolo'],
        }
        for img_type, keywords in keywords_map.items():
            if any(kw in desc for kw in keywords):
                return img_type
        return 'other'

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
    
