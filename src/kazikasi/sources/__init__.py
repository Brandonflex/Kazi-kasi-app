"""Source adapters. Registry lives here so the CLI and pipeline share one truth."""

from __future__ import annotations

from .base import Adapter, Manifest, Payload
from .boards import BOARDS, BrighterMonday, Fuzu, MyJobMag
from .bulletins import NairobiCounty, PSCKenya
from .kenya_p2 import P2, Ajira, CareerPoint, TSC
from .reliefweb import ReliefWeb
from .kenya_additional import ADDITIONAL_SOURCES, JobWebKenya, KenyaJobs, UNJobsKenya, DevexKenya

REGISTRY: dict[str, type[Adapter]] = {
    **BOARDS,
    "reliefweb": ReliefWeb,
    "psc": PSCKenya,
    "nairobi_county": NairobiCounty,
    **P2,
    **ADDITIONAL_SOURCES,
}

__all__ = [
    "Adapter",
    "Manifest",
    "Payload",
    "REGISTRY",
    "BrighterMonday",
    "Fuzu",
    "MyJobMag",
    "ReliefWeb",
    "PSCKenya",
    "NairobiCounty",
    "CareerPoint",
    "TSC",
    "Ajira",
    "JobWebKenya",
    "KenyaJobs",
    "UNJobsKenya",
    "DevexKenya",
]
