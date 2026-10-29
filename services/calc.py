"""Сервис расчета оргштатной структуры и норм ТСПК пункта пропуска."""

import math

from services.db import get_connection, get_settings


def calculate_personnel(data: dict) -> dict:
    """Расчет оргштатной структуры и сменного состава."""
    cabins_in = data.get("cabins_in", 0)
    cabins_out = data.get("cabins_out", 0)
    shift_hours = data.get("shift_hours", 12)
    # category = data.get("capacity_category", "")

    # Загружаем коэффициенты сменности
    settings = get_settings()
    if shift_hours == 12:
        k_shift = float(settings.get("k_shift_12h", 4.0))
    elif shift_hours == 8:
        k_shift = float(settings.get("k_shift_8h", 3.0))
    else:
        k_shift = float(settings.get("k_shift_24h", 4.0))

    # 1. Руководство (постоянный и перспективный штат)
    # 1. Руководство КПП (формируется на основе выбранных в UI чекбоксов)
    management_rows = [
        {"category": "Руководство КПП", "position": "Начальник КПП", "in_shift": "-", "total": 1, "note": "Постоянный штат"},
    ]

    # Извлекаем состояние чекбоксов руководства
    deputies = data.get("deputies", {})

    if deputies.get("deputy_general", True):
        management_rows.append({"category": "Руководство КПП", "position": "Заместитель начальника КПП", "in_shift": "-", "total": 1, "note": "Штатная должность"})

    if deputies.get("deputy_political", False):
        management_rows.append({"category": "Руководство КПП", "position": "Заместитель по воспитательной работе", "in_shift": "-", "total": 1, "note": "Штатная должность"})

    if deputies.get("deputy_tspk", False):
        management_rows.append({"category": "Руководство КПП", "position": "Заместитель по ТСПК", "in_shift": "-", "total": 1, "note": "Штатная должность"})

    if deputies.get("deputy_operational", False):
        management_rows.append({"category": "Руководство КПП", "position": "Заместитель по оперативной деятельности", "in_shift": "-", "total": 1, "note": "Штатная должность"})

    # 2. Состав смены (Инженер ТСПК/АСПК присутствует ВСЕГДА)
    shift_positions = [
        ("Управление смены", "Старший смены (ССПН)", 1, "Офицерский состав"),
        ("Управление смены", "Дежурный по КПП (ДЖ)", 1, "Суточный наряд"),
        ("Управление смены", "Инженер ТСПК/АСПК", 1, "Техническое обслуживание ТСПК и АСПК"),
    ]

    # Паспортный контроль
    shift_positions.append(("Паспортный контроль", "Проверка документов (ПД) (Въезд)", cabins_in, f"По 1 чел. на {cabins_in} кабин"))
    shift_positions.append(("Паспортный контроль", "Проверка документов (ПД) (Выезд)", cabins_out, f"По 1 чел. на {cabins_out} кабин"))

    # Режим и досмотр
    shift_positions.append(("Режимная служба", "Часовой у шлагбаума (ЧШ)", 2, "1 на въезд, 1 на выезд"))
    shift_positions.append(("Досмотровый наряд", "Осмотр ТС (ОТС)", 2, "Досмотр легковых/грузовых ТС"))

    # Кинологическое обеспечение
    k9_mode = data.get("k9_service", "В штате КПП")
    if k9_mode == "В штате КПП":
        shift_positions.append(("Кинологическая служба", "Инспектор-кинолог", 1, "Поиск ВВ, оружия и НС"))
    elif k9_mode == "Приданные силы":
        # Если приданные силы, можно выводить сноску или учитывать без увеличения штатной численности КПП
        pass

    # Специальные комплексы
    if data.get("has_rpm"):
        shift_positions.append(("Спец. контроль", "Оператор РПМ (ОРПМ)", 2, "1 въезд, 1 выезд"))

    if data.get("has_idk"):
        shift_positions.append(("Спец. контроль", "Оператор ИДК", 1, "Прицепной / мобильный ИДК"))
        shift_positions.append(("Спец. контроль", "Инспектор ИДК", 2, "Физический досмотр"))

    # Итоговый расчет сменного состава
    duty_rows = []
    total_shift_people = 0

    for cat, pos, count_in_shift, note in shift_positions:
        total_staff_pos = math.ceil(count_in_shift * k_shift)
        total_shift_people += count_in_shift
        duty_rows.append({
            "category": cat,
            "position": pos,
            "in_shift": str(count_in_shift),
            "total": total_staff_pos,
            "note": note,
        })

    total_management = sum(r["total"] for r in management_rows)
    total_duty_staff = sum(r["total"] for r in duty_rows)

    return {
        "management_table": management_rows,
        "duty_table": duty_rows,
        "shift_total": total_shift_people,
        "total_duty": total_duty_staff,
        "management_count": total_management,
        "total_full_staff": total_duty_staff + total_management,
    }


def calculate_tspk(data: dict, personnel_res: dict) -> list[dict]:
    """Расчет потребности и стоимости ТСПК из единой таблицы dict_tspk."""
    settings = get_settings()
    reserve_pct = float(settings.get("reserve_tspk_percent", 0.10))

    tspk_items = []
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT category, equipment_name, selected_model, norm_type, ratio, unit, unit_price_usd, note 
                FROM dict_tspk
            """)
            tspk_items = [dict(row) for row in cursor.fetchall()]
    except Exception:
        pass

    cabins_total = data.get("cabins_in", 0) + data.get("cabins_out", 0)
    lanes_in = data.get("lanes_truck_in", 1)
    lanes_out = data.get("lanes_truck_out", 1)
    lanes_total = lanes_in + lanes_out

    duty_table = personnel_res.get("duty_table", [])
    pd_personnel_count = sum(
        int(r["in_shift"]) for r in duty_table if "Проверка документов" in r["position"] and str(r["in_shift"]).isdigit()
    )
    inspection_personnel_count = sum(
        int(r["in_shift"]) for r in duty_table if ("Осмотр ТС" in r["position"] or "Часовой" in r["position"]) and str(r["in_shift"]).isdigit()
    )
    
    # Количество досмотровых групп (по числу личного состава ОТС в смене, минимум 1)
    inspection_group_count = inspection_personnel_count if inspection_personnel_count > 0 else 1

    final_items = []

    for item in tspk_items:
        norm_type = item["norm_type"]
        ratio = item["ratio"]
        required = 0
        reserve = 0

        # Обработка правил расчета
        if norm_type == "per_arm":
            required = math.ceil(cabins_total * ratio)
            reserve = math.ceil(required * reserve_pct) if required > 0 else 0
        elif norm_type == "per_entry_lane":
            required = math.ceil(lanes_in * ratio)
        elif norm_type == "manual":
            # Ручной ввод через UI (если значение не задано, по умолчанию 1 или 0)
            required = int(data.get(item["equipment_name"], 1))
        elif norm_type == "per_workstation":
            required = math.ceil(cabins_total * ratio)
        elif norm_type == "per_spec_room":
            required = 1 if cabins_total > 0 else 0
        elif norm_type == "per_controller":
            required = math.ceil(pd_personnel_count * ratio)
            reserve = 2 if required > 0 else 0
        elif norm_type == "per_lane":
            required = math.ceil(lanes_total * ratio)
        elif norm_type in ("per_site", "per_checkpoint"):
            required = math.ceil(1 * ratio)
        elif norm_type == "per_idk":
            if data.get("has_idk"):
                required = math.ceil(1 * ratio)
        elif norm_type == "per_inspection_group":
            required = math.ceil(inspection_group_count * ratio)
        elif norm_type == "per_inspection_personnel":
            required = math.ceil(inspection_personnel_count * ratio)
            reserve = 1 if required > 0 else 0
        elif norm_type == "per_outdoor_personnel":
            outdoor_count = inspection_personnel_count + 2
            required = math.ceil(outdoor_count * ratio)
        elif norm_type == "per_lane_barriers":
            required = math.ceil(lanes_total * ratio)

        total_qty = required + reserve
        unit_price = float(item["unit_price_usd"])
        total_price = total_qty * unit_price

        # Выводим позицию, если есть потребность либо если это ручной ввод
        if total_qty > 0 or norm_type == "manual":
            final_items.append({
                "category": item["category"],
                "name": item["equipment_name"],
                "selected_model": item["selected_model"],
                "required": required,
                "reserve": reserve,
                "total": total_qty,
                "unit": item["unit"],
                "unit_price": unit_price,
                "total_price": total_price,
                "note": item["note"],
            })

    return final_items