import sys
from pathlib import Path

from streamlit.web import cli as stcli


if __name__ == "__main__":
    # PyInstaller extracts bundled app.py into _MEIPASS. In source mode,
    # app.py is located next to this launcher.
    app_root = Path(
        getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)
    )
    app_path = app_root / "app.py"

    sys.argv = [
        "streamlit",
        "run",
        str(app_path),
        "--server.headless=false",
        "--global.developmentMode=false",
    ]
    sys.exit(stcli.main())
