import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import os
import subprocess
import re
import tempfile
from datetime import datetime
from pathlib import Path

WORKING_DIR = Path(r"C:\Users\I522148\OneDrive - SAP SE\SWAT\AI\Claude\working directory")
TEMPLATE_FILE = WORKING_DIR / "HANA_HealthCheck_Prompt_Template.md"
RELEASE_FILE  = WORKING_DIR / "HANA_latest_release.txt"
OUTPUT_DIR    = WORKING_DIR / "Results"
EDGE_PATH     = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
CLAUDE_CLI    = r"C:\Users\I522148\.local\bin\claude.exe"

PRIMARY_BLUE = "#0057a8"
DARK_BLUE    = "#003366"
PAGE_BG      = "#e8f4fd"
WHITE        = "#ffffff"
LIGHT_BLUE   = "#f0f7ff"


def load_text(path: Path) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def extract_sid(text: str) -> str:
    m = re.search(r"\[environment\].*?SID[:\s]+([A-Z0-9]{3})", text, re.IGNORECASE)
    if m:
        return m.group(1).upper()
    m = re.search(r"SID[:\s]+([A-Z0-9]{3})", text, re.IGNORECASE)
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


class HealthCheckApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SAP HANA Health Check Report Generator")
        self.configure(bg=PAGE_BG)
        self.minsize(820, 620)
        self.resizable(True, True)

        self._selected_file: Path | None = None
        self._status_var = tk.StringVar(value="Ready. Select a health check file to begin.")
        self._last_output_file: Path | None = None

        self._build_ui()

    def _build_ui(self):
        # ── Header ──────────────────────────────────────────────────────────
        header = tk.Frame(self, bg=DARK_BLUE)
        header.pack(fill="x")
        tk.Label(
            header,
            text="SAP HANA  Health Check Report Generator",
            bg=DARK_BLUE, fg=WHITE,
            font=("Segoe UI", 14, "bold"),
            pady=14, padx=20,
        ).pack(side="left")
        tk.Label(
            header,
            text="via Claude Code CLI",
            bg=DARK_BLUE, fg="#a8d0f0",
            font=("Segoe UI", 9),
            padx=20,
        ).pack(side="right", pady=14)

        content = tk.Frame(self, bg=PAGE_BG, padx=20, pady=16)
        content.pack(fill="both", expand=True)

        # ── File selection ───────────────────────────────────────────────────
        file_frame = tk.LabelFrame(
            content, text="Health Check File",
            bg=WHITE, fg=DARK_BLUE,
            font=("Segoe UI", 9, "bold"),
            padx=12, pady=10, relief="flat",
            highlightbackground="#c8ddf0", highlightthickness=1,
        )
        file_frame.pack(fill="x", pady=(0, 10))

        self._file_label = tk.Label(
            file_frame, text="No file selected",
            bg=WHITE, fg="#666",
            font=("Segoe UI", 9), anchor="w",
        )
        self._file_label.pack(side="left", fill="x", expand=True)

        tk.Button(
            file_frame, text="Browse…",
            command=self._on_browse,
            bg=PRIMARY_BLUE, fg=WHITE,
            font=("Segoe UI", 9),
            relief="flat", padx=14, cursor="hand2",
        ).pack(side="right")

        # ── Preview ──────────────────────────────────────────────────────────
        preview_frame = tk.LabelFrame(
            content, text="File Preview (first 60 lines)",
            bg=WHITE, fg=DARK_BLUE,
            font=("Segoe UI", 9, "bold"),
            padx=8, pady=8, relief="flat",
            highlightbackground="#c8ddf0", highlightthickness=1,
        )
        preview_frame.pack(fill="both", expand=True, pady=(0, 10))

        self._preview_text = scrolledtext.ScrolledText(
            preview_frame,
            height=12,
            font=("Consolas", 8),
            bg="#f8fbff", fg="#333",
            relief="flat", state="disabled", wrap="none",
        )
        self._preview_text.pack(fill="both", expand=True)

        # ── Log ──────────────────────────────────────────────────────────────
        log_frame = tk.LabelFrame(
            content, text="Generation Log",
            bg=WHITE, fg=DARK_BLUE,
            font=("Segoe UI", 9, "bold"),
            padx=8, pady=8, relief="flat",
            highlightbackground="#c8ddf0", highlightthickness=1,
        )
        log_frame.pack(fill="x", pady=(0, 10))

        self._log_text = scrolledtext.ScrolledText(
            log_frame,
            height=5,
            font=("Consolas", 8),
            bg="#f0f7ff", fg="#333",
            relief="flat", state="disabled", wrap="word",
        )
        self._log_text.pack(fill="both", expand=True)

        # ── Progress bar ─────────────────────────────────────────────────────
        self._progress = ttk.Progressbar(content, mode="indeterminate", length=400)
        self._progress.pack(fill="x", pady=(0, 8))

        # ── Buttons ──────────────────────────────────────────────────────────
        btn_frame = tk.Frame(content, bg=PAGE_BG)
        btn_frame.pack(fill="x")

        self._run_btn = tk.Button(
            btn_frame,
            text="▶  Generate HTML Report",
            command=self._on_generate,
            bg=PRIMARY_BLUE, fg=WHITE,
            font=("Segoe UI", 11, "bold"),
            relief="flat", padx=24, pady=10,
            cursor="hand2", state="disabled",
        )
        self._run_btn.pack(side="left")

        self._open_btn = tk.Button(
            btn_frame,
            text="🌐  Open Last Report in Edge",
            command=self._on_open_last,
            bg="#5cb85c", fg=WHITE,
            font=("Segoe UI", 10),
            relief="flat", padx=16, pady=10,
            cursor="hand2", state="disabled",
        )
        self._open_btn.pack(side="left", padx=(10, 0))

        # ── Status bar ───────────────────────────────────────────────────────
        status_bar = tk.Frame(self, bg=DARK_BLUE, height=24)
        status_bar.pack(fill="x", side="bottom")
        tk.Label(
            status_bar,
            textvariable=self._status_var,
            bg=DARK_BLUE, fg="#a8d0f0",
            font=("Segoe UI", 8),
            anchor="w", padx=12,
        ).pack(fill="x", pady=3)

    # ── Event handlers ────────────────────────────────────────────────────────
    def _on_browse(self):
        initial = str(WORKING_DIR / "HANA Health Check Reports")
        path = filedialog.askopenfilename(
            title="Select HANA Health Check Output File",
            initialdir=initial if os.path.isdir(initial) else str(WORKING_DIR),
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if path:
            self._selected_file = Path(path)
            size_kb = self._selected_file.stat().st_size / 1024
            approx_tokens = int(size_kb * 1024 / 4)
            label = f"{self._selected_file.name}  ({size_kb:.0f} KB  ~{approx_tokens:,} tokens)"
            self._file_label.config(text=label, fg=DARK_BLUE)
            self._load_preview()
            if size_kb > 400:
                self._run_btn.config(state="disabled")
                self._set_status(f"File too large ({size_kb:.0f} KB). Max ~400 KB. Choose a smaller file.")
                messagebox.showwarning(
                    "File Too Large",
                    f"{self._selected_file.name} is {size_kb:.0f} KB (~{approx_tokens:,} tokens).\n\n"
                    "This exceeds the context window. Please select a file under 400 KB.\n\n"
                    "Tip: HP4REY, HP4SVF (smaller ones), or Valuable_Customer files are fine."
                )
            else:
                self._run_btn.config(state="normal")
                self._set_status(f"File selected: {self._selected_file.name}  ({size_kb:.0f} KB)")

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
        self._run_btn.config(state="disabled")
        self._open_btn.config(state="disabled")
        self._log_clear()
        self._progress.start(10)
        self._set_status("Running claude CLI — this may take 1–3 minutes…")
        threading.Thread(target=self._run_generation, daemon=True).start()

    def _on_open_last(self):
        if self._last_output_file and self._last_output_file.exists():
            self._open_in_edge(self._last_output_file)
        else:
            messagebox.showinfo("No Report", "No report has been generated yet in this session.")

    # ── Generation (background thread) ───────────────────────────────────────
    def _run_generation(self):
        try:
            health_check_text = load_text(self._selected_file)
            template          = load_text(TEMPLATE_FILE)
            release_info      = load_text(RELEASE_FILE) if RELEASE_FILE.exists() else ""

            prompt = build_prompt(template, release_info, health_check_text)

            self.after(0, self._log, f"Health check file : {self._selected_file.name}\n")
            self.after(0, self._log, f"Prompt size       : {len(prompt):,} characters\n")
            self.after(0, self._log, "Calling claude CLI via stdin (print mode)...\n")

            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", suffix=".txt", delete=False
            ) as tmp:
                tmp.write(prompt)
                tmp_path = tmp.name

            try:
                with open(tmp_path, "r", encoding="utf-8") as stdin_f:
                    result = subprocess.run(
                        [CLAUDE_CLI, "-p", "--output-format", "text",
                         "--dangerously-skip-permissions"],
                        stdin=stdin_f,
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        timeout=600,
                    )
            finally:
                os.unlink(tmp_path)

            if result.returncode != 0:
                err = result.stderr.strip() or "Unknown error from claude CLI."
                raise RuntimeError(err)

            stdout = result.stdout.strip()

            # Case 1: Claude saved the file itself and told us the path
            saved_path_match = re.search(
                r"`?([A-Za-z]:[^\n`*]+\.html)`?", stdout, re.IGNORECASE
            )
            if saved_path_match and not stdout.lstrip().startswith("<"):
                found_path = Path(saved_path_match.group(1).strip())
                if found_path.exists():
                    self.after(0, self._log, f"Claude saved file at: {found_path}\n")
                    self.after(0, self._log, "Copying to Results folder...\n")
                    sid = extract_sid(health_check_text)
                    ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
                    output_file = OUTPUT_DIR / f"{sid}_HANA_Health_Check_Report_{ts}.html"
                    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
                    import shutil
                    shutil.copy2(found_path, output_file)
                    self._last_output_file = output_file
                    self.after(0, self._on_generation_complete, output_file)
                    return

            # Case 2: stdout is the raw HTML
            full_html = stdout
            full_html = re.sub(r"^```html\s*", "", full_html)
            full_html = re.sub(r"\s*```$",     "", full_html).strip()

            if not full_html.startswith("<"):
                raise ValueError(
                    "Response does not look like HTML.\n\n"
                    f"First 300 chars:\n{full_html[:300]}"
                )

            sid = extract_sid(health_check_text)
            ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = OUTPUT_DIR / f"{sid}_HANA_Health_Check_Report_{ts}.html"
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            output_file.write_text(full_html, encoding="utf-8")

            self._last_output_file = output_file
            self.after(0, self._on_generation_complete, output_file)

        except subprocess.TimeoutExpired:
            self.after(0, self._on_generation_error, "claude CLI timed out after 10 minutes.")
        except Exception as e:
            self.after(0, self._on_generation_error, str(e))

    def _on_generation_complete(self, output_file: Path):
        self._progress.stop()
        self._run_btn.config(state="normal")
        self._open_btn.config(state="normal")
        self._log(f"\n✔ Saved: {output_file}\n")
        self._set_status(f"Done — opening {output_file.name} in Edge…")
        self._open_in_edge(output_file)

    def _on_generation_error(self, msg: str):
        self._progress.stop()
        self._run_btn.config(state="normal")
        self._log(f"\n✘ Error: {msg}\n")
        self._set_status("Error during generation. See log.")
        messagebox.showerror("Generation Failed", msg)

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _open_in_edge(self, path: Path):
        try:
            subprocess.Popen([EDGE_PATH, str(path)])
            self._set_status(f"Opened in Edge: {path.name}")
        except Exception as e:
            messagebox.showerror("Could not open Edge", str(e))

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
    app = HealthCheckApp()
    app.mainloop()
