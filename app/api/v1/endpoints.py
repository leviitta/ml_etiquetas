import os
import shutil
import tempfile
from typing import List
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi import APIRouter, Request, File, UploadFile, BackgroundTasks
from app.utils.extract_label import process_multiple_labels
from app.db.quota import get_quota_status, verify_quota_for_batch, register_usage, QuotaExceededException

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

def format_price(amount: float) -> str:
    """Format price to a string like 4.990"""
    return f"{int(amount):,}".replace(",", ".")

@router.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    """Render the upload form"""
    user = request.session.get('user')
    quota_status = None
    if user and user.get("email"):
        quota_status = await get_quota_status(user["email"])
        
    prices = {
        "pro": format_price(float(os.getenv("PAYMENT_PRO_AMOUNT", "4990"))),
        "infinity": format_price(float(os.getenv("PAYMENT_INFINITY_AMOUNT", "12990"))),
        "upgrade": format_price(float(os.getenv("PAYMENT_UPGRADE_AMOUNT", "8000")))
    }
        
    return templates.TemplateResponse(
        request=request, 
        name="index.html", 
        context={"user": user, "quota_status": quota_status, "prices": prices}
    )

@router.post("/extract")
async def extract_label(
    request: Request, 
    background_tasks: BackgroundTasks, 
    files: List[UploadFile] = File(...)
):
    """Handle PDF upload, extract label, and return the PDF file directly"""
    user = request.session.get('user')
    if not user:
        return JSONResponse(status_code=401, content={"error": "Debes iniciar sesión para extraer etiquetas."})
        
    email = user.get("email")
    if not email:
        return JSONResponse(status_code=401, content={"error": "Usuario no válido."})

    valid_files = [f for f in files if f.filename and f.filename.lower().endswith(".pdf")]
    if not valid_files:
        return JSONResponse(status_code=400, content={"error": "Por favor, sube al menos un archivo PDF válido."})
        
    num_files = len(valid_files)
    
    # 1. Verificar cuota antes de procesar
    try:
        await verify_quota_for_batch(email, num_files)
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
        
        # 2. Registrar el uso de cada archivo exitosamente procesado
        for _ in range(num_files):
            await register_usage(email)
            
    except Exception as e:
        temp_dir_obj.cleanup()
        return JSONResponse(status_code=500, content={"error": f"Error al procesar los PDFs: {str(e)}"})

    # Limpiar el directorio temporal después de enviar el archivo
    # Note: FileResponse can take a background task, but we can also use background_tasks
    background_tasks.add_task(temp_dir_obj.cleanup)

    return FileResponse(
        output_path, 
        media_type="application/pdf", 
        filename="etiquetas_optimizadas.pdf"
    )
