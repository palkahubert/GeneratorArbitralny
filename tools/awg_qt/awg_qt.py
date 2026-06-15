from __future__ import annotations

import math
import random as py_random
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PyQt6 import QtCore, QtGui, QtWidgets

try:
    import serial
    from serial.tools import list_ports
except ImportError:  # pragma: no cover - handled at runtime in the GUI
    serial = None
    list_ports = None


SAMPLE_COUNT = 4096
MAGIC = b"AWG1"
CMD_LOAD = 0x01
CMD_CONFIG = 0x02
CMD_ENABLE = 0x03
CMD_RESET = 0x04
CMD_PING = 0x05


def apply_light_palette(app: QtWidgets.QApplication) -> None:
    app.setStyle("Fusion")
    palette = QtGui.QPalette()
    palette.setColor(QtGui.QPalette.ColorRole.Window, QtGui.QColor("#f5f7fa"))
    palette.setColor(QtGui.QPalette.ColorRole.WindowText, QtGui.QColor("#111827"))
    palette.setColor(QtGui.QPalette.ColorRole.Base, QtGui.QColor("#ffffff"))
    palette.setColor(QtGui.QPalette.ColorRole.AlternateBase, QtGui.QColor("#eef2f7"))
    palette.setColor(QtGui.QPalette.ColorRole.ToolTipBase, QtGui.QColor("#111827"))
    palette.setColor(QtGui.QPalette.ColorRole.ToolTipText, QtGui.QColor("#ffffff"))
    palette.setColor(QtGui.QPalette.ColorRole.Text, QtGui.QColor("#111827"))
    palette.setColor(QtGui.QPalette.ColorRole.Button, QtGui.QColor("#ffffff"))
    palette.setColor(QtGui.QPalette.ColorRole.ButtonText, QtGui.QColor("#111827"))
    palette.setColor(QtGui.QPalette.ColorRole.Highlight, QtGui.QColor("#0f62fe"))
    palette.setColor(QtGui.QPalette.ColorRole.HighlightedText, QtGui.QColor("#ffffff"))
    palette.setColor(QtGui.QPalette.ColorRole.PlaceholderText, QtGui.QColor("#667085"))
    palette.setColor(QtGui.QPalette.ColorGroup.Disabled, QtGui.QPalette.ColorRole.Text, QtGui.QColor("#8a94a6"))
    palette.setColor(QtGui.QPalette.ColorGroup.Disabled, QtGui.QPalette.ColorRole.ButtonText, QtGui.QColor("#8a94a6"))
    app.setPalette(palette)


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def wrap_signed(value: float) -> float:
    if not math.isfinite(value):
        return 0.0
    return clamp(value, -1.0, 1.0)


def imul32(a: int, b: int) -> int:
    return (a * b) & 0xFFFFFFFF


def mulberry32(seed: int) -> Callable[[], float]:
    state = seed & 0xFFFFFFFF

    def rand() -> float:
        nonlocal state
        state = (state + 0x6D2B79F5) & 0xFFFFFFFF
        x = state
        x = imul32(x ^ (x >> 15), x | 1)
        x ^= (x + imul32(x ^ (x >> 7), x | 61)) & 0xFFFFFFFF
        return ((x ^ (x >> 14)) & 0xFFFFFFFF) / 4294967296.0

    return rand


def triangle_wave(x: float) -> float:
    p = x - math.floor(x)
    return 1.0 - 4.0 * abs(p - 0.5)


def saw_wave(x: float) -> float:
    p = x - math.floor(x)
    return 2.0 * p - 1.0


def safe_round(value: float) -> int:
    return int(math.floor(value + 0.5))


@dataclass(frozen=True)
class GeneratorSettings:
    mode: str
    freq_hz: float
    clock_hz: float
    amplitude_percent: int
    offset_percent: int
    cycles: int
    phase_degrees: int
    duty_percent: int
    harmonics: int
    wildness_percent: int
    seed: int
    formula: str
    soft_clip: bool
    invert: bool
    dc_block: bool
    gain_q16: int
    offset_raw: int


def eval_formula(expression: str, t: float, i: int, n: int, rand: Callable[[], float]) -> float:
    def sqr(x: float, duty: float = 0.5) -> float:
        return 1.0 if (x - math.floor(x)) < duty else -1.0

    names = {
        "sin": math.sin,
        "cos": math.cos,
        "tan": math.tan,
        "abs": abs,
        "pow": pow,
        "sqrt": math.sqrt,
        "floor": math.floor,
        "round": round,
        "min": min,
        "max": max,
        "pi": math.pi,
        "tri": triangle_wave,
        "saw": saw_wave,
        "sqr": sqr,
        "t": t,
        "i": i,
        "n": n,
        "rand": rand,
    }
    return float(eval(expression, {"__builtins__": {}}, names))


def base_value(settings: GeneratorSettings, t: float, i: int, rand: Callable[[], float]) -> float:
    cycles = settings.cycles
    phase = settings.phase_degrees / 360.0
    x = cycles * t + phase
    duty = settings.duty_percent / 100.0
    wild = settings.wildness_percent / 100.0

    if settings.mode == "sine":
        return math.sin(2.0 * math.pi * x)

    if settings.mode == "square":
        return 1.0 if (x - math.floor(x)) < duty else -1.0

    if settings.mode == "triangle":
        return triangle_wave(x)

    if settings.mode == "saw":
        return saw_wave(x)

    if settings.mode == "noise":
        slow = math.sin(2.0 * math.pi * x) * (1.0 - wild)
        rough = (rand() * 2.0 - 1.0) * (0.35 + wild)
        return wrap_signed(slow + rough)

    if settings.mode == "fm":
        mod_rate = 1 + round(wild * 14)
        depth = 0.1 + wild * 4.5
        warped = x + depth * math.sin(2.0 * math.pi * mod_rate * t) / (2.0 * math.pi)
        return math.sin(2.0 * math.pi * warped)

    if settings.mode == "additive":
        total = 0.0
        norm = 0.0
        for h in range(1, settings.harmonics + 1):
            weight = 1.0 / math.pow(h, 0.72 + wild)
            sign = 0.65 if h % 2 == 0 else 1.0
            total += sign * weight * math.sin(2.0 * math.pi * h * x)
            norm += abs(sign * weight)
        return total / norm if norm > 0.0 else 0.0

    if settings.mode == "spikes":
        base = 0.42 * math.sin(2.0 * math.pi * x)
        p = x - math.floor(x)
        spike_width = 0.012 + 0.05 * wild
        spike = 1.0 if p < spike_width else -1.0 if p > 1.0 - spike_width else 0.0
        hashed = math.sin((i + 1) * 91.345 + settings.seed) * 43758.5453
        rare = rand() * 2.0 - 1.0 if (hashed - math.floor(hashed)) > 0.985 - wild * 0.03 else 0.0
        return wrap_signed(base + 0.72 * spike + 0.55 * rare)

    if settings.mode == "formula":
        try:
            return wrap_signed(eval_formula(settings.formula, t, i, SAMPLE_COUNT, rand))
        except Exception:
            return 0.0

    return 0.0


def generate_samples(settings: GeneratorSettings) -> list[int]:
    rand = mulberry32(settings.seed)
    amp = settings.amplitude_percent / 100.0
    offset = (settings.offset_percent - 50) / 100.0
    wild = settings.wildness_percent / 100.0
    signed: list[float] = []

    for i in range(SAMPLE_COUNT):
        t = i / SAMPLE_COUNT
        value = base_value(settings, t, i, rand)

        if wild > 0.0 and settings.mode != "noise":
            value += (rand() * 2.0 - 1.0) * wild * 0.12

        if settings.soft_clip:
            value = math.tanh(value * (1.05 + wild * 1.8))

        if settings.invert:
            value = -value

        signed.append(wrap_signed(value))

    if settings.dc_block:
        mean = sum(signed) / len(signed)
        signed = [wrap_signed(value - mean) for value in signed]

    samples: list[int] = []
    for value in signed:
        level = clamp(0.5 + value * 0.5 * amp + offset, 0.0, 1.0)
        samples.append(safe_round(level * 65535.0))
    return samples


def write_u16(value: int) -> bytes:
    return int(value & 0xFFFF).to_bytes(2, "little", signed=False)


def write_u32(value: int) -> bytes:
    return int(value & 0xFFFFFFFF).to_bytes(4, "little", signed=False)


def compute_phase_step(freq_hz: float, clock_hz: float) -> int:
    return safe_round(max(0.0, freq_hz) * 4294967296.0 / max(1.0, clock_hz)) & 0xFFFFFFFF


def build_load_payload(samples: list[int]) -> bytes:
    payload = bytearray()
    payload += write_u16(len(samples))
    for sample in samples:
        payload += write_u16(sample)
    return bytes(payload)


def build_config_payload(settings: GeneratorSettings, enable: bool) -> bytes:
    payload = bytearray()
    payload += write_u32(compute_phase_step(settings.freq_hz, settings.clock_hz))
    payload += write_u16(int(clamp(settings.gain_q16, 0, 65535)))
    payload += write_u16(int(clamp(settings.offset_raw, 0, 65535)))
    payload.append(1 if enable else 0)
    return bytes(payload)


def build_packet(command: int, payload: bytes = b"") -> bytes:
    packet = bytearray()
    packet += MAGIC
    packet.append(command & 0xFF)
    packet += write_u16(len(payload))
    packet += payload
    checksum = (command + packet[5] + packet[6] + sum(payload)) & 0xFFFF
    packet += write_u16(checksum)
    return bytes(packet)


def mem_text(samples: list[int]) -> str:
    return "".join(f"{sample:04X}\n" for sample in samples)


def c_array_text(samples: list[int]) -> str:
    lines = ["static const unsigned short waveform[4096] = {"]
    for i in range(0, SAMPLE_COUNT, 8):
        chunk = ", ".join(f"{sample:5d}" for sample in samples[i : i + 8])
        suffix = "," if i + 8 < SAMPLE_COUNT else ""
        lines.append(f"    {chunk}{suffix}")
    lines.append("};")
    return "\n".join(lines)


def hex32(value: int) -> str:
    return f"0x{value & 0xFFFFFFFF:08X}"


def xsdb_header(title: str) -> list[str]:
    return [
        f"# {title}",
        "# Generated by AWG Signal Forge Qt",
        "# Run in Xilinx SDK XSCT/XSDB console while the board is connected.",
        "catch {connect -url tcp:127.0.0.1:3121}",
        'targets -set -nocase -filter {name =~ "microblaze*#0"} -index 1',
        "configparams force-mem-access 1",
        "",
    ]


def xsdb_footer() -> list[str]:
    return [
        "",
        "configparams force-mem-access 0",
        'puts "AWG update done"',
        "",
    ]


def xsdb_config_lines(settings: GeneratorSettings, enable: bool = True) -> list[str]:
    phase_step = compute_phase_step(settings.freq_hz, settings.clock_hz)
    gain = int(clamp(settings.gain_q16, 0, 65535)) & 0xFFFF
    offset = int(clamp(settings.offset_raw, 0, 65535)) & 0xFFFF
    gain_offset = ((offset << 16) | gain) & 0xFFFFFFFF
    return [
        f"mwr 0x44A00004 {hex32(phase_step)}",
        f"mwr 0x44A00008 {hex32(gain_offset)}",
        f"mwr 0x44A00000 {'0x00000001' if enable else '0x00000000'}",
    ]


def xsdb_config_text(settings: GeneratorSettings) -> str:
    return "\n".join(
        [
            *xsdb_header("AWG config-only update"),
            *xsdb_config_lines(settings, True),
            *xsdb_footer(),
        ]
    )


def xsdb_full_text(settings: GeneratorSettings, samples: list[int]) -> str:
    lines = xsdb_header("AWG waveform and config update")
    lines.append("mwr 0x44A00000 0x00000002")
    lines.append("mwr 0x44A00000 0x00000000")
    for i, sample in enumerate(samples):
        word = (((i & 0x0FFF) << 16) | sample) & 0xFFFFFFFF
        lines.append(f"mwr 0x44A0000C {hex32(word)}")
    lines.extend(xsdb_config_lines(settings, True))
    lines.extend(xsdb_footer())
    return "\n".join(lines)


def xsdb_enable_text(enable: bool) -> str:
    return "\n".join(
        [
            *xsdb_header("AWG enable update"),
            f"mwr 0x44A00000 {'0x00000001' if enable else '0x00000000'}",
            *xsdb_footer(),
        ]
    )


def xsdb_reset_text() -> str:
    return "\n".join(
        [
            *xsdb_header("AWG reset"),
            "mwr 0x44A00000 0x00000002",
            "mwr 0x44A00000 0x00000001",
            *xsdb_footer(),
        ]
    )


def xsdb_check_text() -> str:
    return "\n".join(
        [
            *xsdb_header("AWG XSDB connection check"),
            'puts "Reading AWG control register"',
            "mrd 0x44A00000",
            *xsdb_footer(),
        ]
    )


class WavePlot(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.samples: list[int] = []
        self.setMinimumHeight(300)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)

    def set_samples(self, samples: list[int]) -> None:
        self.samples = samples
        self.update()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        del event
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        rect = self.rect()
        painter.fillRect(rect, QtGui.QColor("#101817"))

        grid_pen = QtGui.QPen(QtGui.QColor(215, 239, 228, 32))
        grid_pen.setWidth(1)
        painter.setPen(grid_pen)
        for x in range(13):
            px = rect.left() + rect.width() * x / 12.0
            painter.drawLine(QtCore.QPointF(px, rect.top()), QtCore.QPointF(px, rect.bottom()))
        for y in range(9):
            py = rect.top() + rect.height() * y / 8.0
            painter.drawLine(QtCore.QPointF(rect.left(), py), QtCore.QPointF(rect.right(), py))

        mid_pen = QtGui.QPen(QtGui.QColor(232, 186, 90, 115))
        mid_pen.setWidth(1)
        painter.setPen(mid_pen)
        mid_y = rect.top() + rect.height() * 0.5
        painter.drawLine(QtCore.QPointF(rect.left(), mid_y), QtCore.QPointF(rect.right(), mid_y))

        if not self.samples:
            return

        path = QtGui.QPainterPath()
        width = max(1, rect.width())
        stride = max(1, SAMPLE_COUNT // width)
        first = True
        for i in range(0, len(self.samples), stride):
            x = rect.left() + i / (SAMPLE_COUNT - 1) * rect.width()
            y = rect.bottom() - self.samples[i] / 65535.0 * rect.height()
            point = QtCore.QPointF(x, y)
            if first:
                path.moveTo(point)
                first = False
            else:
                path.lineTo(point)

        fill_path = QtGui.QPainterPath(path)
        fill_path.lineTo(QtCore.QPointF(rect.right(), rect.bottom()))
        fill_path.lineTo(QtCore.QPointF(rect.left(), rect.bottom()))
        fill_path.closeSubpath()
        painter.fillPath(fill_path, QtGui.QColor(126, 224, 180, 26))

        wave_pen = QtGui.QPen(QtGui.QColor("#7ee0b4"))
        wave_pen.setWidthF(1.8)
        painter.setPen(wave_pen)
        painter.drawPath(path)


class HistogramPlot(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.samples: list[int] = []
        self.setMinimumHeight(120)

    def set_samples(self, samples: list[int]) -> None:
        self.samples = samples
        self.update()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        del event
        painter = QtGui.QPainter(self)
        rect = self.rect()
        painter.fillRect(rect, QtGui.QColor("#fbfcfa"))

        if not self.samples:
            return

        bins = [0] * 96
        for sample in self.samples:
            index = min(len(bins) - 1, int(sample / 65536.0 * len(bins)))
            bins[index] += 1
        max_bin = max(1, max(bins))
        bar_w = rect.width() / len(bins)
        for i, count in enumerate(bins):
            bar_h = count / max_bin * max(1, rect.height() - 14)
            color = QtGui.QColor("#226a86" if i % 2 else "#1f7a5a")
            painter.fillRect(
                QtCore.QRectF(rect.left() + i * bar_w + 1, rect.bottom() - bar_h, max(1.0, bar_w - 2), bar_h),
                color,
            )

        painter.setPen(QtGui.QPen(QtGui.QColor("#d7ddd7")))
        painter.drawLine(rect.left(), rect.bottom() - 1, rect.right(), rect.bottom() - 1)


class SendWorker(QtCore.QThread):
    progress = QtCore.pyqtSignal(int, str)
    message = QtCore.pyqtSignal(str)
    done = QtCore.pyqtSignal(bool)

    def __init__(self, port: object, packets: list[tuple[str, bytes]], parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self.port = port
        self.packets = packets
        self.cancel_requested = False

    def cancel(self) -> None:
        self.cancel_requested = True

    def run(self) -> None:
        try:
            for label, packet in self.packets:
                if self.cancel_requested:
                    self.done.emit(False)
                    return
                self.progress.emit(0, f"{label}: starting")
                for offset in range(0, len(packet), 256):
                    if self.cancel_requested:
                        self.done.emit(False)
                        return
                    chunk = packet[offset : offset + 256]
                    self.port.write(chunk)
                    self.port.flush()
                    sent = offset + len(chunk)
                    ratio = int(sent * 100 / max(1, len(packet)))
                    self.progress.emit(ratio, f"{label}: {sent}/{len(packet)} bytes")
                self.progress.emit(100, f"{label}: sent")
                self.message.emit(f"{label} packet sent ({len(packet)} bytes)")
            self.done.emit(True)
        except Exception as exc:
            self.message.emit(f"Send failed: {exc}")
            self.done.emit(False)


class XsdbWorker(QtCore.QThread):
    progress = QtCore.pyqtSignal(int, str)
    message = QtCore.pyqtSignal(str)
    done = QtCore.pyqtSignal(bool)

    def __init__(self, executable: str, script_text: str, label: str, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self.executable = executable
        self.script_text = script_text
        self.label = label

    def run(self) -> None:
        script_path = None
        try:
            self.progress.emit(5, f"{self.label}: writing XSDB script")
            with tempfile.NamedTemporaryFile("w", suffix=".tcl", delete=False, encoding="utf-8", newline="\n") as handle:
                handle.write(self.script_text)
                script_path = handle.name

            self.progress.emit(20, f"{self.label}: running {self.executable}")
            result = subprocess.run(
                [self.executable, script_path],
                capture_output=True,
                text=True,
                timeout=180,
                check=False,
            )

            output = "\n".join(part.strip() for part in [result.stdout, result.stderr] if part.strip())
            if output:
                for line in output.splitlines()[-12:]:
                    self.message.emit(f"XSDB {line}")

            if result.returncode == 0:
                self.progress.emit(100, f"{self.label}: done")
                self.message.emit(f"{self.label} sent over XSDB/JTAG")
                self.done.emit(True)
            else:
                self.progress.emit(0, f"{self.label}: XSDB failed")
                self.message.emit(f"XSDB failed with exit code {result.returncode}")
                self.done.emit(False)
        except FileNotFoundError:
            self.message.emit(f"Could not find '{self.executable}'. Put xsdb/xsct in PATH or set the full path.")
            self.done.emit(False)
        except subprocess.TimeoutExpired:
            self.message.emit(f"{self.label} timed out while running XSDB")
            self.done.emit(False)
        except Exception as exc:
            self.message.emit(f"XSDB send failed: {exc}")
            self.done.emit(False)
        finally:
            if script_path:
                try:
                    Path(script_path).unlink(missing_ok=True)
                except OSError:
                    pass


class MainWindow(QtWidgets.QMainWindow):
    MODES = ["sine", "square", "triangle", "saw", "fm", "additive", "noise", "spikes", "formula"]

    def __init__(self) -> None:
        super().__init__()
        self.mode = "sine"
        self.samples: list[int] = []
        self.serial_port = None
        self.send_worker: SendWorker | None = None
        self.xsdb_worker: XsdbWorker | None = None
        self.setWindowTitle("AWG Signal Forge Qt")
        self.resize(1320, 820)

        self.rx_timer = QtCore.QTimer(self)
        self.rx_timer.setInterval(50)
        self.rx_timer.timeout.connect(self.poll_serial_rx)

        self._build_ui()
        self.refresh_ports()
        self.update_transport_controls()
        self.generate()
        if serial is None:
            self.log("pyserial is not installed; UART controls are unavailable")
        else:
            self.log("Ready")

    def _build_ui(self) -> None:
        root = QtWidgets.QWidget()
        root_layout = QtWidgets.QVBoxLayout(root)
        root_layout.setContentsMargins(14, 14, 14, 14)
        root_layout.setSpacing(12)

        top = QtWidgets.QHBoxLayout()
        brand = QtWidgets.QLabel("AWG Signal Forge Qt")
        font = brand.font()
        font.setPointSize(16)
        font.setBold(True)
        brand.setFont(font)
        subtitle = QtWidgets.QLabel("4096 samples, unsigned 16-bit, XSDB/JTAG or UART output")
        subtitle.setStyleSheet("color: #334155; background: transparent;")
        brand_box = QtWidgets.QVBoxLayout()
        brand_box.addWidget(brand)
        brand_box.addWidget(subtitle)
        top.addLayout(brand_box)
        top.addStretch(1)

        self.status_label = QtWidgets.QLabel("Serial disconnected")
        self.status_label.setMinimumWidth(150)
        top.addWidget(self.status_label)

        root_layout.addLayout(top)

        body = QtWidgets.QHBoxLayout()
        body.setSpacing(12)
        body.addWidget(self._generator_panel(), 0)
        body.addWidget(self._scope_panel(), 1)
        body.addWidget(self._uart_panel(), 0)
        root_layout.addLayout(body, 1)
        self.setCentralWidget(root)

        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background: #f5f7fa;
                color: #111827;
                font-size: 10pt;
            }
            QGroupBox {
                background: #ffffff;
                color: #111827;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                margin-top: 20px;
                padding: 12px;
                font-weight: 700;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 4px;
                color: #111827;
                background: #f5f7fa;
            }
            QPushButton {
                min-height: 30px;
                border: 1px solid #9aa8bd;
                border-radius: 7px;
                padding: 4px 10px;
                background: #ffffff;
                color: #111827;
                font-weight: 700;
            }
            QPushButton:hover {
                background: #eef4ff;
                border-color: #0f62fe;
            }
            QPushButton:pressed {
                background: #dbeafe;
            }
            QPushButton#primaryButton {
                background: #0f62fe;
                color: #ffffff;
                border-color: #084cdf;
            }
            QPushButton#dangerButton {
                background: #fee2e2;
                color: #991b1b;
                border-color: #ef4444;
            }
            QPushButton:checked {
                background: #0f62fe;
                color: #ffffff;
                border-color: #084cdf;
            }
            QPushButton:disabled {
                background: #e5e7eb;
                color: #6b7280;
                border-color: #cbd5e1;
            }
            QLabel, QCheckBox {
                color: #111827;
                background: transparent;
            }
        QCheckBox::indicator {
                width: 15px;
                height: 15px;
            }
            QToolButton {
                min-height: 30px;
                border: 1px solid #9aa8bd;
                border-radius: 7px;
                padding: 4px 10px;
                background: #ffffff;
                color: #111827;
                font-weight: 700;
            }
            QToolButton::menu-indicator {
                width: 12px;
            }
            QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QTextEdit {
                border: 1px solid #9aa8bd;
                border-radius: 7px;
                padding: 4px;
                background: #ffffff;
                color: #111827;
                selection-background-color: #0f62fe;
                selection-color: #ffffff;
            }
            QSpinBox::up-button, QSpinBox::down-button,
            QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
                background: #eaf0f8;
                border: 1px solid #cbd5e1;
                width: 16px;
            }
            QComboBox QAbstractItemView {
                background: #ffffff;
                color: #111827;
                border: 1px solid #9aa8bd;
                selection-background-color: #0f62fe;
                selection-color: #ffffff;
            }
            QSlider::groove:horizontal {
                height: 8px;
                background: #d0d7e2;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                width: 18px;
                margin: -6px 0;
                border-radius: 9px;
                background: #0f62fe;
                border: 1px solid #084cdf;
            }
            QProgressBar {
                border: 1px solid #9aa8bd;
                border-radius: 5px;
                background: #e5e7eb;
                color: #111827;
                min-height: 14px;
            }
            QProgressBar::chunk {
                background: #f97316;
                border-radius: 4px;
            }
            """
        )

    def _generator_panel(self) -> QtWidgets.QGroupBox:
        box = QtWidgets.QGroupBox("Generator")
        box.setFixedWidth(330)
        layout = QtWidgets.QVBoxLayout(box)
        layout.setSpacing(10)

        mode_grid = QtWidgets.QGridLayout()
        self.mode_group = QtWidgets.QButtonGroup(self)
        self.mode_group.setExclusive(True)
        for index, mode in enumerate(self.MODES):
            button = QtWidgets.QPushButton(mode.capitalize())
            button.setCheckable(True)
            button.setProperty("mode", mode)
            if mode == self.mode:
                button.setChecked(True)
            button.clicked.connect(lambda checked=False, b=button: self.set_mode(str(b.property("mode"))))
            self.mode_group.addButton(button)
            mode_grid.addWidget(button, index // 3, index % 3)
        layout.addLayout(mode_grid)

        form = QtWidgets.QFormLayout()
        form.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)

        self.freq_spin = self._double_spin(0.1, 1_000_000_000.0, 1000.0, 1.0, 3)
        self.clock_spin = self._double_spin(1.0, 1_000_000_000.0, 100_000_000.0, 1.0, 0)
        self.amplitude_slider, self.amplitude_out, amplitude_row = self._slider_row(0, 100, 92, "%")
        self.offset_slider, self.offset_out, offset_row = self._slider_row(0, 100, 50, "%")
        self.cycles_slider, self.cycles_out, cycles_row = self._slider_row(1, 32, 1, "")
        self.phase_slider, self.phase_out, phase_row = self._slider_row(0, 360, 0, " deg")
        self.duty_slider, self.duty_out, duty_row = self._slider_row(1, 99, 50, "%")
        self.harmonics_slider, self.harmonics_out, harmonics_row = self._slider_row(1, 24, 7, "")
        self.wildness_slider, self.wildness_out, wildness_row = self._slider_row(0, 100, 18, "%")
        self.seed_spin = self._spin(1, 999_999, 1337)

        form.addRow("Output frequency", self.freq_spin)
        form.addRow("Clock Hz", self.clock_spin)
        form.addRow("Amplitude", amplitude_row)
        form.addRow("Offset", offset_row)
        form.addRow("Shape cycles", cycles_row)
        form.addRow("Phase", phase_row)
        form.addRow("Duty", duty_row)
        form.addRow("Harmonics", harmonics_row)
        form.addRow("Wildness", wildness_row)
        form.addRow("Seed", self.seed_spin)
        layout.addLayout(form)

        self.formula_edit = QtWidgets.QTextEdit("sin(2*pi*t) + 0.35*sin(9*pi*t)")
        self.formula_edit.setMaximumHeight(82)
        self.formula_edit.textChanged.connect(self.generate)
        self.formula_label = QtWidgets.QLabel("Expression")
        layout.addWidget(self.formula_label)
        layout.addWidget(self.formula_edit)
        self.formula_label.hide()
        self.formula_edit.hide()

        toggles = QtWidgets.QHBoxLayout()
        self.soft_clip_check = QtWidgets.QCheckBox("Soft clip")
        self.soft_clip_check.setChecked(True)
        self.invert_check = QtWidgets.QCheckBox("Invert")
        self.dc_block_check = QtWidgets.QCheckBox("Center")
        for check in [self.soft_clip_check, self.invert_check, self.dc_block_check]:
            check.stateChanged.connect(self.generate)
            toggles.addWidget(check)
        layout.addLayout(toggles)

        actions = QtWidgets.QHBoxLayout()
        randomize = QtWidgets.QPushButton("Randomize")
        randomize.clicked.connect(self.randomize_controls)
        reset = QtWidgets.QPushButton("Reset")
        reset.clicked.connect(self.reset_controls)
        actions.addWidget(randomize)
        actions.addWidget(reset)
        layout.addLayout(actions)
        layout.addStretch(1)
        return box

    def _scope_panel(self) -> QtWidgets.QGroupBox:
        box = QtWidgets.QGroupBox("Waveform")
        layout = QtWidgets.QVBoxLayout(box)
        layout.setSpacing(10)
        self.wave_plot = WavePlot()
        layout.addWidget(self.wave_plot, 1)

        meters = QtWidgets.QGridLayout()
        min_meter, self.min_label = self._meter("Min")
        max_meter, self.max_label = self._meter("Max")
        mean_meter, self.mean_label = self._meter("Mean")
        phase_meter, self.phase_step_label = self._meter("Phase step")
        for index, widget in enumerate([min_meter, max_meter, mean_meter, phase_meter]):
            meters.addWidget(widget, 0, index)
        layout.addLayout(meters)

        self.hist_plot = HistogramPlot()
        layout.addWidget(self.hist_plot)
        return box

    def _uart_panel(self) -> QtWidgets.QGroupBox:
        box = QtWidgets.QGroupBox("Transport")
        box.setFixedWidth(330)
        layout = QtWidgets.QVBoxLayout(box)
        layout.setSpacing(10)

        self.packet_size_label = QtWidgets.QLabel("0 bytes")
        self.packet_size_label.setStyleSheet("color: #334155; background: transparent;")
        layout.addWidget(self.packet_size_label)

        self.transport_combo = QtWidgets.QComboBox()
        self.transport_combo.addItem("XSDB/JTAG single cable", "xsdb")
        self.transport_combo.addItem("UARTLite COM port", "uart")
        self.transport_combo.currentIndexChanged.connect(self.update_transport_controls)
        layout.addWidget(self.transport_combo)

        self.xsdb_container = QtWidgets.QWidget()
        xsdb_form = QtWidgets.QFormLayout(self.xsdb_container)
        xsdb_form.setContentsMargins(0, 0, 0, 0)
        self.xsdb_exec_edit = QtWidgets.QLineEdit("xsdb")
        self.xsdb_exec_edit.setPlaceholderText("xsdb, xsct, or full path to xsdb.bat")
        xsdb_form.addRow("XSDB tool", self.xsdb_exec_edit)
        layout.addWidget(self.xsdb_container)

        config_form = QtWidgets.QFormLayout()
        self.gain_spin = self._spin(0, 65535, 65535)
        self.offset_raw_spin = self._spin(0, 65535, 0)
        self.gain_spin.valueChanged.connect(self.generate)
        self.offset_raw_spin.valueChanged.connect(self.generate)
        config_form.addRow("Gain Q0.16", self.gain_spin)
        config_form.addRow("Offset raw", self.offset_raw_spin)
        layout.addLayout(config_form)

        self.uart_container = QtWidgets.QWidget()
        uart_layout = QtWidgets.QVBoxLayout(self.uart_container)
        uart_layout.setContentsMargins(0, 0, 0, 0)
        uart_layout.setSpacing(8)
        port_row = QtWidgets.QHBoxLayout()
        self.port_combo = QtWidgets.QComboBox()
        self.refresh_button = QtWidgets.QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh_ports)
        port_row.addWidget(self.port_combo, 1)
        port_row.addWidget(self.refresh_button)
        uart_layout.addLayout(port_row)

        form = QtWidgets.QFormLayout()
        self.baud_combo = QtWidgets.QComboBox()
        for baud in ["9600", "19200", "38400", "57600", "115200"]:
            self.baud_combo.addItem(baud)
        form.addRow("Baud", self.baud_combo)
        uart_layout.addLayout(form)

        self.connect_button = QtWidgets.QPushButton("Connect")
        self.connect_button.clicked.connect(self.toggle_serial)
        uart_layout.addWidget(self.connect_button)
        layout.addWidget(self.uart_container)

        self.send_wave_button = QtWidgets.QPushButton("Send Waveform")
        self.send_wave_button.setObjectName("primaryButton")
        self.send_wave_button.clicked.connect(self.send_waveform)
        layout.addWidget(self.send_wave_button)

        action_row = QtWidgets.QHBoxLayout()
        send_config = QtWidgets.QPushButton("Apply Config")
        send_config.clicked.connect(self.send_config)
        check = QtWidgets.QPushButton("Check")
        check.clicked.connect(self.send_ping)
        action_row.addWidget(send_config)
        action_row.addWidget(check)
        layout.addLayout(action_row)

        more_menu = QtWidgets.QMenu(self)
        more_menu.addAction("Enable Output", lambda checked=False: self.send_enable(True))
        more_menu.addAction("Reset AWG", self.send_reset)
        more_menu.addSeparator()
        more_menu.addAction("Export MEM", self.export_mem)
        more_menu.addAction("Copy C Array", self.copy_c_array)
        more_menu.addAction("Export XSDB Script", self.export_xsdb_full)
        more_menu.addAction("Copy XSDB Config", self.copy_xsdb_config)
        more_button = QtWidgets.QToolButton()
        more_button.setText("More")
        more_button.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        more_button.setMenu(more_menu)
        layout.addWidget(more_button)

        self.progress = QtWidgets.QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress_label = QtWidgets.QLabel("Idle")
        self.progress_label.setStyleSheet("color: #334155; background: transparent;")
        layout.addWidget(self.progress)
        layout.addWidget(self.progress_label)

        self.log_box = QtWidgets.QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setMinimumHeight(220)
        self.log_box.setStyleSheet(
            "background: #111827; color: #f8fafc; font-family: Consolas, monospace; border: 1px solid #334155;"
        )
        layout.addWidget(self.log_box, 1)
        return box

    def _spin(self, low: int, high: int, value: int) -> QtWidgets.QSpinBox:
        spin = QtWidgets.QSpinBox()
        spin.setRange(low, high)
        spin.setValue(value)
        spin.valueChanged.connect(self.generate)
        return spin

    def _double_spin(
        self, low: float, high: float, value: float, step: float, decimals: int
    ) -> QtWidgets.QDoubleSpinBox:
        spin = QtWidgets.QDoubleSpinBox()
        spin.setRange(low, high)
        spin.setDecimals(decimals)
        spin.setSingleStep(step)
        spin.setValue(value)
        spin.valueChanged.connect(self.generate)
        return spin

    def _slider_row(
        self, low: int, high: int, value: int, suffix: str
    ) -> tuple[QtWidgets.QSlider, QtWidgets.QLabel, QtWidgets.QWidget]:
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        slider.setRange(low, high)
        slider.setValue(value)
        out = QtWidgets.QLabel(f"{value}{suffix}")
        out.setMinimumWidth(48)

        def update_label(new_value: int) -> None:
            out.setText(f"{new_value}{suffix}")
            self.generate()

        slider.valueChanged.connect(update_label)
        layout.addWidget(slider, 1)
        layout.addWidget(out)
        return slider, out, widget

    def _meter(self, title: str) -> tuple[QtWidgets.QWidget, QtWidgets.QLabel]:
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(10, 8, 10, 8)
        caption = QtWidgets.QLabel(title)
        caption.setStyleSheet("color: #334155; background: transparent;")
        value = QtWidgets.QLabel("0")
        font = value.font()
        font.setPointSize(13)
        font.setBold(True)
        value.setFont(font)
        layout.addWidget(caption)
        layout.addWidget(value)
        widget.setStyleSheet("background: #ffffff; border: 1px solid #cbd5e1; border-radius: 8px;")
        return widget, value

    def settings(self) -> GeneratorSettings:
        return GeneratorSettings(
            mode=self.mode,
            freq_hz=float(self.freq_spin.value()),
            clock_hz=float(self.clock_spin.value()),
            amplitude_percent=int(self.amplitude_slider.value()),
            offset_percent=int(self.offset_slider.value()),
            cycles=int(self.cycles_slider.value()),
            phase_degrees=int(self.phase_slider.value()),
            duty_percent=int(self.duty_slider.value()),
            harmonics=int(self.harmonics_slider.value()),
            wildness_percent=int(self.wildness_slider.value()),
            seed=int(self.seed_spin.value()),
            formula=self.formula_edit.toPlainText(),
            soft_clip=self.soft_clip_check.isChecked(),
            invert=self.invert_check.isChecked(),
            dc_block=self.dc_block_check.isChecked(),
            gain_q16=int(self.gain_spin.value()),
            offset_raw=int(self.offset_raw_spin.value()),
        )

    def set_mode(self, mode: str) -> None:
        self.mode = mode
        visible = mode == "formula"
        self.formula_label.setVisible(visible)
        self.formula_edit.setVisible(visible)
        self.generate()

    def generate(self) -> None:
        if not hasattr(self, "freq_spin"):
            return
        settings = self.settings()
        self.samples = generate_samples(settings)
        self.wave_plot.set_samples(self.samples)
        self.hist_plot.set_samples(self.samples)
        minimum = min(self.samples)
        maximum = max(self.samples)
        mean = safe_round(sum(self.samples) / len(self.samples))
        phase_step = compute_phase_step(settings.freq_hz, settings.clock_hz)
        self.min_label.setText(str(minimum))
        self.max_label.setText(str(maximum))
        self.mean_label.setText(str(mean))
        self.phase_step_label.setText(hex32(phase_step))
        self.packet_size_label.setText(f"{len(build_load_payload(self.samples)) + 9} bytes")

    def reset_controls(self) -> None:
        self.freq_spin.setValue(1000.0)
        self.clock_spin.setValue(100_000_000.0)
        self.amplitude_slider.setValue(92)
        self.offset_slider.setValue(50)
        self.cycles_slider.setValue(1)
        self.phase_slider.setValue(0)
        self.duty_slider.setValue(50)
        self.harmonics_slider.setValue(7)
        self.wildness_slider.setValue(18)
        self.seed_spin.setValue(1337)
        self.gain_spin.setValue(65535)
        self.offset_raw_spin.setValue(0)
        self.soft_clip_check.setChecked(True)
        self.invert_check.setChecked(False)
        self.dc_block_check.setChecked(False)
        for button in self.mode_group.buttons():
            if button.property("mode") == "sine":
                button.setChecked(True)
                break
        self.set_mode("sine")

    def randomize_controls(self) -> None:
        modes = ["sine", "square", "triangle", "saw", "fm", "additive", "noise", "spikes"]
        mode = py_random.choice(modes)
        for button in self.mode_group.buttons():
            if button.property("mode") == mode:
                button.setChecked(True)
                break
        self.set_mode(mode)
        self.cycles_slider.setValue(1 + py_random.randrange(9))
        self.phase_slider.setValue(py_random.randrange(360))
        self.duty_slider.setValue(12 + py_random.randrange(76))
        self.harmonics_slider.setValue(2 + py_random.randrange(18))
        self.wildness_slider.setValue(10 + py_random.randrange(74))
        self.seed_spin.setValue(1 + py_random.randrange(999_999))
        self.generate()

    def refresh_ports(self) -> None:
        current = self.port_combo.currentData() if hasattr(self, "port_combo") else None
        self.port_combo.clear()
        if list_ports is None:
            self.port_combo.addItem("pyserial missing", None)
            return
        ports = list(list_ports.comports())
        if not ports:
            self.port_combo.addItem("No COM ports found", None)
            return
        selected_index = 0
        for index, port in enumerate(ports):
            label = f"{port.device} - {port.description}"
            self.port_combo.addItem(label, port.device)
            if port.device == current:
                selected_index = index
        self.port_combo.setCurrentIndex(selected_index)

    def transport_mode(self) -> str:
        if not hasattr(self, "transport_combo"):
            return "xsdb"
        return str(self.transport_combo.currentData() or "xsdb")

    def update_transport_controls(self) -> None:
        if not hasattr(self, "port_combo"):
            return
        xsdb_mode = self.transport_mode() == "xsdb"
        if xsdb_mode and self.serial_port is not None:
            self.disconnect_serial()
        self.xsdb_container.setVisible(xsdb_mode)
        self.uart_container.setVisible(not xsdb_mode)
        self.xsdb_exec_edit.setEnabled(xsdb_mode)
        self.port_combo.setEnabled(not xsdb_mode and self.serial_port is None)
        self.refresh_button.setEnabled(not xsdb_mode and self.serial_port is None)
        self.baud_combo.setEnabled(not xsdb_mode and self.serial_port is None)
        self.connect_button.setEnabled(not xsdb_mode)
        if xsdb_mode:
            self.status_label.setText("XSDB/JTAG ready")
            self.connect_button.setText("Connect")
        else:
            self.set_connected(self.serial_port is not None)

    def set_connected(self, connected: bool) -> None:
        self.status_label.setText("Serial connected" if connected else "Serial disconnected")
        self.connect_button.setText("Disconnect" if connected else "Connect")
        uart_mode = self.transport_mode() == "uart"
        self.port_combo.setEnabled(uart_mode and not connected)
        self.refresh_button.setEnabled(uart_mode and not connected)
        self.baud_combo.setEnabled(uart_mode and not connected)
        self.rx_timer.start() if connected else self.rx_timer.stop()

    def toggle_serial(self) -> None:
        if self.serial_port is not None:
            self.disconnect_serial()
            return
        if serial is None:
            self.log("Cannot open serial port because pyserial is not installed")
            return
        port_name = self.port_combo.currentData()
        if not port_name:
            self.log("No COM port selected")
            return
        try:
            baud = int(self.baud_combo.currentText())
            self.serial_port = serial.Serial(port_name, baudrate=baud, timeout=0, write_timeout=2)
            self.set_connected(True)
            self.log(f"Opened {port_name} at {baud} baud")
        except Exception as exc:
            self.serial_port = None
            self.set_connected(False)
            self.log(f"Serial open failed: {exc}")

    def disconnect_serial(self) -> None:
        if self.send_worker is not None and self.send_worker.isRunning():
            self.send_worker.cancel()
            self.send_worker.wait(1500)
        try:
            if self.serial_port is not None:
                self.serial_port.close()
        except Exception as exc:
            self.log(f"Disconnect warning: {exc}")
        finally:
            self.serial_port = None
            self.set_connected(False)

    def poll_serial_rx(self) -> None:
        if self.serial_port is None:
            return
        try:
            waiting = self.serial_port.in_waiting
            if waiting:
                data = self.serial_port.read(waiting)
                text = data.decode("utf-8", errors="replace").replace("\r", "").strip()
                if text:
                    self.log(f"RX {text}")
        except Exception as exc:
            self.log(f"RX stopped: {exc}")
            self.disconnect_serial()

    def write_packets(self, packets: list[tuple[str, bytes]]) -> None:
        if self.transport_mode() != "uart":
            self.log("UART transport is not selected")
            return
        if self.serial_port is None:
            self.log("No serial port open")
            return
        if self.send_worker is not None and self.send_worker.isRunning():
            self.log("A send is already in progress")
            return
        self.send_worker = SendWorker(self.serial_port, packets, self)
        self.send_worker.progress.connect(self.update_progress)
        self.send_worker.message.connect(self.log)
        self.send_worker.done.connect(self.send_done)
        self.send_wave_button.setEnabled(False)
        self.send_worker.start()

    def write_xsdb(self, label: str, script_text: str) -> None:
        if self.transport_mode() != "xsdb":
            self.log("XSDB/JTAG transport is not selected")
            return
        if self.xsdb_worker is not None and self.xsdb_worker.isRunning():
            self.log("An XSDB operation is already in progress")
            return
        executable = self.xsdb_exec_edit.text().strip().strip('"') or "xsdb"
        self.xsdb_worker = XsdbWorker(executable, script_text, label, self)
        self.xsdb_worker.progress.connect(self.update_progress)
        self.xsdb_worker.message.connect(self.log)
        self.xsdb_worker.done.connect(self.xsdb_done)
        self.send_wave_button.setEnabled(False)
        self.xsdb_worker.start()

    def update_progress(self, value: int, text: str) -> None:
        self.progress.setValue(value)
        self.progress_label.setText(text)

    def send_done(self, ok: bool) -> None:
        self.send_wave_button.setEnabled(True)
        if ok:
            self.progress_label.setText("Done")
        else:
            self.progress_label.setText("Stopped")

    def xsdb_done(self, ok: bool) -> None:
        self.send_wave_button.setEnabled(True)
        self.progress_label.setText("Done" if ok else "XSDB failed")

    def send_waveform(self) -> None:
        self.generate()
        settings = self.settings()
        if self.transport_mode() == "xsdb":
            self.write_xsdb("Waveform", xsdb_full_text(settings, self.samples))
            return
        packets = [
            ("Waveform", build_packet(CMD_LOAD, build_load_payload(self.samples))),
            ("Config", build_packet(CMD_CONFIG, build_config_payload(settings, True))),
        ]
        self.write_packets(packets)

    def send_config(self) -> None:
        settings = self.settings()
        if self.transport_mode() == "xsdb":
            self.write_xsdb("Config", xsdb_config_text(settings))
            return
        self.write_packets([("Config", build_packet(CMD_CONFIG, build_config_payload(settings, True)))])

    def send_enable(self, enable: bool) -> None:
        if self.transport_mode() == "xsdb":
            self.write_xsdb("Enable" if enable else "Disable", xsdb_enable_text(enable))
            return
        self.write_packets([("Enable" if enable else "Disable", build_packet(CMD_ENABLE, bytes([1 if enable else 0])))])

    def send_reset(self) -> None:
        if self.transport_mode() == "xsdb":
            self.write_xsdb("Reset", xsdb_reset_text())
            return
        self.write_packets([("Reset", build_packet(CMD_RESET))])

    def send_ping(self) -> None:
        if self.transport_mode() == "xsdb":
            self.write_xsdb("XSDB check", xsdb_check_text())
            return
        self.write_packets([("Ping", build_packet(CMD_PING))])

    def export_mem(self) -> None:
        self.generate()
        self.save_text("waveform.mem", mem_text(self.samples))

    def copy_c_array(self) -> None:
        self.generate()
        QtWidgets.QApplication.clipboard().setText(c_array_text(self.samples))
        self.log("Copied C array to clipboard")

    def export_xsdb_full(self) -> None:
        self.generate()
        self.save_text("awg_update.tcl", xsdb_full_text(self.settings(), self.samples))

    def copy_xsdb_config(self) -> None:
        self.generate()
        QtWidgets.QApplication.clipboard().setText(xsdb_config_text(self.settings()))
        self.log("Copied XSDB config script to clipboard")

    def save_text(self, default_name: str, text: str) -> None:
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save file", str(Path.cwd() / default_name), "Text files (*)")
        if not path:
            return
        Path(path).write_text(text, encoding="utf-8", newline="\n")
        self.log(f"Saved {path}")

    def log(self, message: str) -> None:
        timestamp = time.strftime("%H:%M:%S")
        self.log_box.append(f"[{timestamp}] {message}")
        cursor = self.log_box.textCursor()
        cursor.movePosition(QtGui.QTextCursor.MoveOperation.End)
        self.log_box.setTextCursor(cursor)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        self.disconnect_serial()
        event.accept()


def main() -> int:
    app = QtWidgets.QApplication(sys.argv)
    apply_light_palette(app)
    app.setApplicationName("AWG Signal Forge Qt")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
