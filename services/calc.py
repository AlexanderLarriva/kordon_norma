"""Сервис расчета оргштатной структуры и норм ТСПК пункта пропуска."""

import math

from services.db import get_connection, get_personnel_dict, get_settings


def _get_multiplier(data: dict, rule_params: dict) -> int:
    """Возвращает множитель для конкретного типа норматива."""
    calculation_type = rule_params.get("_calculation_type")
    if calculation_type == "per_checkpoint":
        return 1
    if calculation_type == "per_shift":
        return 1
    if calculation_type == "per_lane":
        if rule_params.get("lane_scope", "all") == "all":
            return int(data.get("_lanes_total", 0))
        return int(data.get("_lanes_total", 0))
    if calculation_type == "per_cabin":
        direction = rule_params.get("direction")
        if direction == "in":
            return int(data.get("cabins_in", 0))
        if direction == "out":
            return int(data.get("cabins_out", 0))
        return int(data.get("cabins_in", 0)) + int(data.get("cabins_out", 0))
    if calculation_type == "per_direction":
        directions = rule_params.get("directions", ["in", "out"])
        return len(directions)
    if calculation_type in ("per_inspection_group", "per_inspection_personnel"):
        return int(data.get("_inspection_personnel_count", 0))
    if calculation_type == "manual":
        return 0
    # Незнакомый тип не должен незаметно создавать штат.
    raise ValueError(f"Неизвестный тип расчета персонала: {calculation_type}")


def _condition_is_met(condition_key, data: dict) -> bool:
    if not condition_key:
        return True
    if condition_key.startswith("deputies."):
        return bool(data.get("deputies", {}).get(condition_key.split(".", 1)[1], False))
    if condition_key == "has_idk":
        return bool(data.get("has_idk"))
    if condition_key == "has_rpm":
        return bool(data.get("has_rpm"))
    if condition_key == "k9_staff_enabled":
        return data.get("k9_service", "В штате КПП") == "В штате КПП"
    # Неизвестное условие трактуем безопасно: должность не включаем.
    return False


def _lane_counts(data: dict) -> tuple[int, int]:
    """Число полос въезда/выезда с учетом обоих режимов ввода."""
    if data.get("is_mixed_lanes", True):
        return (
            max(0, int(data.get("lanes_mixed_in", 1))),
            max(0, int(data.get("lanes_mixed_out", 1))),
        )
    lanes_in = sum(
        int(data.get(key, 0))
        for key in ("lanes_auto_in", "lanes_truck_in", "lanes_bus_in")
    )
    lanes_out = sum(
        int(data.get(key, 0))
        for key in ("lanes_auto_out", "lanes_truck_out", "lanes_bus_out")
    )
    return lanes_in, lanes_out


def calculate_personnel(data: dict) -> dict:
    """Рассчитывает штат на основе настраиваемого справочника должностей."""
    personnel_items = get_personnel_dict(include_inactive=False)
    shift_count = int(data.get("shift_hours", 3))
    settings = get_settings()
    shift_setting = {
        2: "k_shift_12h",
        3: "k_shift_8h",
        4: "k_shift_24h",
    }
    if shift_count not in shift_setting:
        raise ValueError("Количество смен должно быть 2, 3 или 4.")
    shift_factor = float(settings.get(shift_setting[shift_count], shift_count))

    lanes_in, lanes_out = _lane_counts(data)
    calc_data = {
        **data,
        "_lanes_total": lanes_in + lanes_out,
    }

    # Сначала определяем численность досмотрового состава для зависимых нормативов.
    inspection_per_shift = sum(
        float(item["quantity"])
        * (lanes_in + lanes_out if item["calculation_type"] == "per_lane" else 1)
        for item in personnel_items
        if item["functional_group"] == "vehicle_inspection"
        and _condition_is_met(item["condition_key"], data)
    )
    calc_data["_inspection_personnel_count"] = math.ceil(inspection_per_shift)

    management_rows = []
    duty_rows = []
    shift_total = 0
    management_total = 0
    duty_total = 0
    functional_group_counts = {}
    role_counts = {}

    for item in personnel_items:
        if not _condition_is_met(item["condition_key"], data):
            continue

        calculation_type = item["calculation_type"]
        rule_params = dict(item["rule_params"] or {})
        rule_params["_calculation_type"] = calculation_type

        if calculation_type == "manual":
            in_shift = "-"
            input_key = rule_params.get("input_key")
            total = math.ceil(float(data.get(input_key, 0))) if input_key else 0
        else:
            multiplier = _get_multiplier(calc_data, rule_params)
            per_shift_count = float(item["quantity"]) * multiplier
            in_shift = per_shift_count if item["apply_shift_factor"] else "-"
            total = (
                math.ceil(per_shift_count * shift_factor)
                if item["apply_shift_factor"]
                else math.ceil(per_shift_count)
            )

        if isinstance(in_shift, (int, float)):
            shift_total += in_shift
            functional_group_counts[item["functional_group"]] = (
                functional_group_counts.get(item["functional_group"], 0) + in_shift
            )
        role_counts[item["role_code"]] = {
            "in_shift": in_shift,
            "total": total,
            "functional_group": item["functional_group"],
        }

        row = {
            "category": item["category"],
            "position": item["position_name"],
            "in_shift": (
                str(int(in_shift))
                if isinstance(in_shift, (int, float)) and float(in_shift).is_integer()
                else str(in_shift)
            ),
            "total": total,
            "note": item["note"] or "",
        }

        if item["functional_group"] in ("management", "technical_management"):
            management_rows.append(row)
            management_total += total
        else:
            duty_rows.append(row)
            duty_total += total

    return {
        "management_table": management_rows,
        "duty_table": duty_rows,
        "shift_total": math.ceil(shift_total),
        "total_duty": duty_total,
        "management_count": management_total,
        "total_full_staff": duty_total + management_total,
        "functional_group_counts": functional_group_counts,
        "role_counts": role_counts,
    }


def calculate_tspk(data: dict, personnel_res: dict) -> list[dict]:
    """Расчет потребности и стоимости ТСПК из единой таблицы dict_tspk."""
    settings = get_settings()
    reserve_pct = float(settings.get("reserve_tspk_percent", 0.10))

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT category, equipment_name, selected_model, norm_type, ratio, unit, unit_price_usd, note
            FROM dict_tspk
        """)
        tspk_items = [dict(row) for row in cursor.fetchall()]

    cabins_total = data.get("cabins_in", 0) + data.get("cabins_out", 0)

    # Проверяем режим полос: универсальные или раздельные по видам транспорта
    is_mixed_lanes = data.get("is_mixed_lanes", True)

    if is_mixed_lanes:
        lanes_in = int(data.get("lanes_mixed_in", 1))
        lanes_out = int(data.get("lanes_mixed_out", 1))
    else:
        # Суммируем полосы по всем типам транспорта (легковые, грузовые, автобусы)
        lanes_in = (
            int(data.get("lanes_car_in", 0)) +
            int(data.get("lanes_truck_in", 0)) +
            int(data.get("lanes_bus_in", 0))
        )
        lanes_out = (
            int(data.get("lanes_car_out", 0)) +
            int(data.get("lanes_truck_out", 0)) +
            int(data.get("lanes_bus_out", 0))
        )
        # На случай если ничего не выбрано, ставим минимум 1
        lanes_in = max(lanes_in, 1)
        lanes_out = max(lanes_out, 1)

    lanes_total = lanes_in + lanes_out

    group_counts = personnel_res.get("functional_group_counts", {})
    role_counts = personnel_res.get("role_counts", {})
    pd_personnel_count = group_counts.get("passport_control", 0)
    inspection_personnel_count = group_counts.get("vehicle_inspection", 0)

    # Досмотровые группы считаются по досмотровому составу и часовым у шлагбаума.
    barrier_guards = role_counts.get("barrier_guard", {}).get("total", 0)
    inspection_group_count = inspection_personnel_count + barrier_guards

    final_items = []

    for item in tspk_items:
        equipment_name = item["equipment_name"]

        # Специальные комплексы учитываются только при выборе в исходных данных.
        if equipment_name == "Инспекционно-досмотровый комплекс (ИДК)" and not data.get("has_idk"):
            continue
        if equipment_name == "Радиационные портальные мониторы (РПМ)" and not data.get("has_rpm"):
            continue

        norm_type = item["norm_type"]
        ratio = item["ratio"]
        required = 0
        reserve = 0

        # Обработка правил расчета
        if norm_type == "per_arm":
            required = math.ceil(cabins_total * ratio)
            # Честный расчет 10% резерва с округлением вверх, но минимум 1, если требуется много
            reserve = math.ceil(required * reserve_pct) if required > 0 else 0
        elif norm_type == "per_entry_lane":
            required = math.ceil(lanes_in * ratio)
            reserve = math.ceil(required * reserve_pct) if required > 0 else 0
        elif norm_type == "manual":
            required = int(data.get("manual_auto_cabins", 0))
            reserve = 0
        elif norm_type == "per_workstation":
            required = math.ceil(cabins_total * ratio)
            reserve = math.ceil(required * reserve_pct) if required > 0 else 0
        elif norm_type == "per_spec_room":
            # Количество оборудования зависит от количества комнат специальной проверки
            spec_rooms = int(data.get("spec_rooms_count", 1))
            required = math.ceil(spec_rooms * ratio)
            reserve = 0
            # reserve = math.ceil(required * reserve_pct) if required > 0 else 0
        elif norm_type == "per_controller":
            required = math.ceil(pd_personnel_count * ratio)
            reserve = math.ceil(required * reserve_pct) if required > 0 else 0
        elif norm_type == "per_lane":
            required = math.ceil(lanes_total * ratio)
            reserve = math.ceil(required * reserve_pct) if required > 0 else 0
        elif norm_type in ("per_site", "per_checkpoint"):
            required = math.ceil(1 * ratio)
            reserve = 0
        elif norm_type == "per_idk":
            if data.get("has_idk"):
                required = math.ceil(1 * ratio)
            reserve = 0
        elif norm_type == "per_inspection_group":
            required = math.ceil(inspection_group_count * ratio)
            reserve = math.ceil(required * reserve_pct) if required > 0 else 0
        elif norm_type == "per_inspection_personnel":
            required = math.ceil(inspection_personnel_count * ratio)
            reserve = math.ceil(required * reserve_pct) if required > 0 else 0
        elif norm_type == "per_outdoor_personnel":
            outdoor_count = inspection_personnel_count + barrier_guards
            required = math.ceil(outdoor_count * ratio)
            reserve = math.ceil(required * reserve_pct) if required > 0 else 0
        elif norm_type == "per_lane_barriers":
            required = math.ceil(lanes_total * ratio)
            reserve = math.ceil(required * reserve_pct) if required > 0 else 0

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
