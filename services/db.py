"""Модуль работы с базой данных SQLite для АС «Кордон – Норма»."""

import json
import sqlite3

DB_PATH = "database.db"


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
        cursor.execute("SELECT COUNT(*) FROM dict_tspk")
        if cursor.fetchone()[0] == 0:
            default_tspk = [
                (
                    "Паспортный контроль",
                    "Прибор контроля подлинности документов (типа «Регула»)",
                    "Регула 4305",
                    "per_arm",
                    1.0,
                    "шт.",
                    1350.0,
                    "1:1 к АРМ ПД",
                ),
                (
                    "Паспортный контроль",
                    "Прибор спецпроверки (микроскоп/компаратор)",
                    "Регула 5001M",
                    "per_spec_room",
                    1.0,
                    "компл.",
                    3900.0,
                    "1:1 к комнатам спецпроверки",
                ),
                (
                    "Паспортный контроль",
                    "Дата-штамп",
                    "Датер стандартный",
                    "per_pd_personnel",
                    1.0,
                    "шт.",
                    55.0,
                    "1:1 к штату контролеров ПД",
                ),
                (
                    "Досмотровые средства",
                    "Переносной автомобильный комплект («Гастроль-П»)",
                    "Гастроль-П",
                    "per_lane",
                    1.0,
                    "компл.",
                    1050.0,
                    "1:1 к полосам движения",
                ),
                (
                    "Досмотровые средства",
                    "Комплект досмотровых зеркал («Поиск»)",
                    "Поиск-2",
                    "per_site",
                    2.0,
                    "компл.",
                    390.0,
                    "2 комплекта на досмотровую площадку",
                ),
                (
                    "Досмотровые средства",
                    "Досмотровый телевизионный эндоскоп («Регула-3002»)",
                    "Регула 3002M",
                    "per_site",
                    1.0,
                    "шт.",
                    2350.0,
                    "1:1 на площадку / бокс ДТС",
                ),
                (
                    "Досмотровые средства",
                    "Детектор взрывчатых и наркотических веществ",
                    "Кербер-2",
                    "per_checkpoint",
                    1.0,
                    "компл.",
                    9400.0,
                    "1 на АПП",
                ),
                (
                    "Досмотровые средства",
                    "Технологическое оборудование ИДК",
                    "СТ-2630T",
                    "per_idk",
                    1.0,
                    "компл.",
                    500000.0,
                    "При наличии ИДК на АПП",
                ),
                (
                    "Спецсредства",
                    "Ручной металлоискатель",
                    "Сфинкс ВМ-611",
                    "per_inspection_personnel",
                    1.0,
                    "шт.",
                    165.0,
                    "1:1 на контролеров ОТС/ДТС и ЧШ в смене",
                ),
                (
                    "Спецсредства",
                    "Устройство принудительной остановки автотранспорта («Гарпун»)",
                    "Гарпун-4М",
                    "per_barrier_lane",
                    1.0,
                    "компл.",
                    500.0,
                    "1:1 к полосам с шлагбаумами",
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
                ("k_shift_12h", "4.0", "Коэффициент сменности 12ч"),
                ("k_shift_8h", "3.0", "Коэффициент сменности 8ч"),
                ("k_shift_24h", "4.0", "Коэффициент сменности 24ч"),
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

if __name__ == "__main__":
    init_db()
    print("База данных успешно инициализирована (dict_tspk единый).")