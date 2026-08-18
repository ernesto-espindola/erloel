"""
SAP HANA Full Analysis Report Generator v2.0
- Streams directly via Anthropic SDK through local HAI proxy (no CLI timeout)
- Real-time progress bar based on output tokens
- Handles large health check files
- RDE LAC legend footer
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import os
import re
import json
import tempfile
from datetime import datetime
from pathlib import Path
import anthropic

# ── Config ────────────────────────────────────────────────────────────────────
WORKING_DIR   = Path(r"C:\Users\I522148\OneDrive - SAP SE\SWAT\AI\Claude\working directory")
TEMPLATE_FILE = WORKING_DIR / "HANA_HealthCheck_Prompt_Template.md"
RELEASE_FILE  = WORKING_DIR / "HANA_latest_release.txt"
OUTPUT_DIR    = WORKING_DIR / "Results"
EDGE_PATH     = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
SETTINGS_FILE = Path(r"C:\Users\I522148\.claude\settings.json")

MAX_FILE_KB         = 800
EXPECTED_OUT_TOKENS = 40000   # for progress bar scaling
MAX_OUTPUT_TOKENS   = 64000

# ── Colors ────────────────────────────────────────────────────────────────────
PRIMARY_BLUE = "#0057a8"
DARK_BLUE    = "#003366"
ACCENT_CYAN  = "#00b4e6"
PAGE_BG      = "#e8f4fd"
WHITE        = "#ffffff"
LIGHT_BLUE   = "#f0f7ff"
OK_GREEN     = "#5cb85c"
WARN_ORANGE  = "#f0ad4e"
DANGER_RED   = "#d9534f"


def load_text(path: Path) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def load_proxy_config() -> tuple[str, str]:
    """Return (base_url, auth_token) from Claude settings.json."""
    try:
        cfg = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        env = cfg.get("env", {})
        base_url = env.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
        token    = env.get("ANTHROPIC_AUTH_TOKEN", "")
        model    = env.get("ANTHROPIC_MODEL", "claude-sonnet-latest")
        return base_url, token, model
    except Exception:
        return "https://api.anthropic.com", "", "claude-sonnet-latest"


def ensure_interactive_html(html: str) -> str:
    """Inject toggleSection + nav + tooltip JS if script block is missing."""
    if "<script" in html.lower():
        return html

    FIX_JS = """
<script>
function toggleSection(id) {
  var body = document.getElementById('body-' + id);
  var chev = document.getElementById('chev-' + id);
  if (!body) return;
  var isOpen = body.classList.contains('open');
  body.classList.toggle('open', !isOpen);
  if (chev) chev.textContent = isOpen ? '▼' : '▲';
}
document.addEventListener('DOMContentLoaded', function() {
  document.querySelectorAll('.nav-pill').forEach(function(pill) {
    pill.addEventListener('click', function() {
      var m = (pill.getAttribute('onclick') || '').match(/'([^']+)'/);
      var el = m && document.getElementById(m[1]);
      if (el) el.scrollIntoView({behavior:'smooth'});
      document.querySelectorAll('.nav-pill').forEach(function(p){ p.classList.remove('active'); });
      pill.classList.add('active');
    });
  });
  var tip = document.getElementById('tooltip');
  if (tip) {
    document.querySelectorAll('.term').forEach(function(el) {
      el.addEventListener('mousemove', function(e) {
        var def = window.GLOSSARY && window.GLOSSARY[el.dataset.term];
        if (!def) return;
        tip.innerHTML = '<strong style="color:#a8d0f0">' + el.dataset.term + '</strong><br>' + def;
        tip.style.display = 'block';
        tip.style.left = (e.clientX+14) + 'px';
        tip.style.top  = (e.clientY+14) + 'px';
      });
      el.addEventListener('mouseleave', function(){ tip.style.display='none'; });
    });
  }
});
</script>
"""
    if "</body>" in html:
        html = html.replace("</body>", FIX_JS + "</body>", 1)
    else:
        html += "\n</div></div>\n" + FIX_JS + "\n</body>\n</html>"
    return html


    for pat in [r"\[environment\].*?SID[:\s]+([A-Z0-9]{3})",
                r"SID[:\s]+([A-Z0-9]{3})"]:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(1).upper()
    return "UNKNOWN"


def extract_sid(text: str) -> str:
    for pat in [r"\[environment\].*?SID[:\s]+([A-Z0-9]{3})",
                r"SID[:\s]+([A-Z0-9]{3})"]:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(1).upper()
    return "UNKNOWN"


def build_prompt(template: str, release_info: str, health_check_text: str) -> str:
    prompt = template.replace(
        "<<< REPLACE THIS LINE WITH THE FULL HANA HEALTH CHECK SCRIPT OUTPUT >>>",
        health_check_text,
    )
    if release_info:
        prompt += f"\n\n[HANA Latest Release Reference]\n{release_info}\n"
    return prompt


# ── App ───────────────────────────────────────────────────────────────────────
class AnalysisApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SAP HANA Full Analysis Report Generator v2.0")
        self.configure(bg=PAGE_BG)
        self.minsize(920, 700)
        self.resizable(True, True)

        self._selected_file: Path | None = None
        self._last_output_file: Path | None = None
        self._status_var   = tk.StringVar(value="Ready — select a health check file to begin.")
        self._progress_var = tk.IntVar(value=0)
        self._pct_var      = tk.StringVar(value="")
        self._cancel_event = threading.Event()

        base_url, token, model = load_proxy_config()
        self._base_url = base_url
        self._token    = token
        self._model    = model

        self._build_ui()

    # ─────────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        self._build_header()
        self._build_content()
        self._build_footer()

    def _build_header(self):
        hdr = tk.Frame(self, bg=DARK_BLUE)
        hdr.pack(fill="x")

        left = tk.Frame(hdr, bg=DARK_BLUE)
        left.pack(side="left", padx=20, pady=12)
        tk.Label(left, text="SAP HANA Full Analysis Report Generator",
                 bg=DARK_BLUE, fg=WHITE, font=("Segoe UI", 15, "bold")).pack(anchor="w")
        tk.Label(left, text=f"Powered by Anthropic SDK  |  v2.0  |  {self._model}",
                 bg=DARK_BLUE, fg="#a8d0f0", font=("Segoe UI", 8)).pack(anchor="w")

        tk.Label(hdr, text="RDE LAC", bg="#e65c00", fg=WHITE,
                 font=("Segoe UI", 9, "bold"), padx=12, pady=4).pack(
                     side="right", padx=20, pady=14)

    def _build_content(self):
        content = tk.Frame(self, bg=PAGE_BG, padx=20, pady=14)
        content.pack(fill="both", expand=True)

        # File selection
        fframe = self._lframe(content, "Health Check Input File")
        fframe.pack(fill="x", pady=(0, 10))

        self._file_label = tk.Label(fframe, text="No file selected",
                                    bg=WHITE, fg="#888", font=("Segoe UI", 9), anchor="w")
        self._file_label.pack(side="left", fill="x", expand=True)

        self._size_badge = tk.Label(fframe, text="", bg=LIGHT_BLUE, fg=PRIMARY_BLUE,
                                    font=("Segoe UI", 8, "bold"), padx=8, pady=2)
        self._size_badge.pack(side="left", padx=(6, 8))

        tk.Button(fframe, text="Browse…", command=self._on_browse,
                  bg=PRIMARY_BLUE, fg=WHITE, font=("Segoe UI", 9, "bold"),
                  relief="flat", padx=14, cursor="hand2").pack(side="right")

        # Preview
        pframe = self._lframe(content, "File Preview  (first 60 lines)")
        pframe.pack(fill="both", expand=True, pady=(0, 10))
        self._preview_text = scrolledtext.ScrolledText(
            pframe, height=10, font=("Consolas", 8),
            bg="#f8fbff", fg="#333", relief="flat", state="disabled", wrap="none")
        self._preview_text.pack(fill="both", expand=True)

        # Progress
        pgframe = self._lframe(content, "Generation Progress")
        pgframe.pack(fill="x", pady=(0, 10))

        row = tk.Frame(pgframe, bg=WHITE)
        row.pack(fill="x")
        self._progress = ttk.Progressbar(row, variable=self._progress_var,
                                          maximum=100, mode="determinate", length=100)
        self._progress.pack(side="left", fill="x", expand=True, padx=(0, 10))
        tk.Label(row, textvariable=self._pct_var, bg=WHITE, fg=PRIMARY_BLUE,
                 font=("Segoe UI", 10, "bold"), width=6).pack(side="left")

        self._phase_label = tk.Label(pgframe, text="", bg=WHITE, fg="#555",
                                     font=("Segoe UI", 8), anchor="w")
        self._phase_label.pack(fill="x", pady=(4, 0))

        # Log
        lframe = self._lframe(content, "Generation Log")
        lframe.pack(fill="x", pady=(0, 10))
        self._log_text = scrolledtext.ScrolledText(
            lframe, height=6, font=("Consolas", 8),
            bg="#f0f7ff", fg="#333", relief="flat", state="disabled", wrap="word")
        self._log_text.pack(fill="both", expand=True)

        # Buttons
        btn_frame = tk.Frame(content, bg=PAGE_BG)
        btn_frame.pack(fill="x")

        self._run_btn = tk.Button(btn_frame, text="▶   Generate Full Analysis Report",
                                   command=self._on_generate, bg=PRIMARY_BLUE, fg=WHITE,
                                   font=("Segoe UI", 11, "bold"), relief="flat",
                                   padx=24, pady=10, cursor="hand2", state="disabled")
        self._run_btn.pack(side="left")

        self._cancel_btn = tk.Button(btn_frame, text="■  Cancel",
                                      command=self._on_cancel, bg=DANGER_RED, fg=WHITE,
                                      font=("Segoe UI", 10), relief="flat",
                                      padx=14, pady=10, cursor="hand2", state="disabled")
        self._cancel_btn.pack(side="left", padx=(8, 0))

        self._open_btn = tk.Button(btn_frame, text="🌐  Open Last Report in Edge",
                                    command=self._on_open_last, bg=OK_GREEN, fg=WHITE,
                                    font=("Segoe UI", 10), relief="flat",
                                    padx=16, pady=10, cursor="hand2", state="disabled")
        self._open_btn.pack(side="left", padx=(8, 0))

    def _build_footer(self):
        footer = tk.Frame(self, bg=DARK_BLUE)
        footer.pack(fill="x", side="bottom")
        tk.Label(footer, textvariable=self._status_var, bg=DARK_BLUE, fg="#a8d0f0",
                 font=("Segoe UI", 8), anchor="w", padx=12).pack(
                     side="left", pady=4, fill="x", expand=True)
        tk.Label(footer, text="RDE LAC", bg=DARK_BLUE, fg=ACCENT_CYAN,
                 font=("Segoe UI", 8, "bold"), padx=16).pack(side="right", pady=4)

    def _lframe(self, parent, title):
        return tk.LabelFrame(parent, text=title, bg=WHITE, fg=DARK_BLUE,
                              font=("Segoe UI", 9, "bold"), padx=10, pady=8,
                              relief="flat", highlightbackground="#c8ddf0",
                              highlightthickness=1)

    # ─────────────────────────────────────────────────────────────────────────
    def _on_browse(self):
        initial = str(WORKING_DIR / "HANA Health Check Reports")
        path = filedialog.askopenfilename(
            title="Select HANA Health Check Output File",
            initialdir=initial if os.path.isdir(initial) else str(WORKING_DIR),
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if not path:
            return
        self._selected_file = Path(path)
        size_kb = self._selected_file.stat().st_size / 1024
        approx_tokens = int(size_kb * 1024 / 4)
        self._file_label.config(text=self._selected_file.name, fg=DARK_BLUE)
        self._size_badge.config(
            text=f"{size_kb:.0f} KB  ~{approx_tokens:,} tokens",
            bg=WARN_ORANGE if size_kb > MAX_FILE_KB * 0.75 else LIGHT_BLUE,
            fg=DARK_BLUE if size_kb > MAX_FILE_KB * 0.75 else PRIMARY_BLUE,
        )
        self._load_preview()
        if size_kb > MAX_FILE_KB:
            self._run_btn.config(state="disabled")
            self._set_status(f"File too large ({size_kb:.0f} KB) — max {MAX_FILE_KB} KB.")
            messagebox.showwarning("File Too Large",
                f"{self._selected_file.name}\n{size_kb:.0f} KB (~{approx_tokens:,} tokens)\n\n"
                f"Exceeds {MAX_FILE_KB} KB limit. Please select a smaller file.")
        else:
            self._run_btn.config(state="normal")
            self._set_status(f"Ready  |  {self._selected_file.name}  ({size_kb:.0f} KB)")

    def _load_preview(self):
        try:
            lines = load_text(self._selected_file).splitlines()[:60]
            preview = "\n".join(lines)
        except Exception as e:
            preview = f"Could not read file: {e}"
        self._preview_text.config(state="normal")
        self._preview_text.delete("1.0", "end")
        self._preview_text.insert("end", preview)
        self._preview_text.config(state="disabled")

    def _on_generate(self):
        if not self._selected_file or not self._selected_file.exists():
            messagebox.showerror("No File", "Please select a valid health check file.")
            return
        self._cancel_event.clear()
        self._run_btn.config(state="disabled")
        self._cancel_btn.config(state="normal")
        self._open_btn.config(state="disabled")
        self._log_clear()
        self._set_progress(0, "Starting…")
        self._set_status("Generating report via streaming API…")
        threading.Thread(target=self._run_generation, daemon=True).start()

    def _on_cancel(self):
        self._cancel_event.set()
        self._cancel_btn.config(state="disabled")
        self._set_status("Cancelling…")

    def _on_open_last(self):
        if self._last_output_file and self._last_output_file.exists():
            self._open_in_edge(self._last_output_file)
        else:
            messagebox.showinfo("No Report", "No report has been generated yet.")

    # ─────────────────────────────────────────────────────────────────────────
    # Generation — background thread using Anthropic SDK streaming
    # ─────────────────────────────────────────────────────────────────────────
    def _run_generation(self):
        try:
            health_check_text = load_text(self._selected_file)
            template          = load_text(TEMPLATE_FILE)
            release_info      = load_text(RELEASE_FILE) if RELEASE_FILE.exists() else ""

            sid = extract_sid(health_check_text)
            if sid == "UNKNOWN":
                sid = self._selected_file.stem.split("_")[0].upper()

            ts          = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = OUTPUT_DIR / f"{sid}_HANA_Analysis_Report_{ts}.html"
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

            prompt = build_prompt(template, release_info, health_check_text)

            self.after(0, self._log, f"File    : {self._selected_file.name}\n")
            self.after(0, self._log, f"Prompt  : {len(prompt):,} chars (~{len(prompt)//4:,} tokens)\n")
            self.after(0, self._log, f"Model   : {self._model}\n")
            self.after(0, self._log, f"Output  : {output_file.name}\n")
            self.after(0, self._set_progress, 5, "Connecting to proxy…")

            client = anthropic.Anthropic(
                base_url=self._base_url,
                api_key=self._token,
            )

            self.after(0, self._log, "Streaming response…\n")
            self.after(0, self._set_progress, 10, "Claude is generating the HTML report…")

            html_chunks    = []
            output_tokens  = 0
            start_time     = datetime.now()

            with client.messages.stream(
                model=self._model,
                max_tokens=MAX_OUTPUT_TOKENS,
                messages=[{"role": "user", "content": prompt}],
            ) as stream:
                for text_chunk in stream.text_stream:
                    if self._cancel_event.is_set():
                        break
                    html_chunks.append(text_chunk)
                    output_tokens += len(text_chunk) // 4  # rough token estimate
                    pct = min(10 + int(output_tokens / EXPECTED_OUT_TOKENS * 85), 95)
                    elapsed = int((datetime.now() - start_time).total_seconds())
                    elapsed_str = f"{elapsed // 60}m {elapsed % 60:02d}s"
                    self.after(0, self._set_progress, pct,
                               f"Generating…  ~{output_tokens:,} tokens  [{elapsed_str}]")

            if self._cancel_event.is_set():
                self.after(0, self._on_generation_error, "Cancelled by user.")
                return

            elapsed = int((datetime.now() - start_time).total_seconds())
            elapsed_str = f"{elapsed // 60}m {elapsed % 60:02d}s"
            self.after(0, self._log, f"Stream complete in {elapsed_str}\n")
            self.after(0, self._set_progress, 96, "Saving HTML file…")

            full_html = "".join(html_chunks).strip()
            full_html = re.sub(r"^```html\s*", "", full_html)
            full_html = re.sub(r"\s*```$",     "", full_html).strip()

            if not full_html.startswith("<"):
                raise ValueError(
                    "Response is not valid HTML.\n\nFirst 300 chars:\n" + full_html[:300]
                )

            full_html = ensure_interactive_html(full_html)

            output_file.write_text(full_html, encoding="utf-8")
            size_kb = output_file.stat().st_size // 1024
            self.after(0, self._log, f"Saved: {output_file.name}  ({size_kb} KB)\n")

            self._last_output_file = output_file
            self.after(0, self._on_generation_complete, output_file)

        except anthropic.APIStatusError as e:
            self.after(0, self._on_generation_error,
                       f"API error {e.status_code}: {e.message}")
        except Exception as e:
            self.after(0, self._on_generation_error, str(e))

    def _on_generation_complete(self, output_file: Path):
        self._set_progress(100, "Complete!")
        self._run_btn.config(state="normal")
        self._cancel_btn.config(state="disabled")
        self._open_btn.config(state="normal")
        self._log(f"\n✔  Report ready: {output_file}\n")
        self._set_status(f"Done — {output_file.name}")
        self._open_in_edge(output_file)

    def _on_generation_error(self, msg: str):
        self._set_progress(0, "")
        self._run_btn.config(state="normal")
        self._cancel_btn.config(state="disabled")
        self._log(f"\n✘  Error: {msg}\n")
        self._set_status("Error — see log.")
        messagebox.showerror("Generation Failed", msg)

    # ─────────────────────────────────────────────────────────────────────────
    def _open_in_edge(self, path: Path):
        import subprocess
        try:
            subprocess.Popen([EDGE_PATH, str(path)])
            self._set_status(f"Opened in Edge: {path.name}")
        except Exception as e:
            messagebox.showerror("Could not open Edge", str(e))

    def _set_progress(self, pct: int, phase: str):
        self._progress_var.set(pct)
        self._pct_var.set(f"{pct}%" if pct > 0 else "")
        self._phase_label.config(text=phase)

    def _log(self, msg: str):
        self._log_text.config(state="normal")
        self._log_text.insert("end", msg)
        self._log_text.see("end")
        self._log_text.config(state="disabled")

    def _log_clear(self):
        self._log_text.config(state="normal")
        self._log_text.delete("1.0", "end")
        self._log_text.config(state="disabled")

    def _set_status(self, msg: str):
        self._status_var.set(msg)


if __name__ == "__main__":
    app = AnalysisApp()
    app.mainloop()
