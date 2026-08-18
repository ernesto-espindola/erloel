import sys
import os

# Add lib\ folder next to this script so --target installed packages are found
_lib = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib")
if os.path.isdir(_lib) and _lib not in sys.path:
    sys.path.insert(0, _lib)

import time
from dataclasses import dataclass
from typing import Any

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import (
    Button, DataTable, Footer, Header,
    Input, Label, LoadingIndicator, RichLog, Static, TextArea,
)
from textual import work

from hdbcli import dbapi


@dataclass
class ConnectionCredentials:
    host: str = "hec45v258553.us1.hec.sap.biz"
    port: int = 30241
    database: str = "HP4"
    user: str = ""
    password: str = ""


class LoginScreen(ModalScreen):
    DEFAULT_CSS = """
    LoginScreen {
        align: center middle;
    }
    #login_dialog {
        width: 62;
        height: auto;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }
    #login_title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
        color: $primary;
    }
    .login_label {
        margin-top: 1;
    }
    #login_dialog Input {
        margin-bottom: 0;
    }
    #login_buttons {
        margin-top: 1;
        height: 3;
    }
    #btn_connect {
        width: 1fr;
        margin-right: 1;
    }
    #btn_quit {
        width: 1fr;
    }
    #login_loading {
        height: 1;
        margin-top: 1;
        display: none;
    }
    #login_error {
        color: $error;
        height: 1;
        margin-top: 1;
        display: none;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="login_dialog"):
            yield Label("SAP HANA SQL Console", id="login_title")
            yield Label("Host", classes="login_label")
            yield Input(value="hec45v258553.us1.hec.sap.biz", id="inp_host")
            yield Label("Port", classes="login_label")
            yield Input(value="30241", id="inp_port")
            yield Label("User", classes="login_label")
            yield Input(placeholder="Username", id="inp_user")
            yield Label("Password", classes="login_label")
            yield Input(placeholder="Password", password=True, id="inp_password")
            with Horizontal(id="login_buttons"):
                yield Button("Connect", variant="primary", id="btn_connect")
                yield Button("Quit", variant="default", id="btn_quit")
            yield LoadingIndicator(id="login_loading")
            yield Label("", id="login_error")

    def on_mount(self) -> None:
        self.query_one("#inp_user", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "inp_password":
            self._attempt_connect()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_connect":
            self._attempt_connect()
        elif event.button.id == "btn_quit":
            self.app.exit()

    def _attempt_connect(self) -> None:
        user = self.query_one("#inp_user", Input).value.strip()
        password = self.query_one("#inp_password", Input).value
        host = self.query_one("#inp_host", Input).value.strip()
        port_str = self.query_one("#inp_port", Input).value.strip()

        error_label = self.query_one("#login_error", Label)

        if not user or not password:
            error_label.update("User and password are required.")
            error_label.display = True
            return

        try:
            port = int(port_str)
        except ValueError:
            error_label.update("Port must be a number.")
            error_label.display = True
            return

        error_label.display = False
        self.query_one("#login_loading").display = True
        self.query_one("#btn_connect", Button).disabled = True

        creds = ConnectionCredentials(host=host, port=port, user=user, password=password)
        self._do_connect(creds)

    @work(thread=True)
    def _do_connect(self, creds: ConnectionCredentials) -> None:
        try:
            conn = dbapi.connect(
                address=creds.host,
                port=creds.port,
                user=creds.user,
                password=creds.password,
            )
            self.app.call_from_thread(self._on_success, creds, conn)
        except Exception as exc:
            self.app.call_from_thread(self._on_failure, str(exc))

    def _on_success(self, creds: ConnectionCredentials, conn: Any) -> None:
        self.query_one("#login_loading").display = False
        self.dismiss((creds, conn))

    def _on_failure(self, message: str) -> None:
        self.query_one("#login_loading").display = False
        self.query_one("#btn_connect", Button).disabled = False
        error_label = self.query_one("#login_error", Label)
        short = message[:120] + "..." if len(message) > 120 else message
        error_label.update(short)
        error_label.display = True


class StatusBar(Static):
    DEFAULT_CSS = """
    StatusBar {
        dock: bottom;
        height: 1;
        background: $primary-darken-2;
        color: $text;
        padding: 0 1;
    }
    """

    def update_status(self, text: str) -> None:
        self.update(text)


class HanaApp(App):
    TITLE = "HANA SQL Console"
    BINDINGS = [
        Binding("f5", "run_query", "Run", priority=True),
        Binding("ctrl+r", "run_query", "Run", priority=True),
        Binding("ctrl+l", "clear_results", "Clear Results"),
        Binding("ctrl+n", "new_query", "New Query"),
    ]
    DEFAULT_CSS = """
    #main_pane {
        height: 1fr;
    }
    #query_editor {
        width: 2fr;
        height: 100%;
        border: tall $primary;
    }
    #results_pane {
        layout: vertical;
        width: 3fr;
        height: 100%;
    }
    #result_table {
        height: 1fr;
        border: tall $surface;
    }
    #result_log {
        height: 7;
        border: tall $surface-darken-1;
        background: $surface;
    }
    """

    def __init__(self):
        super().__init__()
        self._conn = None
        self._creds: ConnectionCredentials | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="main_pane"):
            yield TextArea(
                "-- Paste or type SQL here\n-- F5 or Ctrl+R to execute\n",
                language="sql",
                id="query_editor",
            )
            with Vertical(id="results_pane"):
                yield DataTable(
                    id="result_table",
                    zebra_stripes=True,
                    cursor_type="row",
                )
                yield RichLog(id="result_log", markup=True, highlight=True)
        yield StatusBar("Not connected", id="status_bar")
        yield Footer()

    @work
    async def on_mount(self) -> None:
        result = await self.push_screen_wait(LoginScreen())
        if result is None:
            self.exit()
            return
        creds, conn = result
        self._creds = creds
        self._conn = conn
        status = self.query_one("#status_bar", StatusBar)
        status.update_status(
            f"Connected: {creds.host}:{creds.port} ({creds.database})  |  User: {creds.user}"
        )
        log = self.query_one("#result_log", RichLog)
        log.write(
            f"[green]Connected[/green] to [bold]{creds.host}:{creds.port}[/bold] "
            f"DB=[bold]{creds.database}[/bold] as [bold]{creds.user}[/bold]"
        )

    def action_run_query(self) -> None:
        if self._conn is None:
            self.notify("Not connected to HANA.", severity="error")
            return
        sql = self.query_one("#query_editor", TextArea).text.strip()
        if not sql or sql.startswith("--"):
            sql_lines = [ln for ln in sql.splitlines() if not ln.strip().startswith("--")]
            sql = "\n".join(sql_lines).strip()
        if not sql:
            self.notify("No SQL to execute.", severity="warning")
            return
        sql = sql.rstrip(";").strip()
        self._execute_query(sql)

    @work(thread=True, exclusive=True)
    def _execute_query(self, sql: str) -> None:
        start = time.monotonic()
        try:
            cursor = self._conn.cursor()
            cursor.execute(sql)
            elapsed = time.monotonic() - start
            if cursor.description:
                columns = [d[0] for d in cursor.description]
                rows = cursor.fetchall()
                self.call_from_thread(self._display_results, columns, rows, elapsed)
            else:
                rowcount = cursor.rowcount
                self.call_from_thread(self._display_rowcount, rowcount, elapsed)
            cursor.close()
        except Exception as exc:
            elapsed = time.monotonic() - start
            self.call_from_thread(self._display_error, str(exc), elapsed)

    def _display_results(self, columns: list, rows: list, elapsed: float) -> None:
        table = self.query_one("#result_table", DataTable)
        log = self.query_one("#result_log", RichLog)
        table.clear(columns=True)
        table.add_columns(*columns)
        safe_rows = [
            tuple("" if v is None else str(v)[:200] for v in row)
            for row in rows
        ]
        table.add_rows(safe_rows)
        msg = f"[green]OK[/green]  {len(rows)} row(s) in {elapsed:.3f}s"
        if len(rows) >= 5000:
            msg += "  [yellow]Warning: result capped at 5000 rows[/yellow]"
        log.write(msg)
        status = self.query_one("#status_bar", StatusBar)
        status.update_status(
            f"Connected: {self._creds.host}:{self._creds.port} ({self._creds.database})"
            f"  |  User: {self._creds.user}"
            f"  |  Last: {elapsed:.3f}s  |  {len(rows)} rows"
        )

    def _display_rowcount(self, rowcount: int, elapsed: float) -> None:
        table = self.query_one("#result_table", DataTable)
        log = self.query_one("#result_log", RichLog)
        table.clear(columns=True)
        log.write(f"[green]OK[/green]  {rowcount} row(s) affected in {elapsed:.3f}s")
        status = self.query_one("#status_bar", StatusBar)
        status.update_status(
            f"Connected: {self._creds.host}:{self._creds.port} ({self._creds.database})"
            f"  |  User: {self._creds.user}"
            f"  |  Last: {elapsed:.3f}s  |  {rowcount} affected"
        )

    def _display_error(self, message: str, elapsed: float) -> None:
        log = self.query_one("#result_log", RichLog)
        log.write(f"[red bold]ERROR[/red bold]  {message}")
        self.notify(message[:120], title="Query Error", severity="error")
        status = self.query_one("#status_bar", StatusBar)
        status.update_status(
            f"Connected: {self._creds.host}:{self._creds.port} ({self._creds.database})"
            f"  |  User: {self._creds.user}"
            f"  |  Last: {elapsed:.3f}s  |  ERROR"
        )

    def action_clear_results(self) -> None:
        self.query_one("#result_table", DataTable).clear(columns=True)
        self.query_one("#result_log", RichLog).clear()

    def action_new_query(self) -> None:
        self.query_one("#query_editor", TextArea).clear()
        self.query_one("#query_editor", TextArea).focus()


if __name__ == "__main__":
    HanaApp().run()
