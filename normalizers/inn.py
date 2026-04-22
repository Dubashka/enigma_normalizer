"""Нормализатор ИНН.

Алгоритм:
1. Оставляем только цифры.
2. Проверяем длину: 10 (ЮЛ) или 12 (ФЛ/ИП).
3. Проверяем контрольную сумму по правилам ФНС.
4. Группируем по точному совпадению — fuzzy здесь недопустим (один символ
   меняет субъект).
5. В кандидатах видно, какие исходные записи разошлись по формату
   (например, "7707083893", "ИНН: 7707083893", "7707-083-893").
"""
from __future__ import annotations

import re
from collections import Counter

from .base import BaseNormalizer, NormalizationCandidate


_DIGITS_RE = re.compile(r"\D+")


def _check_inn_10(digits: str) -> bool:
    if len(digits) != 10 or not digits.isdigit():
        return False
    coef = [2, 4, 10, 3, 5, 9, 4, 6, 8, 0]
    s = sum(int(d) * c for d, c in zip(digits, coef))
    control = s % 11 % 10
    return control == int(digits[-1])


def _check_inn_12(digits: str) -> bool:
    if len(digits) != 12 or not digits.isdigit():
        return False
    coef1 = [7, 2, 4, 10, 3, 5, 9, 4, 6, 8, 0]
    coef2 = [3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8, 0]
    n11 = sum(int(digits[i]) * coef1[i] for i in range(11)) % 11 % 10
    n12 = sum(int(digits[i]) * coef2[i] for i in range(12)) % 11 % 10
    return n11 == int(digits[10]) and n12 == int(digits[11])


def is_valid_inn(digits: str) -> bool:
    if len(digits) == 10:
        return _check_inn_10(digits)
    if len(digits) == 12:
        return _check_inn_12(digits)
    return False


class InnNormalizer(BaseNormalizer):
    name = "inn"
    title = "ИНН"

    def normalize_value(self, value: str) -> str:
        text = self._clean(value)
        digits = _DIGITS_RE.sub("", text)
        if len(digits) in (10, 12):
            return digits
        return digits  # возвращаем как есть, валидность проверим отдельно

    def build_candidates(self, values: list[str]) -> list[NormalizationCandidate]:
        cleaned = [self._clean(v) for v in values if self._clean(v)]
        groups: dict[str, dict] = {}

        for v in cleaned:
            canonical = self.normalize_value(v)
            if not canonical:
                continue
            g = groups.setdefault(canonical, {"variants": Counter(), "count": 0})
            g["variants"][v] += 1
            g["count"] += 1

        candidates: list[NormalizationCandidate] = []
        for canonical, data in groups.items():
            valid = is_valid_inn(canonical)
            length_ok = len(canonical) in (10, 12)
            confidence = 1.0 if valid else (0.6 if length_ok else 0.2)

            meta = {
                "valid_checksum": valid,
                "length": len(canonical),
                "type": "ЮЛ" if len(canonical) == 10 else ("ФЛ/ИП" if len(canonical) == 12 else "некорректный"),
            }

            candidates.append(
                NormalizationCandidate(
                    canonical=canonical,
                    variants=list(data["variants"].keys()),
                    count=data["count"],
                    confidence=confidence,
                    meta=meta,
                )
            )

        # Сначала — с расхождением в вариантах, потом по частоте
        candidates.sort(key=lambda c: (-len(c.variants), -c.count))
        return candidates
