import os
import uuid
import shutil
import tempfile
from typing import List
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi import APIRouter, Request, File, UploadFile, BackgroundTasks, Form
from tempfile import NamedTemporaryFile
from app.utils.extract_label import extract_label_from_pdf, process_multiple_labels

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    """Render the upload form"""
    user = request.session.get('user')
    return templates.TemplateResponse(request=request, name="index.html", context={"user": user})

@router.post("/extract")
async def extract_label(
    request: Request, 
    background_tasks: BackgroundTasks, 
    files: List[UploadFile] = File(...),
    labels_per_page: int = Form(1)
):
    """Handle PDF upload, extract label, and return the PDF file directly"""
    user = request.session.get('user')
    if not user:
        return JSONResponse(status_code=401, content={"error": "Debes iniciar sesión para extraer etiquetas."})

    valid_files = [f for f in files if f.filename and f.filename.lower().endswith(".pdf")]
    
    if not valid_files:
        return JSONResponse(status_code=400, content={"error": "Por favor, sube al menos un archivo PDF válido."})
    
    file_id = str(uuid.uuid4())
    temp_dir = tempfile.gettempdir()
    
    output_path = os.path.join(temp_dir, f"{file_id}_output.pdf")
    input_paths = []

    try:
        # Guardar todos los archivos subidos temporalmente
        for i, file in enumerate(valid_files):
            input_path = os.path.join(temp_dir, f"{file_id}_input_{i}.pdf")
            with open(input_path, "wb") as f:
                shutil.copyfileobj(file.file, f)
            input_paths.append(input_path)
            file.file.close()

        # Procesar todos los archivos y generar un único PDF optimizado
        process_multiple_labels(input_paths, output_path, labels_per_page)
        
    except Exception as e:
        for path in input_paths:
            if os.path.exists(path): os.unlink(path)
        if os.path.exists(output_path): os.unlink(output_path)
        return JSONResponse(status_code=500, content={"error": f"Error al procesar los PDFs: {str(e)}"})

    # Limpiar archivos de entrada inmediatamente
    for path in input_paths:
        if os.path.exists(path): os.unlink(path)

    # Limpiar archivo de salida después de enviar
    background_tasks.add_task(os.unlink, output_path)

    return FileResponse(
        output_path, 
        media_type="application/pdf", 
        filename="etiquetas_optimizadas.pdf"
    )
