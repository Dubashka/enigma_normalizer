"""Базовый интерфейс для всех алгоритмов нормализации."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class NormalizationCandidate:
    """Кандидат на нормализацию — группа похожих значений, которые предлагается
    свести к одному каноническому виду.
    """

    canonical: str                       # Предлагаемое каноническое значение
    variants: list[str] = field(default_factory=list)  # Исходные варианты из колонки
    count: int = 0                       # Сколько раз встречается суммарно
    confidence: float = 1.0              # 0..1 — уверенность алгоритма
    meta: dict[str, Any] = field(default_factory=dict)  # Доп. информация

    def to_row(self, idx: int) -> dict[str, Any]:
        """Представление для таблицы в UI."""
        return {
            "id": idx,
            "Каноническое значение": self.canonical,
            "Варианты": " | ".join(self.variants),
            "Кол-во вариантов": len(self.variants),
            "Встречается всего": self.count,
            "Уверенность": round(self.confidence, 3),
        }


class BaseNormalizer(ABC):
    """Базовый класс: каждый тип данных реализует свой алгоритм."""

    name: str = "base"
    title: str = "Базовый нормализатор"

    @abstractmethod
    def normalize_value(self, value: str) -> str:
        """Привести одно значение к каноническому виду."""

    @abstractmethod
    def build_candidates(self, values: list[str]) -> list[NormalizationCandidate]:
        """Сгруппировать все значения колонки в кандидатов на объединение."""

    # Общие утилиты ------------------------------------------------------

    @staticmethod
    def _clean(value: Any) -> str:
        if value is None:
            return ""
        s = str(value).strip()
        # Схлопывание пробелов и неразрывных пробелов
        s = s.replace("\u00a0", " ").replace("\t", " ")
        while "  " in s:
            s = s.replace("  ", " ")
        return s

    @staticmethod
    def _dedupe_with_counts(values: list) -> tuple[list[str], dict[str, int]]:
        """Дедупликация: считаем частоту случаев каждого значения.

        Нормализаторам достаточно прогнать каждое уникальное значение одинраз —
        частоты потом учтываются при подсчёте. Это самая крупная экономия
        на больших файлах с повторами (контрагенты, адреса и т.п.).
        """
        from collections import Counter
        counter: Counter[str] = Counter()
        for v in values:
            if v is None:
                continue
            s = str(v).strip()
            if not s or s.lower() in ("nan", "none", "null", "-"):
                continue
            counter[s] += 1
        # Сортировка по убыванию частоты — это важно для алгоритма кластеризации.
        uniq = sorted(counter, key=lambda k: (-counter[k], -len(k)))
        return uniq, dict(counter)
