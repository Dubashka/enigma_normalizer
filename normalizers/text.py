"""Универсальный нормализатор текстовых колонок.

Назначение — нормализовать произвольные текстовые столбцы, тип которых нельзя
заранее типизировать (названия складов, групп номенклатуры, категорий и т.п.).
Пользователь сам указывает такие колонки, а алгоритм приводит значения к
единому виду и объединяет похожие варианты.

Алгоритм:
1. Unicode-нормализация (NFKC): унифицируется ё/е, схлопываются совместимые формы.
2. Очистка пробелов и неразрывных пробелов, нормализация дефисов/тире.
3. Удаление окаймляющих кавычек (все виды) и обрамляющей пунктуации.
4. Схлопывание множественных разделителей: «Склад №  1», «Склад - 1» → «склад 1».
5. Приведение регистра для ключа сравнения к lower; для канонического вида —
   сохраняется самый частый исходный вариант, но с очищенными пробелами и
   кавычками.
6. Кластеризация по схожести (rapidfuzz token_set_ratio): объединяются
   «Склад №1», «склад 1», «Склад-1» и т.д. Порог по умолчанию выше, чем для
   организаций, т.к. здесь нет доп. признаков вроде ОПФ.
"""
from __future__ import annotations

import re
import unicodedata

from utils.clustering import cluster_by_similarity
from .base import BaseNormalizer, NormalizationCandidate


_QUOTES_RE = re.compile(r"[\"'`«»“”„‟‘’]")
_MULTISPACE_RE = re.compile(r"\s+")
# Разные виды тире/дефисов к одному
_DASH_RE = re.compile(r"[\u2010-\u2015\u2212]")
# Знаки-разделители, которые на уровне ключа сравнения заменяем на пробел
_SEP_RE = re.compile(r"[_/\\|,;:()\[\]{}№#]+")
# Всё, что не буква/цифра/пробел — убираем при построении ключа
_NONWORD_RE = re.compile(r"[^\w\s]", re.UNICODE)


class TextNormalizer(BaseNormalizer):
    """Универсальная нормализация произвольных текстовых значений."""

    name = "text"
    title = "Текстовые значения"

    def __init__(self, similarity_threshold: int = 90):
        self.threshold = similarity_threshold

    # -- Базовая очистка -------------------------------------------------
    def _basic_clean(self, value: str) -> str:
        """NFKC + пробелы + единый дефис. Регистр не трогаем."""
        s = self._clean(value)
        if not s:
            return ""
        # NFC, а не NFKC, чтобы не ломать «№» → «No» и похожие символы
        s = unicodedata.normalize("NFC", s)
        s = s.replace("ё", "е").replace("Ё", "Е")
        s = _DASH_RE.sub("-", s)
        s = _MULTISPACE_RE.sub(" ", s).strip(" ,.-;:")
        return s

    def normalize_value(self, value: str) -> str:
        """Каноническая форма одного значения.

        Мы НЕ приводим регистр принудительно: текстовые колонки часто содержат
        собственные имена (склад «Ромашка», группа «Молочка»). Только чистим
        пробелы, кавычки и тире, и делаем первую букву заглавной, если строка
        начинается со строчной.
        """
        s = self._basic_clean(value)
        if not s:
            return ""
        # Убираем окаймляющие кавычки, но внутренние оставляем (часто часть имени)
        while s and s[0] in "\"'`«»“”„‟‘’":
            s = s[1:]
        while s and s[-1] in "\"'`«»“”„‟‘’":
            s = s[:-1]
        s = s.strip(" ,.-;:")
        if s and s[0].islower():
            s = s[0].upper() + s[1:]
        return s

    # -- Ключ сравнения --------------------------------------------------
    def _compare_key(self, value: str) -> str:
        """Агрессивно-нормализованный ключ для сравнения схожести."""
        s = self._basic_clean(value).lower()
        s = _QUOTES_RE.sub(" ", s)
        s = _SEP_RE.sub(" ", s)
        s = _NONWORD_RE.sub(" ", s)
        return _MULTISPACE_RE.sub(" ", s).strip()

    # -- Кандидаты -------------------------------------------------------
    def build_candidates(self, values: list[str]) -> list[NormalizationCandidate]:
        cleaned = [self._basic_clean(v) for v in values if self._basic_clean(v)]
        if not cleaned:
            return []

        clusters = cluster_by_similarity(
            cleaned,
            key_fn=self._compare_key,
            threshold=self.threshold,
        )

        candidates: list[NormalizationCandidate] = []
        for cl in clusters:
            variants = list(cl["variants"].keys())
            canonical = self.normalize_value(cl["canonical"])
            confidence = 1.0 if len(variants) == 1 else 0.8

            candidates.append(
                NormalizationCandidate(
                    canonical=canonical,
                    variants=variants,
                    count=cl["count"],
                    confidence=confidence,
                    meta={"variant_counts": dict(cl["variants"])},
                )
            )

        candidates.sort(key=lambda c: (-len(c.variants), -c.count))
        return candidates
