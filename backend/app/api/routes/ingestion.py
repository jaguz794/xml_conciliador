from fastapi import APIRouter, File, HTTPException, UploadFile

from backend.app.models.schemas import ProcessedBatchResponse, ScanFolderRequest
from backend.app.services.ingestion_service import process_uploaded_file, scan_input_directory

router = APIRouter()


@router.post("/archivo", response_model=ProcessedBatchResponse)
async def upload_invoice_file(file: UploadFile = File(...)) -> ProcessedBatchResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="El archivo debe tener nombre.")

    try:
        content = await file.read()
        return process_uploaded_file(file.filename, content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/escanear-carpeta", response_model=ProcessedBatchResponse)
def scan_folder(payload: ScanFolderRequest) -> ProcessedBatchResponse:
    try:
        return scan_input_directory(move_processed=payload.move_processed)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

