"""Нормализатор телефонных номеров.

Алгоритм:
1. Парсинг через google libphonenumber (python-phonenumbers).
2. Если страна не определилась — пробуем как RU.
3. Каноническая форма — E.164 (например, +74951234567).
4. Если есть добавочный (ext/доб/вн), парсим отдельно и добавляем ", доб. N".
5. Группировка по точному совпадению канонического номера — разные номера
   не могут принадлежать одной записи.
"""
from __future__ import annotations

import re
from collections import Counter

import phonenumbers

from .base import BaseNormalizer, NormalizationCandidate


_EXT_RE = re.compile(
    r"(?:доб|внутр|ext|вн|доп)\.?\s*[:№#]?\s*(\d{1,6})",
    re.IGNORECASE,
)


class PhoneNormalizer(BaseNormalizer):
    name = "phone"
    title = "Телефоны"

    def __init__(self, default_region: str = "RU"):
        self.default_region = default_region

    def normalize_value(self, value: str) -> str:
        text = self._clean(value)
        if not text:
            return ""

        # Выделяем добавочный
        ext = None
        ext_match = _EXT_RE.search(text)
        if ext_match:
            ext = ext_match.group(1)
            text = _EXT_RE.sub("", text)

        # Нормализуем префикс 8 -> +7 (только если выглядит как RU-номер)
        digits = re.sub(r"\D+", "", text)
        if len(digits) == 11 and digits.startswith("8"):
            text = "+7" + digits[1:]
        elif len(digits) == 10 and not text.strip().startswith("+"):
            text = "+7" + digits
        elif len(digits) == 11 and digits.startswith("7") and not text.strip().startswith("+"):
            text = "+" + digits

        try:
            parsed = phonenumbers.parse(text, self.default_region)
        except phonenumbers.NumberParseException:
            return re.sub(r"\s+", "", text)

        if not phonenumbers.is_possible_number(parsed):
            return re.sub(r"\s+", "", text)

        canonical = phonenumbers.format_number(
            parsed, phonenumbers.PhoneNumberFormat.E164
        )
        if ext:
            canonical += f", доб. {ext}"
        return canonical

    def _is_valid(self, canonical: str) -> bool:
        number_part = canonical.split(",")[0].strip()
        try:
            parsed = phonenumbers.parse(number_part, self.default_region)
        except phonenumbers.NumberParseException:
            return False
        return phonenumbers.is_valid_number(parsed)

    def build_candidates(self, values: list[str]) -> list[NormalizationCandidate]:
        uniq, counts = self._dedupe_with_counts(values)
        groups: dict[str, dict] = {}

        # Нормализуем каждое уникальное значение один раз, учитывая частоту.
        for v in uniq:
            canonical = self.normalize_value(v)
            if not canonical:
                continue
            freq = counts.get(v, 1)
            g = groups.setdefault(canonical, {"variants": Counter(), "count": 0})
            g["variants"][v] += freq
            g["count"] += freq

        candidates: list[NormalizationCandidate] = []
        for canonical, data in groups.items():
            valid = self._is_valid(canonical)
            confidence = 1.0 if valid else 0.5

            meta = {"valid": valid}
            try:
                parsed = phonenumbers.parse(canonical.split(",")[0], self.default_region)
                meta["country"] = phonenumbers.region_code_for_number(parsed) or "?"
            except Exception:
                meta["country"] = "?"

            candidates.append(
                NormalizationCandidate(
                    canonical=canonical,
                    variants=list(data["variants"].keys()),
                    count=data["count"],
                    confidence=confidence,
                    meta=meta,
                )
            )

        candidates.sort(key=lambda c: (-len(c.variants), -c.count))
        return candidates
