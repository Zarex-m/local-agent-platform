from pathlib import Path
from datetime import datetime
import shutil
from typing import Any

from mcp.server.fastmcp import FastMCP


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = PROJECT_ROOT / "workspace_files"

WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)

mcp = FastMCP("workspace")

#把用户传入的相对路径转换成 workspace_files 里面的绝对路径，并防止用户访问工作区外面的文件
def resolve_workspace_path(path: str | None = None) -> Path:
    raw_path = path or "."
    candidate = (WORKSPACE_ROOT / raw_path).resolve()

    if not str(candidate).startswith(str(WORKSPACE_ROOT.resolve())):
        raise ValueError("路径超出 workspace_files 工作目录")

    return candidate

#将一个文件的基本信息整理成字典
def file_info(path: Path) -> dict[str, Any]:
    stat = path.stat()

    return {
        "name": path.name,
        "path": str(path.relative_to(WORKSPACE_ROOT)),
        "type": "directory" if path.is_dir() else "file",
        "size": stat.st_size,
        "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
        "suffix": path.suffix.lower(),
    }
    
@mcp.tool()
def scan_files(path: str = ".", max_depth: int = 2) -> dict:
    """
    扫描 workspace_files 下的文件和目录。
    path 是相对 workspace_files 的路径。
    max_depth 控制递归深度，默认 2。
    """
    root = resolve_workspace_path(path)

    if not root.exists():
        return {
            "success": False,
            "data": None,
            "error": f"路径不存在：{path}",
        }

    if not root.is_dir():
        return {
            "success": False,
            "data": None,
            "error": f"路径不是目录：{path}",
        }

    items = []
    root_depth = len(root.relative_to(WORKSPACE_ROOT).parts)

    for item in root.rglob("*"):
        relative_depth = len(item.relative_to(WORKSPACE_ROOT).parts) - root_depth

        if relative_depth > max_depth:
            continue

        items.append(file_info(item))

    return {
        "success": True,
        "data": {
            "root": str(root.relative_to(WORKSPACE_ROOT)),
            "items": items,
        },
        "error": None,
    }

@mcp.tool()
def read_workspace_file(path: str, max_bytes: int = 200_000) -> dict:
    """
    读取 workspace_files 下的文本文件内容。
    path 是相对 workspace_files 的路径。
    max_bytes 限制最大读取字节数，默认 200000。
    """
    target = resolve_workspace_path(path)

    if not target.exists():
        return {
            "success": False,
            "data": None,
            "error": f"文件不存在：{path}",
        }

    if not target.is_file():
        return {
            "success": False,
            "data": None,
            "error": f"路径不是文件：{path}",
        }

    if target.stat().st_size > max_bytes:
        return {
            "success": False,
            "data": None,
            "error": f"文件过大，超过 {max_bytes} bytes",
        }

    try:
        content = target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return {
            "success": False,
            "data": None,
            "error": f"文件不是 UTF-8 文本文件：{path}",
        }

    return {
        "success": True,
        "data": {
            "path": str(target.relative_to(WORKSPACE_ROOT)),
            "content": content,
        },
        "error": None,
    }

    
@mcp.tool()
def move_file(source_path: str, target_path: str) -> dict:
    """
    移动 workspace_files 下的文件或目录。
    source_path 和 target_path 都是相对 workspace_files 的路径。
    """
    source = resolve_workspace_path(source_path)
    target = resolve_workspace_path(target_path)

    if not source.exists():
        return {
            "success": False,
            "data": None,
            "error": f"源路径不存在：{source_path}",
        }

    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(target))

    return {
        "success": True,
        "data": {
            "source_path": source_path,
            "target_path": target_path,
        },
        "error": None,
    }


@mcp.tool()
def copy_file(source_path: str, target_path: str) -> dict:
    """
    复制 workspace_files 下的文件。
    source_path 和 target_path 都是相对 workspace_files 的路径。
    """
    source = resolve_workspace_path(source_path)
    target = resolve_workspace_path(target_path)

    if not source.exists():
        return {
            "success": False,
            "data": None,
            "error": f"源路径不存在：{source_path}",
        }

    if not source.is_file():
        return {
            "success": False,
            "data": None,
            "error": f"源路径不是文件：{source_path}",
        }

    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)

    return {
        "success": True,
        "data": {
            "source_path": source_path,
            "target_path": target_path,
        },
        "error": None,
    }


@mcp.tool()
def rename_file(source_path: str, new_name: str) -> dict:
    """
    重命名 workspace_files 下的文件或目录。
    new_name 只能是新文件名，不能包含路径分隔符。
    """
    source = resolve_workspace_path(source_path)

    if "/" in new_name or "\\" in new_name:
        return {
            "success": False,
            "data": None,
            "error": "new_name 不能包含路径分隔符",
        }

    if not source.exists():
        return {
            "success": False,
            "data": None,
            "error": f"源路径不存在：{source_path}",
        }

    target = source.with_name(new_name)
    target = resolve_workspace_path(str(target.relative_to(WORKSPACE_ROOT)))
    source.rename(target)

    return {
        "success": True,
        "data": {
            "source_path": source_path,
            "target_path": str(target.relative_to(WORKSPACE_ROOT)),
        },
        "error": None,
    }


@mcp.tool()
def write_markdown_report(path: str, content: str) -> dict:
    """
    写入 Markdown 报告到 workspace_files。
    path 是相对 workspace_files 的路径，必须以 .md 结尾。
    """
    target = resolve_workspace_path(path)

    if target.suffix.lower() != ".md":
        return {
            "success": False,
            "data": None,
            "error": "报告路径必须以 .md 结尾",
        }

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")

    return {
        "success": True,
        "data": {
            "path": str(target.relative_to(WORKSPACE_ROOT)),
            "message": "Markdown 报告已写入",
        },
        "error": None,
    }


if __name__ == "__main__":
    mcp.run()