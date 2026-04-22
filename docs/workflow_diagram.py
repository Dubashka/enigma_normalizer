"""Схема воркфлоу Enigma normalizer stand — рендерим PNG через matplotlib."""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from matplotlib.lines import Line2D


# Палитра
C_USER = "#E3F2FD"      # голубой
C_USER_EDGE = "#1976D2"
C_AUTO = "#E8F5E9"      # зелёный — автоматика
C_AUTO_EDGE = "#2E7D32"
C_HYBRID = "#E1F5FE"    # голубо-зелёный — авто + правки пользователя
C_HYBRID_EDGE = "#00838F"
C_ALGO = "#FFF3E0"      # оранжевый — алгоритмы
C_ALGO_EDGE = "#E65100"
C_OUT = "#F3E5F5"       # фиолетовый — выходы
C_OUT_EDGE = "#6A1B9A"
C_TEXT = "#1a1a1a"

FS_TITLE = 11
FS_BODY = 9
FS_SMALL = 8


def box(ax, x, y, w, h, label, sub=None, face=C_USER, edge=C_USER_EDGE, title_fs=FS_TITLE):
    p = FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.02,rounding_size=0.12",
        linewidth=1.6,
        facecolor=face,
        edgecolor=edge,
    )
    ax.add_patch(p)
    if sub:
        ax.text(x + w / 2, y + h * 0.68, label,
                ha="center", va="center",
                fontsize=title_fs, fontweight="bold", color=C_TEXT)
        ax.text(x + w / 2, y + h * 0.28, sub,
                ha="center", va="center",
                fontsize=FS_SMALL, color="#444")
    else:
        ax.text(x + w / 2, y + h / 2, label,
                ha="center", va="center",
                fontsize=title_fs, fontweight="bold", color=C_TEXT)


def arrow(ax, x1, y1, x2, y2, label=None, color="#555", style="-|>", offset=(0.0, 0.15)):
    a = FancyArrowPatch(
        (x1, y1), (x2, y2),
        arrowstyle=style,
        mutation_scale=16,
        linewidth=1.4,
        color=color,
    )
    ax.add_patch(a)
    if label:
        mx, my = (x1 + x2) / 2 + offset[0], (y1 + y2) / 2 + offset[1]
        ax.text(mx, my, label, ha="center", va="center",
                fontsize=FS_SMALL, color=color,
                bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.85))


def main(out_path: Path):
    fig, ax = plt.subplots(figsize=(14, 11))
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 16)
    ax.axis("off")

    # Заголовок
    ax.text(7, 15.5,
            "Enigma · Тестовый стенд нормализации — схема воркфлоу",
            ha="center", va="center", fontsize=14, fontweight="bold", color=C_TEXT)
    ax.text(7, 15.05,
            "Streamlit-приложение: мультиколоночная нормализация с автодетектом типа данных",
            ha="center", va="center", fontsize=9.5, color="#555", style="italic")

    # ---- Шаг 1: Загрузка ----
    box(ax, 0.3, 13.2, 3.5, 1.3,
        "1. Загрузка Excel",
        "пользователь загружает .xlsx\n→ читаются все листы",
        face=C_USER, edge=C_USER_EDGE)

    # ---- Шаг 2: Выбор листа + авто-скан + пользовательские правки (гибрид) ----
    box(ax, 4.0, 13.2, 5.2, 1.3,
        "2. Выбор листа + авто-скан всех колонок",
        "система сама отмечает колонки, для которых есть алгоритм;\n"
        "пользователь может снять/поставить галочки",
        face=C_HYBRID, edge=C_HYBRID_EDGE)

    # ---- Шаг 3: Проверка/корректировка типа ----
    box(ax, 9.4, 13.2, 4.3, 1.3,
        "3. Проверка типа алгоритма",
        "тип выставлен автоматически;\nможно поменять вручную (override)",
        face=C_HYBRID, edge=C_HYBRID_EDGE)

    arrow(ax, 3.8, 13.85, 4.0, 13.85)
    arrow(ax, 9.2, 13.85, 9.4, 13.85)

    # ---- Блок: движок автодетекта (детали) ----
    det_box = FancyBboxPatch(
        (4.5, 10.1), 6.0, 2.7,
        boxstyle="round,pad=0.02,rounding_size=0.12",
        linewidth=1.6, facecolor=C_AUTO, edgecolor=C_AUTO_EDGE,
    )
    ax.add_patch(det_box)
    ax.text(7.5, 12.55, "Движок scan_dataframe / detect_type",
            ha="center", va="center", fontsize=10, fontweight="bold", color=C_TEXT)
    ax.text(4.7, 12.10,
            "• Прогон по всем колонкам листа\n"
            "• 6 детекторов по приоритету:\n"
            "   email → phone → ИНН → адрес → орг → ФИО\n"
            "• Доля совпадений на выборке (до 200 значений)\n"
            "• Порог детекта 60%, fallback ≥40%\n"
            "• Порог рекомендации 60% → галочка выставляется автоматически\n"
            "• Бейдж уверенности: ≥ 75% / ≥ 50% / <50%",
            ha="left", va="top", fontsize=FS_SMALL, color="#333")

    # стрелка от шага 2 вниз к движку
    arrow(ax, 6.6, 13.2, 6.6, 12.8, color=C_AUTO_EDGE)
    # стрелка от движка к шагу 3 (корректировка)
    arrow(ax, 10.5, 11.4, 11.4, 12.0, color=C_AUTO_EDGE, offset=(0.3, 0.0),
          label="тип по колонке")

    # ---- Шаг 4: Запуск алгоритмов ----
    box(ax, 0.3, 8.2, 13.4, 1.3,
        "4. Запуск алгоритмов (цикл по каждой колонке)",
        "для колонки i: выбираем тип → применяем соответствующий нормализатор → получаем список кандидатов",
        face=C_ALGO, edge=C_ALGO_EDGE)

    arrow(ax, 2.0, 13.2, 2.0, 9.5, color=C_ALGO_EDGE)
    arrow(ax, 7.5, 10.1, 7.5, 9.5, color=C_ALGO_EDGE)
    arrow(ax, 11.5, 13.2, 11.5, 9.5, color=C_ALGO_EDGE)

    # ---- 6 алгоритмов ----
    algos = [
        ("email", "Email", "правила провайдеров:\nGmail/Яндекс/Outlook,\nалиасы доменов"),
        ("phone", "Телефоны", "phonenumbers, E.164,\nдобавочные номера"),
        ("inn", "ИНН", "regex + контрольная\nсумма ФНС\n(10/12 знаков)"),
        ("address", "Адреса", "разворот сокращений\n+ fuzzy-кластеризация\n(rapidfuzz)"),
        ("org", "Организации", "извлечение ОПФ,\nfuzzy без ОПФ"),
        ("fio", "ФИО", "natasha + pymorphy3,\nсклейка полных\nи инициальных форм"),
    ]
    algo_w = 2.15
    algo_h = 1.6
    x0 = 0.3
    y_algo = 6.2
    for i, (key, name, desc) in enumerate(algos):
        x = x0 + i * (algo_w + 0.06)
        box(ax, x, y_algo, algo_w, algo_h, name, desc,
            face=C_ALGO, edge=C_ALGO_EDGE, title_fs=10)
        # стрелка сверху
        arrow(ax, x + algo_w / 2, 8.2, x + algo_w / 2, y_algo + algo_h,
              color=C_ALGO_EDGE)

    # ---- Шаг 5: кандидаты с галочками (табы) ----
    box(ax, 0.3, 3.9, 13.4, 1.6,
        "5. Кандидаты на объединение — отдельная вкладка на каждую колонку",
        "st.tabs: варианты → группы, редактируемое каноническое значение, галочки «Применить», режим «Все группы / только с вариантами»",
        face=C_USER, edge=C_USER_EDGE)

    # стрелки от каждого алгоритма вниз к шагу 5
    for i in range(6):
        x = x0 + i * (algo_w + 0.06) + algo_w / 2
        arrow(ax, x, y_algo, x, 5.5, color=C_USER_EDGE)

    # ---- Шаг 6: Применение и экспорт ----
    box(ax, 0.3, 1.7, 6.4, 1.6,
        "6a. Применение по всем колонкам",
        "копия DataFrame → для каждой колонки\nприменяется её mapping → подсчёт замен",
        face=C_OUT, edge=C_OUT_EDGE)

    box(ax, 7.3, 1.7, 6.4, 1.6,
        "6b. Экспорт",
        "Excel (все листы, целевой заменён)\nJSON mapping с секциями по колонкам\n(data_type, auto_detected, groups)",
        face=C_OUT, edge=C_OUT_EDGE)

    arrow(ax, 3.5, 3.9, 3.5, 3.3, color=C_OUT_EDGE)
    arrow(ax, 10.5, 3.9, 10.5, 3.3, color=C_OUT_EDGE)
    arrow(ax, 6.7, 2.5, 7.3, 2.5, color=C_OUT_EDGE)

    # ---- Легенда ----
    legend_elems = [
        (C_USER, C_USER_EDGE, "Действие пользователя"),
        (C_HYBRID, C_HYBRID_EDGE, "Авто + правки пользователя"),
        (C_AUTO, C_AUTO_EDGE, "Автоматика (детект)"),
        (C_ALGO, C_ALGO_EDGE, "Алгоритмы нормализации"),
        (C_OUT, C_OUT_EDGE, "Применение и экспорт"),
    ]
    for i, (fc, ec, label) in enumerate(legend_elems):
        y = 0.55
        x = 0.3 + i * 2.7
        r = FancyBboxPatch(
            (x, y), 0.32, 0.32,
            boxstyle="round,pad=0.02,rounding_size=0.08",
            linewidth=1.3, facecolor=fc, edgecolor=ec,
        )
        ax.add_patch(r)
        ax.text(x + 0.45, y + 0.16, label, ha="left", va="center",
                fontsize=FS_SMALL, color="#333")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=180, bbox_inches="tight", facecolor="white")
    print(f"saved {out_path}")


if __name__ == "__main__":
    here = Path(__file__).parent
    main(here / "workflow.png")
