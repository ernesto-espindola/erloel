import sys
import os

_lib = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib")
if os.path.isdir(_lib) and _lib not in sys.path:
    sys.path.insert(0, _lib)

import time
import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from hdbcli import dbapi

_conn = None
_creds_info = {}
_conn_lock = threading.Lock()

_MINI_CHECKS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mini_checks")
_OUTPUT_DIR      = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")


class Handler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        print(fmt % args)

    def _send_json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html):
        body = html.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length)) if length else {}

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            self._send_html(HTML_PAGE)
        elif path == "/api/status":
            with _conn_lock:
                connected = _conn is not None
            self._send_json({"connected": connected, "info": _creds_info})
        elif path == "/api/list_outputs":
            files = []
            if os.path.isdir(_OUTPUT_DIR):
                for fname in sorted(os.listdir(_OUTPUT_DIR), reverse=True):
                    if fname.lower().endswith((".csv", ".txt")):
                        fpath = os.path.join(_OUTPUT_DIR, fname)
                        files.append({
                            "name": fname,
                            "size": os.path.getsize(fpath),
                            "modified": os.path.getmtime(fpath)
                        })
            self._send_json({"files": files})
        elif path == "/api/scripts":
            scripts = []
            if os.path.isdir(_MINI_CHECKS_DIR):
                for fname in sorted(os.listdir(_MINI_CHECKS_DIR)):
                    if fname.lower().endswith((".sql", ".txt")):
                        scripts.append(fname)
            self._send_json({"scripts": scripts})
        elif path.startswith("/output/"):
            fname = os.path.basename(path[8:])
            fpath = os.path.join(_OUTPUT_DIR, fname)
            if os.path.isfile(fpath):
                with open(fpath, "rb") as f:
                    body = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Disposition", f'attachment; filename="{fname}"')
                self.send_header("Content-Length", len(body))
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_response(404)
                self.end_headers()
        elif path == "/static/chart.umd.min.js":
            js_path = os.path.join(_lib, "chart.umd.min.js")
            try:
                with open(js_path, "rb") as f:
                    body = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "application/javascript")
                self.send_header("Content-Length", len(body))
                self.end_headers()
                self.wfile.write(body)
            except Exception:
                self.send_response(404)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        global _conn, _creds_info
        path = urlparse(self.path).path
        data = self._read_json()

        if path == "/api/connect":
            host     = data.get("host", "").strip()
            database = data.get("database", "HP4").strip()
            user     = data.get("user", "").strip()
            password = data.get("password", "")
            try:
                port = int(data.get("port", 30241))
            except ValueError:
                return self._send_json({"ok": False, "error": "Port must be a number."})
            if not user or not password:
                return self._send_json({"ok": False, "error": "User and password are required."})
            try:
                conn = dbapi.connect(address=host, port=port, user=user, password=password)
                with _conn_lock:
                    if _conn is not None:
                        try: _conn.close()
                        except Exception: pass
                    _conn = conn
                    _creds_info = {"host": host, "port": port, "database": database, "user": user}
                self._send_json({"ok": True, "info": _creds_info})
            except Exception as exc:
                self._send_json({"ok": False, "error": str(exc)[:300]})

        elif path == "/api/execute":
            with _conn_lock:
                conn = _conn
            if conn is None:
                return self._send_json({"ok": False, "error": "Not connected."})
            sql = data.get("sql", "").strip()
            sql_lines = [ln for ln in sql.splitlines() if not ln.strip().startswith("--")]
            sql = "\n".join(sql_lines).strip().rstrip(";").strip()
            if not sql:
                return self._send_json({"ok": False, "error": "No SQL to execute."})
            start = time.monotonic()
            try:
                cursor = conn.cursor()
                cursor.execute(sql)
                elapsed = round(time.monotonic() - start, 4)
                if cursor.description:
                    columns = [d[0] for d in cursor.description]
                    rows = cursor.fetchmany(5000)
                    capped = cursor.fetchone() is not None
                    safe_rows = [
                        ["" if v is None else str(v)[:300] for v in row]
                        for row in rows
                    ]
                    cursor.close()
                    self._send_json({"ok": True, "type": "rows", "columns": columns,
                                     "rows": safe_rows, "elapsed": elapsed, "capped": capped})
                else:
                    rowcount = cursor.rowcount
                    cursor.close()
                    self._send_json({"ok": True, "type": "rowcount",
                                     "rowcount": rowcount, "elapsed": elapsed})
            except Exception as exc:
                elapsed = round(time.monotonic() - start, 4)
                self._send_json({"ok": False, "error": str(exc), "elapsed": elapsed})

        elif path == "/api/load_script":
            fname = os.path.basename(data.get("filename", ""))
            fpath = os.path.join(_MINI_CHECKS_DIR, fname)
            if not os.path.isfile(fpath):
                return self._send_json({"ok": False, "error": "File not found."})
            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                self._send_json({"ok": True, "filename": fname, "content": content})
            except Exception as exc:
                self._send_json({"ok": False, "error": str(exc)})

        elif path == "/api/save_output":
            fname = os.path.basename(data.get("filename", "output.csv"))
            content = data.get("content", "")
            try:
                os.makedirs(_OUTPUT_DIR, exist_ok=True)
                fpath = os.path.join(_OUTPUT_DIR, fname)
                with open(fpath, "w", encoding="utf-8") as f:
                    f.write(content)
                self._send_json({"ok": True, "filename": fname})
            except Exception as exc:
                self._send_json({"ok": False, "error": str(exc)})

        elif path == "/api/consolidate":
            filenames = data.get("files", [])
            if not filenames:
                return self._send_json({"ok": False, "error": "No files selected."})
            from datetime import datetime
            date_str = datetime.now().strftime("%Y%m%d")
            out_name = f"Consolidated_minichecks_review_{date_str}.txt"
            out_path = os.path.join(_OUTPUT_DIR, out_name)
            try:
                os.makedirs(_OUTPUT_DIR, exist_ok=True)
                with open(out_path, "w", encoding="utf-8") as out_f:
                    out_f.write(f"SAP HANA SQL Console - Consolidated Mini Checks Review\n")
                    out_f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    out_f.write(f"Files included: {len(filenames)}\n")
                    out_f.write("=" * 80 + "\n\n")
                    for fname in filenames:
                        fname = os.path.basename(fname)
                        fpath = os.path.join(_OUTPUT_DIR, fname)
                        if not os.path.isfile(fpath):
                            continue
                        out_f.write(f"{'=' * 80}\n")
                        out_f.write(f"FILE: {fname}\n")
                        out_f.write(f"{'=' * 80}\n")
                        with open(fpath, "r", encoding="utf-8", errors="replace") as in_f:
                            out_f.write(in_f.read())
                        out_f.write("\n\n")
                self._send_json({"ok": True, "filename": out_name})
            except Exception as exc:
                self._send_json({"ok": False, "error": str(exc)})

        elif path == "/api/disconnect":
            with _conn_lock:
                if _conn is not None:
                    try: _conn.close()
                    except Exception: pass
                    _conn = None
                    _creds_info = {}
            self._send_json({"ok": True})

        else:
            self.send_response(404)
            self.end_headers()


HTML_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>SAP HANA SQL Console v2</title>
<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
:root {
  --bg:      #f0f2f5;
  --surf:    #ffffff;
  --surf2:   #f5f7fa;
  --border:  #d1d5db;
  --accent:  #0070d2;
  --success: #22c55e;
  --error:   #dc3545;
  --warn:    #f59e0b;
  --text:    #1e293b;
  --muted:   #64748b;
  --hdr:     48px;
  --stbar:   28px;
  --scripts-w: 280px;
}
html, body { height: 100%; background: var(--bg); color: var(--text);
  font-family: 'Segoe UI', system-ui, sans-serif; font-size: 14px; }

/* ── Header ── */
#header {
  height: var(--hdr); position: fixed; top: 0; left: 0; right: 0; z-index: 100;
  background: linear-gradient(90deg, #162b4a, #1e3a5f);
  border-bottom: 1px solid #0d1f35;
  display: flex; align-items: center; padding: 0 16px; gap: 12px;
}
.logo { font-weight: 700; font-size: 15px; color: #ffffff; letter-spacing: .5px; }
.logo span { color: #b0c8e8; }
.logo small { font-size: 10px; color: #7a9ab8; font-weight: 400; margin-left: 4px; }
#conn-badge { margin-left: auto; display: flex; align-items: center; gap: 8px;
  font-size: 12px; color: #b0c4d8; }
#conn-dot { width: 8px; height: 8px; border-radius: 50%; background: #7a9ab8;
  flex-shrink: 0; transition: background .3s; }
#conn-dot.on  { background: var(--success); box-shadow: 0 0 6px var(--success); }
#conn-dot.off { background: var(--error); }
#btn-disconnect { padding: 3px 10px; border-radius: 4px; border: 1px solid rgba(255,255,255,.25);
  background: transparent; color: #b0c4d8; cursor: pointer; font-size: 12px; display: none; }
#btn-disconnect:hover { border-color: var(--error); color: #ffaaaa; }

/* ── Layout ── */
#app { position: fixed; top: var(--hdr); bottom: var(--stbar); left: 0; right: 0; display: flex; }

/* ── Scripts sidebar ── */
#scripts-pane {
  width: var(--scripts-w); flex-shrink: 0;
  display: none; flex-direction: column;
  border-right: 1px solid var(--border);
  background: var(--surf);
}
#scripts-pane.visible { display: flex; }
#scripts-header {
  height: 38px; flex-shrink: 0; background: var(--surf2);
  border-bottom: 1px solid var(--border);
  display: flex; align-items: center; padding: 0 12px; gap: 8px;
}
#scripts-header .tb-label { font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: .5px; }
#scripts-header .badge { margin-left: auto; font-size: 10px; background: var(--accent);
  color: #fff; padding: 1px 6px; border-radius: 10px; }
#scripts-filter {
  margin: 8px 10px 6px; padding: 5px 8px;
  background: var(--surf); border: 1px solid var(--border);
  border-radius: 4px; color: var(--text); font-size: 12px; outline: none;
  width: calc(100% - 20px);
}
#scripts-filter:focus { border-color: var(--accent); }
#scripts-list { flex: 1; overflow-y: auto; scrollbar-width: thin; scrollbar-color: var(--border) transparent; padding: 4px 0 8px; }
#scripts-list::-webkit-scrollbar { width: 5px; }
#scripts-list::-webkit-scrollbar-thumb { background: var(--border); }
.script-item { display: flex; align-items: flex-start; gap: 8px; padding: 7px 12px; cursor: pointer;
  border-left: 3px solid transparent; transition: background .12s; }
.script-item:hover { background: rgba(0,112,210,.07); }
.script-item.selected { background: rgba(0,112,210,.1); border-left-color: var(--accent); }
.script-item input[type=radio] { margin-top: 2px; flex-shrink: 0; accent-color: var(--accent); cursor: pointer; }
.script-name { font-size: 12px; color: var(--text); line-height: 1.4; word-break: break-word; }
.script-name em { font-style: normal; color: var(--muted); font-size: 11px; display: block; margin-top: 1px; }
#scripts-run-bar { padding: 8px 10px; border-top: 1px solid var(--border); background: var(--surf2); }
#btn-load-script { width: 100%; padding: 7px; border-radius: 5px; border: none;
  background: var(--accent); color: #fff; font-size: 13px; font-weight: 500;
  cursor: pointer; transition: filter .15s; }
#btn-load-script:hover:not(:disabled) { filter: brightness(1.1); }
#btn-load-script:disabled { opacity: .4; cursor: not-allowed; }

/* ── Mini Checks toggle button ── */
#btn-scripts-toggle {
  padding: 4px 10px; border-radius: 5px; border: 1px solid rgba(255,255,255,.25);
  background: rgba(255,255,255,.1); color: #c8daf0; cursor: pointer;
  font-size: 12px; display: none; gap: 5px; align-items: center;
}
#btn-scripts-toggle.active { border-color: #7ab8f5; color: #7ab8f5; background: rgba(122,184,245,.15); }
#btn-scripts-toggle:hover { filter: brightness(1.15); }

#left-pane  { width: 36%; min-width: 260px; display: flex; flex-direction: column;
  border-right: 1px solid var(--border); }
#right-pane { flex: 1; display: flex; flex-direction: column; overflow: hidden; }

/* ── Tabs ── */
#tab-bar { height: 38px; background: var(--surf); border-bottom: 1px solid var(--border);
  display: flex; align-items: stretch; flex-shrink: 0; }
.tab { padding: 0 18px; display: flex; align-items: center; gap: 6px; cursor: pointer;
  font-size: 12px; color: var(--muted); border-bottom: 2px solid transparent;
  transition: color .15s; user-select: none; }
.tab:hover { color: var(--text); }
.tab.active { color: var(--accent); border-bottom-color: var(--accent); }
.tab-panel { display: none; flex: 1; flex-direction: column; overflow: hidden; }
.tab-panel.active { display: flex; }

/* ── Toolbars ── */
.toolbar { height: 38px; flex-shrink: 0; background: var(--surf);
  border-bottom: 1px solid var(--border);
  display: flex; align-items: center; padding: 0 10px; gap: 8px; }
.tb-label { font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: .5px; }
.tb-sep   { width: 1px; height: 18px; background: var(--border); flex-shrink: 0; }
#result-stat { font-size: 12px; color: var(--muted); margin-left: auto; }

/* ── Buttons ── */
.btn { display: inline-flex; align-items: center; gap: 5px; padding: 4px 12px;
  border-radius: 5px; border: none; cursor: pointer; font-size: 13px; font-weight: 500;
  transition: filter .15s; white-space: nowrap; }
.btn:hover   { filter: brightness(1.1); }
.btn:active  { filter: brightness(.92); }
.btn-primary { background: var(--accent); color: #fff; }
.btn-success { background: #16a34a; color: #fff; }
.btn-ghost   { background: var(--surf); color: var(--text); border: 1px solid var(--border); }
.btn:disabled { opacity: .4; cursor: not-allowed; filter: none; }
kbd { font-size: 10px; background: rgba(0,0,0,.08); border-radius: 3px; padding: 1px 5px; }

/* ── Editor ── */
#editor-wrap { flex: 1; overflow: hidden; display: flex; flex-direction: column; }
#sql-editor {
  flex: 1; width: 100%; height: 100%; resize: none; border: none; outline: none;
  background: #0d1b2e; color: #e2eaf5;
  font-family: 'Cascadia Code','Fira Code','Consolas',monospace;
  font-size: 13px; line-height: 1.6; padding: 10px 12px; tab-size: 2;
}

/* ── Table ── */
#table-wrap { flex: 1; overflow: auto; background: var(--bg);
  scrollbar-width: thin; scrollbar-color: var(--border) transparent; }
#table-wrap::-webkit-scrollbar { width: 6px; height: 6px; }
#table-wrap::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
#result-table { width: 100%; border-collapse: collapse; font-size: 12.5px; }
#result-table thead { position: sticky; top: 0; z-index: 5; }
#result-table th { background: var(--surf2); color: var(--text); padding: 7px 12px;
  text-align: left; font-weight: 600; border-bottom: 2px solid var(--border);
  white-space: nowrap; cursor: pointer; user-select: none; }
#result-table th:hover { background: #e8edf5; }
#result-table th .si { color: var(--muted); margin-left: 4px; font-size: 10px; }
#result-table td { padding: 5px 12px; border-bottom: 1px solid var(--border);
  max-width: 400px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  color: var(--text); }
#result-table tr:nth-child(even) td { background: rgba(0,0,0,.018); }
#result-table tr:hover td { background: rgba(0,112,210,.06); }
#result-table td.num { text-align: right; color: var(--accent); font-family: monospace; }
#result-table td.nul { color: var(--muted); font-style: italic; }

/* ── Chart panel ── */
#chart-panel { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
#chart-config { flex-shrink: 0; background: var(--surf); border-bottom: 1px solid var(--border);
  padding: 8px 12px; display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
#chart-config label { font-size: 11px; color: var(--muted); }
#chart-config select, #chart-config input[type=color] {
  background: var(--surf2); color: var(--text); border: 1px solid var(--border);
  border-radius: 4px; padding: 3px 7px; font-size: 12px; outline: none; cursor: pointer; }
#chart-config select:focus { border-color: var(--accent); }
#chart-title-input { background: var(--surf2); color: var(--text); border: 1px solid var(--border);
  border-radius: 4px; padding: 3px 8px; font-size: 12px; outline: none; width: 180px; }
#chart-title-input:focus { border-color: var(--accent); }
#chart-canvas-wrap { flex: 1; position: relative; padding: 16px; overflow: hidden;
  background: var(--surf); }
canvas#myChart { max-height: 100%; }
#chart-placeholder { display: flex; flex-direction: column; align-items: center;
  justify-content: center; height: 100%; color: var(--muted); gap: 10px; font-size: 13px; }
#chart-placeholder svg { opacity: .25; }

/* ── Log ── */
#log-wrap { height: 110px; flex-shrink: 0; border-top: 1px solid var(--border);
  overflow-y: auto; background: #0d1b2e; padding: 6px 12px;
  font-family: 'Cascadia Code','Consolas',monospace; font-size: 12px;
  scrollbar-width: thin; scrollbar-color: #2a4060 transparent; }
#log-wrap::-webkit-scrollbar { width: 5px; }
#log-wrap::-webkit-scrollbar-thumb { background: #2a4060; }
.log-ok   { color: var(--success); }
.log-err  { color: #ff6b6b; }
.log-warn { color: var(--warn); }
.log-info { color: #8ab0d0; }
.log-entry { margin-bottom: 2px; line-height: 1.5; }

/* ── Status bar ── */
#status-bar { position: fixed; bottom: 0; left: 0; right: 0; height: var(--stbar);
  background: linear-gradient(90deg, #162b4a, #1e3a5f);
  border-top: 1px solid #0d1f35;
  display: flex; align-items: center; padding: 0 14px; gap: 18px;
  font-size: 11.5px; color: #8aaac8; }
.seg-val { color: #daeaf8; }
#st-last { margin-left: auto; display: none; }

/* ── Placeholder ── */
#table-ph { display: flex; flex-direction: column; align-items: center;
  justify-content: center; height: 100%; color: var(--muted); gap: 10px; font-size: 13px; }
#table-ph svg { opacity: .25; }

/* ── Login modal ── */
#modal-overlay { position: fixed; inset: 0; background: rgba(15,30,55,.6);
  display: flex; align-items: center; justify-content: center;
  z-index: 200; backdrop-filter: blur(4px); }
#modal-box { background: var(--surf); border: 1px solid var(--border);
  border-radius: 10px; padding: 28px 32px; width: 430px;
  box-shadow: 0 16px 48px rgba(0,0,0,.18); }
#modal-box h2 { text-align: center; font-size: 17px; color: var(--accent);
  margin-bottom: 22px; letter-spacing: .3px; }
.field { margin-bottom: 14px; }
.field label { display: block; font-size: 12px; color: var(--muted); margin-bottom: 5px; }
.field input { width: 100%; padding: 8px 10px; border-radius: 5px;
  border: 1px solid var(--border); background: var(--surf2);
  color: var(--text); font-size: 13px; outline: none; transition: border-color .15s; }
.field input:focus { border-color: var(--accent); }
.field-row { display: flex; gap: 12px; }
.field-row .field { flex: 1; }
#modal-error { color: var(--error); font-size: 12px; min-height: 18px;
  text-align: center; margin-bottom: 8px; }
#modal-actions { display: flex; gap: 10px; }
#modal-actions .btn { flex: 1; justify-content: center; padding: 9px; font-size: 14px; }
#modal-spinner { text-align: center; color: var(--muted); font-size: 12px;
  margin-top: 10px; display: none; }

/* ── Toast ── */
#toast { position: fixed; bottom: 40px; right: 20px; z-index: 300;
  background: var(--text); border: 1px solid transparent;
  color: #fff; padding: 7px 16px; border-radius: 6px;
  font-size: 12px; opacity: 0; transition: opacity .2s; pointer-events: none; }
#toast.show { opacity: 1; }

@keyframes spin { to { transform: rotate(360deg); } }
.spin { display: inline-block; animation: spin .75s linear infinite; }

/* ── About modal ── */
#about-overlay { position: fixed; inset: 0; background: rgba(15,30,55,.6);
  display: none; align-items: center; justify-content: center;
  z-index: 300; backdrop-filter: blur(4px); }
#about-overlay.show { display: flex; }
#about-box { background: var(--surf); border: 1px solid var(--border);
  border-radius: 10px; padding: 32px 36px; width: 380px; text-align: center;
  box-shadow: 0 16px 48px rgba(0,0,0,.18); }
#about-box .about-logo { font-size: 20px; font-weight: 700; color: var(--accent); margin-bottom: 4px; }
#about-box .about-logo span { color: var(--text); }
#about-box .about-version { font-size: 13px; color: var(--muted); margin-bottom: 20px; }
#about-box hr { border: none; border-top: 1px solid var(--border); margin: 16px 0; }
#about-box .about-row { display: flex; justify-content: space-between;
  font-size: 13px; padding: 4px 0; }
#about-box .about-row .lbl { color: var(--muted); }
#about-box .about-row .val { color: var(--text); font-weight: 500; }
#about-box .about-close { margin-top: 24px; padding: 7px 28px; border-radius: 5px;
  border: 1px solid var(--border); background: var(--surf2); color: var(--text);
  cursor: pointer; font-size: 13px; }
#about-box .about-close:hover { border-color: var(--accent); color: var(--accent); }
#btn-about { padding: 4px 10px; border-radius: 5px; border: 1px solid rgba(255,255,255,.25);
  background: rgba(255,255,255,.1); color: #c8daf0; cursor: pointer; font-size: 12px; }
#btn-about:hover { filter: brightness(1.15); }

/* -- Consolidate modal -- */
#consolidate-overlay { position: fixed; inset: 0; background: rgba(15,30,55,.6);
  display: none; align-items: center; justify-content: center;
  z-index: 300; backdrop-filter: blur(4px); }
#consolidate-overlay.show { display: flex; }
#consolidate-box { background: var(--surf); border: 1px solid var(--border);
  border-radius: 10px; padding: 28px 32px; width: 520px;
  box-shadow: 0 16px 48px rgba(0,0,0,.18); display: flex; flex-direction: column; gap: 14px; }
#consolidate-box h2 { font-size: 15px; color: var(--accent); text-align: center; }
#consolidate-box .con-desc { font-size: 12px; color: var(--muted); text-align: center; }
#output-list { max-height: 280px; overflow-y: auto; border: 1px solid var(--border);
  border-radius: 5px; background: var(--bg);
  scrollbar-width: thin; scrollbar-color: var(--border) transparent; }
.output-item { display: flex; align-items: center; gap: 10px; padding: 7px 12px;
  border-bottom: 1px solid var(--border); cursor: pointer; }
.output-item:last-child { border-bottom: none; }
.output-item:hover { background: rgba(0,112,210,.06); }
.output-item input[type=checkbox] { accent-color: var(--accent); flex-shrink: 0; cursor: pointer; }
.output-item .out-name { font-size: 12px; color: var(--text); flex: 1; }
.output-item .out-size { font-size: 11px; color: var(--muted); }
#con-actions { display: flex; gap: 10px; }
#con-actions .btn { flex: 1; justify-content: center; padding: 8px; font-size: 13px; }
#con-sel-all { font-size: 11px; color: var(--accent); cursor: pointer; background: none;
  border: none; padding: 0; }
#con-sel-all:hover { text-decoration: underline; }
#con-status { font-size: 12px; color: var(--muted); text-align: center; min-height: 16px; }
</style>
</head>
<body>

<!-- Header -->
<div id="header">
  <div class="logo">SAP HANA <span>SQL Console</span> <small>v4.0</small></div>
  <button id="btn-scripts-toggle" onclick="toggleScriptsPane()" title="Toggle Mini Checks">
    &#9776; Mini Checks
  </button>
  <button id="btn-about" onclick="showAbout()">&#9432; About</button>
  <button id="btn-consolidate" onclick="showConsolidate()"
    style="padding:4px 10px;border-radius:5px;border:1px solid var(--border);background:var(--surf2);color:var(--muted);cursor:pointer;font-size:12px;display:none;">
    &#128196; Consolidate
  </button>
  <div id="conn-badge">
    <div id="conn-dot" class="off"></div>
    <span id="conn-label">Not connected</span>
    <button id="btn-disconnect" onclick="doDisconnect()">Disconnect</button>
  </div>
</div>

<div id="app">

  <!-- Scripts sidebar -->
  <div id="scripts-pane">
    <div id="scripts-header">
      <span class="tb-label">Mini Checks</span>
      <span class="badge" id="scripts-count">0</span>
    </div>
    <input id="scripts-filter" type="text" placeholder="&#128269; Filter scripts…" oninput="filterScripts()" autocomplete="off"/>
    <div id="scripts-list"></div>
    <div id="scripts-run-bar">
      <button id="btn-load-script" disabled onclick="loadSelectedScript()">&#11123; Load into Editor</button>
    </div>
  </div>

  <!-- Left: SQL editor -->
  <div id="left-pane">
    <div class="toolbar">
      <span class="tb-label">SQL Editor</span>
      <div class="tb-sep"></div>
      <button class="btn btn-primary" id="btn-run" onclick="runQuery()" disabled>
        &#9654; Run <kbd>F5</kbd>
      </button>
      <button class="btn btn-ghost" onclick="clearEditor()">Clear</button>
      <button class="btn btn-ghost" onclick="copySQL()" title="Copy SQL">&#10064;</button>
    </div>
    <div id="editor-wrap">
      <textarea id="sql-editor">	SELECT
/* 

[NAME]

- HANA_Configuration_Overview_2.00.040+

[DESCRIPTION]

- General information

[DETAILS AND RESTRICTIONS]

- WORKLOAD_CLASSES and WORKLOAD_MAPPINGS only available as of Revision 1.00.100
- M_RESULT_CACHE only available as of Rev. 1.00.110
- STATEMENT_HINTS available as of Rev. 1.00.122.02
- M_ENCRYPTION_OVERVIEW available starting with 2.00.000
- M_DYNAMIC_RESULT_CACHE available starting with 2.00.020
- M_MULTIDIMENSIONAL_STATEMENT_STATISTICS available with SAP HANA >= 2.00.024.01
- M_CS_TABLES.PERSISTENT_MEMORY and M_PERSISTENT_MEMORY_VOLUMES available with SAP HANA >= 2.00.030
- TABLES.LOAD_UNIT (NSE) available with SAP HANA >= 2.00.040

[SOURCE]

- SAP Note 1969700

[VALID FOR]

- Revisions:              >= 2.00.040

[SQL COMMAND VERSION]

- 2014/03/31:  1.0 (initial version)
- 2014/05/30:  1.1 (moved parts to other commands like HANA_Configuration_MiniChecks or HANA_Hosts*)
- 2014/09/05:  1.2 (several feature checks added)
- 2014/09/27:  1.3 (SAP_NOTES added)
- 2015/05/20:  1.4 (dedicated Rev90+ version created)
- 2016/02/19:  1.5 (dedicated Rev100+ version created)
- 2016/06/29:  1.6 (dedicated Rev110+ version created)
- 2017/04/04:  1.7 (dedicated 1.00.122.02+ version created)
- 2017/07/20:  1.8 (dedicated 2.00.020+ version created)
- 2018/04/09:  1.9 (M_ENCRYPTION_OVERVIEW considered)
- 2018/11/03:  2.0 (dedicated 2.00.024.01+ version)
- 2018/12/01:  2.1 (section "INSTALLED PRODUCTS:" added)
- 2019/03/16:  2.2 (dedicated 2.00.030+ version)
- 2019/07/02:  2.3 (dedicated 2.00.040+ version)
- 2019/11/03:  2.4 (ABAP kernel version added)
- 2020/05/05:  2.5 (fuzzy search indexes added)
- 2020/05/06:  2.6 (data volume partitioning added)
- 2021/05/10:  2.7 (extension node added)
- 2022/08/17:  2.8 (data statistics added)

[INVOLVED TABLES]

- various

[INPUT PARAMETERS]

[OUTPUT PARAMETERS]

- NAME:     Name of information and check
- VALUE:    Related value
- SAP_NOTE: Related SAP Note number

[EXAMPLE OUTPUT]

----------------------------------------------------------------------------------------------------------------------------
|NAME                                     |VALUE                                        |SAP_NOTE                          |
----------------------------------------------------------------------------------------------------------------------------
|GENERAL INFORMATION:                     |                                             |                                  |
|                                         |                                             |                                  |
|Database type                            |SAP HANA                                     |2000003                           |
|Evaluation time                          |2014/09/27 12:18:27                          |                                  |
|Evaluation user                          |SAPPRD                                       |                                  |
|OS user                                  |prdadm (80384) (8 hosts)                     |                                  |
|SAP database users                       |SAPHANA01                                    |                                  |
|                                         |SAPPRD                                       |                                  |
|SAP database schemas                     |SAPHANA01                                    |                                  |
|                                         |SAPPRD                                       |                                  |
|                                         |SAP_HANA_ADMIN                               |                                  |
|                                         |SAP_XS_LM                                    |                                  |
|Startup time                             |2014/09/13 13:00:14                          |                                  |
|                                         |2014/09/13 13:00:25 (saphana0032)            |                                  |
|                                         |2014/09/13 13:00:16 (saphana0033)            |                                  |
|                                         |2014/09/13 13:00:15 (saphana0034)            |                                  |
|                                         |2014/09/13 13:00:15 (saphana0035)            |                                  |
|                                         |2014/09/13 13:00:15 (saphana0041)            |                                  |
|                                         |2014/09/13 13:00:14 (saphana0042)            |                                  |
|                                         |2014/09/13 13:00:14 (saphana0043)            |                                  |
|                                         |2014/09/13 13:00:14 (saphana0044)            |                                  |
|Database name                            |P06                                          |                                  |
|Instance name                            |P06                                          |                                  |
|Instance number                          |00                                           |                                  |
|Distributed system                       |yes (8 hosts)                                |                                  |
|Everything started                       |yes                                          |                                  |
|Version                                  |1.00.74.02.392316 (NewDB100_REL)             |                                  |
|Support package stack                    |SPS 07                                       |                                  |
|Number of hosts                          |8                                            |                                  |
|Host role                                |MASTER   (saphana0032)                       |                                  |
|                                         |SLAVE    (saphana0033)                       |                                  |
|                                         |SLAVE    (saphana0034)                       |                                  |
|                                         |SLAVE    (saphana0041)                       |                                  |
|                                         |SLAVE    (saphana0042)                       |                                  |
|                                         |SLAVE    (saphana0043)                       |                                  |
|                                         |SLAVE    (saphana0044)                       |                                  |
|                                         |STANDBY  (saphana0035)                       |                                  |
|Host directory                           |/usr/sap/P06/HDB00/saphana0032/ (saphana0032)|                                  |
|                                         |/usr/sap/P06/HDB00/saphana0033/ (saphana0033)|                                  |
|                                         |/usr/sap/P06/HDB00/saphana0034/ (saphana0034)|                                  |
|                                         |/usr/sap/P06/HDB00/saphana0035/ (saphana0035)|                                  |
|                                         |/usr/sap/P06/HDB00/saphana0041/ (saphana0041)|                                  |
|                                         |/usr/sap/P06/HDB00/saphana0042/ (saphana0042)|                                  |
|                                         |/usr/sap/P06/HDB00/saphana0043/ (saphana0043)|                                  |
|                                         |/usr/sap/P06/HDB00/saphana0044/ (saphana0044)|                                  |
|Timezone                                 |CEST (8 hosts)                               |                                  |
|                                         |                                             |                                  |
|PATCH HISTORY:                           |                                             |                                  |
|                                         |                                             |                                  |
|2014/08/09 11:33:12                      |1.00.74.02.392316                            |                                  |
|2014/03/15 09:11:31                      |1.00.72.00.388670                            |                                  |
|2014/02/15 12:58:30                      |1.00.69.385196                               |                                  |
|                                         |                                             |                                  |
|FEATURE AND CONFIGURATION INFORMATION:   |                                             |                                  |
|                                         |                                             |                                  |
|Database log mode                        |normal      (default)                        |1642148                           |
|Automatic log backup                     |yes         (default)                        |1642148                           |
|Query result cache                       |no          (default)                        |2014148                           |
|Global auditing state                    |false       (default)                        |1991634                           |
|Self-signed certificates                 |false       (default)                        |1891055                           |
|Hostname resolution for default route    |ip          (default)                        |1906381                           |
|Mountpoint usage for data and log volumes|yes         (default)                        |1809453, 1820553                  |
|Client distribution mode                 |statement   (default)                        |1743225, 1745057, 1774187, 1785171|
|Parallel mode                            |Auto        (default)                        |2036111                           |
|Parallelism of table preload             |5           (default)                        |2036111                           |
|Table preload during startup             |true        (default)                        |1889081                           |
|Embedded statistics server active        |false       (default)                        |1917938                           |
|Standalone statistics server active      |true        (default)                        |2036111                           |
|Listen interface                         |.global                                      |1999797                           |
|                                         |                                             |                                  |
|SPACE INFORMATION:                       |                                             |                                  |
|                                         |                                             |                                  |
|Database size on disk (GB)               |      1746.19                                |                                  |
|Data backup size (GB)                    |      1726.41                                |                                  |
|Row store size total (GB)                |       212.10 (saphana0032)                  |                                  |
|Column store size total (GB)             |      1213.39                                |                                  |
|Row store tables                         |      2488 (SAP schema:   2246)              |                                  |
|Column store tables                      |     70566 (SAP schema:  70400)              |                                  |
----------------------------------------------------------------------------------------------------------------------------

*/

  NAME,
  VALUE,
  SAP_NOTE
FROM
( SELECT
    100 LINE_NO,
    'GENERAL INFORMATION:' NAME,
    ' ' VALUE,
    ' ' SAP_NOTE
  FROM
    DUMMY
  UNION ALL
  SELECT
    190,
    ' ',
    ' ',
    ' '
  FROM
    DUMMY
  UNION ALL
  SELECT TOP 1
    192,
    'Attention:',
    'Connected to secondary system replication site!',
    '1999880'
  FROM
    M_CONFIGURATION_PARAMETER_VALUES
  WHERE
    SECTION = 'system_replication' AND
    KEY = 'actual_mode' AND
    VALUE != 'primary'
  UNION ALL
  SELECT TOP 1
    193,
    '',
    '',
    ''
  FROM
    M_CONFIGURATION_PARAMETER_VALUES
  WHERE
    SECTION = 'system_replication' AND
    KEY = 'actual_mode' AND
    VALUE != 'primary'
  UNION ALL
  SELECT
    200,
    'Database type',
    'SAP HANA',
    '2000003'
  FROM
    DUMMY
  UNION ALL
  SELECT
    250,
    'Version',
    SUBSTR(VALUE, 1, 3),
    '2115815'
  FROM
    M_SYSTEM_OVERVIEW
  WHERE
    SECTION = 'System' AND
    NAME = 'Version'
  UNION ALL
  SELECT
    300,
    'Support package stack',
    'SPS' || CHAR(32) || LPAD(CASE
      WHEN VERSION LIKE '1%' AND REVISION BETWEEN  45 AND  59 THEN 5
      WHEN VERSION LIKE '1%' AND REVISION BETWEEN  28 AND  44 THEN 4
      WHEN VERSION LIKE '1%' AND REVISION BETWEEN  20 AND  27 THEN 3
      WHEN VERSION LIKE '1%' AND REVISION BETWEEN  12 AND  19 THEN 2
      WHEN VERSION LIKE '1%' AND REVISION BETWEEN   1 AND  11 THEN 1
      ELSE FLOOR(REVISION / 10)
    END, 2, '0'),
    '2115815'
  FROM
  ( SELECT
      SUBSTR(VALUE, 1, 4) VERSION,
      SUBSTR(VALUE, LOCATE(VALUE, '.', 1, 2) + 1, LOCATE(VALUE, '.', 1, 3) - LOCATE(VALUE, '.', 1, 2) - 1) REVISION 
    FROM 
      M_SYSTEM_OVERVIEW 
    WHERE 
      SECTION = 'System' AND 
      NAME = 'Version' 
   )
  UNION ALL
  SELECT
    400,
    'Revision',
    VALUE,
    '2115815'
  FROM
    M_SYSTEM_OVERVIEW
  WHERE
    SECTION = 'System' AND
    NAME = 'Version'
  UNION ALL
  SELECT
    450 + ROWNO,
    MAP(ROWNO, 1, 'ABAP kernel version (DBSL)', ''),
    ABAP_KERNEL || CHAR(32) || '(' || NUM_CONNECTIONS || CHAR(32) || 'connection' || MAP(NUM_CONNECTIONS, 1, '', 's') || ')',
    '19466'
  FROM
  ( SELECT
      VALUE ABAP_KERNEL,
      COUNT(*) NUM_CONNECTIONS,
      ROW_NUMBER () OVER (ORDER BY VALUE) ROWNO
    FROM
      M_SESSION_CONTEXT
    WHERE
      KEY = 'APPLICATIONVERSION' AND
      VALUE LIKE '___ PL %'
    GROUP BY
      VALUE
  )
  UNION ALL
  SELECT
    500,
    'System ID',
    SYSTEM_ID,
    ''
  FROM
    M_DATABASE
  UNION ALL
  SELECT
    600,
    'Database name',
    DATABASE_NAME,
    ' '
  FROM
    M_DATABASE
  UNION ALL
  SELECT
    700,
    'Instance number',
    VALUE,
    ' '
  FROM
    M_SYSTEM_OVERVIEW
  WHERE
    SECTION = 'System' AND
    NAME = 'Instance Number'
  UNION ALL
  SELECT
    750,
    'System usage',
    USAGE,
    ' '
  FROM
    M_DATABASE
  UNION ALL
  SELECT TOP 1
    760,
    'License usage',
    VALUE,
    '2779499'
  FROM
    M_CONFIGURATION_PARAMETER_VALUES
  WHERE
    FILE_NAME = 'global.ini' AND
    KEY = 'license_usage'
  UNION ALL
  SELECT
    800,
    'Evaluation time',
    TO_VARCHAR(CURRENT_TIMESTAMP, 'YYYY/MM/DD HH24:MI:SS'),
    ' '
  FROM
    DUMMY
  UNION ALL
  SELECT
    900,
    'Evaluation user',
    CURRENT_USER,
    ' '
  FROM
    DUMMY
  UNION ALL
  SELECT
    1000 + ROW_NUMBER () OVER (ORDER BY VALUE),
    'OS user',
    VALUE || ' (' || COUNT(*) || ' host' || CASE WHEN COUNT(*) = 1 THEN '' ELSE 's' END || ')',
    ' '
  FROM
    M_HOST_INFORMATION
  WHERE
    KEY = 'os_user'
  GROUP BY
    VALUE
  UNION ALL
  SELECT
    1100 + ROW_NUMBER () OVER (ORDER BY NUM_TABLES DESC) / 1000,
    MAP(ROW_NUMBER () OVER (ORDER BY NUM_TABLES DESC), 1, 'Database schemas with >= 1 GB', ' '),
    IFNULL(SCHEMA_NAME || CHAR(32) || '(' || TO_DECIMAL(ROUND(DISK_GB), 10, 0) || CHAR(32) || 'GB,' || CHAR(32) || NUM_TABLES || CHAR(32) || 'tables)', 'none'),
    ' '
  FROM
    DUMMY LEFT OUTER JOIN
  ( SELECT
      SCHEMA_NAME,
      COUNT(*) NUM_TABLES,
      SUM(DISK_SIZE) / 1024 / 1024 / 1024 DISK_GB
    FROM
      M_TABLE_PERSISTENCE_STATISTICS
    GROUP BY
      SCHEMA_NAME
    HAVING
      SUM(DISK_SIZE) >= 1073741824
  ) ON
  1 = 1
  UNION ALL
  SELECT
    1200,
    'Startup time',
    TO_VARCHAR(START_TIME, 'YYYY/MM/DD HH24:MI:SS'),
    '2177064'
  FROM
    M_DATABASE
  UNION ALL
  SELECT
    1300 + ROW_NUMBER () OVER (ORDER BY HOST),
    ' ',
    TO_VARCHAR(TO_TIMESTAMP(SUBSTR(VALUE, 1, 19), 'YYYY-MM-DD HH24:MI:SS'), 'YYYY/MM/DD HH24:MI:SS') || ' (' || HOST || ')',
    '2177064'
  FROM
    M_HOST_INFORMATION
  WHERE
    KEY = 'start_time'
  UNION ALL
  SELECT
    1400,
    'Distributed system',
    LOWER(VALUE),
    ' '
  FROM
    M_SYSTEM_OVERVIEW
  WHERE
    SECTION = 'System' AND
    NAME = 'Distributed'
  UNION ALL
  SELECT
    1500,
    'Multitenant',
    CASE P.DB_TYPE
      WHEN 'singledb' THEN 'no'
      WHEN 'multidb' THEN MAP(D.DATABASE_NAME, 'SYSTEMDB', 'yes (SystemDB)', 'yes (TenantDB)')
    END,
    '2101244'
  FROM
  ( SELECT
      MAX(VALUE) DB_TYPE
    FROM
      M_CONFIGURATION_PARAMETER_VALUES
    WHERE
      FILE_NAME = 'global.ini' AND
      SECTION = 'multidb' AND
      KEY = 'mode'
  ) P,
    M_DATABASE D
  UNION ALL
  SELECT
    1600,
    'Everything started',
    LOWER(VALUE),
    ' '
  FROM
    M_SYSTEM_OVERVIEW
  WHERE
    SECTION = 'Services' AND
    NAME = 'All Started'
  UNION ALL
  SELECT
    1700,
    'Number of hosts with active DB services',
    TO_VARCHAR(COUNT (DISTINCT HOST)),
    ' '
  FROM
    M_SERVICES
  UNION ALL
  SELECT
    1800 + ROW_NUMBER () OVER (ORDER BY INDEXSERVER_ACTUAL_ROLE, HOST),
    MAP(ROW_NUMBER () OVER (ORDER BY INDEXSERVER_ACTUAL_ROLE, HOST), 1, 'Indexserver role', ' '),
    RPAD(INDEXSERVER_ACTUAL_ROLE, 8) || ' (' || HOST || ')',
    ' '
  FROM
    M_LANDSCAPE_HOST_CONFIGURATION
  UNION ALL
  SELECT
    1850 + ROW_NUMBER () OVER (ORDER BY HOST_ACTUAL_ROLES, HOST),
    MAP(ROW_NUMBER () OVER (ORDER BY HOST_ACTUAL_ROLES, HOST), 1, 'Host role', ' '),
    RPAD(HOST_ACTUAL_ROLES, GREATEST(8, LENGTH(HOST_ACTUAL_ROLES))) || ' (' || HOST || ')',
    ' '
  FROM
    M_LANDSCAPE_HOST_CONFIGURATION
  UNION ALL
  SELECT
    1900 + ROW_NUMBER () OVER (ORDER BY HOST),
    MAP(ROW_NUMBER () OVER (ORDER BY HOST), 1, 'Host directory', ' '),
    VALUE || ' (' || HOST || ')',
    ' '
  FROM
    M_HOST_INFORMATION
  WHERE
    KEY = 'sap_retrieval_path'
  UNION ALL
  SELECT
    2000 + ROW_NUMBER () OVER (ORDER BY VALUE),
    'Timezone',
    VALUE || ' (' || COUNT(*) || ' host' || CASE WHEN COUNT(*) = 1 THEN '' ELSE 's' END || ')',
    ' '
  FROM
    M_HOST_INFORMATION
  WHERE
    KEY = 'timezone_name'
  GROUP BY
    VALUE
  UNION ALL
  SELECT
    2100,
    'NUMA nodes',
    TO_VARCHAR(MAX(NUM)),
    '2100040'
  FROM
  ( SELECT
      COUNT(DISTINCT(NUMA_NODE_ID)) NUM
    FROM
      M_NUMA_NODES
    GROUP BY
      HOST,
      PORT
  )
  UNION ALL
  SELECT
    2110,
    ' ',
    ' ',
    ' '
  FROM
    DUMMY
  UNION ALL
  SELECT
    2115,
    'INSTALLED PRODUCTS:',
    ' ',
    ' '
  FROM
    DUMMY
  UNION ALL
  SELECT
    2120,
    ' ',
    ' ',
    ' '
  FROM
    DUMMY
  UNION ALL
  SELECT
    2125 + ROW_NUMBER () OVER (ORDER BY PRODUCT_NAME, PRODUCT_VERSION),
    PRODUCT_NAME,
    LTRIM(PRODUCT_VERSION),
    ' '
  FROM
  ( SELECT /* Execution of "/hana/shared/&lt;SID>/hdblcm/hdblcm -action=update_component_list" may be required for up-to-date information */
      COMPONENT_NAME PRODUCT_NAME,
      VERSION || MAP(VERSION_SP, '', '', '.' || VERSION_SP || MAP(VERSION_PATCH, '', '', '.' || VERSION_PATCH)) PRODUCT_VERSION 
    FROM
      LCM_SOFTWARE_COMPONENTS
    WHERE
      COMPONENT_NAME != 'HDB'
    UNION
    SELECT
      PRODUCT_NAME,
      VERSION || MAP(SP_STACK_DESCRIPTION, '', '', CHAR(32) || SP_STACK_DESCRIPTION) PRODUCT_VERSION
    FROM
      LCM_PRODUCTS
    WHERE
      PRODUCT_NAME != 'SAP NEWDB'
    UNION
    SELECT
      MAP(PLUGIN_NAME, 'LCAPPS', 'LCAPPS_TECH', PLUGIN_NAME),
      VALUE
    FROM
      M_PLUGIN_MANIFESTS
    WHERE
    ( PLUGIN_NAME = 'LCAPPS' AND KEY = 'LCAPPS technical version' OR
      PLUGIN_NAME NOT IN ( 'LCAPPS', 'AFL' ) AND KEY = 'fullversion'
    )
  )
  UNION ALL
  SELECT
    2170,
    ' ',
    ' ',
    ' '
  FROM
    DUMMY
  UNION ALL
  SELECT
    2180,
    'PATCH HISTORY:',
    ' ',
    ' '
  FROM
    DUMMY
  UNION ALL
  SELECT
    2190,
    ' ',
    ' ',
    ' '
  FROM
    DUMMY
  UNION ALL
  SELECT
    2200 + ROW_NUMBER () OVER (ORDER BY INSTALL_TIME DESC),
    TO_VARCHAR(INSTALL_TIME, 'YYYY/MM/DD HH24:MI:SS'),
    VERSION,
    ' '
  FROM
    M_DATABASE_HISTORY
  UNION ALL
  SELECT
    2270,
    ' ',
    ' ',
    ' '
  FROM 
    DUMMY
  UNION ALL
  SELECT
    2280,
    'FEATURE AND CONFIGURATION INFORMATION:',
    ' ',
    ' '
  FROM 
    DUMMY
  UNION ALL
  SELECT
   2290,
    ' ',
    ' ',
    ' '
  FROM 
    DUMMY
  UNION ALL
  SELECT
    2300 + ROW_NUMBER () OVER (ORDER BY REPLICATION_PATH DESC),
    MAP(ROW_NUMBER () OVER (ORDER BY REPLICATION_PATH DESC), 1, 'System replication', ' '),
    IFNULL(REPLICATION_PATH, 'no'),
    '1999880'
  FROM
  ( SELECT DISTINCT
      REPLICATION_MODE || ' (' || SITE_NAME || ' -> ' || SECONDARY_SITE_NAME || ')' REPLICATION_PATH
    FROM
      DUMMY LEFT OUTER JOIN
      M_SYSTEM_REPLICATION ON
        1 = 1
  )
  UNION ALL
  ( SELECT
      2350,
      'Operation mode',
      STRING_AGG(OPERATION_MODE, ', ' ORDER BY OPERATION_MODE),
      '1999880'
    FROM
    ( SELECT DISTINCT
        OPERATION_MODE
      FROM
        M_SYSTEM_REPLICATION
    )
  )
  UNION ALL
  ( SELECT
      2355,
      'Extension nodes',
      TO_VARCHAR(COUNT(*)),
      '2415279'
    FROM
      M_LANDSCAPE_HOST_CONFIGURATION
    WHERE
      WORKER_ACTUAL_GROUPS LIKE '%worker_dt%'
  )
  UNION ALL
  ( SELECT
      2360 + ROW_NUMBER() OVER (ORDER BY PROVIDER_NAME, PROVIDER_COMPANY),
      MAP(ROW_NUMBER() OVER (ORDER BY PROVIDER_NAME, PROVIDER_COMPANY), 1, 'HA/DR providers', ''),
      IFNULL(PROVIDER_NAME || CHAR(32) || '(' || PROVIDER_COMPANY || ')', 'no'),
      ''
    FROM
      DUMMY LEFT OUTER JOIN
      M_HA_DR_PROVIDERS ON
        1 = 1
  )
  UNION ALL
  SELECT
    2400,
    'liveCache',
    MAP(COUNT(*), 0, 'no', 'yes'),
    '2593571'
  FROM
    M_LIVECACHE_CONTAINER_STATISTICS
  UNION ALL
  SELECT
    2500,
    'Activated audit policies',
    TO_VARCHAR(COUNT(*)),
    '2159014'
  FROM
    AUDIT_POLICIES
  WHERE
    IS_AUDIT_POLICY_ACTIVE = 'TRUE'
  UNION ALL
  SELECT
    2600,
    'Users with individual statement memory limit',
    TO_VARCHAR(COUNT(*)),
    '1999997'
  FROM
    USER_PARAMETERS
  WHERE
    PARAMETER = 'STATEMENT MEMORY LIMIT'
  UNION ALL
  SELECT
    2700,
    'Sequences',
    TO_VARCHAR(TOTAL_SEQUENCES) || MAP(TOTAL_SEQUENCES, 0, '', MAP(SLT_SEQUENCES, 0, '',
      ' (SLT:' || CHAR(32) || SLT_SEQUENCES || ')')) VALUE,
    '2600095'
  FROM
  ( SELECT
      COUNT(*) TOTAL_SEQUENCES,
      SUM(CASE WHEN SEQUENCE_NAME LIKE 'SEQ_/1CADMC/%' OR SEQUENCE_NAME LIKE 'SEQ_/1DH/%' THEN 1 ELSE 0 END) SLT_SEQUENCES
    FROM
      SEQUENCES
    WHERE
      SCHEMA_NAME NOT IN ('SYS', 'SYSTEM')
  )
  UNION ALL
  SELECT
    2800,
    'Triggers',
    TO_VARCHAR(TOTAL_TRIGGERS) || MAP(TOTAL_TRIGGERS, 0, '', MAP(INTERNAL_TRIGGERS, 0, '',
      CHAR(32) || '(' || INTERNAL_TRIGGERS || CHAR(32) || 'internal)')) VALUE,
    '2800020'
  FROM
  ( SELECT
      COUNT(*) TOTAL_TRIGGERS,
      SUM(CASE WHEN OWNER_NAME IN ('_SYS_STATISTICS', '_SYS_SECURITY') THEN 1 ELSE 0 END) INTERNAL_TRIGGERS
    FROM
      TRIGGERS
    WHERE
      OWNER_NAME NOT IN ('SYS', 'SYSTEM')
  )
  UNION ALL
  SELECT
    2850,
    'Referential constraints',
    TO_VARCHAR(TOTAL_REF_CONSTRAINTS) || MAP(INTERNAL_REF_CONSTRAINTS, 0, '', CHAR(32) || '(' || INTERNAL_REF_CONSTRAINTS || CHAR(32) || 'internal)'),
    ''
  FROM
  ( SELECT
      COUNT(DISTINCT(CONSTRAINT_NAME)) TOTAL_REF_CONSTRAINTS
    FROM
      REFERENTIAL_CONSTRAINTS
  ),
  ( SELECT
      COUNT(DISTINCT(CONSTRAINT_NAME)) INTERNAL_REF_CONSTRAINTS
    FROM
      REFERENTIAL_CONSTRAINTS
    WHERE
      SCHEMA_NAME IN ('SYS', 'SYSTEM', '_SYS_STATISTICS')
  )
  UNION ALL
  SELECT
    2900,
    'Fulltext indexes',
    TO_VARCHAR(COUNT(*)),
    '2800008'
  FROM
    FULLTEXT_INDEXES
  WHERE
    SCHEMA_NAME != '_SYS_REPO'
  UNION ALL
  SELECT
    2902,
    'Fuzzy search indexes',
    TO_VARCHAR(COUNT(*)),
    '2800008'
  FROM
    M_FUZZY_SEARCH_INDEXES
  WHERE
    SCHEMA_NAME != '_SYS_REPO'
  UNION ALL
  SELECT
    2908,
    'Document store collections',
    TO_VARCHAR(COUNT(*)),
    '2477204'
  FROM
    TABLES
  WHERE
    TABLE_TYPE = 'COLLECTION'
  UNION ALL
  SELECT
    2910,
    'Text analysis tables',
    TO_VARCHAR(COUNT(*)),
    '2800008'
  FROM
    TABLES
  WHERE
    SUBSTR(TABLE_NAME, 1, 4) = '$TA_'
  UNION ALL
  SELECT
    2911,
    'Text mining tables',
    TO_VARCHAR(COUNT(*)),
    '2800008'
  FROM
    TABLES
  WHERE
    SUBSTR(TABLE_NAME, 1, 4) = '$TM_'
  UNION ALL
  SELECT
    2915,
    'Persistent memory (PMEM) configured',
    MAP(COUNT(*), 0, 'no', 'yes'),
    '2700084'
  FROM
    M_PERSISTENT_MEMORY_VOLUMES
  WHERE
    FILESYSTEM_TYPE != 'tmpfs'
  UNION ALL
  SELECT
    2916,
    'Fast restart option (FRO) configured',
    MAP(COUNT(*), 0, 'no', 'yes'),
    '2700084'
  FROM
    M_PERSISTENT_MEMORY_VOLUMES
  WHERE
    FILESYSTEM_TYPE = 'tmpfs'
  UNION ALL
  SELECT
    2920,
    'Tables / partitions using PMEM or FRO',
    TO_VARCHAR(COUNT(*)),
    '2700084'
  FROM
    M_CS_TABLES
  WHERE
    PERSISTENT_MEMORY = 'TRUE'
  UNION ALL
  SELECT
    3000,
    'Inverted hash indexes',
    TO_VARCHAR(NUM_INDEXES) || MAP(NUM_INTERNAL, 0, '', CHAR(32) || '(' || NUM_INTERNAL || CHAR(32) || 'internal)'),
    '2109355'
  FROM
  ( SELECT
      COUNT(*) NUM_INDEXES,
      IFNULL(SUM(CASE WHEN SCHEMA_NAME IN ('SYS', 'SYSTEM') OR SUBSTR(SCHEMA_NAME, 1, 5) = '_SYS_' THEN 1 ELSE 0 END), 0) NUM_INTERNAL
    FROM
      INDEXES
    WHERE
      INDEX_TYPE LIKE 'INVERTED HASH%'
  )
  UNION ALL
  SELECT
    3010,
    'Inverted individual indexes',
    TO_VARCHAR(NUM_INDEXES) || MAP(NUM_INTERNAL, 0, '', CHAR(32) || '(' || NUM_INTERNAL || CHAR(32) || 'internal)'),
    '2600076'
  FROM
  ( SELECT
      COUNT(*) NUM_INDEXES,
      IFNULL(SUM(CASE WHEN SCHEMA_NAME IN ('SYS', 'SYSTEM') OR SUBSTR(SCHEMA_NAME, 1, 5) = '_SYS_' THEN 1 ELSE 0 END), 0) NUM_INTERNAL
    FROM
      INDEXES
    WHERE
      INDEX_TYPE LIKE 'INVERTED INDIVIDUAL%'
  )
  UNION ALL
  SELECT
    3100,
    'Columns with explicit preload flag',
    TO_VARCHAR(COUNT(*)),
    '2127458'
  FROM
    TABLE_COLUMNS
  WHERE
    PRELOAD = 'TRUE'
  UNION ALL
  SELECT
    3210,
    'Tables with explicit unused retention period',
    TO_VARCHAR(COUNT(DISTINCT(SCHEMA_NAME || TABLE_NAME))),
    '2127458'
  FROM
    M_CS_TABLES
  WHERE
    UNUSED_RETENTION_PERIOD > 0
  UNION ALL
  SELECT
    3300,
    'History tables',
    TO_VARCHAR(COUNT(*)),
    '1910610'
  FROM
    TABLES
  WHERE
    SESSION_TYPE = 'HISTORY'
  UNION ALL
  SELECT
    3310,
    'System-versioned tables',
    TO_VARCHAR(COUNT(*)),
    '3055510'
  FROM
    TEMPORAL_TABLES
  WHERE
    PERIOD_NAME = 'SYSTEM_TIME'
  UNION ALL
  SELECT
    3320,
    'Application-time period tables',
    TO_VARCHAR(COUNT(*)),
    ''
  FROM
    TEMPORAL_TABLES
  WHERE
    PERIOD_NAME = 'APPLICATION_TIME'
  UNION ALL
  SELECT
    3400,
    'Virtual tables',
    TO_VARCHAR(COUNT(*)),
    '2180119'
  FROM
    TABLES
  WHERE
    TABLE_TYPE = 'VIRTUAL'
  UNION ALL
  SELECT
    3410,
    'Series tables',
    TO_VARCHAR(COUNT(*)),
    ''
  FROM
    SERIES_TABLES
  UNION ALL
  SELECT
    3500,
    'Packed LOBs',
    TO_VARCHAR(IFNULL(SUM(L.LOB_COUNT), 0)),
    '2220627'
  FROM
    M_HOST_RESOURCE_UTILIZATION H,
    M_TABLE_LOB_STATISTICS L
  WHERE
    H.HOST = L.HOST AND
    L.CONTAINER_ID IS NOT NULL
  UNION ALL
  SELECT
    3600,
    'Smart Data Access (SDA)',
    MAP(TOTAL, 0, 'no', TOTAL || CHAR(32) || 'source' || MAP(TOTAL, 1, '', 's') || MAP(SR, 0, '', CHAR(32) || '(' || SR || CHAR(32) || 'system replication)')),
    '2180119'
  FROM
  ( SELECT
      COUNT(*) TOTAL,
      SUM(MAP(SUBSTR(REMOTE_SOURCE_NAME, 1, 13), '_SYS_SR_SITE_', 1, 0)) SR
    FROM
      REMOTE_SOURCES
  )
  UNION ALL
  SELECT
    3700,
    'Smart Data Integration (SDI)',
    MAP(NUM_DPSERVERS, 0, 'no', 'yes' || CHAR(32) || '(' || NUM_AGENTS || CHAR(32) || 'agent' || MAP(NUM_AGENTS, 1, '', 's') || ')'),
    '2400022'
  FROM
  ( SELECT COUNT(*) NUM_DPSERVERS FROM M_SERVICES WHERE SERVICE_NAME = 'dpserver' ),
  ( SELECT COUNT(*) NUM_AGENTS FROM M_AGENTS )
  UNION ALL
  SELECT
    3800,
    'Smart Data Streaming (SDS)',
    MAP(COUNT(*), 0, 'no', 'yes'),
    '2367236'
  FROM
    M_STREAMING_SERVICES
  UNION ALL
  SELECT
    3900,
    'Dynamic Tiering',
    MAP(COUNT(*), 0, 'no', 'yes'),
    '2140959'
  FROM
    M_SERVICES
  WHERE
    SERVICE_NAME = 'esserver'
  UNION ALL
  SELECT
    3905,
    'Multi-dimensional Expressions (MDX)',
    MAP(COUNT(*), 0, 'no', 'yes'),
    ''
  FROM
    _SYS_STATISTICS.HOST_SERVICE_THREAD_SAMPLES
  WHERE
    UPPER(THREAD_DETAIL) LIKE 'MDX%'
  UNION ALL
  SELECT
    3910,
    'Multi-dimensional Services (MDS)',
    MAP(COUNT(*), 0, 'no', 'yes'),
    '2670064'
  FROM
    M_MULTIDIMENSIONAL_STATEMENT_STATISTICS
  UNION ALL
  SELECT
    3950,
    'Data volume partitioning',
    CASE WHEN MAX(PARTITION_COUNT) = 1 THEN 'no' ELSE 'yes (' || MAX(PARTITION_COUNT) || CHAR(32) || 'partitions)' END,
    '2400005'
  FROM
    M_DATA_VOLUME_STATISTICS
  UNION ALL
  SELECT
    3980,
    'Data aging',
    MAP(COUNT, 0, 'no', 'yes' || CHAR(32) || '(' || COUNT || CHAR(32) || 'tables)'),
    '2416490'
  FROM
  ( SELECT
      COUNT(DISTINCT(SCHEMA_NAME || TABLE_NAME)) COUNT
    FROM
    ( SELECT
        T.SCHEMA_NAME,
        T.TABLE_NAME
      FROM
        TABLES T LEFT OUTER JOIN
        PARTITIONED_TABLES PT ON
          T.SCHEMA_NAME = PT.SCHEMA_NAME AND
          T.TABLE_NAME = PT.TABLE_NAME
      WHERE
        T.LOAD_UNIT = 'PAGE' AND
        IFNULL(PT.PARTITION_DEFINITION, '') LIKE '%DATAAGING%'
      UNION
      SELECT
        P.SCHEMA_NAME,
        P.TABLE_NAME
      FROM
        TABLES T,
        PARTITIONED_TABLES PT,
        TABLE_PARTITIONS P
      WHERE
        T.SCHEMA_NAME = PT.SCHEMA_NAME AND
        T.TABLE_NAME = PT.TABLE_NAME AND
        T.SCHEMA_NAME = P.SCHEMA_NAME AND
        T.TABLE_NAME = P.TABLE_NAME AND
        P.LOAD_UNIT = 'PAGE' AND
        IFNULL(PT.PARTITION_DEFINITION,'') LIKE '%DATAAGING%'
      UNION
      SELECT
        TC.SCHEMA_NAME,
        TC.TABLE_NAME
      FROM
        TABLES T,
        TABLE_COLUMNS TC LEFT OUTER JOIN
        PARTITIONED_TABLES PT ON
          TC.SCHEMA_NAME = PT.SCHEMA_NAME AND
          TC.TABLE_NAME = PT.TABLE_NAME
      WHERE
        T.SCHEMA_NAME = TC.SCHEMA_NAME AND
        T.TABLE_NAME = TC.TABLE_NAME AND
        TC.LOAD_UNIT = 'PAGE' AND
        IFNULL(PT.PARTITION_DEFINITION, '') LIKE '%DATAAGING%'
    )
  )
  UNION ALL
  SELECT
    3981,
    'Native storage extension (NSE)',
    MAP(COUNT, 0, 'no', 'yes' || CHAR(32) || '(' || COUNT || CHAR(32) || 'table' || MAP(COUNT, 1, '', 's') || ')'),
    '2799997'
  FROM
  ( SELECT
      COUNT(DISTINCT(SCHEMA_NAME || TABLE_NAME)) COUNT
    FROM
    ( SELECT
        T.SCHEMA_NAME,
        T.TABLE_NAME
      FROM
        TABLES T LEFT OUTER JOIN
        PARTITIONED_TABLES PT ON
          T.SCHEMA_NAME = PT.SCHEMA_NAME AND
          T.TABLE_NAME = PT.TABLE_NAME
      WHERE
        T.LOAD_UNIT = 'PAGE' AND
        IFNULL(PT.PARTITION_DEFINITION, '') NOT LIKE '%DATAAGING%'
      UNION
      SELECT
        P.SCHEMA_NAME,
        P.TABLE_NAME
      FROM
        TABLES T,
        PARTITIONED_TABLES PT,
        TABLE_PARTITIONS P
      WHERE
        T.SCHEMA_NAME = PT.SCHEMA_NAME AND
        T.TABLE_NAME = PT.TABLE_NAME AND
        T.SCHEMA_NAME = P.SCHEMA_NAME AND
        T.TABLE_NAME = P.TABLE_NAME AND
        P.LOAD_UNIT = 'PAGE' AND
        IFNULL(PT.PARTITION_DEFINITION, '') NOT LIKE '%DATAAGING%'
      UNION
      SELECT
        TC.SCHEMA_NAME,
        TC.TABLE_NAME
      FROM
        TABLES T,
        TABLE_COLUMNS TC LEFT OUTER JOIN
        PARTITIONED_TABLES PT ON
          TC.SCHEMA_NAME = PT.SCHEMA_NAME AND
          TC.TABLE_NAME = PT.TABLE_NAME
      WHERE
        T.SCHEMA_NAME = TC.SCHEMA_NAME AND
        T.TABLE_NAME = TC.TABLE_NAME AND
        TC.LOAD_UNIT = 'PAGE' AND
        IFNULL(PT.PARTITION_DEFINITION, '') NOT LIKE '%DATAAGING%'
    )
  )
  UNION ALL
  SELECT
    3985,
    'Max. NSE buffer cache size (GB)',
    TO_VARCHAR(TO_DECIMAL(SUM(B.MAX_SIZE) / 1024 / 1024 / 1024, 10, 2)),
    '2799997'
  FROM
    M_SERVICES S,
    M_BUFFER_CACHE_STATISTICS B
  WHERE
    S.SERVICE_NAME IN ( 'nameserver', 'indexserver' ) AND
    S.HOST = B.HOST AND
    S.PORT = B.PORT
  UNION ALL
  SELECT
    3988,
    'Paged objects disk size (GB)',
    TO_VARCHAR(TO_DECIMAL(IFNULL(SUM(MAIN_PHYSICAL_SIZE_IN_PAGE_LOADABLE / 1024 / 1024 / 1024), 0), 10, 2)),
    '1871386'
  FROM
    M_CS_COLUMNS_PERSISTENCE
  WHERE
    PERSISTENCE_TYPE = 'PAGED'
  UNION ALL
  SELECT
    3990,
    'Paged objects memory size (GB)',
    TO_VARCHAR(TO_DECIMAL(SUM(PAGE_LOADABLE_COLUMNS_OBJECT_SIZE) / 1024 / 1024 / 1024, 10, 2)),
    '1871386'
  FROM
    M_MEMORY_OBJECT_DISPOSITIONS
  UNION ALL
  SELECT
    4100,
    'Tables with dynamic range partitioning',
    IFNULL(TO_VARCHAR(COUNT(*)) || CHAR(32) || '(' || TO_VARCHAR(SUM(CASE WHEN TABLE_NAME LIKE '/B%/%' OR TABLE_NAME LIKE 'RSPM%' THEN 1 ELSE 0 END)) || CHAR(32) || 'BW)', '0'),
    '2044468'
  FROM
    TABLES
  WHERE
    PARTITION_SPEC LIKE 'RANGE[DYNAMIC%'
  UNION ALL
  SELECT
    4200,
    'Table replicas',
    TO_VARCHAR(COUNT(*)) || MAP(COUNT(*), 0, '', CHAR(32) || '(' || SUM(MAP(REPLICA_TYPE, 'ASYNCHRONOUS', 1, 0)) || CHAR(32) || 'ATR,' || CHAR(32) ||
      SUM(MAP(REPLICA_TYPE, 'SYNCHRONOUS', 1, 0)) || CHAR(32) || 'OSTR)'),
    '2340450'
  FROM
    M_TABLE_REPLICAS
  UNION ALL
  SELECT
    4300,
    'Volume encryption',
    MAP(COUNT(*), 0, 'no', 'yes' || CHAR(32) || '(' || STRING_AGG(SCOPE, ',' || CHAR(32)) || ')'),
    '2159014'
  FROM
    M_ENCRYPTION_OVERVIEW
  WHERE
    IS_ENCRYPTION_ACTIVE = 'TRUE'
  UNION ALL
  SELECT
    4400,
    'Embedded statistics server active',
    MAP(LOWER(MAX(VALUE)), 'true', 'yes', 'false', 'no', 'unknown'),
    '2147247'
  FROM
      M_CONFIGURATION_PARAMETER_VALUES
  WHERE 
    FILE_NAME IN ('indexserver.ini', 'nameserver.ini') AND
    SECTION = 'statisticsserver' AND
    KEY = 'active'
  UNION ALL
  SELECT
    4500,
    'Standalone statistics server active',
    MAP(COUNT(*), 0, 'no', 'yes'),
    '2147247'
  FROM
    M_SERVICES
  WHERE
    SERVICE_NAME = 'statisticsserver'
  UNION ALL
  SELECT
    4600,
    'Pinned SQL plans',
    TO_VARCHAR(COUNT(*)),
    '2222321'
  FROM
    PINNED_SQL_PLANS
  UNION ALL
  SELECT
    4605,
    'Hint annotations',
    TO_VARCHAR(COUNT(*)) || CHAR(32) || '(' || TO_VARCHAR(SUM(MAP(SCHEMA_NAME, '_SYS_BI', 1, 0))) || CHAR(32) || 'for _SYS_BI user)',
    '2142945'
  FROM
    ANNOTATIONS
  WHERE
    KEY = 'HINT'
  UNION ALL
  SELECT
    4700,
    'Statement hints',
    IFNULL(TO_VARCHAR(COUNT(*)) || CHAR(32) || '(' || TO_VARCHAR(SUM(MAP(LAST_ENABLE_USER, 'SYS', 1, 0))) || CHAR(32) || 'default)', '0'),
    '2400006'
  FROM
    STATEMENT_HINTS
  UNION ALL
  SELECT
    4710,
    'Abstract SQL plans',
    TO_VARCHAR(COUNT(*)),
    '2799998'
  FROM
    ABSTRACT_SQL_PLANS
  UNION ALL
  SELECT
    4720,
    'Data statistics',
    TO_VARCHAR(COUNT(*) || MAP(SUM(SDA), 0, '', NULL, '', CHAR(32) || '(' || SUM(SDA) || CHAR(32) || 'SDA)')),
    '2800028'
  FROM
  ( SELECT DISTINCT
      SCHEMA_NAME,
      TABLE_NAME,
      MAP(T.TABLE_TYPE, 'VIRTUAL', 1, 0) SDA
    FROM
      TABLES T,
      M_DATA_STATISTICS S
    WHERE
      T.SCHEMA_NAME = S.DATA_SOURCE_SCHEMA_NAME AND
      T.TABLE_NAME = S.DATA_SOURCE_OBJECT_NAME
  )
  UNION ALL
  SELECT
    4800,
    'Workload classes',
    TO_VARCHAR(COUNT(*)),
    '2222250'
  FROM
    WORKLOAD_CLASSES
  UNION ALL
  SELECT
    4900,
    'Workload mappings',
    TO_VARCHAR(COUNT(*)),
    '2222250'
  FROM
    WORKLOAD_MAPPINGS
  UNION ALL
  SELECT
    5000,
    'Static result cache entries',
    TO_VARCHAR(COUNT(*)),
    '2336344'
  FROM
    M_RESULT_CACHE
  UNION ALL
  SELECT
    5100,
    'Dynamic result cache entries',
    TO_VARCHAR(COUNT(*)),
    '2506811'
  FROM
    M_DYNAMIC_RESULT_CACHE
  UNION ALL
  SELECT
    5100,
    'Transactions with disabled logging',
    TO_VARCHAR(COUNT(*)),
    '1999930'
  FROM
    M_TRANSACTIONS
  WHERE
    LOGGING_ENABLED = 'FALSE'
  UNION ALL
  SELECT
    5110,
    'Tables with disabled logging',
    TO_VARCHAR(COUNT(*)),
    '1999930'
  FROM
    M_CS_TABLES
  WHERE
    IS_LOG_DELTA = 'FALSE'
  UNION ALL
  SELECT DISTINCT
    5120,
    'I/O throttling',
    MAP(KEY, NULL, 'no', 'yes'),
    '1999930'
  FROM
    DUMMY LEFT OUTER JOIN
    M_CONFIGURATION_PARAMETER_VALUES ON
      SECTION = 'fileio' AND
      KEY LIKE 'max%throughput%' AND
      LAYER_NAME != 'DEFAULT'
  UNION ALL
  SELECT
    5200,
    N.DESCRIPTION,
    TO_VARCHAR(MAP(SUM(MAP(C.ENTRY_TYPE_NAME, N.NAME, 1, 0)), 0, 'no', 'yes')),
    '1642148'
  FROM
  ( SELECT 'data snapshot' NAME,       'Data snapshot backups' DESCRIPTION FROM DUMMY UNION ALL
    SELECT 'differential data backup', 'Differential data backups'         FROM DUMMY UNION ALL
    SELECT 'incremental data backup',  'Incremental data backups'          FROM DUMMY
  ) N LEFT OUTER JOIN
    M_BACKUP_CATALOG C ON
      C.ENTRY_TYPE_NAME = N.NAME
  GROUP BY
    N.DESCRIPTION
  UNION ALL
  SELECT
    5210,
    'Kernel profiler configured',
    MAP(COUNT(*), 0, 'no', 'yes'),
    '2800030'
  FROM
    M_KERNEL_PROFILER
  WHERE
    STATUS != 'STOPPED' OR
    STATUS = 'STOPPED' AND SECONDS_BETWEEN(STOP_TIME, CURRENT_TIMESTAMP) &lt;= 3600
  UNION ALL
  SELECT
    5300 + LINE_NO / 1000,
    DESCRIPTION,
    RPAD(IFNULL(MAP(VALUE, 'TRUE', 'true', 'FALSE', 'false', VALUE), ''), 12) || MAP(LAYER, 'DEFAULT', '(default)', ''),
    SAP_NOTE
  FROM
  ( SELECT
      P.LINE_NO,
      P.DESCRIPTION,
      P.SAP_NOTE,
      MAX(I.LAYER_NAME) LAYER,
      MAX(I.VALUE) VALUE
    FROM 
    ( SELECT  10 LINE_NO, 'Database log mode' DESCRIPTION,             'persistence' SECTION,        'log_mode' KEY,                   '' DEFAULT_VALUE, '1642148' SAP_NOTE FROM DUMMY UNION ALL
      SELECT  20 LINE_NO, 'Automatic log backup',                      'persistence',                'enable_auto_log_backup',         '',               '1642148'          FROM DUMMY UNION ALL
      SELECT  30 LINE_NO, 'Query result cache',                        'cache',                      'resultcache_enabled',            '',               '2014148'          FROM DUMMY UNION ALL
      SELECT  40 LINE_NO, 'Global auditing state',                     'auditing configuration',     'global_auditing_state',          '',               '3421606'          FROM DUMMY UNION ALL
      SELECT  50 LINE_NO, 'Self-signed certificates',                  'communication',              'sslcreateselfsignedcertificate', 'false',          '1891055'          FROM DUMMY UNION ALL
      SELECT  60 LINE_NO, 'Hostname resolution for default route',     'public_hostname_resolution', 'use_default_route',              '',               '1906381'          FROM DUMMY UNION ALL
      SELECT  70 LINE_NO, 'Mountpoint usage for data and log volumes', 'persistence',                'use_mountpoints',                '',               '1820553'          FROM DUMMY UNION ALL
      SELECT  80 LINE_NO, 'Client distribution mode',                  'distribution',               'client_distribution_mode',       '',               '2200772'          FROM DUMMY UNION ALL
      SELECT 100 LINE_NO, 'Parallelism of table preload',              'parallel',                   'tables_preloaded_in_parallel',   '',               '2127458'          FROM DUMMY UNION ALL
      SELECT 110 LINE_NO, 'Table preload during startup',              'sql',                        'reload_tables',                  '',               '2127458'          FROM DUMMY UNION ALL
      SELECT 140 LINE_NO, 'Listen interface',                          'communication',              'listeninterface',                '',               '1999797'          FROM DUMMY UNION ALL
      SELECT 150 LINE_NO, 'Multitenant isolation level',               'multidb',                    'database_isolation',             '',               '2101244'          FROM DUMMY UNION ALL
      SELECT 160 LINE_NO, 'License usage',                             'system_information',         'license_usage',                  '',               '2779499'          FROM DUMMY UNION ALL
      SELECT 170 LINE_NO, 'System replication full-sync',              'system_replication',         'enable_full_sync',               '',               '1999880'          FROM DUMMY
    ) P LEFT OUTER JOIN
      M_CONFIGURATION_PARAMETER_VALUES I ON
        I.SECTION = P.SECTION AND
        I.KEY = P.KEY AND
        I.FILE_NAME IN ('global.ini', 'indexserver.ini', 'nameserver.ini') LEFT OUTER JOIN
      CONFIGURATION_PARAMETER_PROPERTIES PP ON
        PP.SECTION = P.SECTION AND
        PP.KEY = P.KEY
    GROUP BY
      P.LINE_NO,
      P.DESCRIPTION,
      P.SAP_NOTE,
      P.DEFAULT_VALUE,
      PP.DEFAULT_VALUE
  )
  UNION ALL
  SELECT
    5370,
    ' ',
    ' ',
    ' '
  FROM 
    DUMMY
  UNION ALL
  SELECT
    5380,
    'CLIENT APPLICATION LOAD:',
    ' ',
    ' '
  FROM 
    DUMMY
  UNION ALL
  SELECT
    5390,
    ' ',
    ' ',
    ' '
  FROM 
    DUMMY
  UNION ALL
  SELECT
    5400 + ROW_NUMBER () OVER (ORDER BY SAMPLES DESC),
    APPLICATION_NAME,
    TO_VARCHAR(LPAD(TO_DECIMAL(SAMPLES / TOTAL_SAMPLES * 100, 10, 2), 6)) || CHAR(32) || '%',
    MAP(APPLICATION_NAME, 'HANACockpit', '2800006', 'HDBStudio', '2073112', 'SAP_SDA_', '2180119', 'Embedded Statistics Server', '2147247', '2114710')
  FROM
  ( SELECT
      MAP(APPLICATION_NAME, CHAR(63), '&lt;internal / undefined>', APPLICATION_NAME) APPLICATION_NAME,
      COUNT(*) SAMPLES,
      SUM(COUNT(*)) OVER () TOTAL_SAMPLES
    FROM
      _SYS_STATISTICS.HOST_SERVICE_THREAD_SAMPLES T
    WHERE
      TIMESTAMP >= ADD_DAYS(CURRENT_TIMESTAMP, -31) AND
      THREAD_STATE = 'Running' AND
      THREAD_TYPE NOT IN ( 'ChildIOThreads::ErrorStream', 'ChildIOThreads::OutputStream', 'Generic', 'WebDispatcher-Main-Thread' ) AND
      THREAD_METHOD NOT IN ( 'TimerCallback_OdmContextCleanup' )
    GROUP BY
      APPLICATION_NAME
  )
  WHERE
    SAMPLES / TOTAL_SAMPLES * 100 >= 1
  UNION ALL
  SELECT
    6370,
    ' ',
    ' ',
    ' '
  FROM 
    DUMMY
  UNION ALL
  SELECT
    6380,
    'SPACE INFORMATION:',
    ' ',
    ' '
  FROM 
    DUMMY
  UNION ALL
  SELECT
    6390,
    ' ',
    ' ',
    ' '
  FROM 
    DUMMY
  UNION ALL
  SELECT
    D.LINE_NO,
    D.DESCRIPTION,
    MAP(D.DESCRIPTION, 'Data disk size allocated (GB)',                LPAD(TO_DECIMAL(V.ALLOC_GB,            12, 2), 13),
                       'Data disk size used (GB)',                     LPAD(TO_DECIMAL(V.USED_GB,             12, 2), 13),
                       'Data disk size used by tables (GB)',           LPAD(TO_DECIMAL(T.TABLE_GB,            12, 2), 13),
                       'Data disk size used by tables excl. LOB (GB)', LPAD(TO_DECIMAL(T.TABLE_GB - L.LOB_GB, 12, 2), 13)),
    '2400005'
  FROM
  ( SELECT 6400 LINE_NO, 'Data disk size allocated (GB)' DESCRIPTION FROM DUMMY UNION ALL
    SELECT 6500, 'Data disk size used (GB)'                          FROM DUMMY UNION ALL
    SELECT 6550, 'Data disk size used by tables (GB)'                FROM DUMMY UNION ALL
    SELECT 6600, 'Data disk size used by tables excl. LOB (GB)'      FROM DUMMY
  ) D,
  ( SELECT SUM(TOTAL_SIZE) / 1024 / 1024 / 1024 ALLOC_GB, SUM(USED_SIZE) / 1024 / 1024 / 1024 USED_GB FROM M_VOLUME_FILES WHERE FILE_TYPE = 'DATA' ) V,
  ( SELECT SUM(DISK_SIZE) / 1024 / 1024 / 1024 LOB_GB FROM M_TABLE_LOB_STATISTICS ) L,
  ( SELECT SUM(DISK_SIZE) / 1024 / 1024 / 1024 TABLE_GB FROM M_TABLE_PERSISTENCE_STATISTICS ) T
  UNION ALL
  SELECT
    6700,
    'Converter disk size (GB)',
    LPAD(TO_DECIMAL(SUM(ALLOCATED_PAGE_SIZE) / 1024 / 1024 / 1024, 10, 2), 13),
    ' '
  FROM
    M_CONVERTER_STATISTICS
  UNION ALL
  SELECT  /* value may be wrong for data snapshots with &lt;= 1.00.122.26, &lt;= 2.00.037.02 and &lt;= 2.00.041 */
    6800,
    'Data backup size (GB)',
    IFNULL(LPAD(TO_DECIMAL(SUM(BACKUP_SIZE) / 1024 / 1024 / 1024, 12, 2), 13), 'n/a'),
    ' '
  FROM
  ( SELECT TOP 1
      BACKUP_ID
    FROM
      M_BACKUP_CATALOG
    WHERE
      ENTRY_TYPE_NAME IN ( 'complete data backup', 'data snapshot' ) AND 
      STATE_NAME = 'successful'
    ORDER BY
      UTC_START_TIME DESC
  ) MB,
    M_BACKUP_CATALOG_FILES B
  WHERE
    B.BACKUP_ID = MB.BACKUP_ID
  UNION ALL
  SELECT
    6900 + ROW_NUMBER () OVER (ORDER BY HOST),
    MAP(ROW_NUMBER () OVER (ORDER BY HOST), 1, 'Row store memory size total (GB)', ' '),
    LPAD(TO_DECIMAL(SUM(ALLOCATED_SIZE) / 1024 / 1024 / 1024, 12, 2), 13) || ' (' || HOST || ')',
    ' '
  FROM
    M_RS_MEMORY
  GROUP BY
    HOST
  HAVING
    SUM(ALLOCATED_SIZE) / 1024 / 1024 / 1024 > 3
  UNION ALL
  SELECT
    7000,
    'Column store memory size total (GB)',
    LPAD(TO_DECIMAL(SUM(MEMORY_SIZE_IN_TOTAL + PERSISTENT_MEMORY_SIZE_IN_TOTAL) / 1024 / 1024 / 1024, 12, 2), 13),
    ' '
  FROM
    M_CS_TABLES
  UNION ALL
  SELECT
    7100,
    'Row store tables',
    LPAD(COUNT(*), 10) || '    (SAP schema: ' || LPAD(SUM(MAP(SUBSTR(SCHEMA_NAME, 1, 3), 'SAP', 1, 0)), 6) || ')',
    ' '
  FROM
    TABLES
  WHERE 
    TABLE_TYPE = 'ROW'
  UNION ALL
  SELECT
    7200,
    'Column store tables',
    LPAD(COUNT(*), 10) || '    (SAP schema: ' || LPAD(SUM(MAP(SUBSTR(SCHEMA_NAME, 1, 3), 'SAP', 1, 0)), 6) || ')',
    ' '
  FROM
    TABLES
  WHERE 
    TABLE_TYPE = 'COLUMN'
)
ORDER BY
  LINE_NO
WITH HINT ( IGNORE_PLAN_CACHE )
</textarea>
    </div>
  </div>

  <!-- Right: tabbed results -->
  <div id="right-pane">

    <!-- Tab bar -->
    <div id="tab-bar">
      <div class="tab active" id="tab-table" onclick="switchTab('table')">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M3 15h18M9 3v18"/>
        </svg>
        Table
      </div>
      <div class="tab" id="tab-chart" onclick="switchTab('chart')">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M18 20V10M12 20V4M6 20v-6"/>
        </svg>
        Chart
      </div>
      <div style="flex:1; display:flex; align-items:center; justify-content:flex-end; padding-right:10px; gap:8px;">
        <button class="btn btn-ghost" id="btn-csv" onclick="exportCSV()"
          style="font-size:11px;padding:2px 8px;height:24px;" disabled>&#11015; CSV</button>
        <span id="result-stat"></span>
      </div>
    </div>

    <!-- Table panel -->
    <div class="tab-panel active" id="panel-table">
      <div id="table-wrap">
        <div id="table-ph">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2">
            <rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M3 15h18M9 3v18"/>
          </svg>
          <span>Run a query to see results</span>
        </div>
      </div>
    </div>

    <!-- Chart panel -->
    <div class="tab-panel" id="panel-chart">
      <div id="chart-config">
        <label>Type</label>
        <select id="cfg-type" onchange="buildChart()">
          <option value="bar">Bar</option>
          <option value="line">Line</option>
          <option value="pie">Pie</option>
          <option value="doughnut">Doughnut</option>
          <option value="polarArea">Polar Area</option>
          <option value="radar">Radar</option>
        </select>
        <div class="tb-sep"></div>
        <label>Label col</label>
        <select id="cfg-label" onchange="buildChart()"></select>
        <label>Value col</label>
        <select id="cfg-value" onchange="buildChart()"></select>
        <div class="tb-sep"></div>
        <label>Color</label>
        <input type="color" id="cfg-color" value="#0070d2" onchange="buildChart()"/>
        <div class="tb-sep"></div>
        <label>Title</label>
        <input type="text" id="chart-title-input" placeholder="Chart title…" oninput="buildChart()"/>
        <div class="tb-sep"></div>
        <button class="btn btn-success" id="btn-save-png" onclick="saveChartPNG()" disabled
          style="font-size:12px;padding:4px 10px;">&#128190; Save PNG</button>
      </div>
      <div id="chart-canvas-wrap">
        <div id="chart-placeholder">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2">
            <path d="M18 20V10M12 20V4M6 20v-6"/>
          </svg>
          <span>Run a query, then configure chart axes above</span>
        </div>
        <canvas id="myChart" style="display:none;"></canvas>
      </div>
    </div>

    <!-- Log -->
    <div id="log-wrap"></div>
  </div>
</div>

<!-- Status bar -->
<div id="status-bar">
  <span>Host: <span class="seg-val" id="st-host">&#8212;</span></span>
  <span>DB: <span class="seg-val" id="st-db">&#8212;</span></span>
  <span>User: <span class="seg-val" id="st-user">&#8212;</span></span>
  <span id="st-last">
    Last: <span class="seg-val" id="st-elapsed">&#8212;</span>
    &nbsp;|&nbsp; Rows: <span class="seg-val" id="st-rows">&#8212;</span>
  </span>
</div>

<!-- Login modal -->
<div id="modal-overlay">
  <div id="modal-box">
    <h2>Connect to SAP HANA</h2>
    <div class="field-row">
      <div class="field" style="flex:3">
        <label>Host</label>
        <input id="inp-host" type="text" placeholder="hostname" spellcheck="false"/>
      </div>
      <div class="field" style="flex:1">
        <label>Port</label>
        <input id="inp-port" type="number" value="30241"/>
      </div>
    </div>
    <div class="field">
      <label>Database</label>
      <input id="inp-db" type="text" placeholder="Database name" spellcheck="false"/>
    </div>
    <div class="field">
      <label>User</label>
      <input id="inp-user" type="text" placeholder="Username" spellcheck="false" autocomplete="username"/>
    </div>
    <div class="field">
      <label>Password</label>
      <input id="inp-pass" type="password" placeholder="Password" autocomplete="current-password"/>
    </div>
    <div id="modal-error"></div>
    <div id="modal-actions">
      <button class="btn btn-primary" id="btn-conn" onclick="doConnect()">Connect</button>
      <button class="btn btn-ghost" onclick="window.close()">Quit</button>
    </div>
    <div id="modal-spinner"><span class="spin">&#8635;</span> Connecting&hellip;</div>
  </div>
</div>

<!-- Consolidate modal -->
<div id="consolidate-overlay" onclick="if(event.target===this)hideConsolidate()">
  <div id="consolidate-box">
    <h2>&#128196; Consolidate Output Files</h2>
    <div class="con-desc">Select files from the output folder to merge into a single review file.</div>
    <div style="display:flex;align-items:center;justify-content:space-between;">
      <span style="font-size:11px;color:var(--muted)" id="con-file-count">0 files found</span>
      <button id="con-sel-all" onclick="conToggleAll()">Select all</button>
    </div>
    <div id="output-list"><div style="padding:16px;color:var(--muted);font-size:12px;text-align:center;">Loading...</div></div>
    <div id="con-status"></div>
    <div id="con-actions">
      <button class="btn btn-primary" id="btn-con-run" onclick="runConsolidate()" disabled>&#9654; Consolidate</button>
      <button class="btn btn-ghost" onclick="hideConsolidate()">Cancel</button>
    </div>
  </div>
</div>

<!-- About modal -->
<div id="about-overlay" onclick="if(event.target===this)hideAbout()">
  <div id="about-box">
    <div class="about-logo">SAP HANA <span>SQL Console</span></div>
    <div class="about-version">Version 4.0</div>
    <hr/>
    <div class="about-row"><span class="lbl">Version</span><span class="val">4.0</span></div>
    <div class="about-row"><span class="lbl">Date</span><span class="val">2026-07-29</span></div>
    <div class="about-row" style="flex-direction:column;align-items:flex-start;gap:2px;">
      <span class="lbl">Developer</span>
      <span class="val">Ernesto Espindola</span>
      <span style="font-size:11px;color:var(--muted)">ernesto.espindola@sap.com</span>
    </div>
    <div class="about-row" style="flex-direction:column;align-items:flex-start;gap:2px;">
      <span class="lbl">Team</span>
      <span class="val">RDE LAC</span>
      <span style="font-size:11px;color:var(--muted)">DL PCO Regional Operations Team LAC</span>
      <span style="font-size:10px;color:var(--muted)">DL_677C05450B39650137D3CEFA@global.corp.sap</span>
    </div>
    <div class="about-row"><span class="lbl">Wiki</span><span class="val" style="color:var(--muted);font-style:italic;">Coming soon</span></div>
    <hr/>
    <button class="about-close" onclick="hideAbout()">Close</button>
  </div>
</div>

<div id="toast"></div>

<script src="/static/chart.umd.min.js"></script>
<script>
// ── State ─────────────────────────────────────────────────────────────────────
var _connected = false;
var _cols = [], _rows = [], _sortCol = -1, _sortAsc = true;
var _chart = null;
var NUM_RE = /^-?\d+(\.\d+)?([eE][+-]?\d+)?$/;

// ── DOM helpers ───────────────────────────────────────────────────────────────
function $(id)       { return document.getElementById(id); }
function val(id)     { return $(id).value; }
function show(id)    { var e=$(id); if(e) e.style.display=''; }
function hide(id)    { var e=$(id); if(e) e.style.display='none'; }
function dot(cls)    { $('conn-dot').className = cls; }
function setErr(msg) { $('modal-error').textContent = msg; }
function setBusy(b)  { $('btn-conn').disabled=b; $('modal-spinner').style.display=b?'block':'none'; }
function esc(s)      { return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
function getSQL()    { return $('sql-editor').value; }
function setSQL(s)   { $('sql-editor').value = s; }

function toast(msg) {
  var t=$('toast'); t.textContent=msg; t.classList.add('show');
  setTimeout(function(){ t.classList.remove('show'); }, 1800);
}
function log(msg, type) {
  var w=$('log-wrap'), d=document.createElement('div');
  d.className='log-entry log-'+type;
  d.textContent='['+new Date().toLocaleTimeString()+']  '+msg;
  w.appendChild(d); w.scrollTop=w.scrollHeight;
}
async function post(url, body) {
  var r = await fetch(url, {method:'POST',
    headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
  return r.json();
}

// ── Tab switching ─────────────────────────────────────────────────────────────
function switchTab(name) {
  ['table','chart'].forEach(function(t) {
    $('tab-'+t).classList.toggle('active', t===name);
    $('panel-'+t).classList.toggle('active', t===name);
  });
  if (name==='chart' && _cols.length) buildChart();
}

// ── Event wiring ──────────────────────────────────────────────────────────────
$('inp-user').addEventListener('keydown', function(e){ if(e.key==='Enter') $('inp-pass').focus(); });
$('inp-pass').addEventListener('keydown', function(e){ if(e.key==='Enter') doConnect(); });
$('sql-editor').addEventListener('keydown', function(e){
  if (e.key==='F5' || (e.ctrlKey && e.key==='Enter')) { e.preventDefault(); runQuery(); }
  if (e.key==='Tab') {
    e.preventDefault();
    var t=e.target, s=t.selectionStart;
    t.value=t.value.substring(0,s)+'  '+t.value.substring(t.selectionEnd);
    t.selectionStart=t.selectionEnd=s+2;
  }
});
document.addEventListener('keydown', function(e){ if(e.key==='F5'){ e.preventDefault(); runQuery(); } });
$('inp-user').focus();

// ── Connect ───────────────────────────────────────────────────────────────────
async function doConnect() {
  setErr(''); setBusy(true);
  try {
    var r = await post('/api/connect', {
      host: val('inp-host'), port: val('inp-port'),
      database: val('inp-db'), user: val('inp-user'), password: val('inp-pass')
    });
    if (r.ok) onConnected(r.info); else setErr(r.error);
  } catch(e) { setErr('Request failed: '+e.message); }
  finally { setBusy(false); }
}

function onConnected(info) {
  _connected = true;
  hide('modal-overlay'); show('btn-disconnect');
  $('btn-run').disabled = false;
  dot('on');
  $('conn-label').textContent = info.user+'@'+info.host+':'+info.port;
  $('st-host').textContent = info.host+':'+info.port;
  $('st-db').textContent   = info.database;
  $('st-user').textContent = info.user;
  log('Connected to '+info.host+':'+info.port+'  DB='+info.database+'  User='+info.user, 'info');
  var tog = $('btn-scripts-toggle');
  tog.style.display = 'inline-flex';
  $('btn-consolidate').style.display = 'inline-flex';
  loadScriptList();
  $('sql-editor').focus();
}

async function doDisconnect() {
  await post('/api/disconnect', {});
  _connected = false;
  $('btn-run').disabled = true;
  hide('btn-disconnect'); dot('off');
  $('conn-label').textContent = 'Not connected';
  ['st-host','st-db','st-user'].forEach(function(id){ $(id).textContent='—'; });
  hide('st-last'); setErr('');
  log('Disconnected.', 'warn');
  $('inp-pass').value = '';
  $('scripts-pane').classList.remove('visible');
  $('btn-scripts-toggle').style.display = 'none';
  $('btn-scripts-toggle').classList.remove('active');
  $('btn-consolidate').style.display = 'none';
  show('modal-overlay');
}

// ── Execute ───────────────────────────────────────────────────────────────────
async function runQuery() {
  if (!_connected) return;
  var sql = getSQL();
  if (!sql.trim()) return;
  var btn = $('btn-run');
  btn.disabled = true;
  btn.innerHTML = '<span class="spin">&#8635;</span> Running&hellip;';
  try {
    var r = await post('/api/execute', {sql: sql});
    if (r.ok) {
      if (r.type === 'rows') {
        renderTable(r.columns, r.rows);
        var cap = r.capped ? '  ⚠ capped at 5000' : '';
        log('OK  '+r.rows.length+' row(s) in '+r.elapsed+'s'+cap, r.capped?'warn':'ok');
        $('st-elapsed').textContent  = r.elapsed+'s';
        $('st-rows').textContent     = r.rows.length+(r.capped?' (cap)':'');
        $('result-stat').textContent = r.rows.length+' row(s)'+(r.capped?' ⚠':'')+' · '+r.elapsed+'s';
        show('st-last');
      } else {
        clearTableArea('Statement executed — '+r.rowcount+' row(s) affected');
        log('OK  '+r.rowcount+' row(s) affected in '+r.elapsed+'s', 'ok');
        $('st-elapsed').textContent  = r.elapsed+'s';
        $('st-rows').textContent     = r.rowcount+' affected';
        $('result-stat').textContent = r.rowcount+' affected · '+r.elapsed+'s';
        show('st-last');
      }
    } else {
      log('ERROR  '+r.error, 'err');
      $('result-stat').textContent = 'ERROR';
    }
  } catch(e) { log('Request failed: '+e.message, 'err'); }
  finally {
    btn.disabled = false;
    btn.innerHTML = '&#9654; Run <kbd>F5</kbd>';
  }
}

// ── Table ─────────────────────────────────────────────────────────────────────
function renderTable(cols, rows) {
  _cols = cols; _rows = rows; _sortCol = -1; _sortAsc = true;
  _paintTable(cols, rows);
  $('btn-csv').disabled = false;
  populateChartSelectors(cols);
  if (_chart) buildChart();
}

function _paintTable(cols, rows) {
  var tbl = document.createElement('table');
  tbl.id = 'result-table';
  var thead = tbl.createTHead(), hr = thead.insertRow();
  cols.forEach(function(c, i) {
    var th = document.createElement('th');
    th.innerHTML = esc(c)+' <span class="si" id="si'+i+'">&#8645;</span>';
    th.onclick = function(){ sortBy(i); };
    hr.appendChild(th);
  });
  var tb = tbl.createTBody();
  rows.forEach(function(row) {
    var tr = tb.insertRow();
    row.forEach(function(v) {
      var td = tr.insertCell();
      if (v===''||v===null) { td.textContent='NULL'; td.className='nul'; }
      else { td.textContent=v; if(NUM_RE.test(v)) td.className='num'; }
    });
  });
  var w = $('table-wrap');
  w.innerHTML = ''; w.appendChild(tbl);
}

function sortBy(col) {
  if (_sortCol===col) _sortAsc=!_sortAsc; else { _sortCol=col; _sortAsc=true; }
  var sorted = _rows.slice().sort(function(a,b){
    var av=a[col]!=null?a[col]:'', bv=b[col]!=null?b[col]:'';
    var an=parseFloat(av), bn=parseFloat(bv);
    var c=(!isNaN(an)&&!isNaN(bn))?an-bn:av.localeCompare(bv);
    return _sortAsc?c:-c;
  });
  _paintTable(_cols, sorted);
  _cols.forEach(function(_,i){
    var si=$('si'+i); if(si) si.textContent=i===col?(_sortAsc?'↑':'↓'):'⇅';
  });
}

function clearTableArea(msg) {
  _cols=[]; _rows=[]; $('btn-csv').disabled=true;
  $('table-wrap').innerHTML='<div id="table-ph"><span style="color:var(--muted)">'+esc(msg)+'</span></div>';
  destroyChart();
}

function clearResults() {
  clearTableArea('Run a query to see results');
  $('result-stat').textContent=''; hide('st-last');
}

// ── Chart ─────────────────────────────────────────────────────────────────────
var PALETTE = [
  '#0070d2','#22c55e','#f59e0b','#e63946','#7c3aed',
  '#06b6d4','#f97316','#ec4899','#16a34a','#0891b2'
];

function populateChartSelectors(cols) {
  ['cfg-label','cfg-value'].forEach(function(id) {
    var sel=$(id); sel.innerHTML='';
    cols.forEach(function(c,i){
      var o=document.createElement('option');
      o.value=i; o.textContent=c; sel.appendChild(o);
    });
  });
  // default: label=col0, value=last numeric col or col1
  $('cfg-label').value = 0;
  var valIdx = 1;
  for (var i=cols.length-1; i>=0; i--) {
    if (_rows.length && NUM_RE.test(_rows[0][i])) { valIdx=i; break; }
  }
  $('cfg-value').value = valIdx;
}

function destroyChart() {
  if (_chart) { _chart.destroy(); _chart=null; }
  $('myChart').style.display='none';
  $('chart-placeholder').style.display='';
  $('btn-save-png').disabled=true;
}

function buildChart() {
  if (!_cols.length || !_rows.length) return;
  var type    = val('cfg-type');
  var labelIdx= parseInt(val('cfg-label'));
  var valIdx  = parseInt(val('cfg-value'));
  var title   = val('chart-title-input') || (_cols[valIdx]+' by '+_cols[labelIdx]);
  var baseColor = val('cfg-color');

  var labels = _rows.map(function(r){ return r[labelIdx]; });
  var values = _rows.map(function(r){ return parseFloat(r[valIdx]) || 0; });

  // multi-color for pie/doughnut/polar
  var isMulti = (type==='pie'||type==='doughnut'||type==='polarArea');
  var bgColors = isMulti
    ? labels.map(function(_,i){ return PALETTE[i % PALETTE.length]; })
    : baseColor;
  var borderColors = isMulti
    ? labels.map(function(_,i){ return PALETTE[i % PALETTE.length]; })
    : baseColor;

  var dataset = {
    label: _cols[valIdx],
    data: values,
    backgroundColor: isMulti ? bgColors : hexToRgba(baseColor, 0.7),
    borderColor: isMulti ? borderColors : baseColor,
    borderWidth: type==='line' ? 2 : 1,
    fill: type==='line' ? false : undefined,
    tension: 0.3,
    pointRadius: type==='line' ? 3 : undefined,
  };

  if (_chart) { _chart.destroy(); _chart=null; }
  $('chart-placeholder').style.display='none';
  var canvas=$('myChart');
  canvas.style.display='block';

  _chart = new Chart(canvas, {
    type: type,
    data: { labels: labels, datasets: [dataset] },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: isMulti,
          labels: { color: '#1e293b', font: { size: 11 } }
        },
        title: {
          display: !!title,
          text: title,
          color: '#1e293b',
          font: { size: 14, weight: 'bold' }
        },
        tooltip: {
          callbacks: {
            label: function(ctx) {
              return ' '+ctx.label+': '+ctx.raw.toLocaleString();
            }
          }
        }
      },
      scales: isMulti ? {} : {
        x: { ticks: { color: '#64748b', maxRotation: 45 },
             grid:  { color: 'rgba(209,213,219,.6)' } },
        y: { ticks: { color: '#64748b' },
             grid:  { color: 'rgba(209,213,219,.6)' } }
      }
    }
  });

  $('btn-save-png').disabled = false;
}

function saveChartPNG() {
  if (!_chart) return;
  var title = (val('chart-title-input') || 'chart').replace(/[^a-z0-9_-]/gi,'_');
  // draw white background then download
  var src = $('myChart');
  var tmp = document.createElement('canvas');
  tmp.width=src.width; tmp.height=src.height;
  var ctx=tmp.getContext('2d');
  ctx.fillStyle='#ffffff';
  ctx.fillRect(0,0,tmp.width,tmp.height);
  ctx.drawImage(src,0,0);
  var a=document.createElement('a');
  a.href=tmp.toDataURL('image/png');
  a.download=title+'.png';
  a.click();
  toast('Chart saved as '+title+'.png');
}

function hexToRgba(hex, alpha) {
  var r=parseInt(hex.slice(1,3),16),
      g=parseInt(hex.slice(3,5),16),
      b=parseInt(hex.slice(5,7),16);
  return 'rgba('+r+','+g+','+b+','+alpha+')';
}

// ── Mini Checks ───────────────────────────────────────────────────────────────
var _allScripts = [], _selectedScript = null;

async function loadScriptList() {
  try {
    var r = await fetch('/api/scripts');
    var data = await r.json();
    _allScripts = data.scripts || [];
    $('scripts-count').textContent = _allScripts.length;
    renderScriptList(_allScripts);
  } catch(e) { log('Could not load script list: '+e.message, 'err'); }
}

function scriptDisplayName(fname) {
  var name = fname.replace(/\.(sql|txt)$/i, '');
  var m = name.match(/^(.*?)(_\d+\.\d+.*)?$/);
  var title = m[1].replace(/_/g, ' ');
  var ver = m[2] ? m[2].replace(/_/g, ' ').trim() : '';
  return {title: title, ver: ver};
}

function renderScriptList(scripts) {
  var list = $('scripts-list');
  list.innerHTML = '';
  if (!scripts.length) {
    list.innerHTML = '<div style="padding:16px 12px;color:var(--muted);font-size:12px;">No scripts found.</div>';
    return;
  }
  scripts.forEach(function(fname) {
    var info = scriptDisplayName(fname);
    var item = document.createElement('div');
    item.className = 'script-item' + (fname === _selectedScript ? ' selected' : '');
    item.dataset.fname = fname;
    var rb = document.createElement('input');
    rb.type = 'radio'; rb.name = 'script'; rb.value = fname;
    rb.checked = (fname === _selectedScript);
    rb.id = 'rb_' + fname.replace(/[^a-z0-9]/gi, '_');
    var lbl = document.createElement('label');
    lbl.htmlFor = rb.id; lbl.className = 'script-name';
    lbl.innerHTML = esc(info.title) + (info.ver ? '<em>'+esc(info.ver)+'</em>' : '');
    lbl.style.cursor = 'pointer';
    item.appendChild(rb); item.appendChild(lbl);
    item.addEventListener('click', function(e) { if(e.target===rb) return; rb.checked=true; selectScript(fname, item); });
    rb.addEventListener('change', function() { if(rb.checked) selectScript(fname, item); });
    list.appendChild(item);
  });
}

function selectScript(fname) {
  _selectedScript = fname;
  document.querySelectorAll('.script-item').forEach(function(el) {
    el.classList.toggle('selected', el.dataset.fname === fname);
  });
  $('btn-load-script').disabled = false;
}

function filterScripts() {
  var q = $('scripts-filter').value.toLowerCase();
  var filtered = q ? _allScripts.filter(function(f){ return f.toLowerCase().includes(q); }) : _allScripts;
  renderScriptList(filtered);
}

function toggleScriptsPane() {
  var pane = $('scripts-pane'), btn = $('btn-scripts-toggle');
  var visible = pane.classList.toggle('visible');
  btn.classList.toggle('active', visible);
}

async function loadSelectedScript() {
  if (!_selectedScript) return;
  $('btn-load-script').disabled = true;
  try {
    var r = await post('/api/load_script', {filename: _selectedScript});
    if (r.ok) {
      setSQL(r.content);
      log('Loaded: '+r.filename, 'info');
      toast('Script loaded into editor');
      $('sql-editor').focus();
    } else { log('Load error: '+r.error, 'err'); }
  } catch(e) { log('Request failed: '+e.message, 'err'); }
  finally { $('btn-load-script').disabled = false; }
}

function showAbout() { $('about-overlay').classList.add('show'); }
function hideAbout() { $('about-overlay').classList.remove('show'); }

// -- Consolidate ---------------------------------------------------------------
var _outputFiles = [];

function showConsolidate() {
  $('consolidate-overlay').classList.add('show');
  $('con-status').textContent = '';
  $('btn-con-run').disabled = true;
  loadOutputList();
}
function hideConsolidate() { $('consolidate-overlay').classList.remove('show'); }

async function loadOutputList() {
  $('output-list').innerHTML = '<div style="padding:16px;color:var(--muted);font-size:12px;text-align:center;">Loading...</div>';
  try {
    var r = await fetch('/api/list_outputs');
    var data = await r.json();
    _outputFiles = data.files || [];
    $('con-file-count').textContent = _outputFiles.length + ' file' + (_outputFiles.length===1?'':'s') + ' found';
    renderOutputList();
  } catch(e) {
    $('output-list').innerHTML = '<div style="padding:16px;color:var(--error);font-size:12px;">Error loading files: '+esc(e.message)+'</div>';
  }
}

function renderOutputList() {
  var list = $('output-list');
  if (!_outputFiles.length) {
    list.innerHTML = '<div style="padding:16px;color:var(--muted);font-size:12px;text-align:center;">No output files found in the output folder.</div>';
    return;
  }
  list.innerHTML = '';
  _outputFiles.forEach(function(f) {
    var item = document.createElement('div');
    item.className = 'output-item';
    var cb = document.createElement('input');
    cb.type = 'checkbox'; cb.value = f.name; cb.id = 'cb_'+f.name.replace(/[^a-z0-9]/gi,'_');
    cb.addEventListener('change', updateConRunBtn);
    var lbl = document.createElement('label');
    lbl.htmlFor = cb.id; lbl.className = 'out-name'; lbl.textContent = f.name; lbl.style.cursor='pointer';
    var sz = document.createElement('span');
    sz.className = 'out-size';
    sz.textContent = f.size > 1024 ? (f.size/1024).toFixed(1)+' KB' : f.size+' B';
    item.appendChild(cb); item.appendChild(lbl); item.appendChild(sz);
    list.appendChild(item);
  });
}

function updateConRunBtn() {
  var checked = document.querySelectorAll('#output-list input[type=checkbox]:checked');
  $('btn-con-run').disabled = checked.length === 0;
}

function conToggleAll() {
  var boxes = document.querySelectorAll('#output-list input[type=checkbox]');
  var allChecked = Array.from(boxes).every(function(b){ return b.checked; });
  boxes.forEach(function(b){ b.checked = !allChecked; });
  $('con-sel-all').textContent = allChecked ? 'Select all' : 'Deselect all';
  updateConRunBtn();
}

async function runConsolidate() {
  var checked = Array.from(document.querySelectorAll('#output-list input[type=checkbox]:checked'));
  var files = checked.map(function(b){ return b.value; });
  if (!files.length) return;
  $('btn-con-run').disabled = true;
  $('con-status').textContent = 'Consolidating ' + files.length + ' file(s)...';
  try {
    var r = await post('/api/consolidate', {files: files});
    if (r.ok) {
      $('con-status').innerHTML = 'Done! <a href="/output/'+encodeURIComponent(r.filename)+'" download="'+esc(r.filename)+'" style="color:var(--accent)">Download '+esc(r.filename)+'</a>';
      log('Consolidated '+files.length+' file(s) into '+r.filename, 'ok');
    } else {
      $('con-status').textContent = 'Error: '+r.error;
    }
  } catch(e) {
    $('con-status').textContent = 'Request failed: '+e.message;
  } finally {
    $('btn-con-run').disabled = false;
  }
}

// ── Editor helpers ────────────────────────────────────────────────────────────
function clearEditor() { setSQL(''); $('sql-editor').focus(); }
function copySQL() {
  navigator.clipboard.writeText(getSQL()).then(function(){ toast('SQL copied!'); });
}
function exportCSV() {
  if (!_cols.length) return;
  function q(v) { return '"'+String(v).replace(/"/g,'""')+'"'; }
  var lines = [_cols.map(q).join(',')].concat(
    _rows.map(function(r){ return r.map(q).join(','); }));
  var now = new Date();
  var dateStr = now.getFullYear() +
    String(now.getMonth()+1).padStart(2,'0') +
    String(now.getDate()).padStart(2,'0');
  var baseName = _selectedScript
    ? _selectedScript.replace(/\.(sql|txt)$/i, '').replace(/[^a-z0-9_\-]/gi, '_')
    : 'hana_result';
  var fname = baseName + '_OUTPUT_' + dateStr + '.csv';
  var content = lines.join('\r\n');
  // Download in browser
  var a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([content], {type:'text/csv'}));
  a.download = fname; a.click();
  // Also save to server output folder
  post('/api/save_output', {filename: fname, content: content}).then(function(r){
    if (r.ok) toast('CSV saved: '+fname);
    else toast('CSV downloaded (save failed: '+r.error+')');
  }).catch(function(){ toast('CSV downloaded'); });
}
</script>
</body>
</html>
"""


if __name__ == "__main__":
    host, port = "127.0.0.1", 5000
    server = ThreadingHTTPServer((host, port), Handler)
    url = f"http://{host}:{port}"
    print(f"HANA SQL Console v4.0 running at {url}  (Ctrl+C to stop)")
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
