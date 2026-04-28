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

Двухпроходный поиск организаций
---------------------------------
Первый проход (_ORG_FULL_RE) находит полные упоминания с ОПФ:
  «ООО «Рексофт»», «АО Ромашка», «ФГУП Почта России» и т.п.
После первого прохода строим словарь alias_bodies — множество «голых» имён
(тело без ОПФ и кавычек). Второй проход (_ORG_SHORT_RE) ищет эти имена как
отдельные токены. Это позволяет поймать «Рексофт» после того как ранее
встречалось «ООО «Рексофт»».
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
# Регулярные выражения для каждого типа.
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

# ---------------------------------------------------------------------------
# Организации — ДВУХПРОХОДНЫЙ поиск
# ---------------------------------------------------------------------------

# Проход 1: полное упоминание с обязательным ОПФ + название (в кавычках/без).
_ORG_FULL_RE = re.compile(
    r"\b(?:ООО|ОАО|ЗАО|ПАО|НАО|АО|ИП|ГК|НКО|ФГУП|МУП|ГБОУ|ГБУ|МБУ|ФГБУ|ТОО)"
    r"\s+[«\"]?[^«\"»\n.;,]{2,80}[»\"]?",
    re.IGNORECASE,
)

# Вспомогательный: убираем ОПФ и кавычки, получаем «тело» названия.
_STRIP_OPF_RE = re.compile(
    r"^(?:ООО|ОАО|ЗАО|ПАО|НАО|АО|ИП|ГК|НКО|ФГУП|МУП|ГБОУ|ГБУ|МБУ|ФГБУ|ТОО)\s*",
    re.IGNORECASE,
)
_STRIP_QUOTES_RE = re.compile(r"[«»\"'`\u201c\u201d\u2018\u2019]")
_MULTISPACE_RE = re.compile(r"\s+")


def _extract_org_body(full_match: str) -> str:
    """Из «ООО «Рексофт»» извлечь «Рексофт» — для alias-поиска."""
    body = _STRIP_OPF_RE.sub("", full_match)
    body = _STRIP_QUOTES_RE.sub("", body)
    return _MULTISPACE_RE.sub(" ", body).strip(" ,-")


def _build_short_org_re(bodies: set[str]) -> re.Pattern | None:
    """Построить regex для поиска «голых» тел организаций в тексте.

    Тело должно стоять на границе слова и НЕ быть непосредственно после ОПФ
    (чтобы не дублировать уже найденное полное совпадение).
    Слова короче 3 символов пропускаем — слишком высок риск ложных срабатываний.
    """
    filtered = sorted(
        (b for b in bodies if len(b) >= 3),
        key=len,
        reverse=True,  # длинные паттерны первыми → жадность в пользу точных
    )
    if not filtered:
        return None
    parts = "|".join(re.escape(b) for b in filtered)
    # Смотрим назад: если перед телом идёт ОПФ — это уже полное совпадение,
    # пропускаем. Граница слова с обеих сторон.
    opf_lb = r"(?<!(?:ООО|ОАО|ЗАО|ПАО|НАО|АО|ИП|ГК|НКО|ФГУП|МУП|ГБОУ|ГБУ|МБУ|ФГБУ|ТОО)\s)"
    return re.compile(
        rf"(?<![А-ЯЁа-яёA-Za-z])(?:{parts})(?![А-ЯЁа-яёA-Za-z])",
        re.IGNORECASE,
    )


# ---------------------------------------------------------------------------
# Адреса: расширенный паттерн
#
# Изменения по сравнению с предыдущей версией:
# * Добавлены маркеры: ш. (шоссе), пр-д (проезд), туп. (тупик),
#   ал. (аллея), лин. (линия), тер. (территория), влад. (владение).
# * Концевой якорь расширен: теперь ловим «офис N», «помещение N», «эт. N»,
#   «блок N», «участок N», «влад. N» — частые финальные компоненты адреса.
# * Разрешаем адрес начинаться с «ул.», «пр-т», «пр-д» без указания города —
#   это распространённый формат в договорах (адрес получателя/отправителя).
# ---------------------------------------------------------------------------
_ADDRESS_RE = re.compile(
    r"(?:\b\d{6}\s*,\s*)?"
    r"(?:"
    r"\bг\.?\s|\bгород\s|\bобл\.?\s|\bобласть\b|\bресп\.?\s|\bреспублика\b|"
    r"\bкрай\b|"
    # улично-дорожные маркеры (теперь могут стоять в начале без города)
    r"\bул\.?\s|\bулица\s|\bпр-?т\s|\bпроспект\s|"
    r"\bпр-?д\s|\bпроезд\s|"
    r"\bпер\.?\s|\bпереулок\s|"
    r"\bш\.?\s|\bшоссе\s|"
    r"\bнаб\.?\s|\bнабережная\s|"
    r"\bб-?р\s|\bбульвар\s|\bбул\.?\s|"
    r"\bпл\.?\s|\bплощадь\s|"
    r"\bал\.?\s|\bаллея\s|"
    r"\bлин\.?\s|\bлиния\s|"
    r"\bтуп\.?\s|\bтупик\s|"
    r"\bтер\.?\s|\bтеррит[а-я]+\s|"
    r"\bвлад\.?\s|\bвладение\s|"
    r"\bд\.?\s\d|\bдом\s*\d"
    r")"
    r"[^\n;]{2,300}?"
    r"(?:"
    r"\b(?:д\.|дом)\s*\d+[а-яА-Я]?(?:\s*[корп]\.?\s*\d+)?(?:\s*кв\.?\s*\d+)?"
    r"|\bкв\.?\s*\d+"
    r"|\bоф(?:ис)?\.?\s*\d+"          # офис 15 / оф. 3
    r"|\bпом(?:ещение)?\.?\s*\d+"      # помещение 7 / пом. 2
    r"|\bэт(?:аж)?\.?\s*\d+"           # этаж 4 / эт. 1
    r"|\bбл(?:ок)?\.?\s*\d+"           # блок 2
    r"|\bуч(?:асток)?\.?\s*\d+"        # участок 10
    r"|\bвлад(?:ение)?\.?\s*\d+"       # владение 5
    r"|\d{6}"
    r"|(?=\.\s|\n|$)"
    r")",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Валидаторы
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

def _iter_matches(
    text: str,
    org_alias_bodies: set[str] | None = None,
) -> list[tuple[str, str, int, int]]:
    """Найти все PII в одной строке.

    Args:
        text: текст для анализа.
        org_alias_bodies: «голые» тела организаций (без ОПФ), найденные
            в предыдущих chunk'ах — используются для второго прохода поиска
            коротких упоминаний. Если None — второй проход не выполняется.

    Returns:
        Список (type, value, start, end).
    """
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

    # Организации — проход 1: полные упоминания с ОПФ
    local_bodies: set[str] = set()
    for m in _ORG_FULL_RE.finditer(text):
        value = m.group(0).strip().rstrip(",.;")
        found.append(("organization", value, m.start(), m.start() + len(value)))
        body = _extract_org_body(value)
        if len(body) >= 3:
            local_bodies.add(body)

    # Организации — проход 2: «голые» тела (alias)
    # Объединяем тела из текущего chunk'а и переданные извне (из других chunk'ов).
    all_bodies = local_bodies | (org_alias_bodies or set())
    short_re = _build_short_org_re(all_bodies)
    if short_re:
        for m in short_re.finditer(text):
            value = m.group(0).strip()
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
    """Пройти все chunk'и и вернуть все PII-вхождения.

    Реализует двухпроходную логику для организаций: сначала собирает все тела
    (alias) из полных упоминаний по ВСЕМ chunk'ам (первый проход), затем
    повторно сканирует каждый chunk с учётом всех найденных тел (второй проход).
    """
    if not doc.chunks:
        return []

    # --- Предварительный сбор alias-тел (проход по полным упоминаниям ОПФ) ---
    all_bodies: set[str] = set()
    for chunk in doc.chunks:
        if not chunk.text:
            continue
        for m in _ORG_FULL_RE.finditer(chunk.text):
            body = _extract_org_body(m.group(0))
            if len(body) >= 3:
                all_bodies.add(body)

    # --- Основной проход с передачей alias-тел ---
    matches: list[TextMatch] = []
    for chunk in doc.chunks:
        if not chunk.text:
            continue
        for data_type, value, start, end in _iter_matches(chunk.text, all_bodies):
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
