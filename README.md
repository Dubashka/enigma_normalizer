# Normalizer

Веб-приложение на Streamlit для ручного тестирования отдельных алгоритмов
нормализации перед этапом анонимизации документов.

## Возможности

- Загрузка `.xlsx` / `.xls` файла.
- Выбор **типа данных** — для каждого работает свой алгоритм:
  - **ФИО** — `natasha` + `pymorphy3`, лемматизация, объединение полной и инициальной форм.
  - **ИНН** — валидация длины (10/12) и контрольной суммы по правилам ФНС.
  - **Адреса** — разворот сокращений (`г./ул./д./кв.`), индекс в начало, fuzzy-кластеризация.
  - **Номера телефонов** — парсинг через `phonenumbers`, каноническая форма E.164, поддержка добавочных.
  - **Названия организаций** — извлечение ОПФ (`ООО`, `ПАО`, …), fuzzy-сравнение по «телу» названия.
- Выбор листа и колонки.
- Интерактивный чек-лист кандидатов с возможностью редактировать каноническое значение.
- Скачивание нормализованного Excel и JSON-справочника маппингов.

## Структура проекта

```
enigma_normalizer/
├── app.py                       # Streamlit UI
├── requirements.txt
├── normalizers/
│   ├── __init__.py              # REGISTRY всех алгоритмов
│   ├── base.py                  # BaseNormalizer + NormalizationCandidate
│   ├── person.py                # ФИО
│   ├── inn.py                   # ИНН
│   ├── address.py               # Адреса
│   ├── phone.py                 # Телефоны
│   └── organization.py          # Организации
├── utils/
│   └── clustering.py            # Жадная кластеризация через rapidfuzz
└── samples/
    └── sample_data.xlsx         # Пример данных для тестирования
```

## Запуск

```bash
cd enigma_normalizer
python -m venv .venv
source .venv/bin/activate         # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Приложение откроется на `http://localhost:8501`.

## Как добавить новый тип данных

1. Создать `normalizers/<my_type>.py`, унаследоваться от `BaseNormalizer`,
   реализовать `normalize_value` и `build_candidates`.
2. Зарегистрировать класс в `normalizers/__init__.py` — добавить в `REGISTRY`
   и `LABELS`.

Новый тип автоматически появится в UI.

## Формат JSON-справочника

```json
{
  "meta": {
    "source_file": "clients.xlsx",
    "sheet": "Лист1",
    "column": "ФИО клиента",
    "data_type": "fio",
    "data_type_label": "ФИО",
    "created_at": "2026-04-21T14:50:00",
    "total_candidates": 48,
    "applied_groups": 12,
    "total_values_changed": 37
  },
  "mapping": {
    "Иванов И.И.": "Иванов Иван Иванович",
    "иванов иван иванович": "Иванов Иван Иванович"
  },
  "groups": [
    {
      "canonical": "Иванов Иван Иванович",
      "variants": ["Иванов И.И.", "иванов иван иванович"],
      "count": 5,
      "confidence": 0.9,
      "meta": {"variant_counts": {"Иванов И.И.": 3, "иванов иван иванович": 2}}
    }
  ]
}
```
