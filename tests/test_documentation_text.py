from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication, QGraphicsScene

from sekretariat_app.documentation.scene import TextItem


class DocumentationTextResizeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    @staticmethod
    def _ink_pixels(scene: QGraphicsScene) -> int:
        image = QImage(600, 260, QImage.Format.Format_RGB32)
        image.fill(QColor("white"))
        painter = QPainter(image)
        scene.render(painter)
        painter.end()
        return sum(
            image.pixelColor(x, y).lightness() < 180
            for y in range(image.height())
            for x in range(image.width())
        )

    def test_corner_resize_keeps_text_visible_during_preview_and_after_commit(self) -> None:
        scene = QGraphicsScene()
        scene.setSceneRect(QRectF(0, 0, 300, 130))
        item = TextItem({
            "text": "Teks tidak boleh hilang",
            "width": 120.0,
            "font_size": 14.0,
            "x": 20.0,
            "y": 20.0,
        })
        scene.addItem(item)
        before = self._ink_pixels(scene)

        item._resize_text = item.toPlainText()
        item._resize_anchor = item._content_rect().topLeft()
        item._start_item_transform = item.transform()
        item._pending_text_width = item.textWidth() * 1.8
        item._pending_font_size = float(item.data["font_size"]) * 1.8
        item.setTransform(item._resize_transform(item._resize_anchor, 1.8, 1.8))

        self.assertEqual(item.toPlainText(), "Teks tidak boleh hilang")
        self.assertGreater(self._ink_pixels(scene), before)

        item._commit_resize("bottom_right")
        self.assertEqual(item.toPlainText(), "Teks tidak boleh hilang")
        self.assertAlmostEqual(float(item.data["font_size"]), 25.2)
        self.assertGreater(self._ink_pixels(scene), before)

    def test_horizontal_resize_defers_document_width_until_commit(self) -> None:
        item = TextItem({"text": "Satu dua tiga", "width": 100.0, "font_size": 14.0})
        original_width = item.textWidth()
        anchor = QPointF(item._content_rect().left(), item._content_rect().top())
        item.setTransform(item._resize_transform(anchor, 1.5, 1.0))
        self.assertEqual(item.textWidth(), original_width)
        self.assertEqual(item.toPlainText(), "Satu dua tiga")


if __name__ == "__main__":
    unittest.main()
