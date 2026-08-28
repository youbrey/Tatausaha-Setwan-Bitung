from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QTextBlockFormat,
    QTextCursor,
    QTransform,
)
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsDropShadowEffect,
    QGraphicsObject,
    QGraphicsScene,
    QGraphicsSceneMouseEvent,
    QGraphicsTextItem,
    QStyleOptionGraphicsItem,
    QWidget,
)

from sekretariat_app.documentation.models import DocumentPage, PhotoElement, TextElement
from sekretariat_app.documentation.templates import layout_rectangles, template_by_id


class PhotoItem(QGraphicsObject):
    changed = Signal()
    request_crop = Signal(object)

    HANDLE = 4.0

    def __init__(self, data: dict, parent: QGraphicsItem | None = None):
        super().__init__(parent)
        self.data = data
        self._rect = QRectF(0, 0, float(data.get("width", 80)), float(data.get("height", 60)))
        self._pixmap = QPixmap()
        self._loaded_path = ""
        self._resizing = False
        self._start_rect = QRectF()
        self.setPos(float(data.get("x", 20)), float(data.get("y", 20)))
        self.setRotation(float(data.get("rotation", 0)))
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
            | QGraphicsItem.GraphicsItemFlag.ItemIsFocusable
            | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)
        self.set_locked(bool(data.get("locked", False)))

    def boundingRect(self) -> QRectF:
        extra = self.HANDLE + 1
        return self._rect.adjusted(-1, -1, extra, extra)

    def set_locked(self, locked: bool) -> None:
        self.data["locked"] = locked
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, not locked)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.update()

    def _load_pixmap(self) -> QPixmap:
        path = str(self.data.get("photo_path", ""))
        if path != self._loaded_path:
            self._loaded_path = path
            self._pixmap = QPixmap(path) if path and Path(path).exists() else QPixmap()
        rotation = int(self.data.get("image_rotation", 0)) % 360
        if rotation and not self._pixmap.isNull():
            return self._pixmap.transformed(QTransform().rotate(rotation), Qt.TransformationMode.SmoothTransformation)
        return self._pixmap

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None) -> None:
        del option, widget
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self._rect
        radius = max(0.0, float(self.data.get("radius", 1.5)))
        clip = QPainterPath()
        clip.addRoundedRect(rect, radius, radius)

        painter.save()
        painter.setClipPath(clip)
        painter.fillRect(rect, QColor("#e2e8f0"))
        pixmap = self._load_pixmap()
        if pixmap.isNull():
            painter.setPen(QColor("#64748b"))
            placeholder_font = QFont("Segoe UI")
            placeholder_font.setPixelSize(4)
            painter.setFont(placeholder_font)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "Klik dua kali\nuntuk memilih foto")
        else:
            self._draw_photo(painter, pixmap, rect)
        if self.data.get("show_caption") and self.data.get("caption"):
            caption_height = min(12.0, rect.height() * 0.22)
            caption_rect = QRectF(rect.left(), rect.bottom() - caption_height, rect.width(), caption_height)
            painter.fillRect(caption_rect, QColor(15, 23, 42, 190))
            painter.setPen(Qt.GlobalColor.white)
            font = QFont("Arial")
            font.setPixelSize(3)
            painter.setFont(font)
            painter.drawText(caption_rect.adjusted(2, 0, -2, 0), Qt.AlignmentFlag.AlignCenter, str(self.data["caption"]))
        painter.restore()

        border_width = max(0.0, float(self.data.get("border_width", 0.5)))
        if border_width:
            painter.setPen(QPen(QColor(str(self.data.get("border_color", "#94a3b8"))), border_width))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(rect, radius, radius)
        if self.isSelected():
            painter.setPen(QPen(QColor("#0284c7"), 0.8, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(rect)
            if not self.data.get("locked"):
                painter.setBrush(QColor("#0284c7"))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRect(self._handle_rect())

    def _draw_photo(self, painter: QPainter, pixmap: QPixmap, target: QRectF) -> None:
        fit = str(self.data.get("fit", "cover"))
        source = QRectF(pixmap.rect())
        if fit == "fill":
            painter.drawPixmap(target, pixmap, source)
            return
        source_aspect = source.width() / max(1.0, source.height())
        target_aspect = target.width() / max(1.0, target.height())
        if fit == "contain":
            if source_aspect > target_aspect:
                height = target.width() / source_aspect
                draw_rect = QRectF(target.left(), target.center().y() - height / 2, target.width(), height)
            else:
                width = target.height() * source_aspect
                draw_rect = QRectF(target.center().x() - width / 2, target.top(), width, target.height())
            painter.drawPixmap(draw_rect, pixmap, source)
            return

        if source_aspect > target_aspect:
            source_width = source.height() * target_aspect
            source_height = source.height()
        else:
            source_width = source.width()
            source_height = source.width() / target_aspect
        zoom = max(1.0, min(5.0, float(self.data.get("zoom", 1.0))))
        source_width /= zoom
        source_height /= zoom
        max_x = max(0.0, source.width() - source_width)
        max_y = max(0.0, source.height() - source_height)
        crop_x = max(0.0, min(1.0, float(self.data.get("crop_x", 0.5))))
        crop_y = max(0.0, min(1.0, float(self.data.get("crop_y", 0.5))))
        source_rect = QRectF(max_x * crop_x, max_y * crop_y, source_width, source_height)
        painter.drawPixmap(target, pixmap, source_rect)

    def _handle_rect(self) -> QRectF:
        return QRectF(self._rect.right() - self.HANDLE, self._rect.bottom() - self.HANDLE, self.HANDLE, self.HANDLE)

    def hoverMoveEvent(self, event) -> None:
        if not self.data.get("locked") and self._handle_rect().contains(event.pos()):
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        else:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        super().hoverMoveEvent(event)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and not self.data.get("locked") and self._handle_rect().contains(event.pos()):
            self._resizing = True
            self._start_rect = QRectF(self._rect)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        if self._resizing:
            point = event.pos()
            self.prepareGeometryChange()
            self._rect.setWidth(max(15.0, point.x()))
            self._rect.setHeight(max(15.0, point.y()))
            self.update()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        if self._resizing:
            self._resizing = False
            self.changed.emit()
            event.accept()
            return
        super().mouseReleaseEvent(event)
        self.changed.emit()

    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        self.request_crop.emit(self)
        event.accept()

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and self.scene():
            bounds = self.scene().sceneRect()
            pos = value
            x = max(bounds.left(), min(pos.x(), bounds.right() - self._rect.width()))
            y = max(bounds.top(), min(pos.y(), bounds.bottom() - self._rect.height()))
            return QPointF(x, y)
        return super().itemChange(change, value)

    def to_data(self) -> dict:
        self.data.update(
            x=round(self.pos().x(), 3),
            y=round(self.pos().y(), 3),
            width=round(self._rect.width(), 3),
            height=round(self._rect.height(), 3),
            rotation=round(self.rotation(), 3),
        )
        return dict(self.data)


class TextItem(QGraphicsTextItem):
    def __init__(self, data: dict):
        super().__init__()
        self.data = data
        self.setPlainText(str(data.get("text", "Teks")))
        self.setTextWidth(float(data.get("width", 120.0)))
        self.setPos(float(data.get("x", 25.0)), float(data.get("y", 25.0)))
        self.setRotation(float(data.get("rotation", 0.0)))
        self.setOpacity(float(data.get("opacity", 1.0)))
        self.setDefaultTextColor(QColor(str(data.get("color", "#0f172a"))))
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
            | QGraphicsItem.GraphicsItemFlag.ItemIsFocusable
            | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.apply_font()
        self.set_locked(bool(data.get("locked", False)))

    def apply_font(self) -> None:
        font = QFont(str(self.data.get("font_family", "Arial")))
        font.setPixelSize(max(2, round(float(self.data.get("font_size", 14)) * 0.352778)))
        font.setBold(bool(self.data.get("bold", False)))
        font.setItalic(bool(self.data.get("italic", False)))
        font.setUnderline(bool(self.data.get("underline", False)))
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, float(self.data.get("letter_spacing", 0.0)) * 0.352778)
        self.setFont(font)
        self.setDefaultTextColor(QColor(str(self.data.get("color", "#0f172a"))))
        cursor = self.textCursor()
        cursor.select(QTextCursor.SelectionType.Document)
        block_format = cursor.blockFormat()
        alignment = str(self.data.get("alignment", "left"))
        block_format.setAlignment(
            {
                "center": Qt.AlignmentFlag.AlignCenter,
                "right": Qt.AlignmentFlag.AlignRight,
                "justify": Qt.AlignmentFlag.AlignJustify,
            }.get(alignment, Qt.AlignmentFlag.AlignLeft)
        )
        block_format.setLineHeight(
            float(self.data.get("line_height", 1.2)) * 100,
            QTextBlockFormat.LineHeightTypes.ProportionalHeight.value,
        )
        cursor.mergeBlockFormat(block_format)
        effect = str(self.data.get("effect", "none"))
        if effect in {"shadow", "glow"}:
            shadow = QGraphicsDropShadowEffect()
            shadow.setColor(QColor(str(self.data.get("effect_color", "#334155"))))
            shadow.setBlurRadius(10 if effect == "glow" else 5)
            shadow.setOffset(0 if effect == "glow" else 2, 0 if effect == "glow" else 2)
            self.setGraphicsEffect(shadow)
        else:
            self.setGraphicsEffect(None)

    def set_locked(self, locked: bool) -> None:
        self.data["locked"] = locked
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, not locked)

    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        if not self.data.get("locked"):
            self.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
            self.setFocus(Qt.FocusReason.MouseFocusReason)
        super().mouseDoubleClickEvent(event)

    def focusOutEvent(self, event) -> None:
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.data["text"] = self.toPlainText()
        super().focusOutEvent(event)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None) -> None:
        background = QColor(str(self.data.get("background", "#00ffffff")))
        if background.alpha() > 0:
            painter.fillRect(self.boundingRect(), background)
        super().paint(painter, option, widget)
        if self.isSelected():
            painter.setPen(QPen(QColor("#0284c7"), 0.7, Qt.PenStyle.DashLine))
            painter.drawRect(self.boundingRect())

    def to_data(self) -> dict:
        self.data.update(
            text=self.toPlainText(),
            x=round(self.pos().x(), 3),
            y=round(self.pos().y(), 3),
            width=round(self.textWidth(), 3),
            rotation=round(self.rotation(), 3),
            opacity=round(self.opacity(), 3),
        )
        return dict(self.data)


class DocumentScene(QGraphicsScene):
    content_changed = Signal()
    crop_requested = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.page_width = 215.0
        self.page_height = 330.0
        self.margins = (15.0, 15.0, 15.0, 15.0)
        self.background_color = QColor("#ffffff")
        self.letterhead: dict = {}
        self.show_guides = True
        self.setSceneRect(0, 0, self.page_width, self.page_height)
        self.selectionChanged.connect(self.update)

    def configure_page(
        self,
        width: float,
        height: float,
        margins: tuple[float, float, float, float],
        background: str = "#ffffff",
        letterhead: dict | None = None,
    ) -> None:
        self.page_width = width
        self.page_height = height
        self.margins = margins
        self.background_color = QColor(background)
        self.letterhead = dict(letterhead or {})
        self.setSceneRect(0, 0, width, height)
        self.update()

    def drawBackground(self, painter: QPainter, rect: QRectF) -> None:
        painter.fillRect(rect, QColor("#cbd5e1"))
        painter.fillRect(self.sceneRect(), self.background_color)

    def drawForeground(self, painter: QPainter, rect: QRectF) -> None:
        del rect
        if self.letterhead.get("enabled"):
            self._draw_letterhead(painter)
        if not self.show_guides:
            return
        top, right, bottom, left = self.effective_margins()
        guide = QRectF(left, top, self.page_width - left - right, self.page_height - top - bottom)
        painter.setPen(QPen(QColor(2, 132, 199, 100), 0.35, Qt.PenStyle.DashLine))
        painter.drawRect(guide)

    def _draw_letterhead(self, painter: QPainter) -> None:
        top, right, _bottom, left = self.margins
        content_width = self.page_width - left - right
        header_height = 30.0
        logo_size = 22.0
        for key, x in (("logo_left", left + 1.5), ("logo_right", self.page_width - right - logo_size - 1.5)):
            path = str(self.letterhead.get(key, ""))
            pixmap = QPixmap(path) if path and Path(path).exists() else QPixmap()
            if not pixmap.isNull():
                painter.drawPixmap(QRectF(x, top, logo_size, logo_size), pixmap, QRectF(pixmap.rect()))
        text_left = left + logo_size + 4
        text_right = self.page_width - right - logo_size - 4
        text_width = max(20.0, text_right - text_left)
        lines = (
            (str(self.letterhead.get("government_name", "")), 4, True),
            (str(self.letterhead.get("agency_name", "")), 5, True),
            (str(self.letterhead.get("sub_agency_name", "")), 4, True),
            (str(self.letterhead.get("address", "")), 2, False),
            (str(self.letterhead.get("contact", "")), 2, False),
        )
        y = top - 0.5
        for text, pixel_size, bold in lines:
            if not text:
                continue
            font = QFont("Times New Roman")
            font.setPixelSize(pixel_size)
            font.setBold(bold)
            painter.setFont(font)
            painter.setPen(QColor("#111827"))
            height = pixel_size + 1.2
            painter.drawText(QRectF(text_left, y, text_width, height), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter, text)
            y += height
        line_y = top + header_height - 5
        style = str(self.letterhead.get("border_style", "double"))
        if style != "none":
            width = 1.2 if style == "bold" else 0.55
            painter.setPen(QPen(QColor("#111827"), width))
            painter.drawLine(QPointF(left, line_y), QPointF(self.page_width - right, line_y))
            if style == "double":
                painter.setPen(QPen(QColor("#111827"), 0.35))
                painter.drawLine(QPointF(left, line_y + 1.5), QPointF(self.page_width - right, line_y + 1.5))

    def effective_margins(self) -> tuple[float, float, float, float]:
        top, right, bottom, left = self.margins
        if self.letterhead.get("enabled"):
            top += 31.0
        return top, right, bottom, left

    def load_page(
        self,
        page: DocumentPage,
        width: float,
        height: float,
        margins: tuple[float, float, float, float],
        letterhead: dict | None = None,
    ) -> None:
        self.clear()
        self.configure_page(width, height, margins, page.background, letterhead)
        for data in page.elements:
            self.add_element(data)

    def add_element(self, data: dict) -> QGraphicsItem:
        if data.get("kind") == "text":
            item = TextItem(data)
        else:
            item = PhotoItem(data)
            item.changed.connect(self.content_changed)
            item.request_crop.connect(self.crop_requested)
        self.addItem(item)
        return item

    def add_text(self, text: str = "Klik dua kali untuk mengubah teks") -> TextItem:
        item = TextItem(TextElement(text=text).__dict__)
        self.addItem(item)
        item.setSelected(True)
        self.content_changed.emit()
        return item

    def apply_template(self, template_id: str, photo_paths: list[str] | None = None) -> None:
        existing = [item.to_data().get("photo_path", "") for item in self.items() if isinstance(item, PhotoItem)]
        paths = list(photo_paths or existing)
        for item in list(self.items()):
            if isinstance(item, PhotoItem):
                self.removeItem(item)
        template = template_by_id(template_id)
        rectangles = layout_rectangles(template, self.page_width, self.page_height, self.effective_margins())
        for index, (x, y, width, height) in enumerate(rectangles):
            data = PhotoElement(
                photo_path=paths[index] if index < len(paths) else "",
                x=x,
                y=y,
                width=width,
                height=height,
            ).__dict__
            self.add_element(data)
        self.content_changed.emit()

    def serialize_elements(self) -> list[dict]:
        result = []
        for item in reversed(self.items()):
            if isinstance(item, (PhotoItem, TextItem)):
                result.append(item.to_data())
        return result

    def selected_editable(self) -> PhotoItem | TextItem | None:
        for item in self.selectedItems():
            if isinstance(item, (PhotoItem, TextItem)):
                return item
        return None

    def delete_selected(self) -> None:
        changed = False
        for item in list(self.selectedItems()):
            if isinstance(item, (PhotoItem, TextItem)) and not item.data.get("locked"):
                self.removeItem(item)
                changed = True
        if changed:
            self.content_changed.emit()

    def render_image(self, dpi: int = 300) -> QImage:
        pixels_per_mm = dpi / 25.4
        width_px = max(1, round(self.page_width * pixels_per_mm))
        height_px = max(1, round(self.page_height * pixels_per_mm))
        image = QImage(width_px, height_px, QImage.Format.Format_ARGB32)
        image.fill(self.background_color)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        previous = self.show_guides
        self.show_guides = False
        self.clearSelection()
        self.render(painter, QRectF(0, 0, width_px, height_px), self.sceneRect(), Qt.AspectRatioMode.IgnoreAspectRatio)
        self.show_guides = previous
        painter.end()
        return image
