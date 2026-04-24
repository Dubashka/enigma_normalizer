"""Реестр алгоритмов нормализации.

Каждый тип данных — свой отдельный класс-нормализатор. UI выбирает
нужный по ключу из REGISTRY.
"""
from __future__ import annotations

from .address import AddressNormalizer
from .base import BaseNormalizer, NormalizationCandidate
from .document import normalize_document, normalize_docx, extract_text_from_txt
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

DOCUMENT_TYPE_LABELS: dict[str, str] = {
    "fio": "ФИО",
    "phone": "Телефоны",
    "email": "Email",
    "inn": "ИНН",
    "address": "Адреса",
    "organization": "Организации",
}


def get_normalizer(key: str) -> BaseNormalizer:
    if key not in REGISTRY:
        raise ValueError(f"Неизвестный тип данных: {key}")
    return REGISTRY[key]()


__all__ = [
    "REGISTRY",
    "LABELS",
    "DOCUMENT_TYPE_LABELS",
    "get_normalizer",
    "BaseNormalizer",
    "NormalizationCandidate",
    "normalize_document",
    "normalize_docx",
    "extract_text_from_txt",
]