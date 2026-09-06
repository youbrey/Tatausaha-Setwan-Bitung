from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget


class PDFCanvas(QWidget):
    area_selected = Signal(list)
    block_selected = Signal(dict)

    def __init__(self):
        super().__init__()
        self.pixmap = QPixmap()
        self.blocks = []
        self.mode = "view"
        self.selection = None
        self.start = None
        self.zoom = 1.0
        self.page_size = (595.28, 841.89)
        self.setMinimumSize(300, 400)

    def load(self, path: str, metadata: dict):
        self.pixmap = QPixmap(path)
        self.blocks = metadata["blocks"]
        self.page_size = (metadata["width"], metadata["height"])
        self.selection = None
        self.set_zoom(self.zoom)

    def set_zoom(self, zoom: float):
        self.zoom = zoom
        width, height = self.page_size
        self.setFixedSize(round(width * zoom + 40), round(height * zoom + 40))
        self.update()

    def paper(self):
        return QRectF(20, 20, self.width() - 40, self.height() - 40)

    def _point(self, position):
        paper = self.paper()
        return QPointF(max(0, min(1, (position.x() - paper.x()) / paper.width())),
                       max(0, min(1, (position.y() - paper.y()) / paper.height())))

    def _rect(self, values):
        paper = self.paper()
        a, b, c, d = values
        return QRectF(paper.x() + a * paper.width(), paper.y() + b * paper.height(),
                      (c - a) * paper.width(), (d - b) * paper.height())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#e7edf4"))
        paper = self.paper()
        painter.fillRect(paper.translated(3, 4), QColor("#c4ccd7"))
        painter.fillRect(paper, Qt.GlobalColor.white)
        if not self.pixmap.isNull():
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            painter.drawPixmap(paper, self.pixmap, QRectF(self.pixmap.rect()))
        else:
            painter.setPen(QColor("#64748b"))
            painter.drawText(paper, Qt.AlignmentFlag.AlignCenter, "Buka PDF untuk mulai mengedit")
        painter.setPen(QPen(QColor("#2379ec"), 1, Qt.PenStyle.DashLine))
        if self.mode == "replace_text":
            for block in self.blocks:
                painter.drawRect(self._rect(block["visual"]))
        if self.selection:
            painter.fillRect(self._rect(self.selection), QColor(35, 121, 236, 35))
            painter.setPen(QPen(QColor("#2379ec"), 2))
            painter.drawRect(self._rect(self.selection))

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton or self.pixmap.isNull() or not self.paper().contains(event.position()):
            return
        point = self._point(event.position())
        if self.mode == "replace_text":
            matches = [b for b in self.blocks if self._rect(b["visual"]).contains(event.position())]
            if matches:
                block = min(matches, key=lambda b: (b["visual"][2] - b["visual"][0]) * (b["visual"][3] - b["visual"][1]))
                self.selection = block["visual"]
                self.block_selected.emit(block)
                self.update()
        elif self.mode in {"text", "image"}:
            self.start = point
            self.selection = [point.x(), point.y(), point.x(), point.y()]

    def mouseMoveEvent(self, event):
        if self.start is None:
            return
        point = self._point(event.position())
        self.selection = [min(self.start.x(), point.x()), min(self.start.y(), point.y()),
                          max(self.start.x(), point.x()), max(self.start.y(), point.y())]
        self.update()

    def mouseReleaseEvent(self, event):
        if self.start is not None:
            self.mouseMoveEvent(event)
            self.start = None
            self.area_selected.emit(self.selection)
