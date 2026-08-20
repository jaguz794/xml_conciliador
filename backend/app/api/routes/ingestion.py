from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile

from backend.app.api.dependencies import get_application_session
from backend.app.models.schemas import ProcessedBatchResponse, ScanFolderRequest
from backend.app.services.ingestion_service import process_uploaded_file, scan_input_directory
from backend.app.services.auth_service import (
    ACTION_SCAN_INPUT_FOLDER,
    ACTION_UPLOAD_FILE,
    SessionContext,
    log_user_action,
)

router = APIRouter()


@router.post("/archivo", response_model=ProcessedBatchResponse)
async def upload_invoice_file(
    request: Request,
    file: UploadFile = File(...),
    session: SessionContext = Depends(get_application_session),
) -> ProcessedBatchResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="El archivo debe tener nombre.")

    try:
        content = await file.read()
        result = process_uploaded_file(file.filename, content)
        log_user_action(
            session,
            action=ACTION_UPLOAD_FILE,
            request=request,
            detail=f"archivo={file.filename}; procesadas={result.total_procesadas}",
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/escanear-carpeta", response_model=ProcessedBatchResponse)
def scan_folder(
    payload: ScanFolderRequest,
    request: Request,
    session: SessionContext = Depends(get_application_session),
) -> ProcessedBatchResponse:
    try:
        result = scan_input_directory(move_processed=payload.move_processed)
        log_user_action(
            session,
            action=ACTION_SCAN_INPUT_FOLDER,
            request=request,
            detail=f"move_processed={payload.move_processed}; procesadas={result.total_procesadas}",
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

