"""Нормализатор названий организаций.

Алгоритм:
1. Чистка кавычек-ёлочек, двойных пробелов, обрамляющей пунктуации.
2. Отделение организационно-правовой формы (ОПФ):
      ООО, ОАО, ЗАО, ПАО, АО, ИП, ГК, НКО, ФГУП, ГБОУ, МУП и т.д.
   ОПФ выносится в префикс в канонической короткой форме.
3. Разворачивание части полных форм:
      "Общество с ограниченной ответственностью" -> "ООО"
      "Публичное акционерное общество" -> "ПАО"
      и т.д.
4. Удаление двойных кавычек разных типов вокруг названия, но сохранение
   оригинального регистра собственного имени.
5. Лемматизация только общего рода слов (например, "банка" -> "банк") —
   опционально; для собственных имён не применяется.
6. Кластеризация: rapidfuzz token_set_ratio; ключ сравнения — название без ОПФ.
   Это позволяет сгруппировать "ООО Ромашка" и "Ромашка ООО" и "Ромашка".
"""
from __future__ import annotations

import re
from collections import Counter

from utils.clustering import cluster_by_similarity
from .base import BaseNormalizer, NormalizationCandidate


# Канонические ОПФ и их распространённые написания
_OPF_MAP = {
    "ООО": [
        "общество с ограниченной ответственностью",
        "ооо",
        "o.o.o.",
    ],
    "ОАО": ["открытое акционерное общество", "оао"],
    "ЗАО": ["закрытое акционерное общество", "зао"],
    "ПАО": ["публичное акционерное общество", "пао"],
    "НАО": ["непубличное акционерное общество", "нао"],
    "АО":  ["акционерное общество", "ао"],
    "ИП":  ["индивидуальный предприниматель", "ип"],
    "ГК":  ["государственная корпорация", "гк"],
    "НКО": ["некоммерческая организация", "нко"],
    "ФГУП": ["федеральное государственное унитарное предприятие", "фгуп"],
    "МУП":  ["муниципальное унитарное предприятие", "муп"],
    "ГБОУ": ["государственное бюджетное образовательное учреждение", "гбоу"],
    "ГБУ":  ["государственное бюджетное учреждение", "гбу"],
    "МБУ":  ["муниципальное бюджетное учреждение", "мбу"],
    "ФГБУ": ["федеральное государственное бюджетное учреждение", "фгбу"],
    "ТОО":  ["товарищество с ограниченной ответственностью", "тоо"],
}

# Кавычки всех видов
_QUOTES_RE = re.compile(r"[\"'`«»“”„‟‘’]")
_MULTISPACE_RE = re.compile(r"\s+")


def _build_opf_patterns() -> list[tuple[re.Pattern, str]]:
    """Регулярки для поиска ОПФ в любом месте строки."""
    patterns: list[tuple[re.Pattern, str]] = []
    for canonical, variants in _OPF_MAP.items():
        # Более длинные варианты первыми, чтобы не перехватить коротким
        for v in sorted(variants, key=len, reverse=True):
            # \b работает и для кириллицы в Python 3 re с флагом UNICODE по умолчанию
            pat = re.compile(rf"(?<![а-яa-z]){re.escape(v)}(?![а-яa-z])", re.IGNORECASE)
            patterns.append((pat, canonical))
    return patterns


_OPF_PATTERNS = _build_opf_patterns()


class OrganizationNormalizer(BaseNormalizer):
    name = "organization"
    title = "Названия организаций"

    def __init__(self, similarity_threshold: int = 86):
        self.threshold = similarity_threshold

    def _extract_opf(self, text: str) -> tuple[str | None, str]:
        """Находим ОПФ и удаляем её из текста, возвращаем (opf, текст без opf)."""
        for pat, canonical in _OPF_PATTERNS:
            m = pat.search(text)
            if m:
                text = pat.sub(" ", text, count=1)
                return canonical, _MULTISPACE_RE.sub(" ", text).strip(" ,-")
        return None, text

    def normalize_value(self, value: str) -> str:
        text = self._clean(value)
        if not text:
            return ""
        # Убираем кавычки
        text = _QUOTES_RE.sub(" ", text)
        text = _MULTISPACE_RE.sub(" ", text).strip(" ,-.")

        opf, body = self._extract_opf(text)
        body = body.strip(" ,-")

        # Капитализация первой буквы тела (не трогаем аббревиатуры/регистр внутри)
        if body:
            body = body[0].upper() + body[1:]

        if opf and body:
            return f'{opf} «{body}»'
        if opf:
            return opf
        return body

    def _compare_key(self, value: str) -> str:
        """Ключ сравнения без ОПФ и кавычек — сравниваем именно по имени."""
        text = self._clean(value).lower()
        text = _QUOTES_RE.sub(" ", text)
        _, body = self._extract_opf(text)
        body = re.sub(r"[^\w\s]", " ", body, flags=re.UNICODE)
        return _MULTISPACE_RE.sub(" ", body).strip()

    def build_candidates(self, values: list[str]) -> list[NormalizationCandidate]:
        cleaned = [self._clean(v) for v in values if self._clean(v)]
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
            # Канонический вид — нормализация самого частого варианта в кластере
            canonical = self.normalize_value(cl["canonical"])
            confidence = 1.0 if len(variants) == 1 else 0.85

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
