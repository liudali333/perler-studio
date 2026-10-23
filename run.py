"""启动拼豆图纸工坊：python run.py [--port 8848]"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import uvicorn

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8848)
    ap.add_argument("--reload", action="store_true")
    a = ap.parse_args()
    uvicorn.run("perler.app:app", host=a.host, port=a.port, reload=a.reload)
