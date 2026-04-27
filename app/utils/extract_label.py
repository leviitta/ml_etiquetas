import fitz  # PyMuPDF
from pathlib import Path

def get_label_rect(page):
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


def extract_label_from_pdf(input_pdf_path: str, output_pdf_path: str = None):
    """
    Extrae la etiqueta (mitad izquierda de la primera página) de un PDF de MercadoLibre.
    """
    input_path = Path(input_pdf_path)
    if not input_path.exists():
        raise FileNotFoundError(f"No se encontró el archivo: {input_pdf_path}")
        
    if output_pdf_path is None:
        output_path = input_path.parent / f"{input_path.stem}_solo_etiqueta.pdf"
    else:
        output_path = Path(output_pdf_path)

    print(f"Procesando: {input_path}")
    
    # Abrir el PDF original
    doc = fitz.open(input_path)
    
    if len(doc) == 0:
        raise ValueError("El PDF está vacío")
        
    # Crear un nuevo documento para guardar solo la etiqueta
    out_doc = fitz.open()
    
    # Insertar solo la primera página (índice 0)
    out_doc.insert_pdf(doc, from_page=0, to_page=0)
    page = out_doc[0]
    
    # Obtener el bounding box de la etiqueta
    new_rect = get_label_rect(page)
    page.set_cropbox(new_rect)
    
    # Guardar el nuevo PDF
    out_doc.save(output_path)
    out_doc.close()
    doc.close()
    
    print(f"¡Éxito! Etiqueta guardada en: {output_path}")
    return output_path


def process_multiple_labels(input_paths: list[str], output_path: str, labels_per_page: int):
    """
    Procesa múltiples PDFs, extrae la etiqueta de cada uno, y los organiza en una cuadrícula
    en un nuevo documento PDF con hojas tamaño A4.
    """
    merged_doc = fitz.open()
    a4_rect = fitz.paper_rect("a4")  # Tamaño A4 (Portrait)
    
    # Definir la cuadrícula basada en etiquetas por hoja
    if labels_per_page == 1:
        rows, cols = 1, 1
    elif labels_per_page == 2:
        rows, cols = 1, 2  # Asumo que te referías a 1 fila x 2 columnas para que entren 2
    elif labels_per_page <= 4:
        rows, cols = 2, 2
        labels_per_page = 4
    else:
        rows, cols = 2, 3
        labels_per_page = 6
        
    cell_width = a4_rect.width / cols
    cell_height = a4_rect.height / rows
    
    # Margen entre etiquetas y borde de la página (en puntos)
    margin_x = 10
    margin_y = 10
    
    # Tamaño uniforme para 1 a 6 etiquetas (basado en la celda de 6 por hoja: 2x3)
    uniform_label_width = a4_rect.width / 3 - 2 * margin_x
    uniform_label_height = a4_rect.height / 2 - 2 * margin_y
    
    current_page = None
    label_count = 0
    
    # Mantener los documentos abiertos hasta guardar
    src_docs = []
    
    try:
        for pdf_path in input_paths:
            doc = fitz.open(pdf_path)
            src_docs.append(doc)
            
            if len(doc) == 0:
                continue
                
            page = doc[0]
            src_rect = get_label_rect(page)
            
            # Crear nueva página si es necesario
            if current_page is None or label_count >= labels_per_page:
                current_page = merged_doc.new_page(width=a4_rect.width, height=a4_rect.height)
                label_count = 0
                
            row = label_count // cols
            col = label_count % cols
            
            # Determinar el tamaño de la etiqueta a estampar
            label_width = uniform_label_width
            label_height = uniform_label_height
                
            # Esquina superior izquierda de la celda actual
            cell_start_x = col * cell_width
            cell_start_y = row * cell_height
            
            # Calcular las coordenadas alineando la etiqueta a la esquina superior izquierda (con margen)
            x0 = cell_start_x + margin_x
            y0 = cell_start_y + margin_y
            x1 = x0 + label_width
            y1 = y0 + label_height
            
            target_rect = fitz.Rect(x0, y0, x1, y1)
            
            # Estampar la porción recortada de la etiqueta en la celda correspondiente
            current_page.show_pdf_page(target_rect, doc, 0, clip=src_rect)
            
            label_count += 1
            
        merged_doc.save(output_path)
    finally:
        for doc in src_docs:
            doc.close()
        merged_doc.close()
        
    return output_path