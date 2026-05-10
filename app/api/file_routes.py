import re
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.schemas.tasks import UploadedFileResponse


router = APIRouter(prefix="/files", tags=["files"])

PROJECT_ROOT = Path(__file__).resolve().parents[2]
UPLOAD_ROOT = PROJECT_ROOT / "workspace_files" / "uploads"

MAX_UPLOAD_SIZE = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {".txt", ".md", ".csv", ".json", ".pdf"}


def safe_filename(filename: str) -> str:
    raw_name = Path(filename or "upload").name
    stem = Path(raw_name).stem or "file"
    suffix = Path(raw_name).suffix.lower()
    safe_stem = re.sub(r"[^a-zA-Z0-9._-]+", "_", stem).strip("._-") or "file"
    return f"{safe_stem[:80]}{suffix}"


@router.post("/upload", response_model=UploadedFileResponse)
async def upload_file(file: UploadFile = File(...)):
    filename = safe_filename(file.filename or "upload")
    suffix = Path(filename).suffix.lower()

    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="不支持的文件类型")

    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)

    stored_name = f"{uuid4().hex}_{filename}"
    target_path = UPLOAD_ROOT / stored_name
    size = 0

    with target_path.open("wb") as output:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)

            if size > MAX_UPLOAD_SIZE:
                target_path.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail="文件不能超过 10MB")

            output.write(chunk)

    relative_path = f"uploads/{stored_name}"

    return UploadedFileResponse(
        filename=filename,
        stored_name=stored_name,
        path=relative_path,
        display_path=f"workspace_files/{relative_path}",
        size=size,
        content_type=file.content_type,
    )
