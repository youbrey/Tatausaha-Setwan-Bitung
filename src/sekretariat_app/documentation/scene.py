from __future__ import annotations

import math
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QImage,
    QImageReader,
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
    QGraphicsRectItem,
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
    crop_state_changed = Signal(float, float, float)

    HANDLE = 4.0
    MIN_SIZE = 12.0
    _HANDLE_CURSORS = {
        "top_left": Qt.CursorShape.SizeFDiagCursor,
        "top": Qt.CursorShape.SizeVerCursor,
        "top_right": Qt.CursorShape.SizeBDiagCursor,
        "right": Qt.CursorShape.SizeHorCursor,
        "bottom_right": Qt.CursorShape.SizeFDiagCursor,
        "bottom": Qt.CursorShape.SizeVerCursor,
        "bottom_left": Qt.CursorShape.SizeBDiagCursor,
        "left": Qt.CursorShape.SizeHorCursor,
    }

    def __init__(self, data: dict, parent: QGraphicsItem | None = None):
        super().__init__(parent)
        self.data = data
        self._rect = QRectF(0, 0, float(data.get("width", 80)), float(data.get("height", 60)))
        self._pixmap = QPixmap()
        self._loaded_path = ""
        self._loaded_rotation = -1
        self._loaded_target = QSize()
        self._resize_handle = ""
        self._start_rect = QRectF()
        self._start_local_to_scene = QTransform()
        self._start_scene_to_local = QTransform()
        self._crop_mode = False
        self._crop_original: dict[str, float | int | str] = {}
        self._crop_drag_position: QPointF | None = None
        self._crop_z_value = 0.0
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
        bounds = QRectF(self._rect)
        if self._crop_mode and not self._pixmap.isNull():
            _source, visual, _max_x, _max_y = self._cover_geometry(self._pixmap, self._rect)
            bounds = bounds.united(visual)
        extra = self.HANDLE / 2.0 + 1.0
        return bounds.adjusted(-extra, -extra, extra, extra)

    def set_locked(self, locked: bool) -> None:
        self.data["locked"] = locked
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, not locked and not self._crop_mode)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.update()

    @property
    def crop_mode(self) -> bool:
        return self._crop_mode

    def begin_crop(self) -> bool:
        if self._crop_mode or self.data.get("locked") or not self.data.get("photo_path"):
            return False
        self._crop_original = {
            "crop_x": float(self.data.get("crop_x", 0.5)),
            "crop_y": float(self.data.get("crop_y", 0.5)),
            "zoom": float(self.data.get("zoom", 1.0)),
            "image_rotation": int(self.data.get("image_rotation", 0)),
            "fit": str(self.data.get("fit", "cover")),
        }
        self.prepareGeometryChange()
        self._crop_mode = True
        self._crop_z_value = self.zValue()
        self.setZValue(10_000.0)
        self.data["fit"] = "cover"
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        self.setSelected(True)
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        self.update()
        self.crop_state_changed.emit(
            float(self.data.get("crop_x", 0.5)),
            float(self.data.get("crop_y", 0.5)),
            float(self.data.get("zoom", 1.0)),
        )
        return True

    def finish_crop(self, commit: bool) -> None:
        if not self._crop_mode:
            return
        self.prepareGeometryChange()
        if not commit:
            self.data.update(self._crop_original)
            self._loaded_rotation = -1
        self._crop_mode = False
        self._crop_drag_position = None
        self.setZValue(self._crop_z_value)
        self.setFlag(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable,
            not bool(self.data.get("locked", False)),
        )
        self.unsetCursor()
        self.update()

    def reset_crop(self) -> None:
        if not self._crop_mode:
            return
        self.prepareGeometryChange()
        self.data.update(crop_x=0.5, crop_y=0.5, zoom=1.0, fit="cover", image_rotation=0)
        self._loaded_rotation = -1
        self.update()
        self.crop_state_changed.emit(0.5, 0.5, 1.0)

    def set_crop_zoom(self, zoom: float) -> None:
        if not self._crop_mode:
            return
        self.prepareGeometryChange()
        self.data["zoom"] = max(1.0, min(5.0, float(zoom)))
        self.update()
        self.crop_state_changed.emit(
            float(self.data.get("crop_x", 0.5)),
            float(self.data.get("crop_y", 0.5)),
            float(self.data["zoom"]),
        )

    def rotate_crop_image(self, degrees: int) -> None:
        if not self._crop_mode:
            return
        self.prepareGeometryChange()
        self.data["image_rotation"] = (int(self.data.get("image_rotation", 0)) + degrees) % 360
        self.data.update(crop_x=0.5, crop_y=0.5)
        self._loaded_rotation = -1
        self.update()
        self.crop_state_changed.emit(0.5, 0.5, float(self.data.get("zoom", 1.0)))

    def set_frame_size(self, width: float, height: float) -> None:
        width = max(self.MIN_SIZE, float(width))
        height = max(self.MIN_SIZE, float(height))
        if abs(width - self._rect.width()) < 0.001 and abs(height - self._rect.height()) < 0.001:
            return
        self.prepareGeometryChange()
        self._rect = QRectF(0.0, 0.0, width, height)
        self.update()

    def _required_pixmap_size(self, painter: QPainter) -> QSize:
        transform = painter.worldTransform()
        scale_x = max(0.1, math.hypot(transform.m11(), transform.m12()))
        scale_y = max(0.1, math.hypot(transform.m21(), transform.m22()))
        zoom = max(1.0, min(5.0, float(self.data.get("zoom", 1.0))))
        width = max(64, math.ceil(self._rect.width() * scale_x * zoom * 1.15))
        height = max(64, math.ceil(self._rect.height() * scale_y * zoom * 1.15))
        if int(self.data.get("image_rotation", 0)) % 180:
            width, height = height, width
        # Bucket mencegah decode ulang saat zoom/resize hanya berubah sedikit.
        width = min(4096, math.ceil(width / 256) * 256)
        height = min(4096, math.ceil(height / 256) * 256)
        return QSize(width, height)

    def _load_pixmap(self, painter: QPainter) -> QPixmap:
        path = str(self.data.get("photo_path", ""))
        rotation = int(self.data.get("image_rotation", 0)) % 360
        target = self._required_pixmap_size(painter)
        cache_is_sufficient = (
            path == self._loaded_path
            and rotation == self._loaded_rotation
            and self._loaded_target.width() >= target.width()
            and self._loaded_target.height() >= target.height()
        )
        if cache_is_sufficient:
            return self._pixmap

        self._loaded_path = path
        self._loaded_rotation = rotation
        self._loaded_target = target
        self._pixmap = QPixmap()
        if not path or not Path(path).exists():
            return self._pixmap

        reader = QImageReader(path)
        reader.setAutoTransform(True)
        original = reader.size()
        if original.isValid() and original.width() > 0 and original.height() > 0:
            scale = min(
                1.0,
                max(
                    target.width() / original.width(),
                    target.height() / original.height(),
                ),
            )
            scaled_width = max(1, round(original.width() * scale))
            scaled_height = max(1, round(original.height() * scale))
            largest = max(scaled_width, scaled_height)
            if largest > 4096:
                limit = 4096 / largest
                scaled_width = max(1, round(scaled_width * limit))
                scaled_height = max(1, round(scaled_height * limit))
            if scaled_width < original.width() or scaled_height < original.height():
                reader.setScaledSize(QSize(scaled_width, scaled_height))
        image = reader.read()
        if image.isNull():
            return self._pixmap
        pixmap = QPixmap.fromImage(image)
        if rotation:
            pixmap = pixmap.transformed(
                QTransform().rotate(rotation),
                Qt.TransformationMode.SmoothTransformation,
            )
        self._pixmap = pixmap
        return self._pixmap

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None) -> None:
        del option, widget
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self._rect
        radius = max(0.0, float(self.data.get("radius", 1.5)))
        clip = QPainterPath()
        clip.addRoundedRect(rect, radius, radius)

        pixmap = self._load_pixmap(painter)
        if self._crop_mode and not pixmap.isNull():
            self._paint_crop_mode(painter, pixmap, clip)
        else:
            painter.save()
            painter.setClipPath(clip)
            painter.fillRect(rect, QColor("#e2e8f0"))
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
        if border_width and not self._crop_mode:
            painter.setPen(QPen(QColor(str(self.data.get("border_color", "#94a3b8"))), border_width))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(rect, radius, radius)
        if self.isSelected() and not self._crop_mode:
            painter.setPen(QPen(QColor("#0284c7"), 0.8))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(rect)
            if not self.data.get("locked"):
                painter.setBrush(QColor("#ffffff"))
                painter.setPen(QPen(QColor("#0284c7"), 0.7))
                for handle_rect in self._handle_rects().values():
                    painter.drawRect(handle_rect)

    def _paint_crop_mode(self, painter: QPainter, pixmap: QPixmap, clip: QPainterPath) -> None:
        _source, visual, _max_x, _max_y = self._cover_geometry(pixmap, self._rect)
        entire_source = QRectF(pixmap.rect())

        painter.save()
        painter.setOpacity(0.34)
        painter.drawPixmap(visual, pixmap, entire_source)
        painter.restore()

        painter.save()
        painter.setClipPath(clip)
        painter.fillRect(self._rect, QColor("#111827"))
        painter.drawPixmap(visual, pixmap, entire_source)
        painter.restore()

        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor("#22c55e"), 0.9))
        painter.drawRect(self._rect)
        painter.setPen(QPen(QColor(255, 255, 255, 150), 0.35, Qt.PenStyle.DashLine))
        one_third_x = self._rect.width() / 3.0
        one_third_y = self._rect.height() / 3.0
        for step in (1, 2):
            x = self._rect.left() + one_third_x * step
            y = self._rect.top() + one_third_y * step
            painter.drawLine(QPointF(x, self._rect.top()), QPointF(x, self._rect.bottom()))
            painter.drawLine(QPointF(self._rect.left(), y), QPointF(self._rect.right(), y))

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

        source_rect, _visual, _max_x, _max_y = self._cover_geometry(pixmap, target)
        painter.drawPixmap(target, pixmap, source_rect)

    def _cover_geometry(self, pixmap: QPixmap, target: QRectF) -> tuple[QRectF, QRectF, float, float]:
        source = QRectF(pixmap.rect())
        source_aspect = source.width() / max(1.0, source.height())
        target_aspect = target.width() / max(1.0, target.height())
        if source_aspect > target_aspect:
            source_width, source_height = source.height() * target_aspect, source.height()
        else:
            source_width, source_height = source.width(), source.width() / target_aspect
        zoom = max(1.0, min(5.0, float(self.data.get("zoom", 1.0))))
        source_width /= zoom
        source_height /= zoom
        max_x = max(0.0, source.width() - source_width)
        max_y = max(0.0, source.height() - source_height)
        crop_x = max(0.0, min(1.0, float(self.data.get("crop_x", 0.5))))
        crop_y = max(0.0, min(1.0, float(self.data.get("crop_y", 0.5))))
        source_rect = QRectF(max_x * crop_x, max_y * crop_y, source_width, source_height)
        scale_x = target.width() / max(1.0, source_rect.width())
        scale_y = target.height() / max(1.0, source_rect.height())
        visual = QRectF(
            target.left() - source_rect.left() * scale_x,
            target.top() - source_rect.top() * scale_y,
            source.width() * scale_x,
            source.height() * scale_y,
        )
        return source_rect, visual, max_x, max_y

    def _handle_rects(self) -> dict[str, QRectF]:
        half = self.HANDLE / 2.0
        left, center_x, right = self._rect.left(), self._rect.center().x(), self._rect.right()
        top, center_y, bottom = self._rect.top(), self._rect.center().y(), self._rect.bottom()
        return {
            "top_left": QRectF(left - half, top - half, self.HANDLE, self.HANDLE),
            "top": QRectF(center_x - half, top - half, self.HANDLE, self.HANDLE),
            "top_right": QRectF(right - half, top - half, self.HANDLE, self.HANDLE),
            "right": QRectF(right - half, center_y - half, self.HANDLE, self.HANDLE),
            "bottom_right": QRectF(right - half, bottom - half, self.HANDLE, self.HANDLE),
            "bottom": QRectF(center_x - half, bottom - half, self.HANDLE, self.HANDLE),
            "bottom_left": QRectF(left - half, bottom - half, self.HANDLE, self.HANDLE),
            "left": QRectF(left - half, center_y - half, self.HANDLE, self.HANDLE),
        }

    def _handle_at(self, point: QPointF) -> str:
        if not self.isSelected() or self.data.get("locked") or self._crop_mode:
            return ""
        for name, rect in self._handle_rects().items():
            if rect.contains(point):
                return name
        return ""

    def hoverMoveEvent(self, event) -> None:
        handle = self._handle_at(event.pos())
        if handle:
            self.setCursor(self._HANDLE_CURSORS[handle])
        elif self._crop_mode:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        else:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        super().hoverMoveEvent(event)

    def hoverLeaveEvent(self, event) -> None:
        if not self._resize_handle:
            self.unsetCursor()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._crop_mode:
            self._crop_drag_position = event.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        handle = self._handle_at(event.pos())
        if event.button() == Qt.MouseButton.LeftButton and handle:
            self._resize_handle = handle
            self._start_rect = QRectF(self._rect)
            self._start_local_to_scene = self.sceneTransform()
            self._start_scene_to_local, _ok = self._start_local_to_scene.inverted()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        if self._crop_mode and self._crop_drag_position is not None:
            pixmap = self._pixmap
            if pixmap.isNull():
                event.accept()
                return
            source, _visual, max_x, max_y = self._cover_geometry(pixmap, self._rect)
            delta = event.pos() - self._crop_drag_position
            self.prepareGeometryChange()
            if max_x > 0:
                self.data["crop_x"] = max(
                    0.0,
                    min(
                        1.0,
                        float(self.data.get("crop_x", 0.5))
                        - delta.x() * source.width() / self._rect.width() / max_x,
                    ),
                )
            if max_y > 0:
                self.data["crop_y"] = max(
                    0.0,
                    min(
                        1.0,
                        float(self.data.get("crop_y", 0.5))
                        - delta.y() * source.height() / self._rect.height() / max_y,
                    ),
                )
            self._crop_drag_position = event.pos()
            self.update()
            self.crop_state_changed.emit(
                float(self.data.get("crop_x", 0.5)),
                float(self.data.get("crop_y", 0.5)),
                float(self.data.get("zoom", 1.0)),
            )
            event.accept()
            return
        if self._resize_handle:
            point = self._start_scene_to_local.map(event.scenePos())
            left, top = self._start_rect.left(), self._start_rect.top()
            right, bottom = self._start_rect.right(), self._start_rect.bottom()
            if "left" in self._resize_handle:
                left = min(point.x(), right - self.MIN_SIZE)
            if "right" in self._resize_handle:
                right = max(point.x(), left + self.MIN_SIZE)
            if "top" in self._resize_handle:
                top = min(point.y(), bottom - self.MIN_SIZE)
            if "bottom" in self._resize_handle:
                bottom = max(point.y(), top + self.MIN_SIZE)
            new_top_left_scene = self._start_local_to_scene.map(QPointF(left, top))
            new_position = (
                self.parentItem().mapFromScene(new_top_left_scene)
                if self.parentItem()
                else new_top_left_scene
            )
            new_width = right - left
            new_height = bottom - top
            if self.scene() and not self.parentItem() and abs(self.rotation() % 360.0) < 0.001:
                paper = getattr(self.scene(), "paper_rect", self.scene().sceneRect())
                new_position.setX(max(paper.left(), min(new_position.x(), paper.right() - self.MIN_SIZE)))
                new_position.setY(max(paper.top(), min(new_position.y(), paper.bottom() - self.MIN_SIZE)))
                new_width = min(new_width, paper.right() - new_position.x())
                new_height = min(new_height, paper.bottom() - new_position.y())
            self.prepareGeometryChange()
            self.setPos(new_position)
            self._rect = QRectF(0.0, 0.0, new_width, new_height)
            self.update()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        if self._crop_mode and self._crop_drag_position is not None:
            self._crop_drag_position = None
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            event.accept()
            return
        if self._resize_handle:
            self._resize_handle = ""
            self.changed.emit()
            event.accept()
            return
        super().mouseReleaseEvent(event)
        self.changed.emit()

    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        if not self._crop_mode:
            self.request_crop.emit(self)
        event.accept()

    def wheelEvent(self, event) -> None:
        if self._crop_mode:
            step = 0.12 if event.delta() > 0 else -0.12
            self.set_crop_zoom(float(self.data.get("zoom", 1.0)) + step)
            event.accept()
            return
        super().wheelEvent(event)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and self.scene():
            if self._crop_mode:
                return self.pos()
            bounds = getattr(self.scene(), "paper_rect", self.scene().sceneRect())
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


class CollageResizeOverlay(QGraphicsObject):
    """Overlay editor untuk memindahkan dan menskalakan seluruh kolase."""

    changed = Signal()
    HANDLE = 5.0
    MIN_SIZE = 30.0
    _HANDLE_CURSORS = PhotoItem._HANDLE_CURSORS

    def __init__(self, photos: list[PhotoItem]):
        super().__init__()
        self.photos = photos
        self._rect = self._photo_bounds()
        self._handle = ""
        self._moving = False
        self._press_scene = QPointF()
        self._start_group = QRectF()
        self._start_photos: list[tuple[PhotoItem, QPointF, float, float]] = []
        self.setZValue(20_000.0)
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsFocusable, True)

    def _photo_bounds(self) -> QRectF:
        bounds = QRectF()
        for index, item in enumerate(self.photos):
            item_bounds = item.mapRectToScene(item._rect)
            bounds = item_bounds if index == 0 else bounds.united(item_bounds)
        return bounds

    def boundingRect(self) -> QRectF:
        extra = self.HANDLE / 2.0 + 1.0
        return self._rect.adjusted(-extra, -extra, extra, extra)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None) -> None:
        del option
        if widget is None:
            return
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor("#7c3aed"), 0.9))
        painter.drawRect(self._rect)
        painter.setBrush(QColor("#ffffff"))
        painter.setPen(QPen(QColor("#7c3aed"), 0.8))
        for rect in self._handle_rects().values():
            painter.drawRect(rect)

    def _handle_rects(self) -> dict[str, QRectF]:
        half = self.HANDLE / 2.0
        left, center_x, right = self._rect.left(), self._rect.center().x(), self._rect.right()
        top, center_y, bottom = self._rect.top(), self._rect.center().y(), self._rect.bottom()
        return {
            "top_left": QRectF(left - half, top - half, self.HANDLE, self.HANDLE),
            "top": QRectF(center_x - half, top - half, self.HANDLE, self.HANDLE),
            "top_right": QRectF(right - half, top - half, self.HANDLE, self.HANDLE),
            "right": QRectF(right - half, center_y - half, self.HANDLE, self.HANDLE),
            "bottom_right": QRectF(right - half, bottom - half, self.HANDLE, self.HANDLE),
            "bottom": QRectF(center_x - half, bottom - half, self.HANDLE, self.HANDLE),
            "bottom_left": QRectF(left - half, bottom - half, self.HANDLE, self.HANDLE),
            "left": QRectF(left - half, center_y - half, self.HANDLE, self.HANDLE),
        }

    def _handle_at(self, point: QPointF) -> str:
        for name, rect in self._handle_rects().items():
            if rect.contains(point):
                return name
        return ""

    def hoverMoveEvent(self, event) -> None:
        handle = self._handle_at(event.pos())
        self.setCursor(self._HANDLE_CURSORS.get(handle, Qt.CursorShape.SizeAllCursor))
        super().hoverMoveEvent(event)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        self._handle = self._handle_at(event.pos())
        self._moving = not self._handle and self._rect.contains(event.pos())
        if not self._handle and not self._moving:
            super().mousePressEvent(event)
            return
        self._press_scene = event.scenePos()
        self._start_group = QRectF(self._rect)
        self._start_photos = [
            (item, QPointF(item.pos()), item._rect.width(), item._rect.height())
            for item in self.photos
        ]
        self.setCursor(
            self._HANDLE_CURSORS.get(self._handle, Qt.CursorShape.ClosedHandCursor)
        )
        event.accept()

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        if not self._handle and not self._moving:
            super().mouseMoveEvent(event)
            return
        delta = event.scenePos() - self._press_scene
        paper = getattr(self.scene(), "paper_rect", self.scene().sceneRect())
        if self._moving:
            delta.setX(max(paper.left() - self._start_group.left(), min(delta.x(), paper.right() - self._start_group.right())))
            delta.setY(max(paper.top() - self._start_group.top(), min(delta.y(), paper.bottom() - self._start_group.bottom())))
            target = self._start_group.translated(delta)
        else:
            left, top = self._start_group.left(), self._start_group.top()
            right, bottom = self._start_group.right(), self._start_group.bottom()
            if "left" in self._handle:
                left = max(paper.left(), min(left + delta.x(), right - self.MIN_SIZE))
            if "right" in self._handle:
                right = min(paper.right(), max(right + delta.x(), left + self.MIN_SIZE))
            if "top" in self._handle:
                top = max(paper.top(), min(top + delta.y(), bottom - self.MIN_SIZE))
            if "bottom" in self._handle:
                bottom = min(paper.bottom(), max(bottom + delta.y(), top + self.MIN_SIZE))
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                ratio = self._start_group.width() / max(1.0, self._start_group.height())
                if abs((right - left) - self._start_group.width()) >= abs((bottom - top) - self._start_group.height()):
                    height = (right - left) / ratio
                    if "top" in self._handle:
                        top = bottom - height
                    else:
                        bottom = top + height
                else:
                    width = (bottom - top) * ratio
                    if "left" in self._handle:
                        left = right - width
                    else:
                        right = left + width
            target = QRectF(left, top, right - left, bottom - top)
        self._apply_group_rect(target)
        event.accept()

    def _apply_group_rect(self, target: QRectF) -> None:
        scale_x = target.width() / max(1.0, self._start_group.width())
        scale_y = target.height() / max(1.0, self._start_group.height())
        for item, start_pos, start_width, start_height in self._start_photos:
            item.prepareGeometryChange()
            item.setPos(
                target.left() + (start_pos.x() - self._start_group.left()) * scale_x,
                target.top() + (start_pos.y() - self._start_group.top()) * scale_y,
            )
            item._rect = QRectF(0.0, 0.0, start_width * scale_x, start_height * scale_y)
            item.update()
        self.prepareGeometryChange()
        self._rect = QRectF(target)
        self.update()

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        if self._handle or self._moving:
            self._handle = ""
            self._moving = False
            self.setCursor(Qt.CursorShape.SizeAllCursor)
            self.changed.emit()
            event.accept()
            return
        super().mouseReleaseEvent(event)


class TextItem(QGraphicsTextItem):
    changed = Signal()

    HANDLE = 4.0
    MIN_WIDTH = 15.0
    MIN_FONT_SIZE = 6.0
    MAX_FONT_SIZE = 144.0
    _HANDLE_CURSORS = {
        "top_left": Qt.CursorShape.SizeFDiagCursor,
        "top_right": Qt.CursorShape.SizeBDiagCursor,
        "right": Qt.CursorShape.SizeHorCursor,
        "bottom_right": Qt.CursorShape.SizeFDiagCursor,
        "bottom_left": Qt.CursorShape.SizeBDiagCursor,
        "left": Qt.CursorShape.SizeHorCursor,
    }

    def __init__(self, data: dict):
        super().__init__()
        self.data = data
        self._resize_handle = ""
        self._start_text_rect = QRectF()
        self._start_text_width = 0.0
        self._start_font_size = 0.0
        self._start_local_to_scene = QTransform()
        self._start_scene_to_local = QTransform()
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
        self.setAcceptHoverEvents(True)
        self.apply_font()
        self.set_locked(bool(data.get("locked", False)))

    def _content_rect(self) -> QRectF:
        return QRectF(super().boundingRect())

    def boundingRect(self) -> QRectF:
        extra = self.HANDLE / 2.0 + 1.0
        return self._content_rect().adjusted(-extra, -extra, extra, extra)

    def _handle_rects(self) -> dict[str, QRectF]:
        rect = self._content_rect()
        half = self.HANDLE / 2.0
        left, right = rect.left(), rect.right()
        top, center_y, bottom = rect.top(), rect.center().y(), rect.bottom()
        return {
            "top_left": QRectF(left - half, top - half, self.HANDLE, self.HANDLE),
            "top_right": QRectF(right - half, top - half, self.HANDLE, self.HANDLE),
            "right": QRectF(right - half, center_y - half, self.HANDLE, self.HANDLE),
            "bottom_right": QRectF(right - half, bottom - half, self.HANDLE, self.HANDLE),
            "bottom_left": QRectF(left - half, bottom - half, self.HANDLE, self.HANDLE),
            "left": QRectF(left - half, center_y - half, self.HANDLE, self.HANDLE),
        }

    def _handle_at(self, point: QPointF) -> str:
        if (
            not self.isSelected()
            or self.data.get("locked")
            or self.textInteractionFlags() != Qt.TextInteractionFlag.NoTextInteraction
        ):
            return ""
        for name, rect in self._handle_rects().items():
            if rect.contains(point):
                return name
        return ""

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
        self.update()

    def hoverMoveEvent(self, event) -> None:
        handle = self._handle_at(event.pos())
        if handle:
            self.setCursor(self._HANDLE_CURSORS[handle])
        elif self.textInteractionFlags() == Qt.TextInteractionFlag.NoTextInteraction:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        super().hoverMoveEvent(event)

    def hoverLeaveEvent(self, event) -> None:
        if not self._resize_handle:
            self.unsetCursor()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        handle = self._handle_at(event.pos())
        if event.button() == Qt.MouseButton.LeftButton and handle:
            self._resize_handle = handle
            self._start_text_rect = self._content_rect()
            self._start_text_width = max(self.MIN_WIDTH, self.textWidth())
            self._start_font_size = max(
                self.MIN_FONT_SIZE,
                float(self.data.get("font_size", 14.0)),
            )
            self._start_local_to_scene = self.sceneTransform()
            self._start_scene_to_local, _ok = self._start_local_to_scene.inverted()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        if not self._resize_handle:
            super().mouseMoveEvent(event)
            return
        point = self._start_scene_to_local.map(event.scenePos())
        handle = self._resize_handle
        if handle in {"left", "right"}:
            if handle == "left":
                width = self._start_text_rect.right() - point.x()
                start_anchor = QPointF(
                    self._start_text_rect.right(),
                    self._start_text_rect.top(),
                )
            else:
                width = point.x() - self._start_text_rect.left()
                start_anchor = QPointF(
                    self._start_text_rect.left(),
                    self._start_text_rect.top(),
                )
            self.setTextWidth(max(self.MIN_WIDTH, width))
            self.data["width"] = self.textWidth()
            new_rect = self._content_rect()
            new_anchor = QPointF(
                new_rect.right() if handle == "left" else new_rect.left(),
                new_rect.top(),
            )
        else:
            start_corner = {
                "top_left": self._start_text_rect.topLeft(),
                "top_right": self._start_text_rect.topRight(),
                "bottom_right": self._start_text_rect.bottomRight(),
                "bottom_left": self._start_text_rect.bottomLeft(),
            }[handle]
            start_anchor = {
                "top_left": self._start_text_rect.bottomRight(),
                "top_right": self._start_text_rect.bottomLeft(),
                "bottom_right": self._start_text_rect.topLeft(),
                "bottom_left": self._start_text_rect.topRight(),
            }[handle]
            start_distance = max(
                1.0,
                math.hypot(
                    start_corner.x() - start_anchor.x(),
                    start_corner.y() - start_anchor.y(),
                ),
            )
            scale = math.hypot(
                point.x() - start_anchor.x(),
                point.y() - start_anchor.y(),
            ) / start_distance
            font_size = max(
                self.MIN_FONT_SIZE,
                min(self.MAX_FONT_SIZE, self._start_font_size * scale),
            )
            scale = font_size / self._start_font_size
            self.data["font_size"] = font_size
            self.data["width"] = max(self.MIN_WIDTH, self._start_text_width * scale)
            self.setTextWidth(float(self.data["width"]))
            self.apply_font()
            new_rect = self._content_rect()
            new_anchor = {
                "top_left": new_rect.bottomRight(),
                "top_right": new_rect.bottomLeft(),
                "bottom_right": new_rect.topLeft(),
                "bottom_left": new_rect.topRight(),
            }[handle]

        desired_anchor_scene = self._start_local_to_scene.map(start_anchor)
        current_anchor_scene = self.mapToScene(new_anchor)
        scene_delta = desired_anchor_scene - current_anchor_scene
        current_origin_scene = self.mapToScene(QPointF(0.0, 0.0))
        target_origin_scene = current_origin_scene + scene_delta
        self.setPos(
            self.parentItem().mapFromScene(target_origin_scene)
            if self.parentItem()
            else target_origin_scene
        )
        self.update()
        event.accept()

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        if self._resize_handle:
            self._resize_handle = ""
            self.unsetCursor()
            self.changed.emit()
            event.accept()
            return
        super().mouseReleaseEvent(event)
        self.changed.emit()

    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        if not self.data.get("locked"):
            self.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
            self.setFocus(Qt.FocusReason.MouseFocusReason)
        super().mouseDoubleClickEvent(event)

    def focusOutEvent(self, event) -> None:
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.data["text"] = self.toPlainText()
        super().focusOutEvent(event)
        self.changed.emit()

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None) -> None:
        content_rect = self._content_rect()
        background = QColor(str(self.data.get("background", "#00ffffff")))
        if background.alpha() > 0:
            painter.fillRect(content_rect, background)
        super().paint(painter, option, widget)
        if self.isSelected():
            painter.setPen(QPen(QColor("#0284c7"), 0.7, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(content_rect)
            if not self.data.get("locked"):
                painter.setBrush(QColor("#ffffff"))
                painter.setPen(QPen(QColor("#0284c7"), 0.7))
                for handle_rect in self._handle_rects().values():
                    painter.drawRect(handle_rect)

    def itemChange(self, change, value):
        if (
            change == QGraphicsItem.GraphicsItemChange.ItemPositionChange
            and self.scene()
            and abs(self.rotation() % 360.0) < 0.001
        ):
            paper = getattr(self.scene(), "paper_rect", self.scene().sceneRect())
            rect = self._content_rect()
            position = value
            x = max(
                paper.left() - rect.left(),
                min(position.x(), paper.right() - rect.right()),
            )
            y = max(
                paper.top() - rect.top(),
                min(position.y(), paper.bottom() - rect.bottom()),
            )
            return QPointF(x, y)
        return super().itemChange(change, value)

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
    collage_mode_changed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.page_width = 215.0
        self.page_height = 330.0
        self.margins = (15.0, 15.0, 15.0, 15.0)
        self.background_color = QColor("#ffffff")
        self.letterhead: dict = {}
        self.show_guides = True
        self.paper_rect = QRectF(0, 0, self.page_width, self.page_height)
        self.active_crop_item: PhotoItem | None = None
        self.crop_shade: QGraphicsRectItem | None = None
        self.collage_overlay: CollageResizeOverlay | None = None
        self._paper_shadow_item: QGraphicsRectItem | None = None
        self._paper_item: QGraphicsRectItem | None = None
        self._set_padded_scene_rect()
        self._ensure_paper_items()
        self.selectionChanged.connect(self.update)

    def _set_padded_scene_rect(self) -> None:
        padding = max(10.0, min(self.page_width, self.page_height) * 0.055)
        self.setSceneRect(
            -padding,
            -padding,
            self.page_width + padding * 2,
            self.page_height + padding * 2,
        )

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
        self.paper_rect = QRectF(0, 0, width, height)
        self._set_padded_scene_rect()
        self._ensure_paper_items()
        self.update()

    def _ensure_paper_items(self) -> None:
        """Kertas adalah item scene nyata agar selalu tampak di QGraphicsView."""

        if self._paper_shadow_item is None:
            self._paper_shadow_item = QGraphicsRectItem()
            self._paper_shadow_item.setZValue(-10_001.0)
            self._paper_shadow_item.setPen(QPen(Qt.PenStyle.NoPen))
            self._paper_shadow_item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
            self.addItem(self._paper_shadow_item)
        if self._paper_item is None:
            self._paper_item = QGraphicsRectItem()
            self._paper_item.setZValue(-10_000.0)
            self._paper_item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
            self.addItem(self._paper_item)
        self._paper_shadow_item.setRect(self.paper_rect.translated(2.8, 3.2))
        self._paper_shadow_item.setBrush(QColor(15, 23, 42, 58))
        self._paper_item.setRect(self.paper_rect)
        self._paper_item.setBrush(self.background_color)
        self._paper_item.setPen(QPen(QColor("#94a3b8"), 0.45))

    def drawBackground(self, painter: QPainter, rect: QRectF) -> None:
        painter.fillRect(rect, QColor("#cbd5e1"))

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
        self.active_crop_item = None
        self.crop_shade = None
        self.collage_overlay = None
        self._paper_shadow_item = None
        self._paper_item = None
        self.clear()
        self.configure_page(width, height, margins, page.background, letterhead)
        for data in page.elements:
            self.add_element(data)

    def add_element(self, data: dict) -> QGraphicsItem:
        if data.get("kind") == "text":
            item = TextItem(data)
            item.changed.connect(self.content_changed)
        else:
            item = PhotoItem(data)
            item.changed.connect(self.content_changed)
            item.request_crop.connect(self.crop_requested)
        self.addItem(item)
        return item

    def add_text(self, text: str = "Klik dua kali untuk mengubah teks") -> TextItem:
        item = TextItem(TextElement(text=text).__dict__)
        item.changed.connect(self.content_changed)
        self.addItem(item)
        item.setSelected(True)
        self.content_changed.emit()
        return item

    def begin_crop(self, item: PhotoItem) -> bool:
        if self.collage_overlay is not None:
            self.finish_collage_resize()
        if self.active_crop_item is not None and self.active_crop_item is not item:
            self.finish_crop(False)
        self.clearSelection()
        if not item.begin_crop():
            return False
        self.active_crop_item = item
        shade = QGraphicsRectItem(self.paper_rect)
        shade.setPen(QPen(Qt.PenStyle.NoPen))
        shade.setBrush(QColor(15, 23, 42, 125))
        shade.setZValue(9_999.0)
        shade.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.addItem(shade)
        self.crop_shade = shade
        return True

    def finish_crop(self, commit: bool) -> None:
        item = self.active_crop_item
        if item is None:
            return
        item.finish_crop(commit)
        self.active_crop_item = None
        if self.crop_shade is not None:
            self.removeItem(self.crop_shade)
            self.crop_shade = None
        if commit:
            self.content_changed.emit()

    def begin_collage_resize(
        self,
        photos: list[PhotoItem] | None = None,
    ) -> CollageResizeOverlay | None:
        if self.active_crop_item is not None:
            self.finish_crop(False)
        if self.collage_overlay is not None:
            return self.collage_overlay
        candidates = photos if photos is not None else [
            item for item in reversed(self.items()) if isinstance(item, PhotoItem)
        ]
        photos = [item for item in candidates if not item.data.get("locked")]
        if not photos:
            return None
        self.clearSelection()
        overlay = CollageResizeOverlay(photos)
        overlay.changed.connect(self.content_changed)
        self.addItem(overlay)
        self.collage_overlay = overlay
        self.collage_mode_changed.emit(True)
        return overlay

    def finish_collage_resize(self, emit_change: bool = True) -> None:
        overlay = self.collage_overlay
        if overlay is None:
            return
        self.removeItem(overlay)
        self.collage_overlay = None
        self.collage_mode_changed.emit(False)
        if emit_change:
            self.content_changed.emit()

    def apply_template(
        self,
        template_id: str,
        photo_paths: list[str] | None = None,
        *,
        gap: float = 3.0,
        width_percent: float = 100.0,
        height_percent: float = 100.0,
    ) -> None:
        existing = [item.to_data().get("photo_path", "") for item in self.items() if isinstance(item, PhotoItem)]
        paths = list(photo_paths or existing)
        for item in list(self.items()):
            if isinstance(item, PhotoItem):
                self.removeItem(item)
        template = template_by_id(template_id)
        rectangles = layout_rectangles(
            template,
            self.page_width,
            self.page_height,
            self.effective_margins(),
            gap,
            width_percent,
            height_percent,
        )
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
        self.render_to_painter(painter, QRectF(0, 0, width_px, height_px))
        painter.end()
        return image

    def render_to_painter(self, painter: QPainter, target: QRectF) -> None:
        """Render langsung ke PDF/printer agar tidak membuat bitmap satu halaman."""

        previous = self.show_guides
        overlay = self.collage_overlay
        crop_item = self.active_crop_item
        crop_shade = self.crop_shade
        self.show_guides = False
        self.clearSelection()
        if overlay is not None:
            overlay.setVisible(False)
        if crop_shade is not None:
            crop_shade.setVisible(False)
        if crop_item is not None:
            crop_item._crop_mode = False
        try:
            self.render(
                painter,
                target,
                self.paper_rect,
                Qt.AspectRatioMode.IgnoreAspectRatio,
            )
        finally:
            if crop_item is not None:
                crop_item._crop_mode = True
            if overlay is not None:
                overlay.setVisible(True)
            if crop_shade is not None:
                crop_shade.setVisible(True)
            self.show_guides = previous
