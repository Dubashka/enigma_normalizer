"""Реестр алгоритмов нормализации.

Каждый тип данных — свой отдельный класс-нормализатор. UI выбирает
нужный по ключу из REGISTRY.
"""
from __future__ import annotations

from .address import AddressNormalizer
from .base import BaseNormalizer, NormalizationCandidate
from .email import EmailNormalizer
from .inn import InnNormalizer
from .organization import OrganizationNormalizer
from .person import PersonNormalizer
from .phone import PhoneNormalizer
from .text import TextNormalizer


REGISTRY: dict[str, type[BaseNormalizer]] = {
    "fio": PersonNormalizer,
    "inn": InnNormalizer,
    "address": AddressNormalizer,
    "phone": PhoneNormalizer,
    "organization": OrganizationNormalizer,
    "email": EmailNormalizer,
    "text": TextNormalizer,
}


LABELS: dict[str, str] = {
    "fio": "ФИО",
    "inn": "ИНН",
    "address": "Адреса",
    "phone": "Номера телефонов",
    "organization": "Названия организаций",
    "email": "Email-адреса",
    "text": "Текстовые значения",
}


def get_normalizer(key: str) -> BaseNormalizer:
    if key not in REGISTRY:
        raise ValueError(f"Неизвестный тип данных: {key}")
    return REGISTRY[key]()


__all__ = [
    "REGISTRY",
    "LABELS",
    "get_normalizer",
    "BaseNormalizer",
    "NormalizationCandidate",
]
