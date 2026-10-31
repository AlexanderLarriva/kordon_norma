import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


def get_app_path():
    # PyInstaller extracts bundled app.py into _MEIPASS. In source mode,
    # app.py is located next to this launcher.
    app_root = Path(
        getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)
    )
    return app_root, app_root / "app.py"


def run_streamlit_child(app_path, port):
    from streamlit.web import cli as stcli

    sys.argv = [
        "streamlit",
        "run",
        str(app_path),
        "--server.headless=true",
        "--server.address=127.0.0.1",
        f"--server.port={port}",
        "--global.developmentMode=false",
        "--browser.gatherUsageStats=false",
    ]
    sys.exit(stcli.main())


def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_for_server(process, port, timeout=45):
    url = f"http://127.0.0.1:{port}/_stcore/health"
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(
                f"Сервер Смена-Т завершился с кодом {process.returncode}."
            )

        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError, OSError):
            time.sleep(0.25)

    raise RuntimeError("Не удалось запустить сервер Смена-Т за отведённое время.")


def show_error(message):
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Смена-Т", message)
        root.destroy()
    except Exception:
        pass


def stop_server(process):
    if process.poll() is not None:
        return

    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def main():
    app_root, app_path = get_app_path()

    if "--streamlit-child" in sys.argv:
        index = sys.argv.index("--streamlit-child")
        port = int(sys.argv[index + 1])
        run_streamlit_child(app_path, port)
        return

    try:
        import webview
    except Exception as exc:
        show_error(
            "Не удалось загрузить компонент окна приложения.\n\n"
            f"{exc}"
        )
        return

    port = find_free_port()

    if getattr(sys, "frozen", False):
        command = [sys.executable, "--streamlit-child", str(port)]
    else:
        command = [
            sys.executable,
            str(Path(__file__).resolve()),
            "--streamlit-child",
            str(port),
        ]

    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    server_process = subprocess.Popen(
        command,
        cwd=str(app_root),
        creationflags=creationflags,
    )

    try:
        wait_for_server(server_process, port)
        webview.create_window(
            "Смена-Т",
            f"http://127.0.0.1:{port}",
            width=1280,
            height=850,
            min_size=(900, 650),
        )
        webview.start()
    except Exception as exc:
        show_error(f"Не удалось открыть Смена-Т.\n\n{exc}")
    finally:
        stop_server(server_process)


if __name__ == "__main__":
    main()
