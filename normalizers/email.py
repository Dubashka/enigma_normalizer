"""Нормализатор email-адресов.

Алгоритм:
1. Чистка: убираем пробелы, невидимые символы, обёртки вида "<...>", "mailto:".
2. Приведение к нижнему регистру (email case-insensitive по RFC 5321 в части
   домена; локальная часть формально case-sensitive, но на практике все
   крупные провайдеры её не различают).
3. Проверка формата через regex + IDN-домены.
4. Для некоторых провайдеров — применение их правил дедубликации:
   - Gmail: убираются точки в локальной части и всё после "+" (алиасы).
     "John.Doe+promo@gmail.com" == "johndoe@gmail.com".
   - Яндекс: домены yandex.ru/ya.ru/yandex.com — один и тот же ящик;
     в локальной части "." и "-" эквивалентны "_".
   - Outlook/Hotmail/Live: всё после "+" — алиас.
5. Группировка по точному совпадению канонического вида.
"""
from __future__ import annotations

import re
from collections import Counter

from .base import BaseNormalizer, NormalizationCandidate


# RFC 5322-совместимая «достаточная» проверка (не строгая, но покрывает 99%)
_EMAIL_RE = re.compile(
    r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$"
)

_MAILTO_RE = re.compile(r"^mailto:", re.IGNORECASE)
_WRAP_RE = re.compile(r"^<(.+)>$")

# Эквивалентные домены — нормализуем к первому в списке.
_DOMAIN_ALIASES = {
    "yandex.ru": "yandex.ru",
    "ya.ru": "yandex.ru",
    "yandex.com": "yandex.ru",
    "yandex.by": "yandex.ru",
    "yandex.kz": "yandex.ru",
    "yandex.ua": "yandex.ru",
    "googlemail.com": "gmail.com",
    "gmail.com": "gmail.com",
    "hotmail.com": "outlook.com",
    "live.com": "outlook.com",
    "outlook.com": "outlook.com",
    "msn.com": "outlook.com",
}


class EmailNormalizer(BaseNormalizer):
    name = "email"
    title = "Email"

    def _pre_clean(self, value: str) -> str:
        text = self._clean(value)
        text = text.replace("\u200b", "").replace("\ufeff", "")
        # "John Doe <john@example.com>" -> "john@example.com"
        m = re.search(r"<([^>]+@[^>]+)>", text)
        if m:
            text = m.group(1)
        # mailto:
        text = _MAILTO_RE.sub("", text)
        # Уберём обрамляющие скобки/кавычки
        text = text.strip("\"'()[]<> ,;")
        return text

    def normalize_value(self, value: str) -> str:
        text = self._pre_clean(value)
        if not text or "@" not in text:
            return text.lower() if text else ""

        # Разделим на локальную часть и домен
        local, _, domain = text.rpartition("@")
        local = local.strip().lower()
        domain = domain.strip().lower().strip(".")

        # IDN-домены (кириллические и т.п.) — оставим как есть в lower
        # (полноценная IDNA-нормализация не требуется для задачи дедубликации).

        # Приведение домена по алиасам
        canonical_domain = _DOMAIN_ALIASES.get(domain, domain)

        # Правила локальной части по провайдеру
        if canonical_domain == "gmail.com":
            local = local.split("+", 1)[0]
            local = local.replace(".", "")
        elif canonical_domain == "yandex.ru":
            local = local.split("+", 1)[0]
            # В Яндексе "." и "-" эквивалентны "_"
            local = local.replace(".", "-")
        elif canonical_domain == "outlook.com":
            local = local.split("+", 1)[0]

        if not local or not canonical_domain:
            return text.lower()

        return f"{local}@{canonical_domain}"

    def _is_valid(self, canonical: str) -> bool:
        return bool(_EMAIL_RE.match(canonical))

    def build_candidates(self, values: list[str]) -> list[NormalizationCandidate]:
        cleaned = [self._pre_clean(v) for v in values if self._pre_clean(v)]
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
            valid = self._is_valid(canonical)
            confidence = 1.0 if valid else 0.4

            meta = {
                "valid_format": valid,
                "domain": canonical.rpartition("@")[2] if "@" in canonical else "",
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

        candidates.sort(key=lambda c: (-len(c.variants), -c.count))
        return candidates
