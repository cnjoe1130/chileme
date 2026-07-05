#!/usr/bin/env python3
"""
吃了么 - 极简同步服务器（双备份版）
架构：桌面 data/ 为主数据，~/.nutrition-tracker/data/ 为隐藏备份
用户删了桌面的？AI帮你妙手回春 🌟

  GET  /data/2026-07-04.json  → 读当天数据（桌面优先，没有则从备份恢复）
  PUT  /data/2026-07-04.json  → 写当天数据（同时写桌面+备份）
  DELETE /data/2026-07-04.json → 删当天数据（两边都删）
  GET  /                     → 打开GUI
  POST /api/recover          → 从备份恢复所有数据到桌面
  GET  /api/backup/status    → 查看备份状态
"""
import json, os, shutil
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
BACKUP_DIR = Path.home() / ".nutrition-tracker" / "data"
DATA_DIR.mkdir(exist_ok=True)
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

# 首次启动：复制示例数据
import shutil as _shutil
_example_dir = Path(__file__).parent / "example-data"
if _example_dir.exists() and not any(DATA_DIR.glob("*.json")):
    for f in _example_dir.glob("*.json"):
        _shutil.copy2(f, DATA_DIR / f.name)
        _shutil.copy2(f, BACKUP_DIR / f.name)
    print(f"📦 已加载示例数据 ({len(list(_example_dir.glob('*.json')))} 天)")


def dual_write(date_str, data):
    """写入两处：桌面（主）+ 隐藏备份"""
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    # 桌面主数据
    primary = DATA_DIR / f"{date_str}.json"
    primary.write_text(payload, encoding="utf-8")
    # 隐藏备份
    backup = BACKUP_DIR / f"{date_str}.json"
    backup.write_text(payload, encoding="utf-8")


def dual_delete(date_str):
    """删除两处"""
    primary = DATA_DIR / f"{date_str}.json"
    backup = BACKUP_DIR / f"{date_str}.json"
    if primary.exists():
        primary.unlink()
    if backup.exists():
        backup.unlink()


def read_with_recovery(date_str):
    """读取：桌面优先，没有则从备份恢复"""
    primary = DATA_DIR / f"{date_str}.json"
    backup = BACKUP_DIR / f"{date_str}.json"

    if primary.exists():
        return json.loads(primary.read_text(encoding="utf-8"))

    if backup.exists():
        data = json.loads(backup.read_text(encoding="utf-8"))
        # 自动恢复到桌面
        primary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return data

    return {"meals": [], "weights": [], "profile": {}}


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        # 读取每日数据（带自动恢复）
        if self.path.startswith("/data/") and self.path.endswith(".json"):
            date_str = self.path[6:].replace(".json", "")
            data = read_with_recovery(date_str)
            self._json(200, data)
            return

        # 备份状态
        if self.path == "/api/backup/status":
            primary_files = sorted(DATA_DIR.glob("*.json"))
            backup_files = sorted(BACKUP_DIR.glob("*.json"))
            self._json(200, {
                "primary": {"count": len(primary_files),
                            "files": [f.name for f in primary_files]},
                "backup": {"count": len(backup_files),
                           "files": [f.name for f in backup_files],
                           "path": str(BACKUP_DIR)},
            })
            return

        # 静态文件
        if self.path == "/":
            self.path = "/nutrition-gui.html"
        super().do_GET()

    def do_PUT(self):
        if self.path.startswith("/data/") and self.path.endswith(".json"):
            date_str = self.path[6:].replace(".json", "")
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body)
            except Exception:
                self._json(400, {"error": "invalid json"})
                return
            dual_write(date_str, data)
            self._json(200, {"ok": True})
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        # 恢复所有备份到桌面
        if self.path == "/api/recover":
            recovered = []
            for f in BACKUP_DIR.glob("*.json"):
                target = DATA_DIR / f.name
                if not target.exists():
                    shutil.copy2(f, target)
                    recovered.append(f.name)
            self._json(200, {"recovered": recovered, "count": len(recovered)})
            return

        # PUT fallback
        if self.path.startswith("/data/") and self.path.endswith(".json"):
            self.do_PUT()
            return
        self.send_response(404)
        self.end_headers()

    def do_DELETE(self):
        if self.path.startswith("/data/") and self.path.endswith(".json"):
            date_str = self.path[6:].replace(".json", "")
            dual_delete(date_str)
            self._json(200, {"ok": True})
            return
        self.send_response(404)
        self.end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods",
                         "GET, PUT, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _json(self, code, obj):
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(obj, ensure_ascii=False).encode())

    def log_message(self, fmt, *args):
        pass


if __name__ == "__main__":
    import socket
    port = int(os.environ.get("PORT", 8080))
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        lan_ip = s.getsockname()[0]
        s.close()
    except Exception:
        lan_ip = "localhost"

    server = HTTPServer(("0.0.0.0", port), Handler)
    print(f"🍽️ 吃了么 server: http://localhost:{port}")
    print(f"📱 手机访问: http://{lan_ip}:{port}")
    print(f"📂 主数据: {DATA_DIR}/")
    print(f"🔒 备份: {BACKUP_DIR}/")
    print(f"🔄 双写模式：每次保存同时写入两处")
    server.serve_forever()
