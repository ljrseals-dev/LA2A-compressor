"""PyQt6 front end on the 1965 panel photo. UNTESTED on a display (author had no PyQt6 in the sandbox).
Run: python la2a_gui.py   (needs PyQt6, numpy, scipy; panel image la2a_panel_1965.png next to it)
Power switch = mute (the manual lists no bypass). Slope switch (post-serial-572 feature, default Limit) is live: click it."""
import sys, os, math, tempfile
import numpy as np
from scipy.io import wavfile
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QPointF, QRectF, QTimer, QElapsedTimer, QUrl
from PyQt6.QtGui import QPixmap, QPainter, QColor, QPen, QBrush
from PyQt6.QtWidgets import QApplication, QWidget, QFileDialog, QProgressBar, QVBoxLayout, QLabel
from PyQt6.QtMultimedia import QSoundEffect
import la2a_app_logic as L

HERE = os.path.dirname(os.path.abspath(__file__))
# Hotspots in la2a_panel_1965.png pixel coords (estimated from the photo; nudge if off).
GAIN_C, PR_C, SEL_C = (318, 181), (778, 181), (931, 109)
KNOB_R = 38
VU_PIVOT, VU_LEN = (546, 190), 105          # needle pivot/length [?] estimated
SLOPE_C, POWER_C = (108, 224), (936, 219)

def load_wav(path):
    sr, x = wavfile.read(path)
    if x.dtype == np.int16: x = x / 32768.0
    elif x.dtype == np.int32: x = x / 2147483648.0
    elif x.dtype == np.uint8: x = (x - 128) / 128.0
    return sr, x.astype(float)

class Worker(QThread):
    done = pyqtSignal(object); prog = pyqtSignal(float)
    def __init__(self, x, sr, g, p, pw, mode): super().__init__(); self.a = (x, sr, g, p, pw, mode)
    def run(self):
        x, sr, g, p, pw, mode = self.a
        y, grs = L.process_file(x, sr, g, p, pw, progress=self.prog.emit, mode=mode)
        self.done.emit((y, grs, sr))

class Panel(QWidget):
    def __init__(self):
        super().__init__()
        self.pix = QPixmap(os.path.join(HERE, "la2a_panel_1965.png"))
        if self.pix.isNull(): raise FileNotFoundError("la2a_panel_1965.png must sit next to la2a_gui.py")
        self.setFixedSize(self.pix.size()); self.setAcceptDrops(True)
        self.gain, self.pr, self.sel, self.power, self.mode = 50.0, 40.0, 1, True, "limit"   # sel 0=out+10 1=GR 2=out+4
        self.sr = 48000; self.x = None; self.result = None; self.track = None
        self.drag = None; self.vu = 0.0
        self.player = QSoundEffect(); self.clock = QElapsedTimer()
        self.timer = QTimer(self); self.timer.timeout.connect(self.tick); self.timer.start(30)
        self.status = "Drop a WAV on the panel. Click the meter knob to switch meter. Space = play."
    # ---- interaction
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls(): e.acceptProposedAction()
    def dropEvent(self, e):
        p = e.mimeData().urls()[0].toLocalFile()
        try: self.sr, self.x = load_wav(p); self.status = f"Loaded {os.path.basename(p)}"; self.render()
        except Exception as ex: self.status = f"Load failed: {ex}"
        self.update()
    def hit(self, c, pos, r=KNOB_R + 8): return (pos.x() - c[0]) ** 2 + (pos.y() - c[1]) ** 2 <= r * r
    def mousePressEvent(self, e):
        p = e.position()
        if self.hit(GAIN_C, p): self.drag = ("g", p.y(), self.gain)
        elif self.hit(PR_C, p): self.drag = ("p", p.y(), self.pr)
        elif self.hit(SEL_C, p): self.sel = (self.sel + 1) % 3; self.rebuild_track()
        elif self.hit(SLOPE_C, p, 30): self.mode = "compress" if self.mode == "limit" else "limit"; self.render()
        elif self.hit(POWER_C, p, 22): self.power = not self.power; self.render()
        self.update()
    def mouseMoveEvent(self, e):
        if not self.drag: return
        k, y0, v0 = self.drag; v = float(np.clip(v0 + (y0 - e.position().y()) * 0.6, 0, 100))
        if k == "g": self.gain = v
        else: self.pr = v
        self.update()
    def mouseReleaseEvent(self, e):
        if self.drag: self.drag = None; self.render()     # re-render offline on release
    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Space: self.play()
    # ---- processing / playback
    def render(self):
        if self.x is None: return
        self.status = "Processing…"; self.update()
        self.w = Worker(self.x, self.sr, self.gain, self.pr, self.power, self.mode)
        self.w.done.connect(self.on_done); self.w.start()
    def on_done(self, r):
        self.result = r; self.rebuild_track(); self.status = "Ready. Space = play."; self.update()
    def rebuild_track(self):
        if not self.result: return
        y, grs, sr = self.result
        self.track = L.meter_track(y, grs, sr, ("out10", "gr", "out4")[self.sel])
    def play(self):
        if not self.result: return
        y, _, sr = self.result
        pk = max(1e-9, float(np.abs(y).max())); y16 = (np.clip(y / max(1.0, pk), -1, 1) * 32767).astype(np.int16)
        path = os.path.join(tempfile.gettempdir(), "la2a_preview.wav"); wavfile.write(path, sr, y16)
        self.player.setSource(QUrl.fromLocalFile(path)); self.player.play(); self.clock.start()
    def tick(self):
        if self.track and self.clock.isValid():
            vals, hop = self.track; i = int(self.clock.elapsed() / 1000.0 / hop)
            self.vu = float(vals[i]) if i < len(vals) else 0.0 if self.sel == 1 else -20.0
        else: self.vu = 0.0 if self.sel == 1 else -20.0
        self.update()
    # ---- painting
    def paintEvent(self, e):
        q = QPainter(self); q.setRenderHint(QPainter.RenderHint.Antialiasing)
        q.drawPixmap(0, 0, self.pix)
        for c, v in ((GAIN_C, self.gain), (PR_C, self.pr)): self.knob(q, c, v)
        self.knob(q, SEL_C, (0, 50, 100)[self.sel], r=34)          # meter selector knob (3 positions)
        a = math.radians(-45 + 90 * (self.vu + 20) / 23.0)           # -20..+3 VU -> -45..+45 deg [?] face calibration
        px, py = VU_PIVOT; q.setPen(QPen(QColor(20, 20, 20), 2))
        q.drawLine(QPointF(px, py), QPointF(px + VU_LEN * math.sin(a), py - VU_LEN * math.cos(a)))
        q.setBrush(QColor(235, 235, 235)); q.setPen(QPen(QColor(60, 60, 60), 2))   # slope-switch position marker
        q.drawEllipse(QPointF(SLOPE_C[0], SLOPE_C[1] - 14 if self.mode == "limit" else SLOPE_C[1] + 14), 7, 7)
        if not self.power: q.setBrush(QColor(0, 0, 0, 90)); q.drawRect(self.rect())
        q.setPen(QColor(40, 40, 40)); q.drawText(10, self.height() - 8, self.status)
    def knob(self, q, c, v, r=KNOB_R):
        q.setBrush(QBrush(QColor(22, 22, 22))); q.setPen(QPen(QColor(70, 70, 70), 2))
        q.drawEllipse(QPointF(*c), r, r)
        a = math.radians(-135 + 270 * v / 100.0)
        q.setPen(QPen(QColor(235, 235, 235), 3))
        q.drawLine(QPointF(c[0] + 0.25 * r * math.sin(a), c[1] - 0.25 * r * math.cos(a)),
                   QPointF(c[0] + 0.9 * r * math.sin(a), c[1] - 0.9 * r * math.cos(a)))

if __name__ == "__main__":
    app = QApplication(sys.argv); w = Panel(); w.setWindowTitle("LA-2A (1965) — behavioral model, unvalidated")
    w.setFocusPolicy(Qt.FocusPolicy.StrongFocus); w.show(); sys.exit(app.exec())
