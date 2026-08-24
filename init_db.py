import sqlite3

DB_NAME = "database.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # 1. Таблица глобальных настроек
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS dict_settings (
            key TEXT PRIMARY KEY,
            value REAL NOT NULL,
            description TEXT
        )
    ''')

    # 2. Таблица нормативов ТСПК
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS dict_tspk (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            equipment_name TEXT NOT NULL,
            norm_type TEXT NOT NULL, 
            ratio REAL NOT NULL,
            unit TEXT NOT NULL,
            note TEXT
        )
    ''')

    # 3. НОВАЯ ТАБЛИЦА: Справочник должностей и нарядов КПП
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS dict_roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role_name TEXT NOT NULL,
            category TEXT NOT NULL, -- 'leadership' (Руководство) или 'shift' (Смена)
            condition_type TEXT NOT NULL, -- 'mandatory', 'tspk_complex', 'high_category', 'idk', 'rpm', 'k9', 'per_post'
            multiplier REAL DEFAULT 1.0,
            is_active_for_total BOOLEAN DEFAULT 1, -- 0 для справочных нарядов (8-10)
            note TEXT
        )
    ''')

    # 4. Таблица истории расчетов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS calculation_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            app_name TEXT NOT NULL,
            app_code TEXT,
            category TEXT,
            input_json TEXT NOT NULL,
            result_json TEXT NOT NULL
        )
    ''')

    # Глобальные коэффициенты
    settings_data = [
        ('k_shift_12h', 4.0, 'Коэффициент смен для 12-часового графика (4 смены)'),
        ('k_shift_8h', 3.0, 'Коэффициент смен для 8-часового графика (3 смены)'),
        ('k_shift_24h', 4.0, 'Коэффициент смен для 24-часового графика (4 смены)'),
        ('k_substitute_default', 1.15, 'Коэффициент подмены по умолчанию (1.15)'),
        ('reserve_tspk_percent', 0.10, 'Процент неприкосновенного запаса ТСПК (10%)')
    ]
    cursor.executemany('INSERT OR REPLACE INTO dict_settings VALUES (?, ?, ?)', settings_data)

    # Заполнение справочника должностей (Руководство и Смена)
    roles_data = [
        # Руководящий состав
        ('Начальник КПП', 'leadership', 'mandatory', 1.0, 1, 'Обязательная единица'),
        ('Заместитель начальника КПП', 'leadership', 'mandatory', 1.0, 1, 'Обязательная единица'),
        ('Заместитель по ТСПК', 'leadership', 'tspk_complex', 1.0, 1, 'При наличии комплекса ТСПК/АСПК'),
        ('Заместитель по оперативной деятельности', 'leadership', 'high_category', 1.0, 1, 'При высокой категории АПП'),

        # Состав смены
        ('Старший смены (ССПН)', 'shift', 'mandatory', 1.0, 1, '1 в смену'),
        ('Инженер ТСПК/АСПК', 'shift', 'tspk_complex', 1.0, 1, 'При наличии комплекса ТСПК/АСПК'),
        ('Дежурный по КПП (ДЖ)', 'shift', 'mandatory', 1.0, 1, '1 в смену'),
        ('Оператор комплекса ТСПК (ОКТСПК)', 'shift', 'tspk_complex', 1.0, 1, 'При наличии комплекса ТСПК/АСПК'),
        ('Оператор РПМ (ОРПМ)', 'shift', 'rpm', 2.0, 1, 'По 1 на направление (въезд/выезд)'),
        ('Часовой у шлагбаума (ЧШ)', 'shift', 'barriers', 1.0, 1, 'На каждый пост шлагбаума'),
        ('Проверка документов (ПД)', 'shift', 'pd_posts', 1.0, 1, 'На каждую кабину/АРМ ПД'),
        ('Осмотр ТС (ОТС)', 'shift', 'inspection_sites', 2.0, 1, 'По 2 чел. на досмотровую площадку'),
        ('Досмотр ТС в боксах (ДТС)', 'shift', 'dts_boxes', 2.0, 1, 'По 2 чел. на бокс ДТС'),
        ('Инспектор-кинолог', 'shift', 'k9', 1.0, 1, 'При наличии кинологической службы'),
        ('Оператор ИДК', 'shift', 'idk', 1.0, 1, 'При наличии ИДК'),
        ('Инспектор ИДК', 'shift', 'idk', 2.0, 1, 'При наличии ИДК'),

        # Справочные наряды (8-10) - is_active_for_total = 0
        ('Сопровождение ТС (СТС)', 'shift', 'manual_input', 0.0, 0, 'Справочно (не входит в расчет)'),
        ('Наблюдение за ТС (НТС)', 'shift', 'manual_input', 0.0, 0, 'Справочно (не входит в расчет)'),
        ('Дозор (Д)', 'shift', 'manual_input', 0.0, 0, 'Справочно (не входит в расчет)')
    ]

    cursor.execute("DELETE FROM dict_roles")
    cursor.executemany('''
        INSERT INTO dict_roles (role_name, category, condition_type, multiplier, is_active_for_total, note)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', roles_data)

    # Нормы ТСПК
    tspk_data = [
        ('Паспортный контроль', 'АРМ Контролера (ПК + ИБП)', 'per_arm', 1.0, 'компл.', '1:1 к кабинам/АРМ ПД'),
        ('Паспортный контроль', 'Оптический сканер паспортов и виз', 'per_arm', 1.0, 'шт.', '1:1 к АРМ ПД'),
        ('Паспортный контроль', 'Прибор контроля подлинности документов (типа «Регула»)', 'per_arm', 1.0, 'шт.', '1:1 к АРМ ПД'),
        ('Паспортный контроль', 'Прибор спецпроверки (микроскоп/компаратор)', 'per_spec_room', 1.0, 'компл.', '1:1 к комнатам спецпроверки'),
        ('Паспортный контроль', 'Дата-штамп', 'per_pd_personnel', 1.0, 'шт.', '1:1 к штату контролеров ПД'),
        ('Досмотровые средства', 'Переносной автомобильный комплект («Гастроль-П»)', 'per_lane', 1.0, 'компл.', '1:1 к полосам движения'),
        ('Досмотровые средства', 'Комплект досмотровых зеркал («Поиск»)', 'per_site', 2.0, 'компл.', '2 комплекта на досмотровую площадку'),
        ('Досмотровые средства', 'Досмотровый телевизионный эндоскоп («Регула-3002»)', 'per_site', 1.0, 'шт.', '1:1 на площадку / бокс ДТС'),
        ('Досмотровые средства', 'Детектор взрывчатых и наркотических веществ', 'per_checkpoint', 1.0, 'компл.', '1 на АПП'),
        ('Досмотровые средства', 'Технологическое оборудование ИДК', 'per_idk', 1.0, 'компл.', 'При наличии ИДК на АПП'),
        ('Спецсредства', 'Ручной металлоискатель', 'per_inspection_personnel', 1.0, 'шт.', '1:1 на контролеров ОТС/ДТС и ЧШ в смене'),
        ('Спецсредства', 'Устройство принудительной остановки автотранспорта («Гарпун»)', 'per_barrier_lane', 1.0, 'компл.', '1:1 к полосам с шлагбаумами')
    ]

    cursor.execute("DELETE FROM dict_tspk")
    cursor.executemany('''
        INSERT INTO dict_tspk (category, equipment_name, norm_type, ratio, unit, note)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', tspk_data)

    conn.commit()
    conn.close()
    print("База данных 'database.db' инициализирована!")

if __name__ == "__main__":
    init_db()