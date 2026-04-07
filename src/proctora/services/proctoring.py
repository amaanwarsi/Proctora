from __future__ import annotations

import os
import platform
import subprocess
import threading
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

import numpy as np


MPL_CACHE_DIR = Path(tempfile.gettempdir()) / "proctora-matplotlib"
MPL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(MPL_CACHE_DIR))

try:
    import cv2
except ImportError:  # pragma: no cover - depends on local machine setup
    cv2 = None

try:
    import mediapipe as mp
except ImportError:  # pragma: no cover - depends on local machine setup
    mp = None

try:
    import sounddevice as sd
except (ImportError, OSError):  # pragma: no cover - depends on local machine setup
    sd = None

try:
    import pygetwindow as gw
except (ImportError, NotImplementedError):  # pragma: no cover - OS dependent
    gw = None

from proctora.services.alerts import AlertStore


@dataclass
class ProctoringState:
    prev_face_coords: tuple[int, int, int, int] | None = None
    no_face_counter: int = 0
    last_error: str | None = None
    last_alert_times: dict[str, float] = field(
        default_factory=lambda: {
            "face_shift": 0.0,
            "multiple_faces": 0.0,
            "no_face": 0.0,
            "tab_switch": 0.0,
            "sound": 0.0,
            "sound_warning": 0.0,
            "environment": 0.0,
            "camera": 0.0,
        }
    )


class ProctoringService:
    def __init__(self, config, alerts: AlertStore) -> None:
        self.config = config
        self.alerts = alerts
        self.state = ProctoringState()
        self._started = False
        self._start_lock = threading.Lock()

    def cfg(self, key: str):
        return self.config[key]

    def start_background_monitors(self) -> None:
        with self._start_lock:
            if self._started:
                return

            self._started = True
            threading.Thread(
                target=self.monitor_tab_switching,
                daemon=True,
                name="proctora-tab-monitor",
            ).start()
            threading.Thread(
                target=self.monitor_sound_levels,
                daemon=True,
                name="proctora-sound-monitor",
            ).start()
            threading.Thread(
                target=self.detect_vm_environment,
                daemon=True,
                name="proctora-environment-monitor",
            ).start()

    def add_alert(self, message: str) -> None:
        self.alerts.add(message)

    def add_system_notice_once(self, key: str, message: str) -> None:
        if self.state.last_alert_times[key] == 0:
            self.add_alert(message)
            self.state.last_alert_times[key] = time.time()

    def monitor_tab_switching(self) -> None:
        if gw is None:
            self.add_system_notice_once(
                "tab_switch",
                "Tab switching monitor disabled: install PyGetWindow for window tracking.",
            )
            return

        try:
            previous_window = gw.getActiveWindow()
            previous_title = previous_window.title if previous_window else None
        except Exception as exc:  # pragma: no cover - OS dependent
            self.add_alert(f"Tab switching monitor unavailable: {exc}")
            return

        while True:
            try:
                current_window = gw.getActiveWindow()
                current_title = current_window.title if current_window else None
                current_time = time.time()
                if (
                    current_title
                    and current_title != previous_title
                    and current_time - self.state.last_alert_times["tab_switch"]
                    > self.cfg("ALERT_COOLDOWN_SECONDS")
                ):
                    self.add_alert("Tab switching detected!")
                    self.state.last_alert_times["tab_switch"] = current_time
                previous_title = current_title
            except Exception as exc:  # pragma: no cover - OS dependent
                self.add_alert(f"Tab switching monitor error: {exc}")
                return

            time.sleep(self.cfg("TAB_CHECK_INTERVAL"))

    def monitor_sound_levels(self) -> None:
        if sd is None:
            self.add_system_notice_once(
                "sound",
                "Sound monitor disabled: install sounddevice to enable microphone detection.",
            )
            return

        try:
            def audio_callback(indata, frames, callback_time, status) -> None:
                del frames, callback_time
                if status:
                    current_time = time.time()
                    if (
                        current_time - self.state.last_alert_times["sound_warning"]
                        > self.cfg("ALERT_COOLDOWN_SECONDS")
                    ):
                        self.add_alert(f"Sound monitor warning: {status}")
                        self.state.last_alert_times["sound_warning"] = current_time
                    return

                volume = float(np.linalg.norm(indata))
                current_time = time.time()
                if (
                    volume > self.cfg("VOICE_THRESHOLD")
                    and current_time - self.state.last_alert_times["sound"]
                    > self.cfg("ALERT_COOLDOWN_SECONDS")
                ):
                    self.add_alert("Loud noise detected!")
                    self.state.last_alert_times["sound"] = current_time

            with sd.InputStream(
                channels=1,
                samplerate=44100,
                dtype="int16",
                callback=audio_callback,
                blocksize=1024,
            ):
                while True:
                    time.sleep(0.25)
        except Exception as exc:  # pragma: no cover - hardware dependent
            self.add_alert(f"Sound monitor unavailable: {exc}")
            return

    def detect_vm_environment(self) -> None:
        vm_indicators = ["VirtualBox", "VMware", "Hyper-V", "QEMU", "Parallels"]
        try:
            if platform.system() == "Windows":
                bios_info = subprocess.check_output(
                    [
                        "powershell",
                        "-NoProfile",
                        "-Command",
                        "(Get-CimInstance Win32_BIOS | Select-Object -ExpandProperty SMBIOSBIOSVersion)",
                    ],
                    text=True,
                )
            else:
                bios_info = subprocess.check_output(
                    ["dmidecode", "-s", "bios-version"],
                    text=True,
                )
        except Exception as exc:  # pragma: no cover - OS dependent
            self.add_alert(f"Environment check skipped: {exc}")
            return

        for indicator in vm_indicators:
            if indicator.lower() in bios_info.lower():
                self.add_alert(f"Virtual machine detected ({indicator}).")
                break

    def generate_video_feed(self) -> Iterator[bytes]:
        if cv2 is None or mp is None:
            self.add_system_notice_once(
                "environment",
                "Video monitor disabled: install OpenCV and MediaPipe for webcam detection.",
            )
            return

        cap = cv2.VideoCapture(self.cfg("CAMERA_INDEX"))
        if not cap.isOpened():
            self.add_system_notice_once(
                "camera",
                f"Unable to access camera index {self.cfg('CAMERA_INDEX')}. Check camera permissions.",
            )
            return

        with mp.solutions.face_detection.FaceDetection(
            min_detection_confidence=0.7
        ) as face_detection:
            while cap.isOpened():
                success, frame = cap.read()
                if not success:
                    break

                self.detect_face_events(frame, face_detection)
                ok, buffer = cv2.imencode(".jpg", frame)
                if not ok:
                    continue

                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + buffer.tobytes() + b"\r\n"
                )

        cap.release()

    def detect_face_events(self, frame, face_detection) -> None:
        results = face_detection.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        new_error = None

        if results.detections:
            self.state.no_face_counter = 0
            face_count = len(results.detections)

            if face_count > self.cfg("MAX_ALLOWED_FACES"):
                new_error = "Multiple faces detected!"
                self.alerts.remove("No face detected!")

            detection = results.detections[0]
            bbox = detection.location_data.relative_bounding_box
            height, width, _ = frame.shape
            current_coords = (
                int(bbox.xmin * width),
                int(bbox.ymin * height),
                int(bbox.width * width),
                int(bbox.height * height),
            )

            if self.state.prev_face_coords:
                shift_distance = (
                    (self.state.prev_face_coords[0] - current_coords[0]) ** 2
                    + (self.state.prev_face_coords[1] - current_coords[1]) ** 2
                ) ** 0.5
                if (
                    shift_distance > self.cfg("HEAD_SHIFT_THRESHOLD")
                    and time.time() - self.state.last_alert_times["face_shift"]
                    > self.cfg("ALERT_COOLDOWN_SECONDS")
                ):
                    self.add_alert("Face shift detected!")
                    self.state.last_alert_times["face_shift"] = time.time()

            self.state.prev_face_coords = current_coords
        else:
            self.state.no_face_counter += 1
            if self.state.no_face_counter >= self.cfg("NO_FACE_THRESHOLD"):
                new_error = "No face detected!"

        if new_error and new_error != self.state.last_error:
            self.add_alert(new_error)
            self.state.last_error = new_error
        elif not new_error:
            self.state.last_error = None
