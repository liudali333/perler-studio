"""从本机已安装的「无畏契约拼豆专家」技能里拷贝图纸算法与页面模板。

仓库不含 pipeline/ 与 templates/（两者来自拼豆专家技能包，不做二次分发）。
本机装了拼豆专家（WorkBuddy 专家市场）时运行：

    python setup_pipeline.py

脚本会在插件缓存里找 valorant-perler 技能，把需要的文件拷进来，
再打上本仓库的「换图重转」补丁（overlay/remake.js、overlay/remake.css）。
没找到技能时报错并打印找过的位置。
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCRIPTS = ["alignment_search.py", "build_html_blueprint.py", "palette_mard221.csv"]
PALETTES = ["palettes"]          # scripts/ 下的目录
TPL = "templates"                # 技能根目录下的模板目录（整包拷贝）


def candidates():
    home = Path.home()
    yield from [
        home / ".workbuddy" / "plugins" / "cache" / "experts" / "valorant-perler-expert",
        Path(r"C:\Users\Administrator\.workbuddy\plugins\cache\experts\valorant-perler-expert"),
    ]


def find_skill() -> Path | None:
    """返回技能根目录（其下有 scripts/ 与 templates/perler_blueprint/）。"""
    for base in candidates():
        if not base.is_dir():
            continue
        for ver in sorted(base.glob("*/skills/valorant-perler")):
            if all((ver / "scripts" / f).exists() for f in SCRIPTS) and (ver / TPL / "perler_blueprint" / "index.html").exists():
                return ver
    return None


def patch_index(idx: Path):
    """把「换图重转」的 include 注册进模板外壳（已存在则跳过）。"""
    s = idx.read_text(encoding="utf-8")
    if "remake.js" in s and "remake.css" in s:
        return
    s = s.replace("/* @include css/poster.css */",
                  "/* @include css/poster.css */\n/* @include css/remake.css */")
    s = s.replace("/* @include js/title.js */",
                  "/* @include js/title.js */\n/* @include js/remake.js */")
    idx.write_text(s, encoding="utf-8")
    print("补丁：模板已注册 remake 模块")


def main() -> int:
    src = find_skill()
    if src is None:
        print("没找到拼豆专家技能。请先在 WorkBuddy 专家中心安装「无畏契约拼豆专家」，再运行本脚本。")
        print("找过的位置：")
        for c in candidates():
            print(" -", c)
        return 1
    print("使用技能：", src)

    dst = ROOT / "pipeline"
    dst.mkdir(exist_ok=True)
    for f in SCRIPTS:
        shutil.copy2(src / "scripts" / f, dst / f)
        print("复制 scripts/" + f)
    for d in PALETTES:
        if (dst / d).exists():
            shutil.rmtree(dst / d)
        shutil.copytree(src / "scripts" / d, dst / d)
        print("复制 scripts/" + d + "/")

    tdst = ROOT / "templates"
    if tdst.exists():
        shutil.rmtree(tdst)
    shutil.copytree(src / TPL, tdst)
    print("复制 templates/（图纸页面模板）")

    overlay = ROOT / "overlay"
    if overlay.is_dir():
        shutil.copy2(overlay / "remake.js", tdst / "perler_blueprint" / "js" / "remake.js")
        shutil.copy2(overlay / "remake.css", tdst / "perler_blueprint" / "css" / "remake.css")
        patch_index(tdst / "perler_blueprint" / "index.html")
        print("打上「换图重转」补丁（overlay/）")

    print("安装完成 ✓  现在可以 python run.py 启动了")
    return 0


if __name__ == "__main__":
    sys.exit(main())
