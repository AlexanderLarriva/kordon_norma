"""Тесты расчета персонала и привязки ТСПК к функциональным группам."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from services import calc, db


class CalculationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.db_path_patcher = patch.object(
            db, "DB_PATH", Path(self.temp_dir.name) / "calculation_test.db"
        )
        self.db_path_patcher.start()
        self.addCleanup(self.db_path_patcher.stop)
        db.init_db()

    def base_data(self):
        return {
            "shift_hours": 3,
            "cabins_in": 2,
            "cabins_out": 2,
            "is_mixed_lanes": True,
            "lanes_mixed_in": 1,
            "lanes_mixed_out": 1,
            "has_idk": True,
            "has_rpm": True,
            "k9_service": "В штате КПП",
            "deputies": {
                "deputy_general": True,
                "deputy_political": False,
                "deputy_tspk": True,
                "deputy_operational": True,
            },
        }

    def test_personnel_is_calculated_from_dictionary(self):
        result = calc.calculate_personnel(self.base_data())
        rows = result["management_table"] + result["duty_table"]
        by_position = {row["position"]: row for row in rows}

        self.assertEqual(by_position["Начальник КПП"]["total"], 1)
        self.assertEqual(by_position["Инженер по ТСПК"]["total"], 2)
        self.assertEqual(by_position["Старший техник ТСПК"]["in_shift"], "2.0")
        self.assertEqual(by_position["Проверка документов (ПД), въезд"]["in_shift"], "2.0")
        self.assertEqual(by_position["Оператор РПМ"]["in_shift"], "2.0")
        self.assertEqual(by_position["Инспектор ИДК"]["in_shift"], "2.0")
        self.assertEqual(result["functional_group_counts"]["passport_control"], 4.0)
        self.assertEqual(result["functional_group_counts"]["vehicle_inspection"], 6.0)

    def test_disabled_and_conditioned_positions_are_excluded(self):
        data = self.base_data()
        data.update({
            "has_idk": False,
            "has_rpm": False,
            "k9_service": "Приданные силы",
            "deputies": {
                "deputy_general": False,
                "deputy_political": False,
                "deputy_tspk": False,
                "deputy_operational": False,
            },
        })
        result = calc.calculate_personnel(data)
        positions = {
            row["position"]
            for row in result["management_table"] + result["duty_table"]
        }

        self.assertNotIn("Оператор РПМ", positions)
        self.assertNotIn("Оператор ИДК", positions)
        self.assertNotIn("Инспектор ИДК", positions)
        self.assertNotIn("Инспектор-кинолог", positions)
        self.assertNotIn("Заместитель начальника КПП", positions)

    def test_custom_position_name_does_not_change_tspk_norms(self):
        data = self.base_data()
        original_personnel = calc.calculate_personnel(data)
        original_tspk = calc.calculate_tspk(data, original_personnel)

        items = db.get_personnel_dict()
        for item in items:
            if item["role_code"] == "document_control_in":
                item["position_name"] = "Совершенно другое название"
            if item["role_code"] == "vehicle_inspection_junior":
                item["position_name"] = "Новая должность досмотра"
        db.save_personnel_dict(items)

        changed_personnel = calc.calculate_personnel(data)
        changed_tspk = calc.calculate_tspk(data, changed_personnel)

        self.assertEqual(
            [(item["name"], item["required"]) for item in original_tspk],
            [(item["name"], item["required"]) for item in changed_tspk],
        )
        self.assertEqual(
            original_personnel["functional_group_counts"],
            changed_personnel["functional_group_counts"],
        )

    def test_specialized_positions_follow_equipment_conditions(self):
        data = self.base_data()
        data["has_idk"] = False
        data["has_rpm"] = False
        personnel = calc.calculate_personnel(data)
        tspk = calc.calculate_tspk(data, personnel)
        equipment_names = {item["name"] for item in tspk}

        self.assertNotIn("Инспекционно-досмотровый комплекс (ИДК)", equipment_names)
        self.assertNotIn("Радиационные портальные мониторы (РПМ)", equipment_names)


if __name__ == "__main__":
    unittest.main()
