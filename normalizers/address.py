"""Нормализатор адресов.

Алгоритм:
1. Лексическая чистка: убрать кавычки, двойные пробелы, унифицировать разделители.
2. Развернуть сокращения: "г." -> "город", "ул." -> "улица", "д." -> "дом",
   "кв." -> "квартира", "пр-т" -> "проспект" и т.д.
   Расширен список: шоссе ("ш."), проезд ("пр-д"), тупик, аллея,
   линия, дорога, территория ("тер."), влад. ("владение"), этаж ("эт."),
   офис/оф., помещение ("пом."), блок ("бл."), участок ("уч.").
3. Унифицировать индекс (6 цифр) и вынести его в начало.
4. Привести регистр: сохраняем регистр слов, но служебные префиксы в нижнем.
5. Удалить страну "Россия/РФ" (по желанию пользователя — включено по умолчанию).
6. Кластеризация: rapidfuzz token_set_ratio — учитывает перестановки
   (город/улица/дом). Порог 88 по умолчанию.
"""
from __future__ import annotations

import re

from utils.clustering import cluster_by_similarity
from .base import BaseNormalizer, NormalizationCandidate


# Словарь сокращений -> полная форма.
#
# Границы слов в Python re не работают корректно на стыке точка/кириллица,
# поэтому используем явные lookaround'ы:
#   (?<![а-яёА-ЯЁa-zA-Z]) — перед сокращением нет буквы
#   (?![а-яёА-ЯЁa-zA-Z])     — после сокращения тоже нет
# Точка включается в матч, чтобы не оставаться в выводе.

_LB = r"(?<![а-яёА-ЯЁa-zA-Z])"   # left boundary
_RB = r"(?![а-яёА-ЯЁa-zA-Z])"    # right boundary

_ABBREV = [
    # Сначала длинные сокращения, чтобы не были съедены короткими.
    (rf"{_LB}п\.?\s*г\.?\s*т\.?{_RB}", "пгт"),
    (rf"{_LB}пр-?т\.?{_RB}", "проспект"),
    (rf"{_LB}просп\.?{_RB}", "проспект"),
    (rf"{_LB}пр-?д\.?{_RB}", "проезд"),        # пр-д, прд.
    (rf"{_LB}б-?р\.?{_RB}", "бульвар"),
    (rf"{_LB}бул\.?{_RB}", "бульвар"),
    (rf"{_LB}р-?н{_RB}", "район"),
    (rf"{_LB}мкр\.?{_RB}", "микрорайон"),
    (rf"{_LB}м-?он\.?{_RB}", "микрорайон"),     # альтернативное сокр.
    (rf"{_LB}корп\.?{_RB}", "корпус"),
    (rf"{_LB}стр\.?{_RB}", "строение"),
    (rf"{_LB}обл\.?{_RB}", "область"),
    (rf"{_LB}республ?\.?{_RB}", "республика"),
    (rf"{_LB}гор\.?{_RB}", "город"),
    (rf"{_LB}пос\.?{_RB}", "посёлок"),
    (rf"{_LB}наб\.?{_RB}", "набережная"),
    (rf"{_LB}пер\.?{_RB}", "переулок"),
    (rf"{_LB}дом\.?{_RB}", "дом"),
    (rf"{_LB}ул\.?{_RB}", "улица"),
    (rf"{_LB}пл\.?{_RB}", "площадь"),
    (rf"{_LB}ш\.?{_RB}", "шоссе"),              # ш. (шоссе)
    (rf"{_LB}ал\.?{_RB}", "аллея"),             # ал.
    (rf"{_LB}лин\.?{_RB}", "линия"),            # лин.
    (rf"{_LB}дор\.?{_RB}", "дорога"),           # дор.
    (rf"{_LB}туп\.?{_RB}", "тупик"),            # туп.
    (rf"{_LB}тер\.?{_RB}", "территория"),       # тер.
    (rf"{_LB}пом\.?{_RB}", "помещение"),        # пом.
    (rf"{_LB}влад\.?{_RB}", "владение"),        # влад.
    (rf"{_LB}эт\.?{_RB}", "этаж"),              # эт.
    (rf"{_LB}бл\.?{_RB}", "блок"),              # бл.
    (rf"{_LB}уч\.?{_RB}", "участок"),           # уч.
    (rf"{_LB}кв\.?", "квартира "),   # за кв. часто стоит цифра без пробела
    (rf"{_LB}оф\.?{_RB}", "офис"),
    (rf"{_LB}лит\.?{_RB}", "литера"),
    # Однобуквенные — только в контексте цифры или явной границы
    (rf"{_LB}д\.?\s*(?=\d)", "дом "),
    (rf"{_LB}к\.?\s*(?=\d)", "корпус "),
    # "г." разворачиваем в "город" только когда следует точка/пробел
    # и дальше кириллическое слово — чтобы не трогать "Санкт".
    (rf"{_LB}г\.\s*(?=[А-ЯЁ])", "город "),
    (rf"{_LB}г\s+(?=[А-ЯЁ])", "город "),
    # "с." для села — только с точкой и после — заглавная буква.
    (rf"{_LB}с\.\s*(?=[А-ЯЁ])", "село "),
]

_COUNTRY_RE = re.compile(r"\b(россия|российская\s+федерация|рф)\b,?\s*", re.IGNORECASE)
_INDEX_RE = re.compile(r"\b(\d{6})\b")
_MULTISPACE_RE = re.compile(r"\s+")
_PUNCT_EDGES_RE = re.compile(r"\s*,\s*")

# Служебные слова, которые исключаются из ключа сравнения
_SERVICE_WORDS_RE = re.compile(
    r"\b(город|улица|дом|квартира|проспект|переулок|площадь|бульвар|"
    r"шоссе|набережная|микрорайон|район|область|республика|строение|"
    r"корпус|офис|литера|село|посёлок|пгт|проезд|тупик|аллея|линия|"
    r"дорога|территория|владение|этаж|блок|участок|помещение)\b"
)


class AddressNormalizer(BaseNormalizer):
    name = "address"
    title = "Адреса"

    def __init__(self, drop_country: bool = True, similarity_threshold: int = 88):
        self.drop_country = drop_country
        self.threshold = similarity_threshold

    def normalize_value(self, value: str) -> str:
        text = self._clean(value)
        text = text.replace("ё", "е").replace("Ё", "Е")

        # Выделяем индекс отдельно, чтобы он всегда был в начале
        index_match = _INDEX_RE.search(text)
        index = index_match.group(1) if index_match else ""
        if index:
            text = _INDEX_RE.sub("", text, count=1)

        # Страна
        if self.drop_country:
            text = _COUNTRY_RE.sub("", text)

        # Разворачиваем сокращения до приведения к нижнему регистру,
        # чтобы lookahead'ы на Заглавную букву работали для "г. Москва".
        for pattern, replacement in _ABBREV:
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

        text = text.lower()

        # Разделители
        text = _PUNCT_EDGES_RE.sub(", ", text)
        text = _MULTISPACE_RE.sub(" ", text).strip(" ,")

        # Убираем повторяющиеся запятые
        while ",," in text:
            text = text.replace(",,", ",")

        if index:
            text = f"{index}, {text}" if text else index

        # Капитализация каждого компонента через запятую
        def _cap_part(p: str) -> str:
            p = p.strip()
            if not p:
                return p
            tokens = p.split(" ")
            out = []
            for t in tokens:
                if t.isdigit() or re.match(r"^\d", t):
                    out.append(t)
                elif "-" in t:
                    out.append("-".join(
                        (w[:1].upper() + w[1:]) if w else w for w in t.split("-")
                    ))
                else:
                    out.append(t[:1].upper() + t[1:])
            return " ".join(out)

        text = ", ".join(_cap_part(p) for p in text.split(",") if p.strip())
        return text

    def _compare_key(self, value: str) -> str:
        """Ключ для fuzzy-сравнения: тот же нормализованный текст, но
        с выкинутыми служебными словами — для устойчивости к формулировкам."""
        s = self.normalize_value(value)
        s = _SERVICE_WORDS_RE.sub("", s)
        s = _MULTISPACE_RE.sub(" ", s).strip(" ,")
        return s

    def _compare_key_cached(self, value: str, _cache: dict = {}) -> str:
        # Кэш внутри экземпляра не нужен — key_cache в cluster_by_similarity
        # уже захватывает повторы. Метод оставлен для совместимости.
        return self._compare_key(value)

    def build_candidates(self, values: list[str]) -> list[NormalizationCandidate]:
        uniq, counts = self._dedupe_with_counts(values)
        if not uniq:
            return []

        # Пред-нормализуем каждое уникальное значение один раз и кэшируем
        # ключ сравнения — это самый дорогой шаг.
        norm_cache: dict[str, str] = {}
        key_cache: dict[str, str] = {}
        for v in uniq:
            norm = self.normalize_value(v)
            norm_cache[v] = norm
            key_cache[v] = self._key_from_normalized(norm)

        clusters = cluster_by_similarity(
            uniq,
            key_fn=lambda v: key_cache.get(v, ""),
            threshold=self.threshold,
            counts=counts,
        )

        candidates: list[NormalizationCandidate] = []
        for cl in clusters:
            variants = list(cl["variants"].keys())
            canonical = norm_cache.get(cl["canonical"]) or self.normalize_value(cl["canonical"])
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

    def _key_from_normalized(self, normalized: str) -> str:
        """Ключ сравнения из уже нормализованного текста — без повторного
        вызова normalize_value (экономия больших regex)."""
        s = _SERVICE_WORDS_RE.sub("", normalized.lower())
        return _MULTISPACE_RE.sub(" ", s).strip(" ,")
