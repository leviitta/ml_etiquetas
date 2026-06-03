# Estrategia Latam, Watermark y Extensión Chrome

## Confirmado hasta ahora:
**1. Extensión de Chrome (Arquitectura Backend):**
- Endpoint listo: `POST /api/v1/extract` (multipart/form-data).
- **Problema de CORS:** El backend FastAPI actualmente no tiene CORS configurado. La extensión usará un Service Worker (Background Script) para hacer las peticiones `fetch` sin ser bloqueada por las políticas del navegador, o se inyectará CORS en la app de FastAPI.

**2. Watermark de PDF:**
- Se inyectará usando `PyMuPDF (fitz)` dentro de `app/utils/extract_label.py`. 
- El lugar preciso será en la función `process_multiple_labels` cuando se construye el documento unificado final.

**3. Estrategia LATAM:**
- Fuerte base del 90% orgánico (SEO + Inteligencia Artificial Generativa / GEO) enfocada en keywords como "separar etiquetas mercado libre pdf". 
- Posicionamiento centrado en: Gratuito, Sin registro, Rápido.

## Por Definir:
- UX de la extensión de Chrome (Botón inyectado vs Popup autónomo).
- Estilo del Watermark (Texto vs Imagen/Logo).
- Enfoque del 10% Pagado (Google Ads transaccional vs Meta Ads social).