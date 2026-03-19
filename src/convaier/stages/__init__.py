from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from convaier.context import PipelineContext


@dataclass
class StageResult:
    success: bool
    summary: str = ""


class Stage(ABC):
    name: str = ""

    def __init__(self, stage_config: dict | None = None):
        self.stage_config = stage_config or {}

    @abstractmethod
    def run(self, ctx: PipelineContext) -> StageResult:
        ...

    def should_skip(self, ctx: PipelineContext) -> bool:
        return False


STAGE_REGISTRY: dict[str, type[Stage]] = {}


def register(name: str):
    def wrapper(cls: type[Stage]):
        cls.name = name
        STAGE_REGISTRY[name] = cls
        return cls
    return wrapper


def _auto_import() -> None:
    import importlib
    import pkgutil
    import convaier.stages as pkg

    for info in pkgutil.iter_modules(pkg.__path__):
        importlib.import_module(f"convaier.stages.{info.name}")


_auto_import()
