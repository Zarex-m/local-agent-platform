import re
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.schemas.tasks import UploadedFileResponse


PROJECT_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = PROJECT_ROOT / "workspace_files"
UPLOAD_ROOT = WORKSPACE_ROOT / "uploads"

MAX_UPLOAD_SIZE = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {".txt", ".md", ".csv", ".json", ".pdf"}


class AttachmentServiceError(Exception):
    def __init__(self, detail: str, status_code: int = 400):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


def safe_filename(filename: str) -> str:
    raw_name = Path(filename or "upload").name
    stem = Path(raw_name).stem or "file"
    suffix = Path(raw_name).suffix.lower()
    safe_stem = re.sub(r"[^a-zA-Z0-9._-]+", "_", stem).strip("._-") or "file"
    return f"{safe_stem[:80]}{suffix}"


async def save_uploaded_file(file: Any) -> UploadedFileResponse:
    filename = safe_filename(file.filename or "upload")
    suffix = Path(filename).suffix.lower()

    if suffix not in ALLOWED_EXTENSIONS:
        raise AttachmentServiceError("不支持的文件类型")

    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)

    stored_name = f"{uuid4().hex}_{filename}"
    target_path = UPLOAD_ROOT / stored_name
    size = 0

    with target_path.open("wb") as output:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)

            if size > MAX_UPLOAD_SIZE:
                target_path.unlink(missing_ok=True)
                raise AttachmentServiceError("文件不能超过 10MB", status_code=413)

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


def normalize_attachment_path(path: str) -> str:
    candidate = Path(path)

    if candidate.is_absolute() or ".." in candidate.parts:
        raise AttachmentServiceError("附件路径不合法")

    relative_path = candidate.as_posix().lstrip("/")

    if not relative_path.startswith("uploads/"):
        raise AttachmentServiceError("附件必须来自上传目录")

    target_path = (WORKSPACE_ROOT / relative_path).resolve()

    if not target_path.is_relative_to(WORKSPACE_ROOT.resolve()):
        raise AttachmentServiceError("附件路径越界")

    if not target_path.exists():
        raise AttachmentServiceError(f"附件不存在: {relative_path}")

    return relative_path


def build_task_with_attachments(task: str, attachment_paths: list[str]) -> str:
    if not attachment_paths:
        return task

    normalized_paths = [normalize_attachment_path(path) for path in attachment_paths]
    files_text = "\n".join(
        f"- workspace_files/{path}，工具调用时使用相对路径：{path}"
        for path in normalized_paths
    )

    return f"""{task}

用户上传了以下文件：
{files_text}

请优先使用 workspace MCP 文件工具读取这些文件。"""
