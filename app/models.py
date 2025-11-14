from dataclasses import dataclass, field
from typing import List, Tuple

@dataclass
class SceneElement:
    kind: str = "polyline"
    points: List[Tuple[int, int]] = field(default_factory=list)
    color: Tuple[int, int, int] = (255, 0, 0)
    radius: int = 0

    def __repr__(self) -> str:
        return f"<SceneElement {self.kind} pts={len(self.points)} color={self.color} r={self.radius}>"