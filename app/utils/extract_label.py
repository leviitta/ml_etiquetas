import fitz  # PyMuPDF
from pathlib import Path
from typing import List, Optional, Dict, Any

def get_label_rect(page: fitz.Page) -> fitz.Rect:
    """Encuentra y devuelve el bounding box de la etiqueta en la mitad izquierda."""
    rect = page.rect
    half_x = rect.width / 2
    min_x, min_y = float('inf'), float('inf')
    max_x, max_y = float('-inf'), float('-inf')

    # 1. Textos
    for b in page.get_text('blocks'):
        if b[0] < half_x:
            min_x = min(min_x, b[0])
            min_y = min(min_y, b[1])
            max_x = max(max_x, b[2])
            max_y = max(max_y, b[3])

    # 2. Dibujos/Líneas (bordes)
    for p in page.get_drawings():
        r = p['rect']
        if r[0] < half_x:
            min_x = min(min_x, r[0])
            min_y = min(min_y, r[1])
            max_x = max(max_x, r[2])
            max_y = max(max_y, r[3])

    # 3. Imágenes (ej. códigos QR / de barras)
    for img in page.get_images(full=True):
        bbox = page.get_image_bbox(img)
        if bbox.x0 < half_x:
            min_x = min(min_x, bbox.x0)
            min_y = min(min_y, bbox.y0)
            max_x = max(max_x, bbox.x1)
            max_y = max(max_y, bbox.y1)

    # Añadir un pequeño margen de 2 pts por seguridad
    margin = 2
    min_x = max(0, min_x - margin)
    min_y = max(0, min_y - margin)
    max_x = min(rect.width, max_x + margin)
    max_y = min(rect.height, max_y + margin)

    # Si no se encontró nada, usar la mitad izquierda por defecto
    if min_x == float('inf'):
        return fitz.Rect(0, 0, half_x, rect.height)
    
    return fitz.Rect(min_x, min_y, max_x, max_y)

def extract_label_from_pdf(input_pdf_path: str, output_pdf_path: Optional[str] = None) -> str:
    """Extrae la etiqueta (mitad izquierda de la primera página) de un PDF."""
    input_path = Path(input_pdf_path)
    if not input_path.exists():
        raise FileNotFoundError(f"No se encontró el archivo: {input_pdf_path}")
        
    output_path = Path(output_pdf_path) if output_pdf_path else input_path.parent / f"{input_path.stem}_solo_etiqueta.pdf"

    with fitz.open(input_path) as doc:
        if not doc:
            raise ValueError("El PDF está vacío")
            
        with fitz.open() as out_doc:
            out_doc.insert_pdf(doc, from_page=0, to_page=0)
            page = out_doc[0]
            new_rect = get_label_rect(page)
            page.set_cropbox(new_rect)
            out_doc.save(output_path)
            
    return str(output_path)

def extract_product_details(doc: fitz.Document) -> str:
    """Extrae y formatea detalles de empaquetado para múltiples productos desde la página 1."""
    if len(doc) < 2:
        return "Sin detalles de producto"
        
    page1 = doc[1]
    blocks = page1.get_text("blocks")
    
    # Filtrar columna derecha de productos (x0 >= 200) y descartar cabeceras/firmas (100 <= y0 < 700)
    prod_blocks = []
    for b in blocks:
        if isinstance(b, (tuple, list)) and len(b) >= 5:
            x0, y0, text_val = b[0], b[1], b[4]
            if isinstance(x0, (int, float)) and x0 >= 200 and isinstance(y0, (int, float)) and 100 <= y0 < 700:
                prod_blocks.append((x0, y0, text_val))
                    
    prod_blocks.sort(key=lambda b: b[1])  # Ordenar de arriba a abajo
    
    products: List[Dict[str, Any]] = []
    current_product: Optional[Dict[str, Any]] = None
    has_qty = False
    
    for b in prod_blocks:
        text = str(b[2]).strip()
        if not text:
            continue
            
        is_qty = text.startswith("Cantidad:")
        contains_colon = ":" in text
        
        # DETECTAR NUEVO PRODUCTO:
        # Si ya registramos la cantidad del producto actual,
        # y encontramos un bloque sin dos puntos (:), es el título del siguiente producto.
        if current_product is None or (has_qty and not contains_colon):
            if current_product:
                products.append(current_product)
            current_product = {
                "title": text,
                "qty": "Cantidad: 1",
                "attrs": []
            }
            has_qty = False
        else:
            if is_qty:
                current_product["qty"] = text
                has_qty = True
            elif contains_colon:
                if has_qty:
                    current_product["attrs"].append(text)
                else:
                    current_product["title"] += " " + text
            else:
                current_product["title"] += " " + text
                
    if current_product:
        products.append(current_product)
        
    formatted_items = []
    for i, p in enumerate(products, 1):
        p_title = " ".join(p["title"].split())
        p_qty = p["qty"]
        p_attrs = ", ".join(p["attrs"])
        
        item_str = f"{i}. {p_title} ({p_qty})"
        if p_attrs:
            item_str += f"\n   {p_attrs}"
        formatted_items.append(item_str)
        
    return "\n\n".join(formatted_items)

def process_multiple_labels(input_paths: List[str], output_path: str) -> str:
    """Procesa múltiples PDFs, extrae la etiqueta y las organiza en una cuadrícula 2x3 con detalles del producto."""
    merged_doc = fitz.open()
    a4_rect = fitz.paper_rect("a4")
    
    # Cuadrícula fija para Mercado Libre: 6 por hoja (2 filas x 3 columnas)
    rows, cols = 2, 3
    labels_per_page = 6
        
    cell_width = a4_rect.width / cols
    cell_height = a4_rect.height / rows
    
    # Margen para posicionar los elementos dentro de cada celda de la grilla
    margin_x = 8
    margin_y = 8
    
    label_width = cell_width - 2 * margin_x
    label_height = 290  # Reservar altura fija para la etiqueta de envío
    
    current_page = None
    label_count = 0
    src_docs = []
    
    try:
        for pdf_path in input_paths:
            doc = fitz.open(pdf_path)
            src_docs.append(doc)
            
            if len(doc) == 0:
                continue
                
            page = doc[0]
            src_rect = get_label_rect(page)
            
            if current_page is None or label_count >= labels_per_page:
                current_page = merged_doc.new_page(width=a4_rect.width, height=a4_rect.height)
                label_count = 0
                
            row = label_count // cols
            col = label_count % cols
            
            cell_start_x = col * cell_width
            cell_start_y = row * cell_height
            
            # 1. Dibujar etiqueta de envío (Zona Superior)
            x0 = cell_start_x + margin_x
            y0 = cell_start_y + margin_y
            x1 = x0 + label_width
            y1 = y0 + label_height
            
            target_rect = fitz.Rect(x0, y0, x1, y1)
            current_page.show_pdf_page(target_rect, doc, 0, clip=src_rect)
            
            # 2. Dibujar cuadro de productos (Zona Inferior)
            product_y0 = y1 + 5
            product_y1 = cell_start_y + cell_height - margin_y
            product_rect = fitz.Rect(x0, product_y0, x1, product_y1)
            
            # Caja contenedora con fondo gris claro y borde sutil
            current_page.draw_rect(product_rect, color=(0.8, 0.8, 0.8), fill=(0.96, 0.96, 0.96), width=0.5)
            
            # Obtener y escribir detalles del producto
            product_text = extract_product_details(doc)
            
            text_padding = 4
            text_rect = fitz.Rect(
                x0 + text_padding, 
                product_y0 + text_padding, 
                x1 - text_padding, 
                product_y1 - text_padding
            )
            current_page.insert_textbox(
                text_rect, 
                product_text, 
                fontsize=6.5, 
                fontname="helv", 
                color=(0.1, 0.1, 0.1)
            )
            
            label_count += 1
            
        merged_doc.save(output_path)
    finally:
        for doc in src_docs:
            doc.close()
        merged_doc.close()
        
    return output_path
