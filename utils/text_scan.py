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
from dataclasses import dataclass, field
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

# ИНН: 10 или 12 цифр, иногда с префиксом "ИНН".
_INN_RE = re.compile(
    r"(?:ИНН[:\s]*)?(?<!\d)(\d{10}|\d{12})(?!\d)",
    re.IGNORECASE,
)

# ФИО: отчество как якорь в полной форме, либо фамилия + инициалы.
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
# Организации.
#
# Улучшения по сравнению с предыдущей версией:
#   1. \s* вместо \s+ — находит ООО"Название" и ЗАО«Название» без пробела.
#   2. Два режима захвата:
#      • с кавычками — захват строго до закрывающей кавычки;
#      • без кавычек — одно или несколько слов с большой буквы,
#        останавливаемся перед строчным предикатом/пунктуацией.
#      Это устраняет захват целого предложения после ОПФ.
#   3. Именованные группы opf / name_q / name_nq для alias-детекции.
#   4. Полные формы ОПФ в детекторе («Общество с ограниченной ответственностью»).
#   5. АО(?!А) исключает случайный захват «АО» из «ЗАО»/«ОАО».
#   6. Добавлен ТОО.
# ---------------------------------------------------------------------------

_OPF_PATTERN = (
    r"(?:ООО|ОАО|ЗАО|ПАО|НАО|АО(?!А)|ИП|ГК|НКО|ФГУП|МУП|ГБОУ|ГБУ|МБУ|ФГБУ|ТОО"
    r"|общество\s+с\s+ограниченной\s+ответственностью"
    r"|публичное\s+акционерное\s+общество"
    r"|закрытое\s+акционерное\s+общество"
    r"|открытое\s+акционерное\s+общество"
    r"|акционерное\s+общество"
    r"|индивидуальный\s+предприниматель)"
)

_ORG_RE = re.compile(
    r"\b(?P<opf>" + _OPF_PATTERN + r")"
    r"\s*"
    r"(?:"
        # Вариант 1: название в кавычках — захват до закрывающей кавычки.
        r"[«\"'\u201c\u201e\u201f]\s*(?P<name_q>[^«\"'\u201c\u201d\u201e\u201f»\n]{2,80}?)\s*[»\"'\u201d\u201f]"
        # Вариант 2: без кавычек — слово(а) с большой буквы до предиката/пунктуации.
        r"|(?P<name_nq>[А-ЯЁA-Z][^\n,;.(]{1,79}?)(?=\s*[,;.\n(]|\s+[а-яёa-z]{3,}|\s*$)"
    r")",
    re.IGNORECASE | re.UNICODE,
)

# ---------------------------------------------------------------------------
# Адреса.
#
# Улучшения по сравнению с предыдущей версией:
#   1. Убраны короткие омонимичные маркеры пл./б. — оставлены только полные
#      формы «площадь» и «бульвар». Это устраняет ложные срабатывания на
#      «пл. ед.», «б. часть» и т.п.
#   2. Добавлены вариации пр-кт / пр-т для проспекта.
#   3. Убран lookahead (?=\.\s) как терминатор — он обрезал адреса на точке
#      внутри «ул.», «д.» и т.п. Заменён на (?=\n|$).
#   4. Хвостовой якорь: [корп] → (?:корп(?:ус)?) (слово вместо символьного
#      класса, который ловил одну букву к/о/р/п).
#   5. Поддержка стр./строение и оф./офис в хвостовом якоре.
#   6. Маркер «г.» требует за собой букву (не цифру) через lookahead.
# ---------------------------------------------------------------------------

_ADDRESS_RE = re.compile(
    # Опциональный почтовый индекс в начале строки адреса.
    r"(?:\b\d{6}\s*[,\s]\s*)?"
    r"(?:"
        # Маркеры уровня города / региона.
        r"\bг(?:ород)?\s*\.?\s*(?=[А-ЯЁа-яёA-Za-z])"
        r"|\bобл(?:асть)?\s*\.?\s*"
        r"|\bресп(?:ублика)?\s*\.?\s*"
        r"|\bкрай\b\s*"
        # Маркеры улично-дорожной сети.
        r"|\bул(?:ица)?\s*\.?\s*"
        r"|\bпроспект\b\s*"
        r"|\bпр-?кт?\s*\.?\s*"          # пр-т, пр-кт, пр.
        r"|\bпер(?:еулок)?\s*\.?\s*"
        r"|\bшоссе\b\s*"
        r"|\bнаб(?:ережная)?\s*\.?\s*"
        r"|\bбульвар\b\s*"               # только полная форма (б. — омоним)
        r"|\bплощадь\b\s*"               # только полная форма (пл. — омоним)
        r"|\bмкр(?:айон)?\s*\.?\s*"
        r"|\bпос(?:ёлок|елок)?\s*\.?\s*"
        r"|\bсело\b\s*"
        # Маркер «дом N» как самостоятельное начало.
        r"|\bдом\s+\d"
        r"|\bд\.\s*\d"
    r")"
    # Тело адреса: ленивый захват до хвостового якоря, не переходим через \n.
    r"[^\n]{2,300}?"
    # Хвостовой якорь: номер дома / квартиры / строения / индекс / конец строки.
    r"(?:"
        r"\b(?:д(?:ом)?)\s*\.?\s*\d+\s*[а-яА-ЯёЁ]?"
            r"(?:\s*(?:корп(?:ус)?|к)\s*\.?\s*\d+)?"
            r"(?:\s*(?:стр(?:оение)?)\s*\.?\s*\d+)?"
            r"(?:\s*(?:кв(?:артира)?|оф(?:ис)?)\s*\.?\s*\d+)?"
        r"|\b(?:кв(?:артира)?|оф(?:ис)?)\s*\.?\s*\d+"
        r"|\b\d{6}\b"
        r"|(?=\n|$)"
    r")",
    re.IGNORECASE | re.UNICODE,
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
# Построение словаря псевдонимов организаций.
#
# После первого прохода по тексту собираем все найденные организации с ОПФ
# и извлекаем «голое» имя (без ОПФ и кавычек). Затем при повторном поиске
# любое одиночное вхождение этого имени в тексте тоже считается организацией
# (например, «Рексофт» после «ООО "Рексофт"»).
# ---------------------------------------------------------------------------

def _extract_org_name(match: re.Match) -> str:
    """Вернуть нормализованное имя организации из совпадения _ORG_RE."""
    name = match.group("name_q") or match.group("name_nq") or ""
    return name.strip().lower()


def _build_alias_pattern(names: set[str]) -> re.Pattern | None:
    """Составить паттерн для поиска голых псевдонимов организаций."""
    if not names:
        return None
    # Сортируем по убыванию длины — более длинные альтернативы должны идти первыми.
    alts = sorted(
        (re.escape(n) for n in names if len(n) >= 3),
        key=len,
        reverse=True,
    )
    if not alts:
        return None
    return re.compile(
        r"(?<!\w)(?:" + r"|".join(alts) + r")(?!\w)",
        re.IGNORECASE | re.UNICODE,
    )


# ---------------------------------------------------------------------------
# Основной сканер
# ---------------------------------------------------------------------------

def _iter_matches(
    text: str,
    org_aliases: re.Pattern | None = None,
) -> list[tuple[str, str, int, int]]:
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

    # Организации (с ОПФ)
    for m in _ORG_RE.finditer(text):
        value = m.group(0).strip().rstrip(",.;")
        found.append(("organization", value, m.start(), m.start() + len(value)))

    # Псевдонимы организаций (голое имя без ОПФ)
    if org_aliases is not None:
        for m in org_aliases.finditer(text):
            found.append(("organization", m.group(0).strip(), m.start(), m.end()))

    # ФИО — оба варианта
    for m in _FIO_FULL_RE.finditer(text):
        found.append(("fio", m.group(0), m.start(), m.end()))
    for m in _FIO_INITIALS_RE.finditer(text):
        found.append(("fio", m.group(0), m.start(), m.end()))

    # Убираем пересечения: сортируем по приоритету типа, затем по длине (убыванию).
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

    Алгоритм двухпроходный:
      1. Первый проход — ищем организации с ОПФ, извлекаем «голые» имена.
      2. Второй проход — полный поиск всех типов + поиск голых псевдонимов.
    """
    # Проход 1: собираем псевдонимы организаций.
    org_names: set[str] = set()
    for chunk in doc.chunks:
        if not chunk.text:
            continue
        for m in _ORG_RE.finditer(chunk.text):
            name = _extract_org_name(m)
            if name:
                org_names.add(name)

    alias_pattern = _build_alias_pattern(org_names)

    # Проход 2: полный поиск.
    matches: list[TextMatch] = []
    for chunk in doc.chunks:
        if not chunk.text:
            continue
        for data_type, value, start, end in _iter_matches(chunk.text, alias_pattern):
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
        # Сортируем по убыванию старта, чтобы offset'ы не ломались.
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
