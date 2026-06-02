import os
import uuid
import shutil
import tempfile
from typing import List
from fastapi import APIRouter, Request, File, UploadFile, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from app.utils.extract_label import process_multiple_labels
from app.db.quota import verify_quota_for_batch, QuotaExceededException, ensure_user

router = APIRouter()

@router.post("/extract")
async def extract_label(
    request: Request, 
    background_tasks: BackgroundTasks, 
    files: List[UploadFile] = File(...)
):
    """Handle PDF upload, extract label, and return the PDF file directly"""
    user = request.session.get('user')
    
    if user and user.get("email"):
        identifier = user["email"]
    else:
        identifier = request.session.get("anon_id")
        if not identifier:
            # Fallback (should have been created on index load)
            identifier = f"anon_{uuid.uuid4().hex[:12]}"
            request.session["anon_id"] = identifier
            
    await ensure_user(identifier, user.get("name", "Usuario Anónimo") if user else "Usuario Anónimo")

    valid_files = [f for f in files if f.filename and f.filename.lower().endswith(".pdf")]
    if not valid_files:
        return JSONResponse(status_code=400, content={"error": "Por favor, sube al menos un archivo PDF válido."})
        
    # Validar límite de tamaño de 200 KB por archivo
    for file in valid_files:
        _ = file.file.seek(0, 2)
        size = file.file.tell()
        _ = file.file.seek(0)
        if size > 200 * 1024:
            return JSONResponse(
                status_code=400,
                content={"error": f"El archivo {file.filename} supera el límite de tamaño permitido de 200 KB."}
            )
            
    num_files = len(valid_files)
    
    # 1. Verificar cuota antes de procesar
    try:
        await verify_quota_for_batch(identifier, num_files)
    except QuotaExceededException as e:
        return JSONResponse(status_code=403, content={"error": str(e.detail)})
        
    # Usar un directorio temporal seguro
    temp_dir_obj = tempfile.TemporaryDirectory()
    temp_dir = temp_dir_obj.name
    
    output_path = os.path.join(temp_dir, "output.pdf")
    input_paths = []

    try:
        # Guardar todos los archivos subidos temporalmente
        for i, file in enumerate(valid_files):
            input_path = os.path.join(temp_dir, f"input_{i}.pdf")
            with open(input_path, "wb") as f:
                shutil.copyfileobj(file.file, f)
            input_paths.append(input_path)
            file.file.close()

        # Procesar todos los archivos y generar un único PDF optimizado
        process_multiple_labels(input_paths, output_path)
            
    except Exception as e:
        temp_dir_obj.cleanup()
        return JSONResponse(status_code=500, content={"error": f"Error al procesar los PDFs: {str(e)}"})

    # Limpiar el directorio temporal después de enviar el archivo
    background_tasks.add_task(temp_dir_obj.cleanup)

    return FileResponse(
        output_path, 
        media_type="application/pdf", 
        filename="etiquetas_optimizadas.pdf"
    )
