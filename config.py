"""Load config.yaml into a typed Config object."""

from dataclasses import dataclass, field

import yaml


@dataclass
class Config:
    greenhouse_boards: list = field(default_factory=list)
    lever_companies: list = field(default_factory=list)
    ashby_boards: list = field(default_factory=list)
    # group label -> {"keywords": [...], "exclude": [...]}
    include_groups: dict = field(default_factory=dict)
    exclude_keywords: list = field(default_factory=list)
    location_keywords: list = field(default_factory=list)
    location_exclude_keywords: list = field(default_factory=list)


def load_config(path: str = "config.yaml") -> Config:
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    # include_keywords may be a plain list (legacy), a mapping of
    # group label -> keyword list, or group label -> {keywords, exclude}
    # where exclude holds per-group exclusions (e.g. "manager" for Finance
    # but not Product). Group labels tag alerts, e.g. [Finance].
    include = raw.get("include_keywords") or {}
    if isinstance(include, list):
        include = {"": include}
    groups = {}
    for label, spec in include.items():
        if isinstance(spec, dict):
            groups[label] = {"keywords": spec.get("keywords") or [],
                             "exclude": spec.get("exclude") or []}
        else:
            groups[label] = {"keywords": spec or [], "exclude": []}

    # `or []` handles keys whose entries are all commented out (YAML null).
    return Config(
        greenhouse_boards=raw.get("greenhouse_boards") or [],
        lever_companies=raw.get("lever_companies") or [],
        ashby_boards=raw.get("ashby_boards") or [],
        include_groups=groups,
        exclude_keywords=raw.get("exclude_keywords") or [],
        location_keywords=raw.get("location_keywords") or [],
        location_exclude_keywords=raw.get("location_exclude_keywords") or [],
    )
