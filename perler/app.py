"""拼豆图纸工坊 · 服务端。

上传一张图 → 后台跑确定性管线 → 得到一份完整的可交互拼豆图纸页面。
页面本身自带编辑、换色板、换尺寸、3D 预览与海报导出，所以这里只负责「把图变成图纸」和「把图纸取回来」。
"""
from __future__ import annotations

import json
import shutil
import threading
import traceback
from datetime import datetime
from pathlib import Path
from typing import Literal

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel

from .converter import JOBS, Options, convert, new_job_dir, parse_boards

app = FastAPI(title="拼豆图纸工坊", version="1.0")
STATIC = JOBS.parent.parent / "static"

ALLOWED = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
MAX_BYTES = 12 * 1024 * 1024


class Job(BaseModel):
    id: str
    task: str
    status: Literal["queued", "running", "done", "error"]
    step: str = ""
    created: str
    boards: list[int] = []
    defaultSize: int | None = None
    boards_summary: list[dict] = []
    source: str | None = None
    error: str | None = None


JOBS.mkdir(parents=True, exist_ok=True)
_jobs: dict[str, Job] = {}


def _job_file(job_id: str) -> Path | None:
    if not job_id or any(c in job_id for c in "/\\."):
        return None
    d = JOBS / job_id
    return d if d.is_dir() else None


def _load_all():
    for meta in sorted(JOBS.glob("*/meta.json")):
        try:
            data = json.loads(meta.read_text(encoding="utf-8"))
        except Exception:
            continue
        jid = meta.parent.name
        if jid in _jobs:
            continue
        _jobs[jid] = Job(id=jid, task=data.get("task", "拼豆图纸"), status="done",
                         created=data.get("created", ""), boards=data.get("boards", []),
                         defaultSize=data.get("defaultSize"), boards_summary=data.get("boards_summary", []),
                         source=data.get("source"))


_load_all()
_lock = threading.Lock()


def _set(job_id: str, **kw):
    with _lock:
        j = _jobs.get(job_id)
        if j:
            for k, v in kw.items():
                setattr(j, k, v)


def _run(job_id: str, src: Path, task: str, opts: Options):
    _set(job_id, status="running", step="准备图片")
    try:
        meta = convert(src, JOBS / job_id, task, opts,
                       log=lambda s: _set(job_id, step=s))
        _set(job_id, status="done", step="完成", boards=meta["boards"],
             defaultSize=meta["defaultSize"], boards_summary=meta["boards_summary"], source=meta["source"])
    except Exception as e:  # 转换失败把原因如实留给玩家
        traceback.print_exc()
        _set(job_id, status="error", error=str(e) or e.__class__.__name__)


@app.get("/", response_class=HTMLResponse)
def index():
    return (STATIC / "index.html").read_text(encoding="utf-8")


@app.post("/api/convert", response_model=Job)
async def api_convert(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    task: str = Form(""),
    boards: str = Form("36,52,78,104,156"),
    default_size: int = Form(0),
    max_colors: int = Form(28),
    trim_border: bool = Form(True),
    merge_colors: bool = Form(False),
):
    suffix = Path(file.filename or "image.png").suffix.lower()
    if suffix not in ALLOWED:
        raise HTTPException(400, f"支持 PNG、JPG、WEBP、BMP、GIF，当前是 {suffix or '未知格式'}")
    data = await file.read()
    if not data:
        raise HTTPException(400, "图片是空的")
    if len(data) > MAX_BYTES:
        raise HTTPException(400, "图片超过 12MB，先压缩一下再上传")
    d = new_job_dir()
    src = d / f"upload{suffix}"
    src.write_bytes(data)
    try:
        board_list = parse_boards(boards)
    except ValueError as e:
        raise HTTPException(400, str(e))
    name = (task.strip() or Path(file.filename or "拼豆图纸").stem)[:24]
    opts = Options(boards=board_list, default_size=default_size or None,
                   max_colors=max_colors, trim_white_border=trim_border,
                   merge_close_colors=merge_colors)
    job = Job(id=d.name, task=name, status="queued", step="排队中",
              created=datetime.now().strftime("%Y-%m-%d %H:%M:%S"), boards=board_list)
    with _lock:
        _jobs[job.id] = job
    background.add_task(_run, job.id, src, name, opts)
    return job


@app.get("/api/jobs", response_model=list[Job])
def api_jobs():
    with _lock:
        items = list(_jobs.values())
    return sorted(items, key=lambda j: j.id, reverse=True)


@app.get("/api/jobs/{job_id}", response_model=Job)
def api_job(job_id: str):
    with _lock:
        j = _jobs.get(job_id)
    if not j:
        raise HTTPException(404, "没有这份图纸")
    return j


@app.get("/api/jobs/{job_id}/blueprint", response_class=HTMLResponse)
def api_blueprint(job_id: str):
    d = _job_file(job_id)
    f = d / "blueprint.html" if d else None
    if not f or not f.exists():
        raise HTTPException(404, "图纸还没生成好")
    return HTMLResponse(f.read_text(encoding="utf-8"),
                        headers={"Content-Disposition": f'inline; filename="{job_id}.html"'})


@app.get("/api/jobs/{job_id}/download")
def api_download(job_id: str):
    d = _job_file(job_id)
    f = d / "blueprint.html" if d else None
    if not f or not f.exists():
        raise HTTPException(404, "图纸还没生成好")
    with _lock:
        task = (_jobs.get(job_id).task if _jobs.get(job_id) else "拼豆图纸")
    safe = "".join(c for c in task if c not in '\\/:*?"<>|').strip() or "拼豆图纸"
    stamp = datetime.fromisoformat(_jobs[job_id].created).strftime("%m月%d日_%H点%M分") if _jobs.get(job_id) and _jobs[job_id].created else ""
    return FileResponse(f, media_type="text/html", filename=f"{safe}{'-' + stamp if stamp else ''}.html")


@app.delete("/api/jobs/{job_id}")
def api_delete(job_id: str):
    d = _job_file(job_id)
    if not d:
        raise HTTPException(404, "没有这份图纸")
    shutil.rmtree(d, ignore_errors=True)
    with _lock:
        _jobs.pop(job_id, None)
    return JSONResponse({"ok": True})
