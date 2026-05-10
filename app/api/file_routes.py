from fastapi import APIRouter, File, HTTPException, UploadFile

from app.schemas.tasks import UploadedFileResponse
from app.services.attachment_service import AttachmentServiceError, save_uploaded_file


router = APIRouter(prefix="/files", tags=["files"])


@router.post("/upload", response_model=UploadedFileResponse)
async def upload_file(file: UploadFile = File(...)):
    try:
        return await save_uploaded_file(file)
    except AttachmentServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
