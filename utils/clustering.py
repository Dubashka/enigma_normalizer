"""Автокластеризация значений по схожести (rapidfuzz).

Используется нормализаторами, где нужно объединять разные написания одного
объекта: ФИО, адреса, организации. Для строго формализуемых типов (ИНН,
телефоны) кластеризация не нужна — там группировка по ключу.
"""
from __future__ import annotations

from collections import Counter
from typing import Callable

from rapidfuzz import fuzz


def cluster_by_similarity(
    values: list[str],
    key_fn: Callable[[str], str],
    threshold: int = 88,
    scorer=fuzz.token_set_ratio,
) -> list[dict]:
    """Сгруппировать значения в кластеры по схожести их нормализованных ключей.

    Алгоритм: жадная кластеризация.
    1. Значения сортируются по убыванию частоты (самый частый — лидер кластера).
    2. Для каждого нового значения ищется ближайший существующий кластер.
    3. Если расстояние >= threshold — добавляем, иначе создаём новый кластер.

    Args:
        values: исходные значения колонки (с дубликатами).
        key_fn: функция приведения к ключу сравнения.
        threshold: порог схожести 0..100.
        scorer: функция сравнения из rapidfuzz.

    Returns:
        Список кластеров: [{canonical, keys, variants(Counter), count}, ...].
    """
    if not values:
        return []

    counter: Counter[str] = Counter(v for v in values if v)
    # Сортируем по частоте, а при равной частоте — по длине (более полные впереди)
    ordered = sorted(counter.items(), key=lambda x: (-x[1], -len(x[0])))

    clusters: list[dict] = []
    for value, freq in ordered:
        key = key_fn(value)
        if not key:
            continue

        best_idx, best_score = -1, -1.0
        for i, cl in enumerate(clusters):
            score = max(scorer(key, k) for k in cl["keys"])
            if score > best_score:
                best_score, best_idx = score, i

        if best_idx >= 0 and best_score >= threshold:
            cl = clusters[best_idx]
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

    return clusters
