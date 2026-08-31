import json
from functools import lru_cache
from pathlib import Path
from string import Formatter

from core.resource import resource_path

DEFAULT_LOCALE = "zh_CN"
LOCALE_DIR = resource_path("assets/locales")


@lru_cache(maxsize=None)
def load_catalog(locale: str = DEFAULT_LOCALE) -> dict[str, str]:
    path = Path(LOCALE_DIR) / f"{locale}.json"
    with path.open(encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in data.items()):
        raise ValueError(f"Invalid locale catalog: {path}")
    return data


def t(key: str, /, **values: object) -> str:
    catalog = load_catalog()
    try:
        text = catalog[key]
    except KeyError as exc:
        raise KeyError(f"Missing locale key: {key}") from exc
    return text.format(**values) if values else text


def placeholders(text: str) -> set[str]:
    return {name for _, name, _, _ in Formatter().parse(text) if name}
