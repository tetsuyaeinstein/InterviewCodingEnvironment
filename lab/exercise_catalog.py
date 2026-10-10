"""Exercise metadata catalog.

Metadata lives in per-topic YAML files so topics can be authored independently:
  sql/checks/catalog/<topic>.yaml     (metadata + validation config)
  python/catalog/<topic>.yaml         (metadata + module/function contract)

Each file:  {topic: 03_gaps_islands_time, exercises: [ {id: SQL-021, title: ..., ...}, ... ]}
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

from .config import PY_DIR, SQL_DIR

SQL_TOPICS = ["01_foundations", "02_aggregates_windows", "03_gaps_islands_time",
              "04_dimensional_modeling", "05_cdc_data_quality", "06_postgres_performance"]
PY_TOPICS = ["01_fundamentals", "02_algorithms", "03_etl_file_processing",
             "04_streaming_reliability", "05_database_integrations"]
DIFFICULTIES = ["easy", "medium", "hard"]
SQL_MODES = {"query", "mutation", "plan", "modeling"}
ID_RE = re.compile(r"\b(SQL|PY)[-_ ]?(\d{1,3})\b", re.IGNORECASE)


class CatalogError(ValueError):
    pass


@dataclass
class Exercise:
    id: str
    lang: str                     # 'sql' | 'python'
    title: str
    topic: str                    # folder name, e.g. '03_gaps_islands_time'
    difficulty: str
    estimated_minutes: int
    validation_mode: str          # sql: query|mutation|plan|modeling ; python: pytest
    requires_database: bool
    prerequisites: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    meta: dict = field(default_factory=dict)

    # ------------------------------------------------------------------ basics
    @property
    def area(self) -> str:
        return self.topic.split("_", 1)[1]

    @property
    def number(self) -> int:
        return int(self.id.split("-")[1])

    @property
    def base(self) -> Path:
        return SQL_DIR if self.lang == "sql" else PY_DIR

    @property
    def ext(self) -> str:
        return "sql" if self.lang == "sql" else "py"

    @property
    def check(self) -> dict:
        return self.meta.get("check") or {}

    # ------------------------------------------------------------------ paths
    def _p(self, kind: str, suffix: str = "", ext: str | None = None) -> Path:
        return self.base / kind / self.topic / f"{self.id}{suffix}.{ext or self.ext}"

    @property
    def question_path(self) -> Path:
        return self._p("questions", ext="md")

    @property
    def hint_path(self) -> Path:
        return self._p("hints", ext="md")

    @property
    def practice_path(self) -> Path:
        return self._p("practice")

    @property
    def stub_path(self) -> Path:
        return self._p("stubs")

    def solution_path(self, alt: bool = False) -> Path:
        return self._p("solutions", "_alt" if alt else "")

    @property
    def has_alt(self) -> bool:
        return self.solution_path(alt=True).exists()

    @property
    def explanation_path(self) -> Path:
        return self._p("explanations", ext="md")

    # SQL validation artefacts
    @property
    def expected_path(self) -> Path:
        return SQL_DIR / "checks" / "expected" / f"{self.id}.json"

    @property
    def adversarial_path(self) -> Path:
        return SQL_DIR / "checks" / "adversarial" / f"{self.id}.yaml"

    @property
    def rubric_path(self) -> Path:
        return SQL_DIR / "checks" / "rubrics" / f"{self.id}.md"

    # Python validation artefacts
    @property
    def test_path(self) -> Path:
        return PY_DIR / "tests" / f"test_{self.id.lower().replace('-', '_')}.py"

    @property
    def requires_postgres(self) -> bool:
        return bool(self.meta.get("requires_postgres", False))


def normalize_id(text: str) -> str | None:
    m = ID_RE.search(text or "")
    if not m:
        return None
    prefix = m.group(1).upper()
    return f"{prefix}-{int(m.group(2)):03d}"


def _load_file(path: Path, lang: str) -> list[Exercise]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    topic = data.get("topic") or path.stem
    valid_topics = SQL_TOPICS if lang == "sql" else PY_TOPICS
    if topic not in valid_topics:
        raise CatalogError(f"{path}: unknown topic {topic!r}")
    out = []
    for raw in data.get("exercises") or []:
        try:
            ex = Exercise(
                id=raw["id"], lang=lang, title=raw["title"], topic=topic,
                difficulty=raw["difficulty"], estimated_minutes=int(raw["estimated_minutes"]),
                validation_mode=raw.get("validation_mode", "query" if lang == "sql" else "pytest"),
                requires_database=bool(raw.get("requires_database", lang == "sql")),
                prerequisites=list(raw.get("prerequisites") or []), tags=list(raw.get("tags") or []),
                meta=raw,
            )
        except KeyError as e:
            raise CatalogError(f"{path}: exercise {raw.get('id', '?')} missing field {e}") from e
        if normalize_id(ex.id) != ex.id:
            raise CatalogError(f"{path}: bad id {ex.id!r}")
        if ex.difficulty not in DIFFICULTIES:
            raise CatalogError(f"{path}: {ex.id} difficulty must be one of {DIFFICULTIES}")
        if lang == "sql" and ex.validation_mode not in SQL_MODES:
            raise CatalogError(f"{path}: {ex.id} validation_mode must be one of {sorted(SQL_MODES)}")
        out.append(ex)
    return out


@lru_cache(maxsize=1)
def load_catalog() -> dict[str, Exercise]:
    exercises: dict[str, Exercise] = {}
    sources = [(SQL_DIR / "checks" / "catalog", "sql"), (PY_DIR / "catalog", "python")]
    for directory, lang in sources:
        for path in sorted(directory.glob("*.yaml")):
            try:
                loaded = _load_file(path, lang)
            except (CatalogError, yaml.YAMLError) as e:  # one broken topic file must not break the CLI
                print(f"warning: skipping catalog file {path.name}: {e}", file=sys.stderr)
                continue
            for ex in loaded:
                if ex.id in exercises:
                    raise CatalogError(f"duplicate exercise id {ex.id} in {path}")
                exercises[ex.id] = ex
    return dict(sorted(exercises.items(), key=lambda kv: (kv[1].lang != "sql", kv[1].number)))


def get(exercise_id: str) -> Exercise:
    norm = normalize_id(exercise_id)
    cat = load_catalog()
    if norm is None or norm not in cat:
        known = ", ".join(list(cat)[:3])
        raise CatalogError(f"Unknown exercise {exercise_id!r}. Try `python -m lab list` (e.g. {known}).")
    return cat[norm]


def filter_exercises(lang: str | None = None, topic: str | None = None, difficulty: str | None = None,
                     tag: str | None = None) -> list[Exercise]:
    out = []
    for ex in load_catalog().values():
        if lang and ex.lang != lang:
            continue
        if topic and topic.lower() not in ex.topic.lower():
            continue
        if difficulty and ex.difficulty != difficulty:
            continue
        if tag and not any(tag.lower() in t.lower() for t in ex.tags):
            continue
        out.append(ex)
    return out
