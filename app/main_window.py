import os
import csv
import json
import sqlite3
from io import StringIO
from typing import List, Optional, Tuple

from PyQt6 import QtCore, QtGui, QtWidgets, uic
from PyQt6.QtGui import QColor
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication, QComboBox, QDialog, QFileDialog, QTableWidgetItem,
    QLabel, QMainWindow, QMessageBox, QPushButton, QSpinBox, QVBoxLayout
)

from .ui_xml import _ui_xml
from .scene_tab import SceneTab
from .models import SceneElement
from .utils import color_to_code, code_to_color, circle_to_points

# detect pandas availability (kept local here)
try:
    import pandas as pd
    _HAS_PANDAS = True
except Exception:
    _HAS_PANDAS = False


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._load_ui()
        self.setWindowTitle("Laser Scene Editor")

        self.tabWidget: QtWidgets.QTabWidget = self.ui.tabWidget
        self.elementsTable: QtWidgets.QTableWidget = self.ui.elementsTable

        self.grid_size = 255
        self.cell_size = 1
        self._circle_export_steps = 90
        self._normalize_on_export = False
        self._last_export_path = ""
        self._recent_files: List[str] = []

        self._setup_db()
        self._create_toolbar()
        self._setup_table()

        self.new_scene_tab()
        self.tabWidget.tabCloseRequested.connect(self.close_tab)

        self.table_row_map: List[Tuple[int, int]] = []
        self.update_elements_table()

    def _load_ui(self) -> None:
        f = StringIO(_ui_xml)
        Ui_MainWindow, _ = uic.loadUiType(f)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

    def _setup_db(self) -> None:
        self.db_path = os.path.join(os.path.expanduser("~"), ".laser_scene_editor.sqlite")
        try:
            self.conn = sqlite3.connect(self.db_path)
            cur = self.conn.cursor()
            cur.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
            self.conn.commit()

            def _get(key: str, cast=None, default=None):
                cur.execute("SELECT value FROM settings WHERE key=?", (key,))
                r = cur.fetchone()
                if not r:
                    return default
                val = r[0]
                try:
                    return cast(val) if cast else val
                except Exception:
                    return default

            self.grid_size = _get("grid_size", int, self.grid_size)
            self.cell_size = _get("cell_size", int, self.cell_size)
            self._circle_export_steps = _get("circle_steps", int, self._circle_export_steps)
            self._normalize_on_export = _get("normalize_export", lambda v: v == "1", self._normalize_on_export)
            self._last_export_path = _get("last_export_path", str, self._last_export_path)
            recent = _get("recent_files", None, None)
            if recent:
                try:
                    self._recent_files = json.loads(recent)
                except Exception:
                    self._recent_files = []
        except Exception:
            self.conn = None

    def _save_setting(self, key: str, value: str) -> None:
        if not getattr(self, "conn", None):
            return
        cur = self.conn.cursor()
        cur.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)", (key, str(value)))
        self.conn.commit()

    def _create_toolbar(self) -> None:
        tb = self.addToolBar("Tools")
        tb.setMovable(False)
        a_new = QtGui.QAction("New", self)
        a_new.triggered.connect(self.new_scene_tab)
        tb.addAction(a_new)

        a_open = QtGui.QAction("Open CSV", self)
        a_open.triggered.connect(self.open_csv)
        tb.addAction(a_open)

        a_save = QtGui.QAction("Save CSV", self)
        a_save.triggered.connect(self.save_csv)
        tb.addAction(a_save)
        tb.addSeparator()

        a_export = QtGui.QAction("Export Laser", self)
        a_export.triggered.connect(self.export_laser_format)
        tb.addAction(a_export)

        a_import_laser = QtGui.QAction("Import Laser", self)
        a_import_laser.triggered.connect(self.import_laser_format)
        tb.addAction(a_import_laser)
        tb.addSeparator()

        a_reset = QtGui.QAction("Reset", self)
        a_reset.triggered.connect(self.reset_scene)
        tb.addAction(a_reset)
        tb.addSeparator()

        self.tool_group = QtGui.QActionGroup(self)
        a_poly = QtGui.QAction("Polyline", self, checkable=True)
        a_circle = QtGui.QAction("Circle", self, checkable=True)
        a_poly.setChecked(True)

        self.tool_group.addAction(a_poly)
        self.tool_group.addAction(a_circle)
        a_poly.triggered.connect(lambda: self.set_tool("polyline"))
        a_circle.triggered.connect(lambda: self.set_tool("circle"))
        tb.addAction(a_poly)
        tb.addAction(a_circle)

        tb.addSeparator()
        for (label, color) in [("Red", (255, 0, 0)), ("Green", (0, 255, 0)), ("Blue", (0, 0, 255))]:
            btn = QPushButton(label)
            btn.clicked.connect(lambda _checked=False, c=color: self.set_color(c))
            tb.addWidget(btn)

        tb.addSeparator()
        a_finish = QtGui.QAction("Finish Polyline", self)
        a_finish.triggered.connect(self.finish_polyline_button)
        tb.addAction(a_finish)

        tb.addSeparator()
        a_undo = QtGui.QAction("Undo", self)
        a_undo.triggered.connect(self.undo)
        tb.addAction(a_undo)

        a_redo = QtGui.QAction("Redo", self)
        a_redo.triggered.connect(self.redo)
        tb.addAction(a_redo)

        tb.addSeparator()
        a_settings = QtGui.QAction("Settings", self)
        a_settings.triggered.connect(self.show_settings_dialog)
        tb.addAction(a_settings)

    def _setup_table(self) -> None:
        self.elementsTable.setColumnCount(7)
        self.elementsTable.setHorizontalHeaderLabels(["El #", "Sub #", "Kind", "Color", "X", "Y", "Radius"])
        self.elementsTable.horizontalHeader().setStretchLastSection(True)
        self.elementsTable.itemChanged.connect(self._on_table_item_changed)
        self.elementsTable.cellClicked.connect(self._on_table_cell_clicked)

    def new_scene_tab(self) -> None:
        st = SceneTab(self, grid_size=self.grid_size, cell_size=self.cell_size)
        idx = self.tabWidget.addTab(st, f"Scene {self.tabWidget.count() + 1}")
        self.tabWidget.setCurrentIndex(idx)
        st.element_changed.connect(self.update_elements_table)
        self.tabWidget.currentChanged.connect(self.update_elements_table)
        st._draw_grid()
        self.update_elements_table()

    def close_tab(self, index: int) -> None:
        w = self.tabWidget.widget(index)
        if w:
            try:
                w.element_changed.disconnect(self.update_elements_table)
            except Exception:
                pass
            self.tabWidget.removeTab(index)
            w.deleteLater()
        self.update_elements_table()

    def current_scene(self) -> Optional[SceneTab]:
        w = self.tabWidget.currentWidget()
        return w if isinstance(w, SceneTab) else None

    def set_tool(self, tool_name: str) -> None:
        sc = self.current_scene()
        if sc:
            sc.tool = tool_name
            self.statusBar().showMessage(f"Tool: {tool_name}")

    def set_color(self, rgb: Tuple[int, int, int]) -> None:
        sc = self.current_scene()
        if sc:
            sc.cc = rgb
            self.statusBar().showMessage(f"Color set to {rgb}")

    def finish_polyline_button(self) -> None:
        sc = self.current_scene()
        if not sc:
            return
        el = sc.commit_polyline()
        if el:
            self.statusBar().showMessage("Polyline finished")
        else:
            self.statusBar().showMessage("Nothing to finish")

    def undo(self) -> None:
        sc = self.current_scene()
        if sc:
            sc.undo()

    def redo(self) -> None:
        sc = self.current_scene()
        if sc:
            sc.redo()

    def reset_scene(self) -> None:
        sc = self.current_scene()
        if sc and QMessageBox.question(self, "Reset", "Очистить текущую сцену?") == QMessageBox.StandardButton.Yes:
            sc.clear_all()

    def show_settings_dialog(self) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle("Settings")
        layout = QVBoxLayout(dlg)

        lbl1 = QLabel("Grid size (max 255):")
        sp_grid = QSpinBox()
        sp_grid.setRange(1, 255)
        sp_grid.setValue(self.grid_size)

        lbl2 = QLabel("Cell size (pixels):")
        sp_cell = QSpinBox()
        sp_cell.setRange(1, 16)
        sp_cell.setValue(self.cell_size)

        lbl3 = QLabel("Circle export steps (points):")
        sp_steps = QSpinBox()
        sp_steps.setRange(8, 360)
        sp_steps.setValue(self._circle_export_steps)

        chk_norm = QtWidgets.QCheckBox("Normalize coordinates to 0..255 on export")
        chk_norm.setChecked(self._normalize_on_export)

        lbl_recent = QLabel(f"Recent files (last {len(self._recent_files)}):")
        btn_ok = QPushButton("Apply")

        layout.addWidget(lbl1)
        layout.addWidget(sp_grid)
        layout.addWidget(lbl2)
        layout.addWidget(sp_cell)
        layout.addWidget(lbl3)
        layout.addWidget(sp_steps)
        layout.addWidget(chk_norm)
        layout.addWidget(lbl_recent)
        for p in self._recent_files[-10:][::-1]:
            layout.addWidget(QLabel(p))
        layout.addWidget(btn_ok)

        def apply():
            self.grid_size = int(sp_grid.value())
            self.cell_size = int(sp_cell.value())
            self._circle_export_steps = int(sp_steps.value())
            self._normalize_on_export = chk_norm.isChecked()
            for i in range(self.tabWidget.count()):
                w = self.tabWidget.widget(i)
                if isinstance(w, SceneTab):
                    w.grid_size = self.grid_size
                    w.cell_size = self.cell_size
                    w.scene.setSceneRect(0, 0, self.grid_size, self.grid_size)
                    w._draw_grid()
            self._save_setting("grid_size", str(self.grid_size))
            self._save_setting("cell_size", str(self.cell_size))
            self._save_setting("circle_steps", str(self._circle_export_steps))
            self._save_setting("normalize_export", "1" if self._normalize_on_export else "0")
            self._save_setting("last_export_path", self._last_export_path or "")
            try:
                self._save_setting("recent_files", json.dumps(self._recent_files))
            except Exception:
                pass
            dlg.accept()

        btn_ok.clicked.connect(apply)
        dlg.exec()

    def update_elements_table(self) -> None:
        sc = self.current_scene()
        if sc is None:
            self.elementsTable.setRowCount(0)
            self.table_row_map = []
            return

        rows = []
        for el_idx, el in enumerate(sc.elements, start=1):
            if el.kind == "polyline":
                for sub_idx, (x, y) in enumerate(el.points, start=1):
                    rows.append({
                        "el": el_idx,
                        "sub": sub_idx,
                        "kind": "polyline",
                        "color": el.color,
                        "x": x,
                        "y": y,
                        "radius": "",
                    })
            elif el.kind == "circle":
                cx, cy = el.points[0] if el.points else (0, 0)
                rows.append({
                    "el": el_idx,
                    "sub": 1,
                    "kind": "circle",
                    "color": el.color,
                    "x": cx,
                    "y": cy,
                    "radius": el.radius,
                })

        self.elementsTable.blockSignals(True)
        self.elementsTable.setRowCount(len(rows))
        self.table_row_map = []

        for r_idx, r in enumerate(rows):
            it_el = QTableWidgetItem(str(r["el"]))
            it_el.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            self.elementsTable.setItem(r_idx, 0, it_el)

            it_sub = QTableWidgetItem(str(r["sub"]))
            it_sub.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            self.elementsTable.setItem(r_idx, 1, it_sub)

            it_kind = QTableWidgetItem(r["kind"])
            it_kind.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            self.elementsTable.setItem(r_idx, 2, it_kind)

            combo = QComboBox()
            combo.addItems(["Red", "Green", "Blue"])
            code = color_to_code(tuple(r["color"]))
            combo.setCurrentIndex(code - 1)
            combo.currentIndexChanged.connect(lambda idx, row=r_idx: self._on_color_changed_in_table(row, idx))
            self.elementsTable.setCellWidget(r_idx, 3, combo)

            item_x = QTableWidgetItem(str(r["x"]))
            item_x.setFlags(item_x.flags() | Qt.ItemFlag.ItemIsEditable)
            self.elementsTable.setItem(r_idx, 4, item_x)

            item_y = QTableWidgetItem(str(r["y"]))
            item_y.setFlags(item_y.flags() | Qt.ItemFlag.ItemIsEditable)
            self.elementsTable.setItem(r_idx, 5, item_y)

            item_r = QTableWidgetItem(str(r["radius"]))
            if r["kind"] == "circle":
                item_r.setFlags(item_r.flags() | Qt.ItemFlag.ItemIsEditable)
            else:
                item_r.setFlags(item_r.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.elementsTable.setItem(r_idx, 6, item_r)

            self.table_row_map.append((r["el"] - 1, r["sub"] - 1))

        self.elementsTable.blockSignals(False)
        self.elementsTable.resizeColumnsToContents()

    def _on_color_changed_in_table(self, row: int, combo_index: int) -> None:
        if row < 0 or row >= len(self.table_row_map):
            return
        el_idx, _ = self.table_row_map[row]
        sc = self.current_scene()
        if not sc:
            return
        if el_idx < 0 or el_idx >= len(sc.elements):
            return
        el = sc.elements[el_idx]
        new_color = code_to_color(combo_index + 1)
        el.color = new_color
        sc._draw_grid()
        sc.element_changed.emit()

    def _on_table_item_changed(self, item: QTableWidgetItem) -> None:
        row = item.row()
        col = item.column()

        if row < 0 or row >= len(self.table_row_map):
            return
        el_idx, sub_idx = self.table_row_map[row]
        sc = self.current_scene()
        if not sc:
            return
        if el_idx < 0 or el_idx >= len(sc.elements):
            return
        el = sc.elements[el_idx]

        try:
            if col in (4, 5):
                x_item = self.elementsTable.item(row, 4)
                y_item = self.elementsTable.item(row, 5)
                if not x_item or not y_item:
                    return
                x = int(float(x_item.text()))
                y = int(float(y_item.text()))
                x = max(0, min(sc.grid_size, x))
                y = max(0, min(sc.grid_size, y))
                if el.kind == "polyline":
                    if 0 <= sub_idx < len(el.points):
                        el.points[sub_idx] = (x, y)
                        sc._draw_grid()
                        sc.element_changed.emit()
                elif el.kind == "circle":
                    if sub_idx == 0:
                        el.points[0] = (x, y)
                        sc._draw_grid()
                        sc.element_changed.emit()
            elif col == 6:  # radius
                if el.kind == "circle":
                    val = int(float(item.text()))
                    el.radius = max(0, val)
                    sc._draw_grid()
                    sc.element_changed.emit()
        except Exception:
            return

    def _on_table_cell_clicked(self, row: int, col: int) -> None:
        if row < 0 or row >= len(self.table_row_map):
            return
        el_idx, _ = self.table_row_map[row]
        sc = self.current_scene()
        if not sc:
            return
        sc.set_highlight(el_idx)

    def save_csv(self) -> None:
        sc = self.current_scene()
        if not sc:
            QMessageBox.warning(self, "No scene", "Нет активной сцены для сохранения.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save CSV", "", "CSV Files (*.csv)")
        if not path:
            return
        rows = []

        for el in sc.elements:
            if el.kind == "polyline":
                for (x, y) in el.points:
                    rows.append({
                        "kind": "polyline",
                        "x": int(x),
                        "y": int(y),
                        "r": el.color[0],
                        "g": el.color[1],
                        "b": el.color[2],
                        "radius": "",
                    })
            elif el.kind == "circle":
                cx, cy = el.points[0]
                rows.append({
                    "kind": "circle",
                    "x": int(cx),
                    "y": int(cy),
                    "r": el.color[0],
                    "g": el.color[1],
                    "b": el.color[2],
                    "radius": el.radius,
                })
        try:
            if _HAS_PANDAS:
                df = pd.DataFrame(rows)
                df.to_csv(path, index=False)
            else:
                with open(path, "w", newline="") as f:
                    w = csv.DictWriter(f, fieldnames=["kind", "x", "y", "r", "g", "b", "radius"])
                    w.writeheader()
                    for r in rows:
                        w.writerow(r)
            self.statusBar().showMessage(f"Saved CSV: {path}")
            self._add_to_recent(path)
        except Exception as e:
            QMessageBox.critical(self, "Save error", str(e))

    def open_csv(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open CSV", "", "CSV Files (*.csv)")
        if not path:
            return
        self.new_scene_tab()
        sc = self.current_scene()
        if sc is None:
            return
        rows = []
        try:
            if _HAS_PANDAS:
                df = pd.read_csv(path)
                rows = df.to_dict("records")
            else:
                with open(path, newline="") as f:
                    reader = csv.DictReader(f)
                    for r in reader:
                        rows.append(r)
        except Exception as e:
            QMessageBox.critical(self, "Load error", str(e))
            return

        current_poly = []
        cc = None

        for r in rows:
            kind = r.get("kind", "polyline")
            x = int(float(r.get("x", 0)))
            y = int(float(r.get("y", 0)))
            rc = int(float(r.get("r", 0)))
            gc = int(float(r.get("g", 0)))
            bc = int(float(r.get("b", 0)))
            radius = r.get("radius", "")
            color = (rc, gc, bc)

            if kind == "polyline":
                if cc is None:
                    cc = color
                    current_poly = []
                if color != cc and current_poly:
                    sc.elements.append(SceneElement("polyline", current_poly[:], cc))
                    sc.undo_manager.push_add(sc.elements[-1])
                    current_poly = []
                    cc = color
                current_poly.append((x, y))
            elif kind == "circle":
                if current_poly:
                    sc.elements.append(SceneElement("polyline", current_poly[:], cc))
                    sc.undo_manager.push_add(sc.elements[-1])
                    current_poly = []
                    cc = None
                rr = int(radius) if radius not in (None, "") else 0
                sc.elements.append(SceneElement("circle", [(x, y)], color, rr))
                sc.undo_manager.push_add(sc.elements[-1])

        if current_poly:
            sc.elements.append(SceneElement("polyline", current_poly[:], cc))
            sc.undo_manager.push_add(sc.elements[-1])

        sc._draw_grid()
        sc.element_changed.emit()
        self._add_to_recent(path)
        self.statusBar().showMessage(f"Opened CSV: {path}")

    def export_laser_format(self) -> None:
        sc = self.current_scene()
        if sc is None:
            QMessageBox.warning(self, "No scene", "Нет активной сцены для экспорта.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export Laser Format", "", "Text Files (*.txt);;All Files (*)", options=QFileDialog.Option.DontUseNativeDialog)
        if not path:
            return
        self._last_export_path = os.path.dirname(path)
        self._save_setting("last_export_path", self._last_export_path)
        s = self._circle_export_steps

        try:
            normalize = self._normalize_on_export
            gx = self.grid_size
            gy = self.grid_size
            with open(path, "w", encoding="utf-8") as f:
                for el in sc.elements:
                    code = color_to_code(el.color)
                    f.write(f"COLOR {code}\n")
                    pts = []
                    if el.kind == "polyline":
                        pts = el.points
                    elif el.kind == "circle":
                        pts = circle_to_points(el.points[0], el.radius, s)
                    for (x, y) in pts:
                        ox, oy = int(x), int(y)
                        if normalize:
                            nx = round((ox / max(1, gx)) * 255)
                            ny = round((oy / max(1, gy)) * 255)
                            f.write(f"{int(nx)},{int(ny)}\n")
                        else:
                            f.write(f"{ox},{oy}\n")
                    f.write("STOP\n")
            self.statusBar().showMessage(f"Exported laser format: {path}")
            self._add_to_recent(path)
        except Exception as e:
            QMessageBox.critical(self, "Export error", str(e))

    def import_laser_format(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Import Laser Format", "", "Text Files (*.txt);;All Files (*)")

        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                lines = [ln.strip() for ln in f.readlines()]
        except Exception as e:
            QMessageBox.critical(self, "Import error", str(e))
            return

        self.new_scene_tab()
        sc = self.current_scene()
        if sc is None:
            return

        idx = 0
        cc = None
        cp = []

        while idx < len(lines):
            ln = lines[idx]
            idx += 1
            if not ln:
                continue
            if ln.upper().startswith("COLOR"):
                if cp and cc is not None:
                    sc.elements.append(SceneElement("polyline", list(cp), cc))
                    sc.undo_manager.push_add(sc.elements[-1])
                    cp = []
                parts = ln.split()
                code = 1
                if len(parts) >= 2:
                    try:
                        code = int(parts[1])
                    except Exception:
                        code = 1
                cc = code_to_color(code)
            elif ln.upper() == "STOP":
                if cp and cc is not None:
                    sc.elements.append(SceneElement("polyline", list(cp), cc))
                    sc.undo_manager.push_add(sc.elements[-1])
                cp = []
            else:
                try:
                    px, py = ln.split(",", 1)
                    x = int(float(px.strip()))
                    y = int(float(py.strip()))
                    cp.append((x, y))
                except Exception:
                    continue

        if cp and cc is not None:
            sc.elements.append(SceneElement("polyline", list(cp), cc))
            sc.undo_manager.push_add(sc.elements[-1])

        sc._draw_grid()
        sc.element_changed.emit()
        self._add_to_recent(path)
        self.statusBar().showMessage(f"Imported laser format: {path}")

    def _add_to_recent(self, path: str) -> None:
        try:
            if path in self._recent_files:
                self._recent_files.remove(path)
            self._recent_files.append(path)
            self._recent_files = self._recent_files[-50:]
            self._save_setting("recent_files", json.dumps(self._recent_files))
        except Exception:
            pass