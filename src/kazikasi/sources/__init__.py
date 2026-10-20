"""Source adapters. Registry lives here so the CLI and pipeline share one truth."""

from __future__ import annotations

from .base import Adapter, FetchResult, Manifest
from .boards import BOARDS, BrighterMonday, Fuzu, MyJobMag
from .reliefweb import ReliefWeb

REGISTRY: dict[str, type[Adapter]] = {**BOARDS, "reliefweb": ReliefWeb}

__all__ = [
    "Adapter",
    "FetchResult",
    "Manifest",
    "REGISTRY",
    "BrighterMonday",
    "Fuzu",
    "MyJobMag",
    "ReliefWeb",
]
