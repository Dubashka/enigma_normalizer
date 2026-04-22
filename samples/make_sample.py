"""Генератор тестового Excel с разными типами данных и грязными вариантами."""
from pathlib import Path

import pandas as pd


def main():
    fio = pd.DataFrame({
        "ФИО": [
            "Иванов Иван Иванович",
            "иванов иван иванович",
            "ИВАНОВ И.И.",
            "Иванов И. И.",
            "Петрова Мария Сергеевна",
            "Петрова М.С.",
            "М. С. Петрова",
            "Сидоров Петр Александрович",
            "Сидоров П.А.",
            "Козлова-Смирнова Анна Владимировна",
            "Ким Чен",
        ],
        "Комментарий": ["a"] * 11,
    })

    inn = pd.DataFrame({
        "ИНН": [
            "7707083893",            # валидный ЮЛ (Сбербанк)
            "ИНН: 7707083893",
            "7707-083-893",
            "7707083893 ",
            "500100732259",          # валидный ФЛ
            "500100732259",
            "1234567890",            # невалидный
            "abc",
        ],
    })

    address = pd.DataFrame({
        "Адрес": [
            "г. Москва, ул. Ленина, д. 5, кв. 10",
            "Москва, ул Ленина д.5 кв.10",
            "г Москва ул. Ленина 5-10",
            "101000, Россия, г. Москва, ул. Ленина, дом 5",
            "Санкт-Петербург, Невский пр-т, 25",
            "СПб, Невский проспект, д. 25",
            "Казань, ул Баумана 10",
            "город Казань, улица Баумана, дом 10",
        ],
    })

    phone = pd.DataFrame({
        "Телефон": [
            "+7 (495) 123-45-67",
            "8 495 123 45 67",
            "84951234567",
            "+74951234567 доб. 101",
            "8(495)123-45-67 доб.101",
            "+7-916-000-00-11",
            "89160000011",
            "123",
        ],
    })

    org = pd.DataFrame({
        "Организация": [
            'ООО "Ромашка"',
            "ООО Ромашка",
            "Ромашка ООО",
            'Общество с ограниченной ответственностью "Ромашка"',
            'ПАО "Сбербанк"',
            "Сбербанк ПАО",
            'Публичное акционерное общество "Сбербанк"',
            'ИП Иванов И.И.',
            "Индивидуальный предприниматель Иванов И.И.",
        ],
    })

    email = pd.DataFrame({
        "Email": [
            "John.Doe@gmail.com",
            "johndoe@gmail.com",
            "john.doe+promo@gmail.com",
            "JOHNDOE@googlemail.com",
            "anna.petrova@yandex.ru",
            "anna-petrova@ya.ru",
            "anna.petrova+work@yandex.com",
            "user123@hotmail.com",
            "user123@outlook.com",
            "User123+alias@live.com",
            "sales@example.ru",
            "Sales@Example.RU",
            "mailto:support@firm.org",
            "Ivan Ivanov <ivan@firm.org>",
        ],
    })

    # Лист со смешанными колонками — типичная таблица клиентов.
    # Позволяет протестировать мультивыбор колонок и автодетект по каждой.
    mixed = pd.DataFrame({
        "Клиент": [
            "Иванов Иван Иванович",
            "ИВАНОВ И.И.",
            "Петрова Мария Сергеевна",
            "Петрова М.С.",
            "Сидоров П.А.",
        ],
        "Контакт": [
            "+7 (495) 123-45-67",
            "84951234567",
            "+7-916-000-00-11",
            "89160000011",
            "8 495 987 65 43",
        ],
        "Почта": [
            "ivan.ivanov@gmail.com",
            "ivanivanov@gmail.com",
            "petrova.ms@yandex.ru",
            "petrova-ms@ya.ru",
            "sidorov@example.ru",
        ],
        "Работодатель": [
            'ООО "Ромашка"',
            "ООО Ромашка",
            'ПАО "Сбербанк"',
            "Сбербанк ПАО",
            'ИП Иванов И.И.',
        ],
        "Сумма": [1000, 2500, 3000, 1200, 500],
    })

    out = Path(__file__).with_name("sample_data.xlsx")
    with pd.ExcelWriter(out, engine="xlsxwriter") as writer:
        fio.to_excel(writer, sheet_name="ФИО", index=False)
        inn.to_excel(writer, sheet_name="ИНН", index=False)
        address.to_excel(writer, sheet_name="Адреса", index=False)
        phone.to_excel(writer, sheet_name="Телефоны", index=False)
        org.to_excel(writer, sheet_name="Организации", index=False)
        email.to_excel(writer, sheet_name="Email", index=False)
        mixed.to_excel(writer, sheet_name="Смешанные", index=False)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
