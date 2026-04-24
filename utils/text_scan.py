"""Поиск PII-сущностей в свободном тексте документа.

Для каждой поддерживаемой категории данных определяется набор regex-паттернов
(или комбинация паттерн + валидатор). По результату поиска возвращается
список `TextMatch` — каждое совпадение содержит:

  * тип данных (`fio`, `inn`, `phone`, `email`, `address`, `organization`);
  * исходный текст;
  * абсолютные offset'ы в полном тексте документа;
  * номер chunk'а и offset внутри него (для точечной замены).

После этого значения группируются по типу — и на каждую группу запускается
штатный нормализатор из `normalizers/` так же, как для excel-колонки.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from .text_extract import ExtractedDocument, TextChunk


@dataclass
class TextMatch:
    """Одно PII-вхождение в тексте."""

    data_type: str          # fio | inn | phone | email | address | organization
    value: str              # исходная подстрока (как в документе)
    chunk_idx: int          # номер chunk'а
    start: int              # offset от начала chunk'а
    end: int                # offset конца в chunk'е


# ---------------------------------------------------------------------------
# Регулярные выражения для каждого типа. Используются существующие правила из
# utils/detect.py + дополнения для свободного текста (нужны другие якоря).
# ---------------------------------------------------------------------------

# Email — стандартный
_EMAIL_RE = re.compile(
    r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"
)

# Телефоны РФ: +7/8, опциональные скобки и дефисы. Длина 11 цифр.
_PHONE_RE = re.compile(
    r"(?<![\d])"
    r"(?:\+?7|8)\s*[\-\(]?\s*\d{3}\s*[\-\)]?\s*\d{3}\s*[\-]?\s*\d{2}\s*[\-]?\s*\d{2}"
    r"(?![\d])"
)

# ИНН: 10 или 12 цифр, иногда с префиксом "ИНН". Ставим отдельно, чтобы не
# перехватывать телефонные номера (у них 11 цифр).
_INN_RE = re.compile(
    r"(?:ИНН[:\s]*)?(?<!\d)(\d{10}|\d{12})(?!\d)",
    re.IGNORECASE,
)

# ФИО: отчество как якорь в полной форме (во избежание ложных срабатываний),
# либо фамилия + инициалы.
# Отчества: заканчиваются на -вич/-ьич/-вна/-ична/-инична и пр.
_FIO_FULL_RE = re.compile(
    r"\b[А-ЯЁ][а-яё]{1,}(?:-[А-ЯЁ][а-яё]{1,})?"
    r"\s+[А-ЯЁ][а-яё]{1,}"
    r"\s+[А-ЯЁ][а-яё]+(?:вич|ьич|вна|ична|инична|ович|евич|овна|евна|ыч)\b"
)
_FIO_INITIALS_RE = re.compile(
    r"\b[А-ЯЁ][а-яё]{1,}(?:-[А-ЯЁ][а-яё]{1,})?"
    r"\s+[А-ЯЁ]\.\s*[А-ЯЁ]\.?"
    r"|\b[А-ЯЁ]\.\s*[А-ЯЁ]\.\s*[А-ЯЁ][а-яё]{1,}"
)

# Организации: ОПФ + название в кавычках/без (до конца предложения или кавычек)
_ORG_RE = re.compile(
    r"\b(?:ООО|ОАО|ЗАО|ПАО|НАО|АО|ИП|ГК|НКО|ФГУП|МУП|ГБОУ|ГБУ|МБУ|ФГБУ)"
    r"\s+[«\"]?[^«\"»\n.;,]{2,80}[»\"]?"
)

# Адреса: начинается с маркера (г./ул./пр-т/индекс и т.п.) и дотягивается
# до номера дома/квартиры или конца предложения. Нарочно взято
# жадно — потом обрезаем лишнее в _iter_matches.
_ADDRESS_RE = re.compile(
    r"(?:\b\d{6}\s*,\s*)?"
    r"(?:\bг\.?\s|\bгород\s|\bобл\.?\s|\bобласть\b|\bресп\.?\s|\bреспублика\b|"
    r"\bкрай\b|\bул\.?\s|\bулица\s|\bпр-?т\s|\bпроспект\s|"
    r"\bпер\.?\s|\bпереулок\s|\bш\.?\s|\bшоссе\s|"
    r"\bнаб\.?\s|\bнабережная\s|\bб-?р\s|\bбульвар\s|"
    r"\bпл\.?\s|\bплощадь\s|\bд\.?\s\d|\bдом\s*\d)"
    r"[^\n;]{2,250}?"
    r"(?:\b(?:д\.|дом)\s*\d+[а-яА-Я]?(?:\s*[корп]\.?\s*\d+)?(?:\s*кв\.?\s*\d+)?"
    r"|\bкв\.?\s*\d+"
    r"|\d{6}"
    r"|(?=\.\s|\n|$))",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Валидаторы (повторное использование минимального набора из detect.py)
# ---------------------------------------------------------------------------

def _valid_inn(digits: str) -> bool:
    """Контрольная сумма ИНН по правилам ФНС."""
    if len(digits) == 10:
        coefs = [2, 4, 10, 3, 5, 9, 4, 6, 8]
        s = sum(int(digits[i]) * coefs[i] for i in range(9))
        return (s % 11) % 10 == int(digits[9])
    if len(digits) == 12:
        c1 = [7, 2, 4, 10, 3, 5, 9, 4, 6, 8]
        c2 = [3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8]
        s1 = sum(int(digits[i]) * c1[i] for i in range(10))
        s2 = sum(int(digits[i]) * c2[i] for i in range(11))
        return (s1 % 11) % 10 == int(digits[10]) and (s2 % 11) % 10 == int(digits[11])
    return False


def _valid_phone(raw: str) -> bool:
    digits = re.sub(r"\D", "", raw)
    return len(digits) == 11 and digits[0] in ("7", "8")


# ---------------------------------------------------------------------------
# Основной сканер
# ---------------------------------------------------------------------------

def _iter_matches(text: str) -> list[tuple[str, str, int, int]]:
    """Найти все PII в одной строке. Возвращает (type, value, start, end)."""
    found: list[tuple[str, str, int, int]] = []

    # Email — самый однозначный, сначала
    for m in _EMAIL_RE.finditer(text):
        found.append(("email", m.group(0), m.start(), m.end()))

    # Телефоны
    for m in _PHONE_RE.finditer(text):
        if _valid_phone(m.group(0)):
            found.append(("phone", m.group(0).strip(), m.start(), m.end()))

    # ИНН — строгая валидация по КС
    for m in _INN_RE.finditer(text):
        digits = m.group(1)
        if _valid_inn(digits):
            found.append(("inn", digits, m.start(1), m.end(1)))

    # Адреса
    for m in _ADDRESS_RE.finditer(text):
        value = m.group(0).strip().rstrip(",;")
        if len(value) >= 6:
            found.append(("address", value, m.start(), m.start() + len(value)))

    # Организации
    for m in _ORG_RE.finditer(text):
        value = m.group(0).strip().rstrip(",.;")
        found.append(("organization", value, m.start(), m.start() + len(value)))

    # ФИО — оба варианта
    for m in _FIO_FULL_RE.finditer(text):
        found.append(("fio", m.group(0), m.start(), m.end()))
    for m in _FIO_INITIALS_RE.finditer(text):
        found.append(("fio", m.group(0), m.start(), m.end()))

    # Убираем пересечения: email важнее телефона/ИНН, адрес важнее организации,
    # длинное ФИО важнее инициалов. Стратегия: сортируем по приоритету типа,
    # затем по длине (убыванию) и выбрасываем пересекающиеся.
    priority = {"email": 0, "phone": 1, "inn": 2, "address": 3,
                "organization": 4, "fio": 5}
    found.sort(key=lambda x: (priority[x[0]], -(x[3] - x[2])))

    accepted: list[tuple[str, str, int, int]] = []
    for item in found:
        _, _, s, e = item
        overlap = any(not (e <= a_s or s >= a_e) for _, _, a_s, a_e in accepted)
        if not overlap:
            accepted.append(item)

    accepted.sort(key=lambda x: x[2])  # по позиции в тексте
    return accepted


def scan_text_document(doc: ExtractedDocument) -> list[TextMatch]:
    """Пройти все chunk'и и вернуть все PII-вхождения."""
    matches: list[TextMatch] = []
    for chunk in doc.chunks:
        if not chunk.text:
            continue
        for data_type, value, start, end in _iter_matches(chunk.text):
            matches.append(TextMatch(
                data_type=data_type,
                value=value,
                chunk_idx=chunk.idx,
                start=start,
                end=end,
            ))
    return matches


def group_by_type(matches: Iterable[TextMatch]) -> dict[str, list[str]]:
    """Сгруппировать значения по типу (для подачи в нормализаторы).

    Возвращает словарь {data_type: [value, ...]} — с повторениями, чтобы
    нормализаторы видели частотность.
    """
    groups: dict[str, list[str]] = {}
    for m in matches:
        groups.setdefault(m.data_type, []).append(m.value)
    return groups


# ---------------------------------------------------------------------------
# Замена в тексте
# ---------------------------------------------------------------------------

def apply_replacements(
    doc: ExtractedDocument,
    matches: list[TextMatch],
    mapping: dict[str, dict[str, str]],
) -> tuple[dict[int, str], int]:
    """Применить нормализованные значения к chunk'ам документа.

    Args:
        doc: исходный документ.
        matches: найденные PII.
        mapping: {data_type: {original_value: canonical_value}}.

    Returns:
        (replaced_chunks, changed_count)
        replaced_chunks — {chunk_idx: новый текст}.
    """
    # Группируем совпадения по chunk'ам, сортируем по началу в обратном порядке,
    # чтобы offset'ы не ломались при последовательных заменах.
    per_chunk: dict[int, list[TextMatch]] = {}
    for m in matches:
        per_chunk.setdefault(m.chunk_idx, []).append(m)

    chunk_by_idx = {c.idx: c for c in doc.chunks}
    replaced: dict[int, str] = {}
    changed = 0

    for idx, chunk_matches in per_chunk.items():
        chunk = chunk_by_idx.get(idx)
        if chunk is None:
            continue
        text = chunk.text
        # Сортируем по убыванию старта
        chunk_matches.sort(key=lambda m: m.start, reverse=True)
        new_text = text
        changed_in_chunk = False
        for m in chunk_matches:
            canonical = mapping.get(m.data_type, {}).get(m.value)
            if canonical is None or canonical == m.value:
                continue
            new_text = new_text[:m.start] + canonical + new_text[m.end:]
            changed_in_chunk = True
            changed += 1
        if changed_in_chunk:
            replaced[idx] = new_text

    return replaced, changed
