from typing import List, Tuple
from .models import SceneElement

class UndoManager:
    def __init__(self):
        self._undo: List[Tuple[str, SceneElement]] = []
        self._redo: List[Tuple[str, SceneElement]] = []

    def push_add(self, element: SceneElement) -> None:
        self._undo.append(("add", element))
        self._redo.clear()

    def push_remove(self, element: SceneElement) -> None:
        self._undo.append(("remove", element))
        self._redo.clear()

    def can_undo(self) -> bool:
        return bool(self._undo)

    def can_redo(self) -> bool:
        return bool(self._redo)

    def undo(self, elements: List[SceneElement]) -> None:
        if not self._undo:
            return
        op, el = self._undo.pop()
        if op == "add":
            if el in elements:
                elements.remove(el)
            self._redo.append(("add", el))
        elif op == "remove":
            elements.append(el)
            self._redo.append(("remove", el))

    def redo(self, elements: List[SceneElement]) -> None:
        if not self._redo:
            return
        op, el = self._redo.pop()
        if op == "add":
            elements.append(el)
            self._undo.append(("add", el))
        elif op == "remove":
            if el in elements:
                elements.remove(el)
            self._undo.append(("remove", el))