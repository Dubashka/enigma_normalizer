"""Нормализатор ФИО.

Алгоритм:
1. Чистка: убираем лишние пробелы, служебные символы, кавычки.
2. Приведение к Title Case (кроме инициалов).
3. Если видим паттерн "Фамилия И. О." / "И. О. Фамилия" — парсим вручную.
4. Иначе — пытаемся использовать natasha.NamesExtractor. Если natasha
   недоступна (например, из-за окружения без pkg_resources) — fallback
   на эвристику по порядку слов и окончаниям отчеств.
5. Лемматизация каждой части в именительный падеж (pymorphy3).
6. Капитализация: двойные фамилии с дефисом — обе части с заглавной.
7. Кластеризация: группируем по нормализованному виду, а затем объединяем
   полное ФИО с его инициальной формой (ключ: Фамилия + инициалы).
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Optional

import pymorphy3

from .base import BaseNormalizer, NormalizationCandidate


# Natasha опциональна — если окружение не позволяет её загрузить,
# работаем на pymorphy3 + собственных эвристиках.
try:
    from natasha import MorphVocab, NamesExtractor  # type: ignore
    _NATASHA_AVAILABLE = True
except Exception:
    MorphVocab = None  # type: ignore
    NamesExtractor = None  # type: ignore
    _NATASHA_AVAILABLE = False


_PUNCT_RE = re.compile(r"[\"'`«»\(\)\[\]]")
_SEP_RE = re.compile(r"[,;]+")
_INITIAL_RE = re.compile(r"^[А-ЯЁA-Z]\.?$")


_morph_vocab = None
_names_extractor = None
_pymorph: Optional[pymorphy3.MorphAnalyzer] = None


def _get_pymorph() -> pymorphy3.MorphAnalyzer:
    global _pymorph
    if _pymorph is None:
        _pymorph = pymorphy3.MorphAnalyzer()
    return _pymorph


def _get_names_extractor():
    """Ленивый NamesExtractor natasha; None, если natasha недоступна."""
    global _morph_vocab, _names_extractor
    if not _NATASHA_AVAILABLE:
        return None
    if _names_extractor is None:
        try:
            _morph_vocab = MorphVocab()
            _names_extractor = NamesExtractor(_morph_vocab)
        except Exception:
            return None
    return _names_extractor


def _capitalize_part(part: str) -> str:
    """Капитализация с поддержкой двойных фамилий и приставок."""
    if not part:
        return part
    tokens = re.split(r"([\- ])", part.lower())
    out = []
    for tok in tokens:
        if tok in ("-", " ") or not tok:
            out.append(tok)
        else:
            out.append(tok[0].upper() + tok[1:])
    return "".join(out)


def _lemma_nom(word: str, gram: str | None = None, gender: str | None = None) -> str:
    """Лемматизация слова в именительный падеж с учётом рода."""
    morph = _get_pymorph()
    parses = morph.parse(word)
    if not parses:
        return word

    target = {"nomn"}
    if gender in ("femn", "masc"):
        target.add(gender)

    if gram:
        for p in parses:
            if gram in p.tag:
                inflected = p.inflect(target)
                if inflected:
                    return inflected.word
    p = parses[0]
    inflected = p.inflect(target)
    return inflected.word if inflected else p.normal_form


def _detect_gender_from_middle(middle: str | None) -> str | None:
    """Определяем пол по отчеству. Надёжнее, чем по имени."""
    if not middle:
        return None
    m = middle.lower()
    if m.endswith(("вич", "ьич")):
        return "masc"
    if m.endswith(("вна", "ична", "инична")):
        return "femn"
    return None


def _detect_gender_from_first(first: str | None) -> str | None:
    """Определяем пол по полному имени через pymorphy3."""
    if not first or len(first) <= 1:
        return None
    morph = _get_pymorph()
    for p in morph.parse(first):
        if "Name" in p.tag:
            if "femn" in p.tag:
                return "femn"
            if "masc" in p.tag:
                return "masc"
    return None


def _is_patronymic(word: str) -> bool:
    w = word.lower()
    return w.endswith(("вич", "ьич", "вна", "ична", "инична"))


class PersonNormalizer(BaseNormalizer):
    name = "fio"
    title = "ФИО"

    def normalize_value(self, value: str) -> str:
        text = self._clean(value)
        text = _PUNCT_RE.sub("", text)
        text = _SEP_RE.sub(" ", text)
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            return ""

        # Нормализуем инициалы: "И.И." -> "И. И."
        text = re.sub(r"([А-ЯЁA-Z])\.\s*([А-ЯЁA-Z])\.", r"\1. \2.", text)

        # Приведение к Title Case, кроме инициалов
        def _title_token(tok: str) -> str:
            if _INITIAL_RE.match(tok):
                return tok.upper()
            parts = re.split(r"([\- ])", tok.lower())
            out = []
            for p in parts:
                if p in ("-", " ") or not p:
                    out.append(p)
                else:
                    out.append(p[0].upper() + p[1:])
            return "".join(out)

        text_titled = " ".join(_title_token(t) for t in text.split())
        tokens = text_titled.split()

        initials = [t for t in tokens if _INITIAL_RE.match(t)]
        non_initials = [t for t in tokens if not _INITIAL_RE.match(t)]

        surname = first = middle = None

        # Короткая форма: Фамилия + 1-2 инициала (в любом порядке).
        # Фамилию здесь не лемматизируем — она уже в именительном;
        # pymorphy3 без отчества может неверно определить пол ("Петрова" → "Петров").
        short_form = False
        if initials and len(non_initials) == 1:
            surname = non_initials[0]
            if len(initials) >= 1:
                first = initials[0].rstrip(".")
            if len(initials) >= 2:
                middle = initials[1].rstrip(".")
            short_form = True
        else:
            # Полная форма — natasha, если доступна
            extractor = _get_names_extractor()
            if extractor is not None:
                try:
                    matches = list(extractor(text_titled))
                    if matches:
                        fact = matches[0].fact
                        surname = fact.last
                        first = fact.first
                        middle = fact.middle
                except Exception:
                    pass

            # Fallback: эвристика по порядку слов
            if not (surname or first or middle):
                surname, first, middle = self._fallback_parse(tokens)

        # Определяем пол — сначала по отчеству (надёжнее), потом по имени.
        # Это нужно, чтобы pymorphy3 не превращал "Петрова" в "Петров".
        gender = _detect_gender_from_middle(middle) or _detect_gender_from_first(first)

        parts: list[str] = []
        if surname:
            if short_form:
                # В форме "Фамилия И.О." фамилия уже в именительном —
                # просто капитализируем.
                parts.append(_capitalize_part(surname))
            else:
                parts.append(_capitalize_part(_lemma_nom(surname, "Surn", gender)))
        if first:
            parts.append(self._format_name_piece(first, gender))
        if middle:
            parts.append(self._format_name_piece(middle, gender))

        return " ".join(p for p in parts if p).strip()

    def _format_name_piece(self, piece: str, gender: str | None = None) -> str:
        piece = piece.strip().rstrip(".")
        if not piece:
            return ""
        if len(piece) == 1:
            return f"{piece.upper()}."
        return _capitalize_part(_lemma_nom(piece, gender=gender))

    def _fallback_parse(self, tokens: list[str]) -> tuple[str | None, str | None, str | None]:
        words = [t.rstrip(".") for t in tokens if t]
        if not words:
            return None, None, None

        surname = first = middle = None
        if len(words) == 3:
            if _is_patronymic(words[2]):
                surname, first, middle = words[0], words[1], words[2]
            elif _is_patronymic(words[1]):
                first, middle, surname = words[0], words[1], words[2]
            else:
                surname, first, middle = words[0], words[1], words[2]
        elif len(words) == 2:
            surname, first = words[0], words[1]
        elif len(words) == 1:
            surname = words[0]
        return surname, first, middle

    # ------------------------------------------------------------------

    def build_candidates(self, values: list[str]) -> list[NormalizationCandidate]:
        """Группируем ФИО: по нормализованному виду + объединяем полное ФИО
        с его инициальной формой."""
        cleaned = [v for v in (self._clean(x) for x in values) if v]
        if not cleaned:
            return []

        groups: dict[str, dict] = {}
        for v in cleaned:
            try:
                canonical = self.normalize_value(v)
            except Exception:
                canonical = v
            if not canonical:
                continue
            g = groups.setdefault(canonical, {"variants": Counter(), "count": 0})
            g["variants"][v] += 1
            g["count"] += 1

        # Ключ слияния: Фамилия + первые буквы имени и отчества.
        def short_key(canonical: str) -> str | None:
            parts = canonical.split()
            if not parts:
                return None
            surname = parts[0].lower()
            initials = "".join(
                p[0].lower() for p in parts[1:] if p and p[0].isalpha()
            )
            return f"{surname}|{initials}" if initials else surname

        # Идём сначала от длинных к коротким, чтобы canonical был максимально
        # развёрнутой формой.
        merged: dict[str, dict] = {}
        for canonical in sorted(groups.keys(), key=lambda c: -len(c)):
            k = short_key(canonical)
            if not k:
                continue
            if k in merged:
                merged[k]["variants"].update(groups[canonical]["variants"])
                merged[k]["count"] += groups[canonical]["count"]
            else:
                merged[k] = {
                    "canonical": canonical,
                    "variants": groups[canonical]["variants"].copy(),
                    "count": groups[canonical]["count"],
                }

        candidates: list[NormalizationCandidate] = []
        for data in merged.values():
            variants = list(data["variants"].keys())
            confidence = 1.0 if len(variants) == 1 else 0.9
            candidates.append(
                NormalizationCandidate(
                    canonical=data["canonical"],
                    variants=variants,
                    count=data["count"],
                    confidence=confidence,
                    meta={"variant_counts": dict(data["variants"])},
                )
            )

        candidates.sort(key=lambda c: (-len(c.variants), -c.count))
        return candidates
