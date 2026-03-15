"""Provider AI per l'analisi delle immagini"""

import base64
import io
from abc import ABC, abstractmethod
from typing import Tuple
import aiohttp
from config import AIProvider, AIProviderConfig
from models import TokenUsage

class BaseAIProvider(ABC):
    """Classe base per i provider AI"""
    
    def __init__(self, config: AIProviderConfig):
        self.config = config
        
    @abstractmethod
    async def analyze_image(
        self, 
        image_data: str, 
        image_format: str, 
        prompt: str
    ) -> Tuple[str, TokenUsage]:
        """Analizza un'immagine e restituisce il risultato con l'utilizzo dei token"""
        pass
    
    def _prepare_image_data(self, image_data: str) -> str:
        """Prepara i dati dell'immagine per l'API"""
        if image_data.startswith('data:'):
            image_data = image_data.split(',')[1]
        return image_data

    @staticmethod
    def _is_pdf(image_format: str) -> bool:
        return image_format.lower() == "pdf"

    @staticmethod
    def _extract_pdf_text(pdf_bytes: bytes, max_pages: int = 10) -> str:
        """Estrae il testo da un PDF usando pypdf (fallback per provider senza supporto nativo)"""
        try:
            import pypdf
        except ImportError:
            raise RuntimeError("pypdf non installato. Eseguire: pip install pypdf")

        try:
            reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
            pages = reader.pages[:max_pages]
            text = "\n\n".join(page.extract_text() or "" for page in pages)
            return text.strip() or "[PDF senza testo estraibile]"
        except Exception as e:
            raise ValueError(f"Errore nella lettura del PDF: {e}")
    
    def _get_default_prompt(self) -> str:
        """Prompt di default per l'analisi"""
        return """
Analyze this image and provide a response in JSON format with the following structure:

{
  "image_type": "Type of image. Must be exactly one of: 'photo' (for regular photographs), 'document' (for official documents/IDs/passports/calling card), 'receipt' (for payment receipts/invoices), or 'product' (for product/item images)",
  "confidence": "detection confidence from 0 to 1",
  "description": "general description of the image",
  "text_content": "all visible text in the image",
  "extracted_data": {
    "person": {
      "first_name": "first name if present",
      "last_name": "last name if present", 
      "date_of_birth": "date of birth if present",
      "nationality": "nationality if present"
    },
    "business": {
      "company_name": "company name if present",
      "vat_number": "VAT number if present",
      "tax_code": "tax code if present",
      "address": "address if present",
      "phone": "phone if present",
      "email": "email if present",
      "website": "website if present",
      "registration_number": "business registration number if present",
      "legal_form": "legal form if present",
      "industry": "industry sector if present"
    },
    "document": {
      "document_type": "document type (ID card, passport, etc.)",
      "document_number": "document number if present",
      "issue_date": "issue date if present",
      "expiry_date": "expiry date if present", 
      "issuing_authority": "issuing authority if present",
      "issuing_country": "issuing country if present",
      "mrz_code": "MRZ code if present",
      "place_of_birth": "place of birth if present",
      "gender": "gender if present",
      "height": "height if present",
      "nationality": "nationality if present",
      "personal_number": "personal number/tax code if present",
      "signature": "signature present (true/false)",
      "photo": "photo present (true/false)",
      "security_features": {
        "hologram": "hologram present (true/false)",
        "uv_features": "UV features present (true/false)",
        "microprint": "microprint present (true/false)"
      }
    },
    "receipt": {
      "amount": "amount if present",
      "currency": "currency if present",
      "tax_amount": "tax amount if present",
      "total_amount": "total amount if present",
      "payment_method": "payment method if present",
      "transaction_date": "transaction date if present",
      "transaction_id": "transaction ID if present",
      "merchant_name": "merchant name if present",
      "merchant_id": "merchant ID if present",
      "invoice_number": "invoice number if present",
      "discount_amount": "discount amount if present",
      "discount_percentage": "discount percentage if present",
      "subtotal": "subtotal before taxes if present",
      "tip_amount": "tip amount if present",
      "service_charges": "service charges if present",
      "payment_status": "payment status if present"
    },
    "product": {
      "name": "product name if present",
      "description": "product description if present",
      "price": "price if present",
      "currency": "currency if present",
      "brand": "brand if present",
      "model": "model if present",
      "sku": "SKU code if present",
      "barcode": "barcode if present",
      "category": "product category if present",
      "quantity": "quantity if present",
      "unit": "unit of measure if present",
      "discount": "applied discount if present",
      "tax_rate": "VAT rate if present",
      "availability": "availability if present",
      "condition": "product condition if present"
    }
  }
}

If a field is not present or not applicable, omit it from the response.
Respond ONLY with the JSON, without additional text.
"""

class OpenAIProvider(BaseAIProvider):
    """Provider per OpenAI GPT-4 Vision"""

    async def analyze_image(
        self,
        image_data: str,
        image_format: str,
        prompt: str
    ) -> Tuple[str, TokenUsage]:
        image_data = self._prepare_image_data(image_data)

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json"
        }

        if self._is_pdf(image_format):
            # OpenAI non supporta PDF nativamente: estrai il testo e invialo come prompt testuale
            pdf_bytes = base64.b64decode(image_data)
            pdf_text = self._extract_pdf_text(pdf_bytes)
            user_content = [
                {"type": "text", "text": prompt},
                {"type": "text", "text": f"\n\n--- CONTENUTO PDF ---\n{pdf_text}"}
            ]
        else:
            user_content = [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/{image_format};base64,{image_data}"}}
            ]

        payload = {
            "model": self.config.model,
            "messages": [{"role": "user", "content": user_content}],
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature
        }

        base_url = self.config.base_url or "https://api.openai.com/v1"
        url = f"{base_url}/chat/completions"

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"OpenAI API error: {response.status} - {error_text}")

                result = await response.json()
                content = result['choices'][0]['message']['content']
                usage = result.get('usage', {})

                token_usage = TokenUsage(
                    input_tokens=usage.get('prompt_tokens', 0),
                    output_tokens=usage.get('completion_tokens', 0),
                    total_tokens=usage.get('total_tokens', 0)
                )

                return content, token_usage

class ClaudeProvider(BaseAIProvider):
    """Provider per Anthropic Claude"""

    async def analyze_image(
        self,
        image_data: str,
        image_format: str,
        prompt: str
    ) -> Tuple[str, TokenUsage]:
        image_data = self._prepare_image_data(image_data)

        headers = {
            "x-api-key": self.config.api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
            "anthropic-beta": "pdfs-2024-09-25"
        }

        if self._is_pdf(image_format):
            # Claude supporta PDF nativamente tramite block "document"
            media_block = {
                "type": "document",
                "source": {
                    "type": "base64",
                    "media_type": "application/pdf",
                    "data": image_data
                }
            }
        else:
            media_block = {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": f"image/{image_format}",
                    "data": image_data
                }
            }

        payload = {
            "model": self.config.model,
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
            "messages": [
                {
                    "role": "user",
                    "content": [media_block, {"type": "text", "text": prompt}]
                }
            ]
        }

        base_url = self.config.base_url or "https://api.anthropic.com/v1"
        url = f"{base_url}/messages"

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Claude API error: {response.status} - {error_text}")

                result = await response.json()
                content = result['content'][0]['text']
                usage = result.get('usage', {})

                token_usage = TokenUsage(
                    input_tokens=usage.get('input_tokens', 0),
                    output_tokens=usage.get('output_tokens', 0),
                    total_tokens=usage.get('input_tokens', 0) + usage.get('output_tokens', 0)
                )

                return content, token_usage

class OllamaProvider(BaseAIProvider):
    """Provider per Ollama locale"""

    async def analyze_image(
        self,
        image_data: str,
        image_format: str,
        prompt: str
    ) -> Tuple[str, TokenUsage]:
        image_data = self._prepare_image_data(image_data)
        headers = {"Content-Type": "application/json"}

        if self._is_pdf(image_format):
            # Ollama non supporta PDF: estrai il testo e aggiungilo al prompt
            pdf_bytes = base64.b64decode(image_data)
            pdf_text = self._extract_pdf_text(pdf_bytes)
            full_prompt = f"{prompt}\n\n--- CONTENUTO PDF ---\n{pdf_text}"
            payload = {
                "model": self.config.model,
                "prompt": full_prompt,
                "stream": False,
                "options": {"temperature": self.config.temperature, "num_predict": self.config.max_tokens}
            }
        else:
            payload = {
                "model": self.config.model,
                "prompt": prompt,
                "images": [image_data],
                "stream": False,
                "options": {"temperature": self.config.temperature, "num_predict": self.config.max_tokens}
            }

        if not self.config.base_url:
            raise ValueError("Ollama base_url non configurato")
        url = f"{self.config.base_url}/api/generate"

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Ollama API error: {response.status} - {error_text}")

                result = await response.json()
                content = result.get('response', '')

                # Ollama non espone sempre i token: stima approssimativa
                estimated_input_tokens = len(prompt.split()) * 1.3
                estimated_output_tokens = len(content.split()) * 1.3

                token_usage = TokenUsage(
                    input_tokens=int(estimated_input_tokens),
                    output_tokens=int(estimated_output_tokens),
                    total_tokens=int(estimated_input_tokens + estimated_output_tokens)
                )

                return content, token_usage

class OpenRouterProvider(BaseAIProvider):
    """Provider per OpenRouter"""

    async def analyze_image(
        self,
        image_data: str,
        image_format: str,
        prompt: str
    ) -> Tuple[str, TokenUsage]:
        image_data = self._prepare_image_data(image_data)

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://generic-image-analyzer",
            "X-Title": "Generic Media Analyzer"
        }

        if self._is_pdf(image_format):
            # OpenRouter non supporta PDF nativamente: estrai il testo
            pdf_bytes = base64.b64decode(image_data)
            pdf_text = self._extract_pdf_text(pdf_bytes)
            user_content = [
                {"type": "text", "text": prompt},
                {"type": "text", "text": f"\n\n--- CONTENUTO PDF ---\n{pdf_text}"}
            ]
        else:
            user_content = [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/{image_format};base64,{image_data}"}}
            ]

        payload = {
            "model": self.config.model,
            "messages": [{"role": "user", "content": user_content}],
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature
        }

        base_url = self.config.base_url or "https://openrouter.ai/api/v1"
        url = f"{base_url}/chat/completions"

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"OpenRouter API error: {response.status} - {error_text}")

                result = await response.json()
                content = result['choices'][0]['message']['content']
                usage = result.get('usage', {})

                token_usage = TokenUsage(
                    input_tokens=usage.get('prompt_tokens', 0),
                    output_tokens=usage.get('completion_tokens', 0),
                    total_tokens=usage.get('total_tokens', 0)
                )

                return content, token_usage

class GeminiProvider(BaseAIProvider):
    """Provider per Google Gemini"""

    async def analyze_image(
        self,
        image_data: str,
        image_format: str,
        prompt: str
    ) -> Tuple[str, TokenUsage]:
        image_data = self._prepare_image_data(image_data)

        # Gemini supporta PDF nativamente con mime_type application/pdf
        mime_type = "application/pdf" if self._is_pdf(image_format) else f"image/{image_format}"

        headers = {"Content-Type": "application/json"}

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {"inline_data": {"mime_type": mime_type, "data": image_data}}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": self.config.temperature,
                "maxOutputTokens": self.config.max_tokens
            }
        }

        base_url = self.config.base_url or "https://generativelanguage.googleapis.com/v1beta"
        url = f"{base_url}/models/{self.config.model}:generateContent?key={self.config.api_key}"

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Gemini API error: {response.status} - {error_text}")

                result = await response.json()
                content = result['candidates'][0]['content']['parts'][0]['text']
                usage_metadata = result.get('usageMetadata', {})

                token_usage = TokenUsage(
                    input_tokens=usage_metadata.get('promptTokenCount', 0),
                    output_tokens=usage_metadata.get('candidatesTokenCount', 0),
                    total_tokens=usage_metadata.get('totalTokenCount', 0)
                )

                return content, token_usage

def create_ai_provider(config: AIProviderConfig) -> BaseAIProvider:
    """Factory per creare il provider AI appropriato"""
    
    providers = {
        AIProvider.OPENAI: OpenAIProvider,
        AIProvider.CLAUDE: ClaudeProvider,
        AIProvider.OLLAMA: OllamaProvider,
        AIProvider.OPENROUTER: OpenRouterProvider,
        AIProvider.GEMINI: GeminiProvider
    }
    
    provider_class = providers.get(config.provider)
    if not provider_class:
        raise ValueError(f"Provider non supportato: {config.provider}")
    
    return provider_class(config)
