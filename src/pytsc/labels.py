import math
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Label:
    width_mm: float
    height_mm: float

    def __post_init__(self):
        for value in (self.width_mm, self.height_mm):
            if not math.isfinite(value) or not 0 < value <= 1000:
                raise ValueError("Label dimensions must be finite and between 0 and 1000 mm")

    def pixels(self, dots_per_mm):
        size = (round(self.width_mm * dots_per_mm), round(self.height_mm * dots_per_mm))
        if min(size) < 1:
            raise ValueError("Label is smaller than one dot")
        return size


class LabelsManager:
    def get_label_by_identifier(self, identifier):
        if isinstance(identifier, Label):
            return identifier
        if not isinstance(identifier, str) or not re.fullmatch(
            r"\d+(?:\.\d+)?x\d+(?:\.\d+)?", identifier
        ):
            raise ValueError("Label must be WIDTHxHEIGHT in mm, e.g. 50x30")
        return Label(*map(float, identifier.split("x")))
