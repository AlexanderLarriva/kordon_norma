import sqlite3

DB_NAME = "kordon_norma.db"

def get_connection():
    return sqlite3.connect(DB_NAME)

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # Таблица 1. Классы ТСПК (нормативные группы)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dict_tspk_classes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            class_name TEXT NOT NULL UNIQUE,
            norm_type TEXT NOT NULL,
            ratio REAL NOT NULL,
            unit TEXT NOT NULL,
            note TEXT
        )
    """)

    # Таблица 2. Конкретные модели оборудования
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dict_tspk_models (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_id INTEGER NOT NULL,
            model_name TEXT NOT NULL,
            manufacturer TEXT,
            FOREIGN KEY (class_id) REFERENCES dict_tspk_classes (id) ON DELETE CASCADE
        )
    """)

    # Таблица 3. Системные настройки (пароли и т.д.)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('admin_password', 'admin123')")

    # Таблица 4. История расчетов
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS calculation_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            app_name TEXT,
            app_code TEXT,
            category TEXT,
            input_params TEXT,
            results_json TEXT
        )
    """)

    # Сидирование начальных данных (если таблица пуста)
    cursor.execute("SELECT COUNT(*) FROM dict_tspk_classes")
    if cursor.fetchone()[0] == 0:
        seed_tspk_data(cursor)

    conn.commit()
    conn.close()


def seed_tspk_data(cursor):
    """Первоначальное наполнение классификатором ТСПК и базовыми моделями."""
    classes_data = [
        # Паспортный контроль
        ("Технические средства паспортного контроля", "Автоматизированные системы пограничного контроля (АСПК)", "per_checkpoint", 1.0, "комплекс", "При наличии условий"),
        ("Технические средства паспортного контроля", "Технические средства общей проверки документов", "per_arm", 1.0, "комплект", "1 на кабин/АРМ ПД"),
        ("Технические средства паспортного контроля", "Технические средства специальной проверки документов", "per_site", 1.0, "комплект", "1 на комнату спецпроверки"),
        ("Технические средства паспортного контроля", "Средства простановки оттисков дата-штампов", "per_arm", 1.0, "шт.", "по числу контролеров ПД"),

        # Досмотр ТС и грузов + РПМ/ИДК
        ("Средства досмотра ТС и грузов", "Инспекционно-досмотровые комплексы (ИДК)", "per_checkpoint", 1.0, "комплекс", "При наличии ИДК"),
        ("Средства досмотра ТС и грузов", "Радиационные портальные мониторы (РПМ)", "per_site", 1.0, "комплекс", "На въезд/выезд полос"),
        ("Средства досмотра ТС и грузов", "Приборы для обнаружения тайников в ТС", "per_site", 1.0, "шт.", "1 на досмотровую площадку"),
        ("Средства досмотра ТС и грузов", "Комплекты досмотровой техники и специнструмента", "per_site", 1.0, "комплект", "1 на площадку/бокс"),
        ("Средства досмотра ТС и грузов", "Досмотровые телевизионные приборы", "per_site", 1.0, "шт.", "1 на площадку осмотра"),
        ("Средства досмотра ТС и грузов", "Эндоскопы", "per_site", 1.0, "шт.", "1 на бокс ДТС"),
        ("Средства досмотра ТС и грузов", "Фонари досмотровые", "per_personnel", 1.0, "шт.", "На каждого контролера смены"),
        ("Средства досмотра ТС и грузов", "Щупы досмотровые", "per_site", 2.0, "шт.", "2 на площадку"),

        # Обнаружение оружия, ВВ и НВ
        ("Средства обнаружения оружия, ВВ и НВ", "Ручные металлоискатели", "per_arm", 1.0, "шт.", "1 на пост/кабину"),
        ("Средства обнаружения оружия, ВВ и НВ", "Стационарные металлоискатели", "per_checkpoint", 2.0, "комплект", "Вход/выход пешеходки"),
        ("Средства обнаружения оружия, ВВ и НВ", "Переносные детекторы ВВ и НВ", "per_site", 1.0, "шт.", "1 на площадку спецдосмотра"),
        ("Средства обнаружения оружия, ВВ и НВ", "Тесты по обнаружению наркотических веществ", "per_checkpoint", 10.0, "комплект", "Расходный норматив"),

        # Аудио, видео, фото
        ("Средства аудио, видео и фото документирования", "Фотоаппараты и средства фотопечати", "per_checkpoint", 1.0, "комплект", "1 на КПП"),
        ("Средства аудио, видео и фото документирования", "Диктофоны", "per_site", 1.0, "шт.", "1 на комнату спецпроверки"),

        # Оборудование и принудительная остановка
        ("Средства обеспечения, технологическое оборудование", "Средства принудительной остановки автотранспорта", "per_site", 2.0, "комплект", "Въезд / выезд КПП"),
        ("Средства обеспечения, технологическое оборудование", "Автоматические шлагбаумы", "per_site", 1.0, "шт.", "На полосу движения"),

        # Учебное оборудование
        ("Специальные технические средства обучения", "Атласы паспортов (включая электронные)", "per_arm", 1.0, "шт./лицензия", "1 на АРМ ПД")
    ]
    
    for cat, name, ntype, ratio, unit, note in classes_data:
        cursor.execute("""
            INSERT INTO dict_tspk_classes (category, class_name, norm_type, ratio, unit, note)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (cat, name, ntype, ratio, unit, note))

    cursor.execute("SELECT id, class_name FROM dict_tspk_classes")
    classes_dict = {row[1]: row[0] for row in cursor.fetchall()}

    models_data = [
        (classes_dict["Технические средства специальной проверки документов"], "Регула 4305"),
        (classes_dict["Технические средства специальной проверки документов"], "ST-30 (Газпром)"),
        (classes_dict["Технические средства специальной проверки документов"], "Ультрамаг-A6"),
        (classes_dict["Эндоскопы"], "Каскад-2"),
        (classes_dict["Эндоскопы"], "ЭТ-230"),
        (classes_dict["Ручные металлоискатели"], "СФИНКС ВМ-611"),
        (classes_dict["Ручные металлоискатели"], "Garrett Super Scanner"),
        (classes_dict["Радиационные портальные мониторы (РПМ)"], "Янтарь-1П"),
        (classes_dict["Инспекционно-досмотровые комплексы (ИДК)"], "С T-SCAN"),
    ]

    for class_id, m_name in models_data:
        cursor.execute("INSERT INTO dict_tspk_models (class_id, model_name) VALUES (?, ?)", (class_id, m_name))


def get_tspk_classes():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, category, class_name, norm_type, ratio, unit, note FROM dict_tspk_classes ORDER BY category, class_name")
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_models_by_class(class_id: int) -> list[str]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT model_name FROM dict_tspk_models WHERE class_id = ?", (class_id,))
    rows = cursor.fetchall()
    conn.close()
    return [r[0] for r in rows]

def get_admin_password():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = 'admin_password'")
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else "admin123"

def set_admin_password(new_password):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE settings SET value = ? WHERE key = 'admin_password'", (new_password,))
    conn.commit()
    conn.close()

def save_calculation(app_name, app_code, category, input_params, results_json):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO calculation_history (app_name, app_code, category, input_params, results_json)
        VALUES (?, ?, ?, ?, ?)
    """, (app_name, app_code, category, str(input_params), str(results_json)))
    conn.commit()
    conn.close()

def get_calculation_history():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, created_at, app_name, app_code, category FROM calculation_history ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return rows