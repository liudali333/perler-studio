"""拼豆图纸转换引擎。

直接复用拼豆专家技能里的确定性管线（对齐搜索 → 簇票数 → HTML 图纸模板），
把任意一张图片转成可交互、可编辑、可导出的拼豆图纸页面。

管线：
    pipeline.alignment_search  —— 在 36/52/78/104/156 五档板上搜索对齐（内容格数 n + 相位 dx,dy）
    pipeline.build_html_blueprint —— 聚类出簇与格内票数，拼装单文件 HTML（含 25 套色板、编辑、3D、导出）
"""
from __future__ import annotations

import base64
import io
import json
import re
import shutil
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable
from zoneinfo import ZoneInfo

import numpy as np
from PIL import Image
from skimage.color import rgb2lab

import pipeline.alignment_search as A
import pipeline.build_html_blueprint as B

TZ = ZoneInfo("Asia/Shanghai")
ROOT = Path(__file__).resolve().parent
JOBS = ROOT / "jobs"
CANVAS = 1024  # 参考图统一缩放到 1024 长边，与专家管线的生图尺寸一致，切格精度也一致


@dataclass
class Options:
    boards: list[int] = field(default_factory=lambda: [36, 52, 78, 104, 156])
    default_size: int | None = None
    max_colors: int = 28
    white_threshold: int = 245
    merge_close_colors: bool = False
    trim_white_border: bool = True
    palette: str = "palette_mard221.csv"


def parse_boards(text: str | Iterable[int] | None) -> list[int]:
    if text is None:
        return [36, 52, 78, 104, 156]
    if isinstance(text, str):
        parts = [p for p in re.split(r"[,\s]+", text.strip()) if p]
    else:
        parts = [str(p) for p in text]
    out = []
    for p in parts:
        n = A.parse_board(p)
        if n not in out:
            out.append(n)
    return sorted(out) or [36, 52, 78, 104, 156]


def prepare_canvas(src: Path, dst: Path, trim_white_border: bool) -> Path:
    """统一成 1024 长边、带透明通道的 PNG；白底图把白色抠成透明，让剪影检测拿到真正的轮廓。"""
    im = Image.open(src)
    im.seek(0)
    im = im.convert("RGBA")
    w, h = im.size
    scale = CANVAS / max(w, h)
    if scale < 1:
        im = im.resize((max(1, round(w * scale)), max(1, round(h * scale))), Image.Resampling.LANCZOS)
    arr = np.array(im)
    rgb, alpha = arr[..., :3].astype(np.int16), arr[..., 3].astype(np.int16)
    if alpha.min() >= 250:  # 没有透明通道：把接近纯白的像素当背景
        near_white = (rgb.min(axis=-1) >= 238) & ((rgb.max(axis=-1) - rgb.min(axis=-1)) <= 22)
        if near_white.mean() < 0.62:  # 白色太多的图（如纯白背景肖像）反而扣掉会吃掉主体高光，阈值收严
            alpha[near_white] = 0
        else:
            stricter = (rgb.min(axis=-1) >= 250) & ((rgb.max(axis=-1) - rgb.min(axis=-1)) <= 10)
            alpha[stricter] = 0
        arr[..., 3] = alpha.astype(np.uint8)
        im = Image.fromarray(arr, "RGBA")
    dst.parent.mkdir(parents=True, exist_ok=True)
    im.save(dst)
    if trim_white_border:
        # 一圈贴纸白边会让图纸多一圈白豆：先裁掉贴纸边再切格（函数内部会判断有没有白边）
        trimmed = dst.with_name(dst.stem + "_trim.png")
        try:
            info = A.strip_sticker_border(dst, trimmed)
            if info and trimmed.exists():
                shutil.move(str(trimmed), str(dst))
        except Exception:
            trimmed.unlink(missing_ok=True)
    return dst


def shrink(im: Image.Image, side: int = 96) -> str:
    im = im.copy()
    im.thumbnail((side, side), Image.Resampling.NEAREST)
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def convert(src: Path, job_dir: Path, task_name: str, opts: Options,
            log: Callable[[str], None] = lambda s: None) -> dict:
    job_dir.mkdir(parents=True, exist_ok=True)
    source = prepare_canvas(src, job_dir / "source.png", opts.trim_white_border)
    log("正在分析画面轮廓")
    rgb, mask, bbox = A.foreground(A.open_image(source), opts.white_threshold)
    if mask.sum() < 64:
        raise ValueError("没能在图里找到主体，换一张对比更清楚的图片试试（背景干净、主体完整的图效果最好）")

    boards = parse_boards(opts.boards)
    palette_csv = B.DEFAULT_PALETTE if opts.palette.endswith(".csv") else B.DEFAULT_PALETTE
    max_colors = int(np.clip(opts.max_colors, 4, 60))

    labels, colors, codes = A.palette_labels(rgb, mask, palette_csv, max_colors, opts.merge_close_colors)
    sampler = A.Sampler(labels, len(colors))
    evaluator = A.Evaluator(rgb, mask, bbox)

    process = job_dir / "process"
    process.mkdir(parents=True, exist_ok=True)
    summaries = []
    for board in boards:
        t0 = time.perf_counter()
        log(f"正在排布 {board} 格的豆子")
        records = A.search(sampler, evaluator, colors, bbox, board, None, 5, 0.025)
        target = process / f"{basis_name(board)}_k{max_colors}"
        selection = dict(records[0])
        selection["content_width"] = selection.get("content_width", board)
        selection["content_height"] = selection.get("content_height", board)
        selected_grid = A.board_grid(sampler.sample(bbox, selection["n"], selection["dx"], selection["dy"])[0], board)
        pitch = A.geometry(bbox, selection["n"], selection["dx"], selection["dy"])[2]
        ring, total = A.outline_ring(labels, mask, len(colors), pitch)
        target.mkdir(parents=True, exist_ok=True)
        (target / "grid_mard.csv").write_text(
            "\n".join(",".join(codes[i] for i in row) for row in selected_grid), encoding="utf-8")
        (target / "metrics.json").write_text(json.dumps(dict(
            selected={k: (int(v) if isinstance(v, (np.integer,)) else float(v) if isinstance(v, (np.floating,)) else v)
                      for k, v in selection.items()},
            max_colors=max_colors, merge_close_colors=opts.merge_close_colors,
            search=dict(phases=5, size_weight=0.025, white_threshold=opts.white_threshold, evaluation_side=384,
                        loss_weights=dict(color=0.5, edge=0.3, local=0.2)),
            content_width=int(selection["content_width"]), content_height=int(selection["content_height"]),
            ring=[int(v) for v in ring], total=[int(v) for v in total],
        ), ensure_ascii=False), encoding="utf-8")
        summaries.append(dict(board=board, n=selection["n"], seconds=round(time.perf_counter() - t0, 1)))

    default_size = opts.default_size if opts.default_size in boards else (78 if 78 in boards else boards[0])
    log("正在装配可交互图纸")
    out_dir = job_dir / "out"
    build_args = [
        "--process-dir", str(process),
        "--source", str(source),
        "--pixel-art", str(source),
        "--task-name", task_name,
        "--output", str(out_dir),
        "--sizes", *[str(b) for b in boards],
        "--default-size", str(default_size),
    ]
    old = __import__("sys").argv
    __import__("sys").argv = ["build_html_blueprint.py", *build_args]
    try:
        B.main()
    finally:
        __import__("sys").argv = old
    html = next(out_dir.glob("*.html"))
    # 统一改名：项目里用稳定的 id，玩家下载时用任务名
    final = job_dir / "blueprint.html"
    shutil.move(str(html), final)
    meta = dict(
        id=job_dir.name, task=task_name, created=datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S"),
        boards=boards, defaultSize=default_size, boards_summary=summaries,
        source=shrink(Image.open(source).convert("RGBA"), 240),
    )
    (job_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    shutil.rmtree(process, ignore_errors=True)
    return meta


def basis_name(board: int) -> str:
    return A.board_name(board)


def new_job_dir(jobs_root: Path | None = None) -> Path:
    root = jobs_root or JOBS
    root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(TZ).strftime("%Y%m%d-%H%M%S")
    d = root / f"{stamp}-{uuid.uuid4().hex[:6]}"
    d.mkdir(parents=True, exist_ok=True)
    return d
