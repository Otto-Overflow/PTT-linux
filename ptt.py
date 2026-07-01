#!/usr/bin/env python3

import sys
import subprocess
from pathlib import Path

from evdev import InputDevice, ecodes

from PyQt6.QtCore import QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QMenu,
    QSystemTrayIcon,
)

########################################################################
# Configuration
########################################################################

DEVICE = "/dev/input/by-id/usb-Logitech_G502_X_206231615046-event-mouse"

RELEASE_DELAY_MS = 50

SHOW_NOTIFICATION = False

BASE_DIR = Path(__file__).resolve().parent

ICON_ON = QIcon(str(BASE_DIR / "icons/mic_on.svg"))
ICON_OFF = QIcon(str(BASE_DIR / "icons/mic_off.svg"))

########################################################################
# Fonctions Micro
########################################################################


def get_mic_state() -> bool:
    """Retourne True si le micro est actif."""

    try:
        out = subprocess.check_output(
            ["pactl", "get-source-mute", "@DEFAULT_SOURCE@"],
            text=True,
        )

        return "no" in out.lower()

    except Exception:
        return False


mic_on = get_mic_state()


def update_icon():

    tray.setIcon(ICON_ON if mic_on else ICON_OFF)
    tray.setToolTip("Micro ON" if mic_on else "Micro OFF")


def set_mic(state: bool):

    global mic_on

    if state == mic_on:
        return

    mic_on = state

    update_icon()

    subprocess.run(
        [
            "pactl",
            "set-source-mute",
            "@DEFAULT_SOURCE@",
            "0" if state else "1",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


    if SHOW_NOTIFICATION:
        tray.showMessage(
            "Push-To-Talk",
            "Micro activé" if state else "Micro coupé",
            QSystemTrayIcon.MessageIcon.Information,
            500,
        )


########################################################################
# Thread lecture souris
########################################################################


class MouseThread(QThread):

    buttonPressed = pyqtSignal()
    buttonReleased = pyqtSignal()

    def __init__(self):
        super().__init__()

        self.running = True
        self.device = InputDevice(DEVICE)

    def run(self):

        while self.running:

            try:

                for event in self.device.read_loop():

                    if not self.running:
                        return

                    if (
                        event.type == ecodes.EV_KEY
                        and event.code == ecodes.BTN_EXTRA
                    ):

                        if event.value == 1:
                            self.buttonPressed.emit()

                        elif event.value == 0:
                            self.buttonReleased.emit()

            except OSError:
                break

    def stop(self):

        self.running = False

        try:
            self.device.close()
        except Exception:
            pass


########################################################################
# Application
########################################################################

app = QApplication(sys.argv)

tray = QSystemTrayIcon()

menu = QMenu()

quit_action = menu.addAction("Quitter")
quit_action.triggered.connect(app.quit)

tray.setContextMenu(menu)

update_icon()
tray.show()

########################################################################
# Timer de relâchement
########################################################################

release_timer = QTimer()
release_timer.setSingleShot(True)
release_timer.timeout.connect(lambda: set_mic(False))

########################################################################
# Thread souris
########################################################################

mouse_thread = MouseThread()

mouse_thread.buttonPressed.connect(release_timer.stop)
mouse_thread.buttonPressed.connect(lambda: set_mic(True))

mouse_thread.buttonReleased.connect(
    lambda: release_timer.start(RELEASE_DELAY_MS)
)

mouse_thread.start()

########################################################################
# Fermeture propre
########################################################################


def cleanup():

    release_timer.stop()

    mouse_thread.stop()
    mouse_thread.wait(1000)


app.aboutToQuit.connect(cleanup)

########################################################################

sys.exit(app.exec())
