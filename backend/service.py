"""Windows Service wrapper for the agent.

Registers as `SyroceKBSAgent`. Starts uvicorn in a worker thread so the
service control handler stays responsive.

Commands (must run as Administrator):
  python -m backend.service install    # register service
  python -m backend.service start      # start it
  python -m backend.service stop
  python -m backend.service remove     # uninstall
  python -m backend.service debug      # run in foreground for debugging

This module imports pywin32 at the top — so it only loads on Windows. The
fallback path (when pywin32 missing) prints a friendly message.
"""
from __future__ import annotations

import logging
import sys
import threading

log = logging.getLogger("kbs-bridge.service")

SERVICE_NAME = "SyroceKBSAgent"
SERVICE_DISPLAY = "Syroce KBS Agent"
SERVICE_DESC = (
    "Otel resepsiyonundan EGM/Jandarma KBS sistemine "
    "misafir kayitlarini otomatik gonderir."
)


def _is_windows() -> bool:
    return sys.platform == "win32"


if _is_windows():  # pragma: no cover - Windows-only branch
    try:
        import servicemanager  # type: ignore[import-not-found]
        import win32event  # type: ignore[import-not-found]
        import win32service  # type: ignore[import-not-found]
        import win32serviceutil  # type: ignore[import-not-found]

        class SyroceKBSService(win32serviceutil.ServiceFramework):
            _svc_name_ = SERVICE_NAME
            _svc_display_name_ = SERVICE_DISPLAY
            _svc_description_ = SERVICE_DESC

            def __init__(self, args):
                super().__init__(args)
                self.stop_event = win32event.CreateEvent(None, 0, 0, None)
                self._server_thread = None
                self._uvicorn_server = None

            def SvcStop(self):
                self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
                win32event.SetEvent(self.stop_event)
                if self._uvicorn_server is not None:
                    try:
                        self._uvicorn_server.should_exit = True
                    except Exception:
                        log.exception("uvicorn shutdown istegi basarisiz")

            def SvcDoRun(self):
                servicemanager.LogMsg(
                    servicemanager.EVENTLOG_INFORMATION_TYPE,
                    servicemanager.PYS_SERVICE_STARTED,
                    (self._svc_name_, ""),
                )
                self._run_uvicorn_blocking()
                servicemanager.LogMsg(
                    servicemanager.EVENTLOG_INFORMATION_TYPE,
                    servicemanager.PYS_SERVICE_STOPPED,
                    (self._svc_name_, ""),
                )

            def _run_uvicorn_blocking(self):
                from app_runtime import build_uvicorn_server
                self._uvicorn_server = build_uvicorn_server()
                self._uvicorn_server.run()

        def main():
            if len(sys.argv) == 1:
                servicemanager.Initialize()
                servicemanager.PrepareToHostSingle(SyroceKBSService)
                servicemanager.StartServiceCtrlDispatcher()
            else:
                win32serviceutil.HandleCommandLine(SyroceKBSService)

    except ImportError:
        def main():
            log.error("pywin32 yuklu degil. Service modu icin: pip install pywin32")
            sys.exit(1)
else:
    def main():
        log.error(
            "Service modu yalnizca Windows'ta calisir. "
            "Linux/macOS'ta 'tray' veya 'server' modunu kullanin."
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
