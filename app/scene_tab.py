from typing import List, Tuple, Optional
import math

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtGui import QColor, QPen
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QWidget, QGraphicsView, QGraphicsScene, QVBoxLayout

from .models import SceneElement
from .undo import UndoManager
from .utils import circle_to_points



class SceneTab(QWidget):
    element_changed = pyqtSignal()

    def __init__(self, p=None, grid_size: int = 255, cell_size: int = 1):
        super().__init__(p)
        self.grid_size = int(grid_size)
        self.cell_size = int(cell_size)

        self._init_ui()

        self.cc: Tuple[int, int, int] = (255, 0, 0)
        self.tool: str = "polyline"
        self._temp_points: List[Tuple[int, int]] = []
        self._circle_center: Optional[Tuple[int, int]] = None
        self.elements: List[SceneElement] = []
        self.undo_manager = UndoManager()

        self.highlight_idx: Optional[int] = None
        self.view.viewport().installEventFilter(self)
        self.view.setMouseTracking(True)
        self._panning: bool = False
        self._last_pan_point = None

        self._draw_grid()

    def _init_ui(self) -> None:
        l = QVBoxLayout(self)
        self.view = QGraphicsView()
        self.view.setRenderHints(QtGui.QPainter.RenderHint.Antialiasing)
        self.scene = QGraphicsScene()
        self.view.setScene(self.scene)
        self.scene.setSceneRect(0, 0, self.grid_size, self.grid_size)
        l.addWidget(self.view)

    def _rgb_to_qcolor(self, rgb: Tuple[int, int, int]) -> QColor:
        r, g, b = rgb
        return QColor(r, g, b)

    def _draw_grid(self) -> None:
        self.scene.clear()
        step = max(1, int(self.cell_size))
        pen_grid = QPen(QColor(70, 70, 70))

        for x in range(0, self.grid_size + 1, step):
            self.scene.addLine(x, 0, x, self.grid_size, pen_grid)
        for y in range(0, self.grid_size + 1, step):
            self.scene.addLine(0, y, self.grid_size, y, pen_grid)

        for el in self.elements:
            self._draw_element(el)

        if self._temp_points:
            pen_t = QPen(self._rgb_to_qcolor(self.cc), 0)
            prev = None
            for (x, y) in self._temp_points:
                self.scene.addEllipse(x - 0.5, y - 0.5, 1, 1, pen_t)
                if prev:
                    self.scene.addLine(prev[0], prev[1], x, y, pen_t)
                prev = (x, y)
        if self.tool == "circle" and self._circle_center:
            cx, cy = self._circle_center
            pen_c = QPen(self._rgb_to_qcolor(self.cc), 0)
            self.scene.addEllipse(cx - 0.5, cy - 0.5, 1, 1, pen_c)

        if self.highlight_idx is not None and 0 <= self.highlight_idx < len(self.elements):
            self._draw_highlight(self.highlight_idx)

    def _draw_element(self, el: SceneElement) -> None:
        pen = QPen(self._rgb_to_qcolor(el.color), 0)
        if el.kind == "polyline":
            pts = el.points
            if not pts:
                return
            for i in range(1, len(pts)):
                x1, y1 = pts[i - 1]
                x2, y2 = pts[i]
                self.scene.addLine(x1, y1, x2, y2, pen)
            for (x, y) in pts:
                self.scene.addEllipse(x - 0.5, y - 0.5, 1, 1, pen)
        elif el.kind == "circle" and el.points:
            cx, cy = el.points[0]
            r = el.radius
            if r > 0:
                self.scene.addEllipse(cx - r, cy - r, 2 * r, 2 * r, pen)
                self.scene.addEllipse(cx - 0.5, cy - 0.5, 1, 1, pen)

    def _draw_highlight(self, idx: int) -> None:
        el = self.elements[idx]
        pen = QPen(QColor(255, 255, 255), 2)
        pen.setCosmetic(True)
        if el.kind == "polyline":
            pts = el.points
            for i in range(1, len(pts)):
                x1, y1 = pts[i - 1]
                x2, y2 = pts[i]
                self.scene.addLine(x1, y1, x2, y2, pen)
        elif el.kind == "circle" and el.points:
            cx, cy = el.points[0]
            r = el.radius
            if r > 0:
                self.scene.addEllipse(cx - r, cy - r, 2 * r, 2 * r, pen)

    def commit_polyline(self) -> Optional[SceneElement]:
        if len(self._temp_points) >= 2:
            el = SceneElement("polyline", list(self._temp_points), self.cc)
            self.elements.append(el)
            self.undo_manager.push_add(el)
            self._temp_points.clear()
            self._draw_grid()
            self.element_changed.emit()
            return el
        return None

    def commit_circle_from_center(self, cen: Tuple[int, int], r: int) -> SceneElement:
        el = SceneElement("circle", [cen], self.cc, r)
        self.elements.append(el)
        self.undo_manager.push_add(el)
        self._circle_center = None
        self._draw_grid()
        self.element_changed.emit()
        return el

    def clear_temporary(self) -> None:
        self._temp_points.clear()
        self._circle_center = None
        self._draw_grid()

    def clear_all(self) -> None:
        self.elements.clear()
        self.undo_manager = UndoManager()
        self._temp_points.clear()
        self._circle_center = None
        self._draw_grid()
        self.element_changed.emit()

    def remove_element(self, el: SceneElement) -> None:
        if el in self.elements:
            self.elements.remove(el)
            self.undo_manager.push_remove(el)
            self._draw_grid()
            self.element_changed.emit()

    def undo(self) -> None:
        self.undo_manager.undo(self.elements)
        self._draw_grid()
        self.element_changed.emit()

    def redo(self) -> None:
        self.undo_manager.redo(self.elements)
        self._draw_grid()
        self.element_changed.emit()

    def set_highlight(self, idx: Optional[int]) -> None:
        self.highlight_idx = idx
        self._draw_grid()

    # --- event filter and helpers ---
    def eventFilter(self, obj, e):
        et = e.type()
        if et == QtCore.QEvent.Type.MouseButtonPress:
            return self._handle_mouse_press(e)
        if et == QtCore.QEvent.Type.MouseButtonDblClick:
            return self._handle_mouse_double_click(e)
        if et == QtCore.QEvent.Type.MouseMove:
            return self._handle_mouse_move(e)
        if et == QtCore.QEvent.Type.MouseButtonRelease:
            return self._handle_mouse_release(e)
        if et == QtCore.QEvent.Type.Wheel:
            return self._handle_wheel(e)
        return super().eventFilter(obj, e)

    def _map_event_to_scene(self, p) -> Tuple[int, int]:
        sp = self.view.mapToScene(int(p.x()), int(p.y()))
        x = max(0, min(self.grid_size, int(round(sp.x()))))
        y = max(0, min(self.grid_size, int(round(sp.y()))))
        return x, y

    def _handle_mouse_press(self, e):
        mb = e.button()
        pos = e.position()
        if mb == Qt.MouseButton.LeftButton:
            x, y = self._map_event_to_scene(pos)
            if self.tool == "polyline":
                self._temp_points.append((x, y))
                self._draw_grid()
            elif self.tool == "circle":
                if self._circle_center is None:
                    self._circle_center = (x, y)
                    self._draw_grid()
                else:
                    cx, cy = self._circle_center
                    r = int(round(math.hypot(x - cx, y - cy)))
                    self.commit_circle_from_center((cx, cy), r)
            return True

        if mb in (Qt.MouseButton.MiddleButton, Qt.MouseButton.RightButton):
            self._panning = True
            self._last_pan_point = e.position()
            self.view.setCursor(Qt.CursorShape.ClosedHandCursor)
            return True
        return False

    def _handle_mouse_double_click(self, e):
        mb = e.button()
        if mb == Qt.MouseButton.LeftButton and self.tool == "polyline":
            self.commit_polyline()
            return True
        return False

    def _handle_mouse_move(self, e):
        if self._panning and self._last_pan_point is not None:
            newpos = e.position()
            dx = newpos.x() - self._last_pan_point.x()
            dy = newpos.y() - self._last_pan_point.y()
            self._last_pan_point = newpos
            self.view.horizontalScrollBar().setValue(int(self.view.horizontalScrollBar().value() - dx))
            self.view.verticalScrollBar().setValue(int(self.view.verticalScrollBar().value() - dy))
            return True
        return False

    def _handle_mouse_release(self, e):
        if e.button() in (Qt.MouseButton.MiddleButton, Qt.MouseButton.RightButton):
            self._panning = False
            self.view.setCursor(Qt.CursorShape.ArrowCursor)
            return True
        return False

    def _handle_wheel(self, e):
        d = e.angleDelta().y()
        f = 1.0 + (d / 1000.0)
        cur = self.view.transform()
        sn = cur.m11() if not cur.isIdentity() else 1.0
        ns = sn * f
        if 0.1 < ns < 10:
            self.view.scale(f, f)
        return True