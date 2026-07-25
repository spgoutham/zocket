"""Load and validate config.yaml.

Keeping this dumb on purpose: the pipeline is config-driven (topics, source,
storage, classification taxonomy all live in one YAML file per the assessment
brief), so this module's only job is "read the file, fail loudly if it's
missing something a later stage will need."
"""

from __future__ import annotations

import pathlib
from dataclasses import dataclass, field

import yaml

REQUIRED_TOP_LEVEL_KEYS = ("source", "topics", "storage", "classification", "logging")


@dataclass
class Topic:
    id: str
    label: str
    query: str
    target_items: int


@dataclass
class PipelineConfig:
    raw: dict
    topics: list[Topic] = field(init=False)

    def __post_init__(self) -> None:
        self.topics = [Topic(**t) for t in self.raw["topics"]]

    @property
    def source(self) -> dict:
        return self.raw["source"]

    @property
    def storage(self) -> dict:
        return self.raw["storage"]

    @property
    def classification(self) -> dict:
        return self.raw["classification"]

    @property
    def logging(self) -> dict:
        return self.raw["logging"]


def load_config(path: str | pathlib.Path = "config.yaml") -> PipelineConfig:
    config_path = pathlib.Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"config file not found: {config_path.resolve()}")

    with config_path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    missing = [k for k in REQUIRED_TOP_LEVEL_KEYS if k not in raw]
    if missing:
        raise ValueError(f"config.yaml is missing required section(s): {missing}")
    if not raw["topics"]:
        raise ValueError("config.yaml must define at least one topic")

    return PipelineConfig(raw=raw)
