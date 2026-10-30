"""Модуль работы с базой данных SQLite для АС «Кордон – Норма»."""

import json
import os
import shutil
import sqlite3
import sys
from pathlib import Path

import pandas as pd


def get_db_path() -> Path:
    """Возвращает безопасный путь к рабочей базе данных."""
    if not getattr(sys, "frozen", False):
        # При запуске из исходного кода база находится в корне проекта.
        return Path(__file__).resolve().parent.parent / "database.db"

    # В собранной версии база хранится в профиле пользователя Windows.
    app_data = Path(
        os.environ.get("LOCALAPPDATA")
        or os.environ.get("APPDATA")
        or Path.home()
    )
    data_dir = app_data / "SmenaT"
    data_dir.mkdir(parents=True, exist_ok=True)
    db_path = data_dir / "database.db"

    # Однократно переносим старую базу из известных прежних расположений.
    if not db_path.exists():
        legacy_paths = [
            Path(sys.executable).resolve().parent / "database.db",
            Path.cwd() / "database.db",
        ]
        for legacy_path in legacy_paths:
            if legacy_path.is_file() and legacy_path.resolve() != db_path.resolve():
                shutil.copy2(legacy_path, db_path)
                break

    return db_path


DB_PATH = get_db_path()


def get_connection():
    """Создает подключение к базе данных SQLite."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Инициализирует структуры таблиц и заполняет базовые справочники."""
    with get_connection() as conn:
        cursor = conn.cursor()

        # Единый справочник ТСПК (нормы + модели + цены)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dict_tspk (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                equipment_name TEXT NOT NULL,
                selected_model TEXT,
                norm_type TEXT NOT NULL,
                ratio REAL NOT NULL,
                unit TEXT NOT NULL,
                unit_price_usd REAL DEFAULT 0.0,
                note TEXT
            )
        """)

        # Таблица системных настроек и коэффициентов
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dict_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                description TEXT
            )
        """)

        # Таблица истории расчетов
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS calculation_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                app_name TEXT,
                app_code TEXT,
                category TEXT,
                input_params TEXT,
                results TEXT
            )
        """)

        # Наполнение единой таблицы dict_tspk
        # Наполнение единой таблицы dict_tspk
        cursor.execute("SELECT COUNT(*) FROM dict_tspk")
        if cursor.fetchone()[0] == 0:
            default_tspk = [
                # Категория 1.3.1
                (
                    "Паспортный контроль",
                    "Автоматизированная система пограничного контроля",
                    "АСПК",
                    "per_checkpoint",
                    1.0,
                    "компл.",
                    12000.0,
                    "1 комплекс на пункт пропуска",
                ),
                (
                    "Паспортный контроль",
                    "Автоматизированная кабина ПК",
                    "Автоматизированная кабина ПК",
                    "manual",
                    0.0,
                    "шт.",
                    8500.0,
                    "Количество выбирается оператором",
                ),
                (
                    "Паспортный контроль",
                    "Технические средства общей проверки документов",
                    "Считыватель паспортов и виз Regula 7024",
                    "per_workstation",
                    1.0,
                    "шт.",
                    1350.0,
                    "1:1 на рабочее место контролера",
                ),
                (
                    "Паспортный контроль",
                    "Технические средства общей проверки документов",
                    "Прибор контроля подлинности документов Regula 4115",
                    "per_workstation",
                    1.0,
                    "шт.",
                    1350.0,
                    "1:1 на рабочее место контролера",
                ),
                (
                    "Паспортный контроль",
                    "Технические средства специальной проверки документов",
                    "Компаратор Regula 4305 DMH",
                    "per_spec_room",
                    1.0,
                    "компл.",
                    3900.0,
                    "1 комплект на комнату специальной проверки",
                ),
                (
                    "Паспортный контроль",
                    "Технические средства специальной проверки документов",
                    "Микроскоп цифровой Regula 5001",
                    "per_spec_room",
                    1.0,
                    "компл.",
                    4000.0,
                    "1 комплект на комнату специальной проверки",
                ),
                (
                    "Паспортный контроль",
                    "Технические средства специальной проверки документов",
                    "Микроскоп МБС-10",
                    "per_spec_room",
                    1.0,
                    "компл.",
                    1000.0,
                    "1 комплект на комнату специальной проверки",
                ),
                (
                    "Паспортный контроль",
                    "Средства простановки оттиска датоштампа",
                    "Trodat 5430",
                    "per_controller",
                    1.0,
                    "шт.",
                    55.0,
                    "1:1 на каждого контролера в смене",
                ),
                # Категория 1.3.2
                (
                    "Досмотровые средства",
                    "Инспекционно-досмотровый комплекс (ИДК)",
                    "Инспекционно-досмотровый комплекс (ИДК)",
                    "per_checkpoint",
                    1.0,
                    "компл.",
                    500000.0,
                    "1 на пункт пропуска",
                ),
                (
                    "Досмотровые средства",
                    "Переносной досмотровый комплект",
                    "Гастроль-П",
                    "per_inspection_group",
                    1.0,
                    "компл.",
                    1050.0,
                    "1 на досмотровую группу",
                ),
                (
                    "Досмотровые средства",
                    "Комплект досмотровых зеркал",
                    "Поиск-2",
                    "per_inspection_group",
                    1.0,
                    "компл.",
                    390.0,
                    "1 на досмотровую группу",
                ),
                (
                    "Досмотровые средства",
                    "Досмотровый телевизионный эндоскоп",
                    "Регула-3022",
                    "per_inspection_group",
                    1.0,
                    "компл.",
                    2350.0,
                    "1 на досмотровую группу",
                ),
                (
                    "Досмотровые средства",
                    "Досмотровый телевизионный эндоскоп",
                    "ЭТВЦ",
                    "per_inspection_group",
                    1.0,
                    "компл.",
                    2000.0,
                    "1 на досмотровую группу",
                ),
                (
                    "Досмотровые средства",
                    "Комплект щупов",
                    "КЩ-3М",
                    "per_inspection_group",
                    1.0,
                    "компл.",
                    150.0,
                    "1 на досмотровую группу",
                ),
                (
                    "Досмотровые средства",
                    "Аккумуляторные фонари с зарядными устройствами",
                    "Фонарь досмотровый с ЗУ",
                    "per_inspection_group",
                    1.0,
                    "шт.",
                    120.0,
                    "1 на досмотровую группу",
                ),
                # Категория 1.3.3
                (
                    "Обнаружение оружия, ВВ и НВ",
                    "Ручные металлоискатели",
                    "Сфинкс",
                    "per_inspection_group",
                    1.0,
                    "шт.",
                    165.0,
                    "1 на досмотровую группу",
                ),
                (
                    "Обнаружение оружия, ВВ и НВ",
                    "Переносные детекторы взрывчатых и наркотических веществ",
                    "Кербер-2",
                    "per_inspection_group",
                    1.0,
                    "компл.",
                    9400.0,
                    "1 на досмотровую группу",
                ),
                (
                    "Обнаружение оружия, ВВ и НВ",
                    "Газоанализаторы",
                    "След",
                    "per_inspection_group",
                    1.0,
                    "шт.",
                    4500.0,
                    "1 на досмотровую группу",
                ),
                (
                    "Обнаружение оружия, ВВ и НВ",
                    "Радиационные портальные мониторы (РПМ)",
                    "РПМ",
                    "per_checkpoint",
                    2.0,
                    "компл.",
                    3500.0,
                    "2 на пункт пропуска",
                ),
                # Категория 1.3.4
                (
                    "Аудио-, видео- и фотодокументирование",
                    "Портативные носимые видеорегистраторы",
                    "Дозор",
                    "per_outdoor_personnel",
                    1.0,
                    "шт.",
                    350.0,
                    "На личный состав на досмотре и улице",
                ),
                # Категория 1.3.5
                (
                    "Эксплуатационные / технологические средства",
                    "Средства принудительной остановки автотранспорта",
                    "Лиана",
                    "per_checkpoint",
                    4.0,
                    "компл.",
                    800.0,
                    "4 на пункт пропуска",
                ),
                (
                    "Эксплуатационные / технологические средства",
                    "Заградительные шлагбаумы",
                    "Шлагбаум автоматический",
                    "per_checkpoint",
                    4.0,
                    "шт.",
                    1200.0,
                    "4 на пункт пропуска",
                ),
                # Категория 1.3.6
                (
                    "Учебно-материальная база",
                    "Учебный класс (включая АКТСО и электронные тренажёры)",
                    "АКТСО + Тренажёры",
                    "per_checkpoint",
                    1.0,
                    "компл.",
                    15000.0,
                    "1 на пункт пропуска",
                ),
                (
                    "Учебно-материальная база",
                    "Атласы паспортов",
                    "Справочные альбомы",
                    "per_checkpoint",
                    1.0,
                    "компл.",
                    400.0,
                    "1 комплект на пункт пропуска",
                ),
            ]
            cursor.executemany(
                """INSERT INTO dict_tspk 
                (category, equipment_name, selected_model, norm_type, ratio, unit, unit_price_usd, note) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                default_tspk,
            )

        # Наполнение базовых настроек
        cursor.execute("SELECT COUNT(*) FROM dict_settings")
        if cursor.fetchone()[0] == 0:
            default_settings = [
                ("k_shift_12h", "2.0", "Коэффициент для двух смен"),
                ("k_shift_8h", "3.0", "Коэффициент для трех смен"),
                ("k_shift_24h", "4.0", "Коэффициент для четырех смен"),
                ("reserve_tspk_percent", "0.10", "Процент НЗ для ТСПК"),
            ]
            cursor.executemany(
                "INSERT INTO dict_settings (key, value, description) VALUES (?, ?, ?)",
                default_settings,
            )

        conn.commit()


def get_settings() -> dict:
    """Возвращает настройки из dict_settings в виде словаря."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM dict_settings")
        return {row["key"]: row["value"] for row in cursor.fetchall()}


def save_calculation(app_name, app_code, category, input_params, results) -> int:
    """Сохраняет проведенный расчет в таблицу истории."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO calculation_history 
            (app_name, app_code, category, input_params, results) 
            VALUES (?, ?, ?, ?, ?)""",
            (
                app_name,
                app_code,
                category,
                json.dumps(input_params, ensure_ascii=False),
                json.dumps(results, ensure_ascii=False),
            ),
        )
        conn.commit()
        return cursor.lastrowid


def get_calculation_history(limit: int = 20) -> list[dict]:
    """Возвращает историю расчетов."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT id, created_at, app_name, app_code, category, input_params, results 
            FROM calculation_history ORDER BY id DESC LIMIT ?""",
            (limit,),
        )
        history = []
        for row in cursor.fetchall():
            item = dict(row)
            item["input_params"] = json.loads(item["input_params"]) if item["input_params"] else {}
            item["results"] = json.loads(item["results"]) if item["results"] else {}
            history.append(item)
        return history
    
def get_all_calculations() -> list[dict]:
  """Возвращает все сохраненные расчеты из истории."""
  with get_connection() as conn:
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, app_name, category, created_at, input_params, results FROM"
        " calculation_history ORDER BY id DESC"
    )
    return [dict(row) for row in cursor.fetchall()]


def delete_calculation(calc_id: int) -> None:
  """Удаляет расчет из истории по ID."""
  with get_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("DELETE FROM calculation_history WHERE id = ?", (calc_id,))
    conn.commit()

def get_tspk_dict() -> list[dict]:
    """Возвращает все записи справочника ТСПК в виде списка словарей."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM dict_tspk ORDER BY id")
        return [dict(row) for row in cursor.fetchall()]


def save_tspk_dict(updated_df) -> None:
    """Сохраняет изменения из DataFrame в таблицу dict_tspk (полная перезапись/синхронизация)."""
    with get_connection() as conn:
        cursor = conn.cursor()
        # Очищаем таблицу и заново заливаем актуальные данные из редактора
        cursor.execute("DELETE FROM dict_tspk")
        
        for _, row in updated_df.iterrows():
            cursor.execute(
                """
                INSERT INTO dict_tspk 
                (id, category, equipment_name, selected_model, norm_type, ratio, unit, unit_price_usd, note) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(row["id"]) if pd.notna(row.get("id")) else None,
                    row.get("category", ""),
                    row.get("equipment_name", ""),
                    row.get("selected_model", ""),
                    row.get("norm_type", ""),
                    float(row.get("ratio", 1.0)),
                    row.get("unit", ""),
                    float(row.get("unit_price_usd", 0.0)),
                    row.get("note", ""),
                ),
            )
        conn.commit()

def reset_tspk_to_default() -> None:
    """Сбрасывает справочник ТСПК: полностью очищает таблицу и заново заполняет её дефолтными значениями из init_db."""
    with get_connection() as conn:
        cursor = conn.cursor()
        # Полностью очищаем текущую таблицу справочника
        cursor.execute("DELETE FROM dict_tspk")
        # Сбрасываем автоинкремент ID (опционально, чтобы ID снова шли с 1)
        cursor.execute("DELETE FROM sqlite_sequence WHERE name='dict_tspk'")
        conn.commit()
    
    # Повторно вызываем инициализацию, которая заново зальет стандартный список оборудования
    init_db()

if __name__ == "__main__":
    init_db()
    print("База данных успешно инициализирована (dict_tspk единый).")