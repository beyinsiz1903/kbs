"""Single entry-point dispatched by the `MODE` env var.

Modes:
  - server  (default)    Plain uvicorn — used in containers, dev, CI.
  - tray                 uvicorn in a thread + pystray icon (Windows desktop).
  - service              NT Service framework (Windows; admin install).

PyInstaller produces one `SyroceKBSAgent.exe`; the .exe checks MODE and
dispatches. `--installer` flag triggers the Inno Setup post-install hook
(register service + create shortcut).
"""
from __future__ import annotations

import logging
import os
import sys
import threading

# Ensure 'backend/' is on sys.path when launched from the project root.
_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

import log_setup
import single_instance


def _bootstrap_logging() -> None:
    log_path = log_setup.configure()
    logging.getLogger("kbs-bridge").info("Log dosyasi: %s", log_path)


def _mode() -> str:
    return (os.environ.get("MODE") or "server").strip().lower()


def _run_server_mode() -> None:
    import app_runtime
    app_runtime.run_blocking()


def _run_tray_mode() -> None:
    import app_runtime
    import tray as tray_mod

    server = app_runtime.build_uvicorn_server()

    def _serve():
        try:
            server.run()
        except Exception:
            logging.getLogger("kbs-bridge").exception("uvicorn server hata")

    t = threading.Thread(target=_serve, name="uvicorn", daemon=True)
    t.start()

    def _on_quit():
        try:
            server.should_exit = True
        except Exception:
            pass

    started = tray_mod.run_tray(log_setup.default_log_dir(), on_quit=_on_quit)
    if not started:
        logging.getLogger("kbs-bridge").info(
            "Tray baslatilamadi, uvicorn arka planda calismaya devam ediyor"
        )
        t.join()


def _run_service_mode() -> None:
    import service
    service.main()


def main(argv=None) -> None:
    argv = list(argv if argv is not None else sys.argv[1:])
    if "--installer" in argv:
        # Post-install hook (Inno Setup): register the service.
        os.environ["MODE"] = "service"
        sys.argv = [sys.argv[0], "install"]
        _run_service_mode()
        return

    _bootstrap_logging()
    single_instance.acquire_or_exit()

    mode = _mode()
    if mode == "server":
        _run_server_mode()
    elif mode == "tray":
        _run_tray_mode()
    elif mode == "service":
        _run_service_mode()
    else:
        print(f"Bilinmeyen MODE={mode}. Kullanin: server | tray | service", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
