"""Автокластеризация значений по схожести (rapidfuzz).

Используется нормализаторами, где нужно объединять разные написания одного
объекта: ФИО, адреса, организации. Для строго формализуемых типов (ИНН,
телефоны) кластеризация не нужна — там группировка по ключу.
"""
from __future__ import annotations

from collections import Counter
from typing import Callable, Mapping

from rapidfuzz import fuzz, process


def cluster_by_similarity(
    values: list[str],
    key_fn: Callable[[str], str],
    threshold: int = 88,
    scorer=fuzz.token_set_ratio,
    counts: Mapping[str, int] | None = None,
) -> list[dict]:
    """Сгруппировать значения в кластеры по схожести их нормализованных ключей.

    Алгоритм — жадная кластеризация с быстрым отбором через `rapidfuzz.process`.

    Args:
        values: исходные значения. Если `counts` не передан — допускаются
            дубликаты, они будут посчитаны. Если `counts` передан, `values`
            должны уже быть уникальными и отсортированными по убыванию частоты.
        key_fn: функция приведения к ключу сравнения. Результат кэшируется.
        threshold: порог схожести 0..100.
        scorer: функция сравнения из rapidfuzz.
        counts: опциональный словарь {value: count}. Если передан, ускоряет
            работу (не нужно считать Counter).

    Returns:
        Список кластеров: [{canonical, keys, variants(Counter), count}, ...].
    """
    if not values:
        return []

    if counts is None:
        counter: Counter[str] = Counter(v for v in values if v)
        ordered = sorted(counter.items(), key=lambda x: (-x[1], -len(x[0])))
    else:
        ordered = [(v, counts.get(v, 1)) for v in values if v]

    # Ключи лидеров кластеров — для быстрого поиска через rapidfuzz.process.
    leader_keys: list[str] = []
    clusters: list[dict] = []
    # Кэшируем key_fn: значения могут повторяться между вызовами через cleaned-форму.
    key_cache: dict[str, str] = {}

    for value, freq in ordered:
        key = key_cache.get(value)
        if key is None:
            key = key_fn(value)
            key_cache[value] = key
        if not key:
            continue

        # Быстрый отбор ближайшего лидера через rapidfuzz.process.extractOne —
        # реализовано на C, заметно быстрее ручного цикла для больших наборов.
        if leader_keys:
            match = process.extractOne(
                key, leader_keys, scorer=scorer, score_cutoff=threshold,
            )
        else:
            match = None

        if match is not None:
            _, _, idx = match
            cl = clusters[idx]
            cl["keys"].add(key)
            cl["variants"][value] += freq
            cl["count"] += freq
        else:
            clusters.append({
                "canonical": value,          # лидер кластера = самый частый
                "canonical_key": key,
                "keys": {key},
                "variants": Counter({value: freq}),
                "count": freq,
            })
            leader_keys.append(key)

    return clusters
