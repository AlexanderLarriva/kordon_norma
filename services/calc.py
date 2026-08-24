import math

from services.db import get_models_by_class, get_tspk_classes


def calculate_personnel(data: dict) -> dict:
    # (Логика расчета штата остается прежней)
    total_pd = data.get("pd_cabins_pedestrian", 0) + data.get("pd_cabins_auto", 0)
    total_lanes = (
        data.get("lanes_auto_in", 0) + data.get("lanes_auto_out", 0) +
        data.get("lanes_truck_in", 0) + data.get("lanes_truck_out", 0) +
        data.get("lanes_bus_in", 0) + data.get("lanes_bus_out", 0)
    )
    total_inspection = data.get("inspection_sites_in", 0) + data.get("inspection_sites_out", 0)

    shift_duty = {
        "Старший смены КПП": 1,
        "Помощник старшего смены": 1 if data.get("is_high_category") else 0,
        "Контролер ПД (кабины/АРМ)": total_pd,
        "Контролер спецпроверки": data.get("spec_rooms", 0),
        "Часовой у шлагбаума": data.get("barriers_in", 0) + data.get("barriers_out", 0),
        "Проверка документов на полосах": total_lanes,
        "Осмотр ТС (ОТК)": total_inspection,
        "Досмотр ТС в боксах (ДТС)": data.get("dts_boxes", 0),
        "Инспектор-кинолог": 1 if data.get("has_k9") else 0,
        "Оператор ИДК": 2 if data.get("has_idk") else 0,
        "Инспектор ИДК": 2 if data.get("has_idk") else 0,
    }

    per_shift = sum(shift_duty.values())
    k_shift = 4 if data.get("shift_type") in ["12h", "24h"] else 3
    k_sub = data.get("k_substitute", 1.15)
    
    total_operational = math.ceil(per_shift * k_shift * k_sub)
    leadership = {
        "Начальник КПП": 1,
        "Заместитель начальника КПП": 1,
        "Начальник отделения ТСПК": 1 if data.get("has_tspk_complex") else 0,
    }
    total_leadership = sum(leadership.values())
    
    return {
        "leadership": leadership,
        "shift_duty": shift_duty,
        "total_per_shift": per_shift,
        "total_operational": total_operational,
        "total_leadership": total_leadership,
        "total_full_staff": total_operational + total_leadership,
    }


def calculate_tspk(data: dict, personnel_res: dict) -> list:
    """Расчет потребности ТСПК по классам оборудования с возможностью выбора моделей."""
    classes = get_tspk_classes()
    total_pd = data.get("pd_cabins_pedestrian", 0) + data.get("pd_cabins_auto", 0)
    total_inspection = data.get("inspection_sites_in", 0) + data.get("inspection_sites_out", 0)
    total_lanes = (
        data.get("lanes_auto_in", 0) + data.get("lanes_auto_out", 0) +
        data.get("lanes_truck_in", 0) + data.get("lanes_truck_out", 0)
    )
    total_staff = personnel_res.get("total_full_staff", 0)

    result = []
    for row in classes:
        class_id, category, class_name, norm_type, ratio, unit, note = row

        # Фильтрация по наличию спецсистем
        if "ИДК" in class_name and not data.get("has_idk"):
            continue
        if "РПМ" in class_name and not data.get("has_rpm"):
            continue

        # Расчет нормы
        if norm_type == "per_checkpoint":
            base_count = ratio
        elif norm_type == "per_arm":
            base_count = total_pd * ratio
        elif norm_type == "per_site":
            if "РПМ" in class_name or "принудительной" in class_name:
                base_count = total_lanes * ratio
            elif "специальной проверки" in class_name:
                base_count = data.get("spec_rooms", 0) * ratio
            elif "Эндоскопы" in class_name:
                base_count = data.get("dts_boxes", 0) * ratio
            else:
                base_count = total_inspection * ratio
        elif norm_type == "per_personnel":
            base_count = personnel_res.get("total_per_shift", 0) * ratio
        else:
            base_count = 1.0

        base_count = math.ceil(base_count)
        reserve = math.ceil(base_count * 0.10)  # 10% НЗ
        total_required = base_count + reserve

        # Получаем список доступных брендов/моделей для этого класса
        available_models = get_models_by_class(class_id)

        result.append({
            "class_id": class_id,
            "category": category,
            "class_name": class_name,
            "base_count": base_count,
            "reserve": reserve,
            "total_required": total_required,
            "unit": unit,
            "available_models": available_models,
            "note": note
        })

    return result