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

# Directory that holds mini-check SQL scripts (relative to this file)
_MINI_CHECKS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mini_checks")


# ── Request handler ──────────────────────────────────────────────────────────

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
        elif path == "/api/scripts":
            scripts = []
            if os.path.isdir(_MINI_CHECKS_DIR):
                for fname in sorted(os.listdir(_MINI_CHECKS_DIR)):
                    if fname.lower().endswith((".sql", ".txt")):
                        scripts.append(fname)
            self._send_json({"scripts": scripts})
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        global _conn, _creds_info
        path = urlparse(self.path).path
        data = self._read_json()

        if path == "/api/connect":
            host = data.get("host", "").strip()
            database = data.get("database", "HP4").strip()
            user = data.get("user", "").strip()
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

        elif path == "/api/load_script":
            fname = data.get("filename", "")
            # Prevent path traversal: basename only
            fname = os.path.basename(fname)
            fpath = os.path.join(_MINI_CHECKS_DIR, fname)
            if not os.path.isfile(fpath):
                return self._send_json({"ok": False, "error": "File not found."})
            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                self._send_json({"ok": True, "filename": fname, "content": content})
            except Exception as exc:
                self._send_json({"ok": False, "error": str(exc)})

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


# ── HTML / CSS / JS (single-file SPA) ────────────────────────────────────────

HTML_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>SAP HANA SQL Console</title>
<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --bg:       #0f1117;
  --surface:  #1a1d27;
  --surface2: #22263a;
  --border:   #2e3250;
  --accent:   #4f8ef7;
  --success:  #22c55e;
  --error:    #ef4444;
  --warn:     #f59e0b;
  --text:     #e2e8f0;
  --muted:    #64748b;
  --hdr:      48px;
  --stbar:    28px;
  --scripts-w: 280px;
}

html, body { height: 100%; background: var(--bg); color: var(--text);
  font-family: 'Segoe UI', system-ui, sans-serif; font-size: 14px; }

/* Header */
#header {
  height: var(--hdr); position: fixed; top: 0; left: 0; right: 0; z-index: 100;
  background: linear-gradient(90deg,#1a1d27,#1e2235);
  border-bottom: 1px solid var(--border);
  display: flex; align-items: center; padding: 0 16px; gap: 12px;
}
#header .logo { font-weight: 700; font-size: 15px; color: var(--accent); letter-spacing: .5px; }
#header .logo span { color: var(--text); }
#conn-badge { margin-left: auto; display: flex; align-items: center; gap: 8px; font-size: 12px; color: var(--muted); }
#conn-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--muted); flex-shrink: 0; transition: background .3s; }
#conn-dot.on  { background: var(--success); box-shadow: 0 0 6px var(--success); }
#conn-dot.off { background: var(--error); }
#btn-disconnect { padding: 3px 10px; border-radius: 4px; border: 1px solid var(--border);
  background: transparent; color: var(--muted); cursor: pointer; font-size: 12px; display: none; }
#btn-disconnect:hover { border-color: var(--error); color: var(--error); }

/* Layout */
#app { position: fixed; top: var(--hdr); bottom: var(--stbar); left: 0; right: 0; display: flex; }

/* Scripts sidebar */
#scripts-pane {
  width: var(--scripts-w); flex-shrink: 0;
  display: none; flex-direction: column;
  border-right: 1px solid var(--border);
  background: var(--surface);
}
#scripts-pane.visible { display: flex; }
#scripts-header {
  height: 38px; flex-shrink: 0; background: var(--surface2);
  border-bottom: 1px solid var(--border);
  display: flex; align-items: center; padding: 0 12px; gap: 8px;
}
#scripts-header .tb-label { font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: .5px; }
#scripts-header .badge {
  margin-left: auto; font-size: 10px; background: var(--accent);
  color: #fff; padding: 1px 6px; border-radius: 10px;
}
#scripts-filter {
  margin: 8px 10px 6px; padding: 5px 8px;
  background: var(--surface2); border: 1px solid var(--border);
  border-radius: 4px; color: var(--text); font-size: 12px; outline: none;
  width: calc(100% - 20px);
}
#scripts-filter:focus { border-color: var(--accent); }
#scripts-list {
  flex: 1; overflow-y: auto;
  scrollbar-width: thin; scrollbar-color: var(--border) transparent;
  padding: 4px 0 8px;
}
#scripts-list::-webkit-scrollbar { width: 5px; }
#scripts-list::-webkit-scrollbar-thumb { background: var(--border); }
.script-item {
  display: flex; align-items: flex-start; gap: 8px;
  padding: 7px 12px; cursor: pointer; border-left: 3px solid transparent;
  transition: background .12s;
}
.script-item:hover { background: rgba(79,142,247,.08); }
.script-item.selected { background: rgba(79,142,247,.13); border-left-color: var(--accent); }
.script-item input[type=radio] { margin-top: 2px; flex-shrink: 0; accent-color: var(--accent); cursor: pointer; }
.script-name { font-size: 12px; color: var(--text); line-height: 1.4; word-break: break-word; }
.script-name em { font-style: normal; color: var(--muted); font-size: 11px; display: block; margin-top: 1px; }
#scripts-run-bar {
  padding: 8px 10px; border-top: 1px solid var(--border);
  background: var(--surface2);
}
#btn-load-script {
  width: 100%; padding: 7px; border-radius: 5px; border: none;
  background: var(--accent); color: #fff; font-size: 13px; font-weight: 500;
  cursor: pointer; transition: filter .15s;
}
#btn-load-script:hover:not(:disabled) { filter: brightness(1.15); }
#btn-load-script:disabled { opacity: .4; cursor: not-allowed; }

/* Main area (editor + results) */
#main-area { flex: 1; display: flex; min-width: 0; }
#left-pane  { width: 38%; min-width: 240px; display: flex; flex-direction: column; border-right: 1px solid var(--border); }
#right-pane { flex: 1; display: flex; flex-direction: column; overflow: hidden; }

/* Toolbars */
.toolbar {
  height: 38px; flex-shrink: 0; background: var(--surface);
  border-bottom: 1px solid var(--border);
  display: flex; align-items: center; padding: 0 10px; gap: 8px;
}
.tb-label { font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: .5px; }
.tb-sep   { width: 1px; height: 18px; background: var(--border); }
#result-stat { font-size: 12px; color: var(--muted); margin-left: auto; }

/* Buttons */
.btn { display: inline-flex; align-items: center; gap: 5px; padding: 4px 12px;
  border-radius: 5px; border: none; cursor: pointer; font-size: 13px; font-weight: 500;
  transition: filter .15s; }
.btn:hover   { filter: brightness(1.15); }
.btn:active  { filter: brightness(.9); }
.btn-primary { background: var(--accent); color: #fff; }
.btn-ghost   { background: var(--surface2); color: var(--text); border: 1px solid var(--border); }
.btn:disabled { opacity: .4; cursor: not-allowed; filter: none; }
kbd { font-size: 10px; background: rgba(255,255,255,.1); border-radius: 3px; padding: 1px 5px; }

/* Editor */
#editor-wrap { flex: 1; overflow: hidden; display: flex; flex-direction: column; }
#sql-editor {
  flex: 1; width: 100%; height: 100%; resize: none; border: none; outline: none;
  background: #0f1117; color: #f8f8f2;
  font-family: 'Cascadia Code','Fira Code','Consolas',monospace;
  font-size: 13px; line-height: 1.6; padding: 10px 12px;
  tab-size: 2;
}

/* Table */
#table-wrap {
  flex: 1; overflow: auto; background: var(--bg);
  scrollbar-width: thin; scrollbar-color: var(--border) transparent;
}
#table-wrap::-webkit-scrollbar { width: 6px; height: 6px; }
#table-wrap::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }

#result-table { width: 100%; border-collapse: collapse; font-size: 12.5px; }
#result-table thead { position: sticky; top: 0; z-index: 5; }
#result-table th {
  background: var(--surface2); color: var(--text); padding: 7px 12px;
  text-align: left; font-weight: 600; border-bottom: 2px solid var(--border);
  white-space: nowrap; cursor: pointer; user-select: none;
}
#result-table th:hover { background: #2a2f4a; }
#result-table th .si { color: var(--muted); margin-left: 4px; font-size: 10px; }
#result-table td {
  padding: 5px 12px; border-bottom: 1px solid var(--border);
  max-width: 400px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
#result-table tr:nth-child(even) td { background: rgba(255,255,255,.018); }
#result-table tr:hover td { background: rgba(79,142,247,.08); }
#result-table td.num  { text-align: right; color: #93c5fd; font-family: monospace; }
#result-table td.nul  { color: var(--muted); font-style: italic; }

/* Log */
#log-wrap {
  height: 120px; flex-shrink: 0; border-top: 1px solid var(--border);
  overflow-y: auto; background: var(--surface); padding: 6px 12px;
  font-family: 'Cascadia Code','Consolas',monospace; font-size: 12px;
  scrollbar-width: thin; scrollbar-color: var(--border) transparent;
}
#log-wrap::-webkit-scrollbar { width: 5px; }
#log-wrap::-webkit-scrollbar-thumb { background: var(--border); }
.log-ok   { color: var(--success); }
.log-err  { color: var(--error); }
.log-warn { color: var(--warn); }
.log-info { color: var(--muted); }
.log-entry { margin-bottom: 2px; line-height: 1.5; }

/* Status bar */
#status-bar {
  position: fixed; bottom: 0; left: 0; right: 0; height: var(--stbar);
  background: var(--surface2); border-top: 1px solid var(--border);
  display: flex; align-items: center; padding: 0 14px; gap: 18px;
  font-size: 11.5px; color: var(--muted);
}
.seg-val { color: var(--text); }
#st-last { margin-left: auto; display: none; }

/* Placeholder */
#table-ph {
  display: flex; flex-direction: column; align-items: center;
  justify-content: center; height: 100%; color: var(--muted); gap: 10px; font-size: 13px;
}
#table-ph svg { opacity: .2; }

/* Modal */
#modal-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,.75);
  display: flex; align-items: center; justify-content: center;
  z-index: 200; backdrop-filter: blur(4px);
}
#modal-box {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 10px; padding: 28px 32px; width: 430px;
  box-shadow: 0 24px 56px rgba(0,0,0,.6);
}
#modal-box h2 { text-align: center; font-size: 17px; color: var(--accent);
  margin-bottom: 22px; letter-spacing: .3px; }
.field { margin-bottom: 14px; }
.field label { display: block; font-size: 12px; color: var(--muted); margin-bottom: 5px; }
.field input {
  width: 100%; padding: 8px 10px; border-radius: 5px;
  border: 1px solid var(--border); background: var(--surface2);
  color: var(--text); font-size: 13px; outline: none; transition: border-color .15s;
}
.field input:focus { border-color: var(--accent); }
.field-row { display: flex; gap: 12px; }
.field-row .field { flex: 1; }
#modal-error { color: var(--error); font-size: 12px; min-height: 18px;
  text-align: center; margin-bottom: 8px; }
#modal-actions { display: flex; gap: 10px; }
#modal-actions .btn { flex: 1; justify-content: center; padding: 9px; font-size: 14px; }
#modal-spinner { text-align: center; color: var(--muted); font-size: 12px;
  margin-top: 10px; display: none; }

/* Toast */
#toast {
  position: fixed; bottom: 40px; right: 20px; z-index: 300;
  background: var(--surface2); border: 1px solid var(--border);
  color: var(--text); padding: 7px 16px; border-radius: 6px;
  font-size: 12px; opacity: 0; transition: opacity .2s; pointer-events: none;
}
#toast.show { opacity: 1; }

@keyframes spin { to { transform: rotate(360deg); } }
.spin { display: inline-block; animation: spin .75s linear infinite; }

/* Scripts pane toggle button in toolbar */
#btn-scripts-toggle {
  padding: 4px 10px; border-radius: 5px; border: 1px solid var(--border);
  background: var(--surface2); color: var(--text); cursor: pointer;
  font-size: 12px; display: none; gap: 5px; align-items: center;
}
#btn-scripts-toggle.active { border-color: var(--accent); color: var(--accent); }
#btn-scripts-toggle:hover { filter: brightness(1.2); }
</style>
</head>
<body>

<div id="header">
  <div class="logo">SAP HANA <span>SQL Console</span></div>
  <button id="btn-scripts-toggle" onclick="toggleScriptsPane()" title="Toggle Mini Checks">
    &#9776; Mini Checks
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
      <button id="btn-load-script" disabled onclick="loadSelectedScript()">
        &#11123; Load into Editor
      </button>
    </div>
  </div>

  <!-- Main area -->
  <div id="main-area">
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
        <textarea id="sql-editor">-- SAP HANA SQL Console
-- F5 or Ctrl+Enter to execute

SELECT TOP 20 * FROM M_DATABASES;
</textarea>
      </div>
    </div>

    <div id="right-pane">
      <div class="toolbar">
        <span class="tb-label">Results</span>
        <button class="btn btn-ghost" onclick="clearResults()" style="font-size:12px;padding:3px 9px;">Clear</button>
        <button class="btn btn-ghost" id="btn-csv" onclick="exportCSV()" style="font-size:12px;padding:3px 9px;" disabled>&#11015; CSV</button>
        <span id="result-stat"></span>
      </div>
      <div id="table-wrap">
        <div id="table-ph">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2">
            <rect x="3" y="3" width="18" height="18" rx="2"/>
            <path d="M3 9h18M3 15h18M9 3v18"/>
          </svg>
          <span>Run a query to see results</span>
        </div>
      </div>
      <div id="log-wrap"></div>
    </div>
  </div>
</div>

<div id="status-bar">
  <span>Host: <span class="seg-val" id="st-host">&#8212;</span></span>
  <span>DB: <span class="seg-val" id="st-db">&#8212;</span></span>
  <span>User: <span class="seg-val" id="st-user">&#8212;</span></span>
  <span id="st-last">
    Last: <span class="seg-val" id="st-elapsed">&#8212;</span>
    &nbsp;|&nbsp; Rows: <span class="seg-val" id="st-rows">&#8212;</span>
  </span>
</div>

<div id="modal-overlay">
  <div id="modal-box">
    <h2>Connect to SAP HANA</h2>
    <div class="field-row">
      <div class="field" style="flex:3">
        <label>Host</label>
        <input id="inp-host" type="text" value="hec45v258553.us1.hec.sap.biz" spellcheck="false"/>
      </div>
      <div class="field" style="flex:1">
        <label>Port</label>
        <input id="inp-port" type="number" value="30241"/>
      </div>
    </div>
    <div class="field">
      <label>Database</label>
      <input id="inp-db" type="text" value="HP4" spellcheck="false"/>
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

<div id="toast"></div>

<script>
// ── State ────────────────────────────────────────────────────────────────────
var _connected = false;
var _cols = [], _rows = [], _sortCol = -1, _sortAsc = true;
var _allScripts = [];
var _selectedScript = null;
var NUM_RE = /^-?\d+(\.\d+)?([eE][+-]?\d+)?$/;

// ── Helpers ──────────────────────────────────────────────────────────────────
function $(id)          { return document.getElementById(id); }
function val(id)        { return $(id).value; }
function show(id)       { var e=$(id); if(e) e.style.display=''; }
function hide(id)       { var e=$(id); if(e) e.style.display='none'; }
function dot(cls)       { $('conn-dot').className = cls; }
function setErr(msg)    { $('modal-error').textContent = msg; }
function setBusy(b)     { $('btn-conn').disabled = b; $('modal-spinner').style.display = b?'block':'none'; }
function esc(s)         { return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
function toast(msg)     { var t=$('toast'); t.textContent=msg; t.classList.add('show'); setTimeout(function(){ t.classList.remove('show'); },1800); }
function log(msg, type) { var w=$('log-wrap'),d=document.createElement('div'); d.className='log-entry log-'+type; d.textContent='['+new Date().toLocaleTimeString()+']  '+msg; w.appendChild(d); w.scrollTop=w.scrollHeight; }
function getSQL()       { return $('sql-editor').value; }
function setSQL(s)      { $('sql-editor').value = s; }

async function post(url, body) {
  var r = await fetch(url, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
  return r.json();
}

// ── Event listeners ──────────────────────────────────────────────────────────
$('inp-user').addEventListener('keydown', function(e){ if(e.key==='Enter') $('inp-pass').focus(); });
$('inp-pass').addEventListener('keydown', function(e){ if(e.key==='Enter') doConnect(); });
$('sql-editor').addEventListener('keydown', function(e){
  if (e.key==='F5' || (e.ctrlKey && e.key==='Enter')) { e.preventDefault(); runQuery(); }
  if (e.key==='Tab') { e.preventDefault(); var t=e.target, s=t.selectionStart; t.value=t.value.substring(0,s)+'  '+t.value.substring(t.selectionEnd); t.selectionStart=t.selectionEnd=s+2; }
});
document.addEventListener('keydown', function(e){ if(e.key==='F5'){ e.preventDefault(); runQuery(); } });
$('inp-user').focus();

// ── Connect ──────────────────────────────────────────────────────────────────
async function doConnect() {
  setErr(''); setBusy(true);
  try {
    var r = await post('/api/connect', {
      host: val('inp-host'), port: val('inp-port'),
      database: val('inp-db'), user: val('inp-user'), password: val('inp-pass')
    });
    if (r.ok) onConnected(r.info); else setErr(r.error);
  } catch(e) { setErr('Request failed: ' + e.message); }
  finally { setBusy(false); }
}

function onConnected(info) {
  _connected = true;
  hide('modal-overlay'); show('btn-disconnect');
  $('btn-run').disabled = false;
  dot('on');
  $('conn-label').textContent = info.user + '@' + info.host + ':' + info.port;
  $('st-host').textContent = info.host + ':' + info.port;
  $('st-db').textContent   = info.database;
  $('st-user').textContent = info.user;
  log('Connected to ' + info.host + ':' + info.port + '  DB=' + info.database + '  User=' + info.user, 'info');
  $('sql-editor').focus();
  // Reveal the Mini Checks toggle and load script list
  var tog = $('btn-scripts-toggle');
  tog.style.display = 'inline-flex';
  loadScriptList();
}

async function doDisconnect() {
  await post('/api/disconnect', {});
  _connected = false;
  $('btn-run').disabled = true;
  hide('btn-disconnect'); dot('off');
  $('conn-label').textContent = 'Not connected';
  ['st-host','st-db','st-user'].forEach(function(id){ $(id).textContent = '—'; });
  hide('st-last'); setErr('');
  log('Disconnected.', 'warn');
  $('inp-pass').value = '';
  // Hide scripts pane and toggle
  $('scripts-pane').classList.remove('visible');
  $('btn-scripts-toggle').style.display = 'none';
  $('btn-scripts-toggle').classList.remove('active');
  show('modal-overlay');
}

// ── Mini Checks sidebar ──────────────────────────────────────────────────────
async function loadScriptList() {
  try {
    var r = await fetch('/api/scripts');
    var data = await r.json();
    _allScripts = data.scripts || [];
    $('scripts-count').textContent = _allScripts.length;
    renderScriptList(_allScripts);
  } catch(e) {
    log('Could not load script list: ' + e.message, 'err');
  }
}

function scriptDisplayName(fname) {
  // Strip extension and replace underscores/dashes with spaces for readability
  var name = fname.replace(/\.(sql|txt)$/i, '');
  // Extract version suffix if present (e.g. "_2.00.040+")
  var m = name.match(/^(.*?)(_\d+\.\d+.*)?$/);
  var title = m[1].replace(/_/g, ' ');
  var ver = m[2] ? m[2].replace(/_/g, ' ').trim() : '';
  return {title: title, ver: ver, full: fname};
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
    rb.type = 'radio';
    rb.name = 'script';
    rb.value = fname;
    rb.checked = (fname === _selectedScript);
    rb.id = 'rb_' + fname.replace(/[^a-z0-9]/gi, '_');

    var lbl = document.createElement('label');
    lbl.htmlFor = rb.id;
    lbl.className = 'script-name';
    lbl.innerHTML = esc(info.title) + (info.ver ? '<em>' + esc(info.ver) + '</em>' : '');
    lbl.style.cursor = 'pointer';

    item.appendChild(rb);
    item.appendChild(lbl);

    item.addEventListener('click', function(e) {
      if (e.target === rb) return; // native radio handles itself
      rb.checked = true;
      selectScript(fname, item);
    });
    rb.addEventListener('change', function() {
      if (rb.checked) selectScript(fname, item);
    });

    list.appendChild(item);
  });
}

function selectScript(fname, itemEl) {
  _selectedScript = fname;
  // Update visual selection
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
  var pane = $('scripts-pane');
  var btn  = $('btn-scripts-toggle');
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
      log('Loaded: ' + r.filename, 'info');
      toast('Script loaded into editor');
      $('sql-editor').focus();
    } else {
      log('Load error: ' + r.error, 'err');
      toast('Error: ' + r.error);
    }
  } catch(e) {
    log('Request failed: ' + e.message, 'err');
  } finally {
    $('btn-load-script').disabled = false;
  }
}

// ── Execute ──────────────────────────────────────────────────────────────────
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
        log('OK  ' + r.rows.length + ' row(s) in ' + r.elapsed + 's' + cap, r.capped ? 'warn' : 'ok');
        $('st-elapsed').textContent  = r.elapsed + 's';
        $('st-rows').textContent     = r.rows.length + (r.capped ? ' (cap)' : '');
        $('result-stat').textContent = r.rows.length + ' row(s)' + (r.capped?' ⚠':'') + ' \xb7 ' + r.elapsed + 's';
        show('st-last');
      } else {
        clearTableArea('Statement executed — ' + r.rowcount + ' row(s) affected');
        log('OK  ' + r.rowcount + ' row(s) affected in ' + r.elapsed + 's', 'ok');
        $('st-elapsed').textContent  = r.elapsed + 's';
        $('st-rows').textContent     = r.rowcount + ' affected';
        $('result-stat').textContent = r.rowcount + ' affected \xb7 ' + r.elapsed + 's';
        show('st-last');
      }
    } else {
      log('ERROR  ' + r.error, 'err');
      $('result-stat').textContent = 'ERROR';
    }
  } catch(e) { log('Request failed: ' + e.message, 'err'); }
  finally {
    btn.disabled = false;
    btn.innerHTML = '&#9654; Run <kbd>F5</kbd>';
  }
}

// ── Table ────────────────────────────────────────────────────────────────────
function renderTable(cols, rows) {
  _cols = cols; _rows = rows; _sortCol = -1; _sortAsc = true;
  _paint(cols, rows);
  $('btn-csv').disabled = false;
}

function _paint(cols, rows) {
  var tbl = document.createElement('table');
  tbl.id = 'result-table';
  var thead = tbl.createTHead(), hr = thead.insertRow();
  cols.forEach(function(c, i) {
    var th = document.createElement('th');
    th.innerHTML = esc(c) + ' <span class="si" id="si'+i+'">⇅</span>';
    th.onclick = function(){ sortBy(i); };
    hr.appendChild(th);
  });
  var tb = tbl.createTBody();
  rows.forEach(function(row) {
    var tr = tb.insertRow();
    row.forEach(function(val) {
      var td = tr.insertCell();
      if (val === '' || val === null) { td.textContent = 'NULL'; td.className = 'nul'; }
      else { td.textContent = val; if (NUM_RE.test(val)) td.className = 'num'; }
    });
  });
  var w = $('table-wrap');
  w.innerHTML = ''; w.appendChild(tbl);
}

function sortBy(col) {
  if (_sortCol === col) _sortAsc = !_sortAsc; else { _sortCol = col; _sortAsc = true; }
  var sorted = _rows.slice().sort(function(a, b) {
    var av = a[col] != null ? a[col] : '', bv = b[col] != null ? b[col] : '';
    var an = parseFloat(av), bn = parseFloat(bv);
    var c = (!isNaN(an) && !isNaN(bn)) ? an - bn : av.localeCompare(bv);
    return _sortAsc ? c : -c;
  });
  _paint(_cols, sorted);
  _cols.forEach(function(_, i) {
    var si = $('si'+i);
    if (si) si.textContent = i===col ? (_sortAsc?'↑':'↓') : '⇅';
  });
}

function clearTableArea(msg) {
  _cols = []; _rows = []; $('btn-csv').disabled = true;
  $('table-wrap').innerHTML = '<div id="table-ph"><span style="color:var(--muted)">' + esc(msg) + '</span></div>';
}

function clearResults() {
  clearTableArea('Run a query to see results');
  $('result-stat').textContent = ''; hide('st-last');
}

// ── Editor helpers ───────────────────────────────────────────────────────────
function clearEditor() { setSQL(''); $('sql-editor').focus(); }
function copySQL()     { navigator.clipboard.writeText(getSQL()).then(function(){ toast('SQL copied!'); }); }
function exportCSV() {
  if (!_cols.length) return;
  function q(v) { return '"' + String(v).replace(/"/g,'""') + '"'; }
  var lines = [_cols.map(q).join(',')].concat(_rows.map(function(r){ return r.map(q).join(','); }));
  var a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([lines.join('\r\n')], {type:'text/csv'}));
  a.download = 'hana_result.csv'; a.click(); toast('CSV downloaded');
}
</script>
</body>
</html>
"""


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    host, port = "127.0.0.1", 5000
    server = ThreadingHTTPServer((host, port), Handler)
    url = f"http://{host}:{port}"
    print(f"HANA SQL Console running at {url}  (Ctrl+C to stop)")
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
