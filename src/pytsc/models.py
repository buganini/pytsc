"""Experimental profiles; catalog membership is not hardware verification."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Model:
    identifier: str
    dpi: int
    dots_per_mm: int
    max_width_mm: int = 104
    hardware_verified: bool = False


MODELS = {
    "TTP-342": Model("TTP-342", 300, 12),
    "generic-203": Model("generic-203", 203, 8),
    "generic-300": Model("generic-300", 300, 12),
}


class ModelsManager:
    def get_model_by_identifier(self, identifier):
        try:
            return MODELS[identifier]
        except KeyError:
            raise ValueError(f"Unknown model: {identifier}") from None

    def get_models(self):
        return list(MODELS.values())
