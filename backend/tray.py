"""System tray icon for the agent (Windows + cross-platform via pystray).

Run as the 'tray' MODE — agent runs in the user's desktop session with a
small icon next to the clock. Right-click menu:
  - Durum (worker son tur)        → opens the status web UI
  - Ayarlar (tarayici ac)         → opens settings page
  - Loglari ac (Explorer)         → reveals %LOCALAPPDATA%\\SyroceKBSAgent\\logs
  - Cik                           → graceful shutdown

Double-click the icon → opens http://127.0.0.1:8765.

This module is deliberately defensive: pystray and Pillow are Windows/desktop
only. If they're missing (e.g. headless Linux dev), `run_tray()` returns
without starting an icon and the agent runs as a plain background process.
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path
from typing import Callable, Optional

log = logging.getLogger("kbs-bridge.tray")

DEFAULT_URL = "http://127.0.0.1:8765"


def _open_browser(path: str = "/") -> None:
    url = f"{DEFAULT_URL.rstrip('/')}{path}"
    try:
        webbrowser.open(url)
    except Exception as e:
        log.warning("Tarayici acilamadi: %s", e)


def _open_log_folder(log_dir: Path) -> None:
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(str(log_dir))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(log_dir)])
        else:
            subprocess.Popen(["xdg-open", str(log_dir)])
    except Exception as e:
        log.warning("Log klasoru acilamadi: %s", e)


def _build_icon_image():
    """Build a 64x64 RGBA tray icon programmatically (no asset file needed)."""
    try:
        from PIL import Image, ImageDraw  # type: ignore[import-not-found]
    except ImportError:
        return None
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # Solid blue rounded square with white "K"
    d.rounded_rectangle((4, 4, 60, 60), radius=12, fill=(30, 100, 200, 255))
    try:
        from PIL import ImageFont
        font = ImageFont.load_default()
        d.text((20, 16), "K", fill=(255, 255, 255, 255), font=font)
    except Exception:
        d.text((22, 18), "K", fill=(255, 255, 255, 255))
    return img


def run_tray(
    log_dir: Path,
    on_quit: Optional[Callable[[], None]] = None,
) -> bool:
    """Start the tray icon. Blocks until 'Cik' is selected.

    Returns False (without blocking) if pystray/Pillow aren't available.
    """
    try:
        import pystray  # type: ignore[import-not-found]
    except ImportError:
        log.warning("pystray yok; tray modu atlandi (headless calisma)")
        return False

    image = _build_icon_image()
    if image is None:
        log.warning("Pillow yok; tray ikonu olusturulamadi")
        return False

    def _on_status(icon, item):
        _open_browser("/")

    def _on_settings(icon, item):
        _open_browser("/settings")

    def _on_logs(icon, item):
        _open_log_folder(log_dir)

    def _on_quit(icon, item):
        if on_quit is not None:
            try:
                on_quit()
            except Exception:
                log.exception("on_quit handler hata")
        icon.stop()

    menu = pystray.Menu(
        pystray.MenuItem("Durum", _on_status, default=True),
        pystray.MenuItem("Ayarlar", _on_settings),
        pystray.MenuItem("Loglari ac", _on_logs),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Cik", _on_quit),
    )
    icon = pystray.Icon("SyroceKBSAgent", image, "Syroce KBS Agent", menu)
    log.info("Tray ikonu basliyor")
    icon.run()  # blocks
    return True
