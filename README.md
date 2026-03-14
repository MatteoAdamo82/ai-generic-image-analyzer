# Generic Image Analyzer

Servizio per l'analisi delle immagini utilizzando provider AI multipli. Questo README documenta il **funzionamento reale** del servizio, distinguendo tra funzionalità implementate e quelle ancora in sviluppo.

## 🚀 Stato Attuale del Servizio

### ✅ Funzionalità Implementate

- **Analisi completa delle immagini** tramite provider AI
- **Supporto provider multipli**: OpenAI, Claude, Ollama, OpenRouter
- **Estrazione automatica** di testo e dati strutturati
- **API REST** con endpoint `/analyze` e documentazione Swagger
- **Validazione robusta** delle immagini (formato, dimensioni)
- **Gestione errori** completa con logging dettagliato
- **Ottimizzazione automatica** delle immagini per ridurre costi API
- **Configurazione flessibile** tramite variabili d'ambiente

### ⚠️ Limitazioni Attuali

- **Parametri di controllo non implementati**: `extract_text`, `detect_type`, `extract_data` sono accettati ma **non influenzano l'analisi**
- **Prompt fisso**: Il servizio usa sempre lo stesso prompt indipendentemente dai parametri
- **Analisi sempre completa**: Non è possibile disabilitare specifiche funzionalità

## 📋 Come Funziona Realmente

### Flusso di Analisi

1. **Ricezione richiesta** via POST `/analyze`
2. **Validazione immagine** (formato, dimensioni, integrità)
3. **Selezione provider AI** basata sulla configurazione
4. **Invio prompt fisso** al provider con l'immagine
5. **Parsing risposta JSON** dal provider AI
6. **Estrazione dati strutturati** sempre completa
7. **Restituzione risultato** con metadati

### Prompt Utilizzato

Il servizio utilizza **sempre** questo prompt dettagliato, indipendentemente dai parametri:

```
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
```

## 🚀 Avvio Rapido

### Con Docker Compose

```bash
# Clona o copia la directory del servizio
cd generic-image-analyzer

# Copia il file di configurazione
cp .env.example .env

# Avvia il servizio
docker-compose up -d

# Verifica che sia in esecuzione
curl http://localhost:8002/health
```

### Installazione Locale

```bash
# Installa le dipendenze
pip install -r requirements.txt

# Avvia il servizio
python main.py
```

## 📡 API Endpoints

### `GET /docks`
Informazioni dettagliate sul servizio


### `POST /analyze`
Endpoint principale per l'analisi delle immagini

## 🔧 Utilizzo

### Esempio di Richiesta

```json
{
  "image_data": "base64_encoded_image_data",
  "image_format": "jpg",
  "prompt": "Analizza questa immagine e estrai tutti i dati",
  "ai_config": {
    "provider": "openai",
    "api_key": "sk-your-openai-key",
    "model": "gpt-4-vision-preview",
    "temperature": 0.1,
    "max_tokens": 2000
  },
  "extract_text": true,
  "detect_type": true,
  "extract_data": true
}
```

### Esempio di Risposta

```json
{
  "success": true,
  "image_type": "id_card",
  "confidence": 0.95,
  "description": "Carta d'identità italiana con foto e dati personali",
  "extracted_data": {
    "person": {
      "first_name": "Mario",
      "last_name": "Rossi",
      "date_of_birth": "1985-03-15",
      "place_of_birth": "Roma",
      "nationality": "Italiana"
    },
    "document": {
      "document_number": "AB1234567",
      "issue_date": "2020-01-15",
      "expiry_date": "2030-01-15",
      "issuing_authority": "Comune di Roma",
      "document_type": "identity_document"
    },
    "text_content": "REPUBBLICA ITALIANA CARTA D'IDENTITÀ..."
  },
  "token_usage": {
    "input_tokens": 1250,
    "output_tokens": 180,
    "total_tokens": 1430,
    "cost_estimate": 0.0286
  },
  "processing_time": 2.34,
  "ai_provider": "openai",
  "ai_model_used": "gpt-4-vision-preview",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

## 🤖 Provider Supportati

### OpenAI
```json
{
  "provider": "openai",
  "api_key": "sk-your-key",
  "model": "gpt-4-vision-preview",
  "temperature": 0.1,
  "max_tokens": 2000
}
```

### Claude (Anthropic)
```json
{
  "provider": "claude",
  "api_key": "your-claude-key",
  "model": "claude-3-sonnet-20240229",
  "temperature": 0.1,
  "max_tokens": 2000
}
```

### Ollama (Locale)
```json
{
  "provider": "ollama",
  "api_key": "not_required",
  "model": "llava",
  "base_url": "http://localhost:11434",
  "temperature": 0.1,
  "max_tokens": 2000
}
```

### OpenRouter
```json
{
  "provider": "openrouter",
  "api_key": "your-openrouter-key",
  "model": "anthropic/claude-3-sonnet",
  "temperature": 0.1,
  "max_tokens": 2000
}
```

### Gemini (Google)
```json
{
  "provider": "gemini",
  "api_key": "your-gemini-key",
  "model": "gemini-pro-vision",
  "temperature": 0.1,
  "max_tokens": 2000
}
```

## 📋 Tipi di Immagine Riconosciuti

- `photo` - Foto generiche
- `selfie` - Selfie e ritratti
- `document` - Documenti generici
- `receipt` - Ricevute e scontrini
- `invoice` - Fatture
- `id_card` - Carte d'identità
- `passport` - Passaporti
- `driving_license` - Patenti di guida
- `business_card` - Biglietti da visita
- `menu` - Menu di ristoranti
- `screenshot` - Screenshot
- `product` - Immagini di prodotti
- `text` - Immagini con solo testo
- `other` - Altri tipi

## 📊 Struttura Dati Estratti

### Dati Persona
- `first_name`, `last_name`, `full_name`
- `date_of_birth`, `place_of_birth`
- `nationality`, `gender`
- `address`, `phone`, `email`

### Dati Documento
- `document_number`, `document_type`
- `issue_date`, `expiry_date`
- `issuing_authority`

### Dati Finanziari
- `amount`, `currency`
- `tax_amount`, `total_amount`
- `payment_method`, `transaction_date`

### Dati Aziendali
- `company_name`, `vat_number`, `tax_code`
- `address`, `phone`, `email`, `website`

### Dati Prodotto
- `name`, `description`
- `price`, `currency`
- `brand`, `category`, `sku`

## ⚙️ Configurazione

### Variabili d'Ambiente

| Variable                  | Default                                  | Description                         |
|---------------------------|------------------------------------------|-------------------------------------|  
| `HOST`                    | `0.0.0.0`                                | Server host address                 |
| `PORT`                    | `8006`                                   | Server port number                  |
| `DEBUG`                   | `false`                                  | Debug mode toggle                   |
| `API_KEY`                 | -                                        | Optional API key for authentication |
| `ALLOWED_ORIGINS`         | `*`                                      | Allowed CORS origins                |
| `LOG_LEVEL`               | `INFO`                                   | Logging level                       |
| `LOG_DIR`                 | `logs`                                   | Log directory                       |
| `MAX_IMAGE_SIZE_MB`       | `10`                                     | Maximum image size in MB            |
| `MAX_IMAGE_WIDTH`         | `4096`                                   | Maximum image width in pixels       |
| `MAX_IMAGE_HEIGHT`        | `4096`                                   | Maximum image height in pixels      |
| `SUPPORTED_FORMATS`       | `jpg,jpeg,png,webp,gif,bmp`              | Supported image formats             |
| `SUPPORTED_PROVIDERS`     | `openai,claude,ollama,openrouter,gemini` | Supported AI providers              | 
| `ANALYSIS_TIMEOUT`        | `60`                                     | Analysis timeout in seconds         |
| `SUPPORTED_PROVIDERS`     | `openai,claude,ollama,openrouter,gemini` | Supported AI providers              |
| `MAX_CONCURRENT_REQUESTS` | `5`                                      | Maximum concurrent requests         | 

## 🔒 Sicurezza

- **API Key opzionale**: Proteggi il servizio con una API key
- **CORS configurabile**: Controlla le origini consentite
- **Rate limiting**: Limita le richieste per prevenire abusi
- **Validazione input**: Controlli rigorosi su immagini e parametri
- **Timeout**: Previene richieste che si bloccano

## 🐳 Docker

### Build dell'immagine
```bash
docker build -t generic-image-analyzer .
```

### Esecuzione del container
```bash
docker run -p 8002:8002 \
  -e API_KEY=your-api-key \
  -e LOG_LEVEL=DEBUG \
  generic-image-analyzer
```

## 🔗 Integrazione

### Python
```python
import requests
import base64

# Carica e codifica l'immagine
with open('image.jpg', 'rb') as f:
    image_data = base64.b64encode(f.read()).decode()

# Richiesta di analisi
response = requests.post('http://localhost:8002/analyze', json={
    'image_data': image_data,
    'image_format': 'jpg',
    'ai_config': {
        'provider': 'openai',
        'api_key': 'your-key',
        'model': 'gpt-4-vision-preview'
    }
})

result = response.json()
print(f"Tipo: {result['image_type']}")
print(f"Descrizione: {result['description']}")
```

### JavaScript/Node.js
```javascript
const fs = require('fs');
const axios = require('axios');

// Carica e codifica l'immagine
const imageBuffer = fs.readFileSync('image.jpg');
const imageData = imageBuffer.toString('base64');

// Richiesta di analisi
const response = await axios.post('http://localhost:8002/analyze', {
  image_data: imageData,
  image_format: 'jpg',
  ai_config: {
    provider: 'openai',
    api_key: 'your-key',
    model: 'gpt-4-vision-preview'
  }
});

console.log('Tipo:', response.data.image_type);
console.log('Descrizione:', response.data.description);
```

### cURL
```bash
curl -X POST http://localhost:8002/analyze \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "image_data": "base64_encoded_image",
    "image_format": "jpg",
    "ai_config": {
      "provider": "openai",
      "api_key": "your-openai-key",
      "model": "gpt-4-vision-preview"
    }
  }'
```

## 📈 Monitoraggio

- **Health check**: `/health` per verificare lo stato
- **Logging strutturato**: Log dettagliati di tutte le operazioni
- **Metriche token**: Tracciamento preciso dell'utilizzo
- **Timing**: Misurazione dei tempi di elaborazione

## 🤝 Contributi

Il servizio è progettato per essere estensibile:

1. **Nuovi provider**: Aggiungi nuovi provider AI implementando `BaseAIProvider`
2. **Nuovi tipi**: Estendi `ImageType` e `DocumentType` per nuove categorie
3. **Nuovi campi**: Aggiungi campi ai modelli di dati estratti
4. **Middleware**: Aggiungi middleware personalizzati per logging, autenticazione, etc.

## 📄 Licenza

MIT License - Vedi file LICENSE per dettagli.
