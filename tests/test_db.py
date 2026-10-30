"""Автоматические тесты SQLite-хранилища.

Запуск из корня проекта:
    python -m unittest discover -s tests -v

Все тесты используют временную БД и не затрагивают рабочую database.db.
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from services import db


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

        self.db_path = Path(self.temp_dir.name) / "test_database.db"
        self.db_path_patcher = patch.object(db, "DB_PATH", self.db_path)
        self.db_path_patcher.start()
        self.addCleanup(self.db_path_patcher.stop)

        db.init_db()

    def test_init_creates_tables_and_default_data(self):
        with db.get_connection() as conn:
            tables = {
                row["name"]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }

        self.assertTrue(
            {"dict_tspk", "dict_personnel", "dict_settings", "calculation_history"}.issubset(tables)
        )
        self.assertGreater(len(db.get_tspk_dict()), 0)

        settings = db.get_settings()
        self.assertIn("k_shift_12h", settings)
        self.assertIn("k_shift_8h", settings)
        self.assertIn("k_shift_24h", settings)

    def test_repeated_init_preserves_custom_dictionary_and_history(self):
        equipment = db.get_tspk_dict()
        original_count = len(equipment)
        equipment[0]["selected_model"] = "ТЕСТОВАЯ МОДЕЛЬ"
        db.save_tspk_dict(pd.DataFrame(equipment))

        calculation_id = db.save_calculation(
            "Тестовое приложение",
            "TEST-01",
            "Тестовая категория",
            {"shift_hours": 3},
            {"personnel": 12},
        )

        db.init_db()

        updated_equipment = db.get_tspk_dict()
        self.assertEqual(len(updated_equipment), original_count)
        self.assertEqual(updated_equipment[0]["selected_model"], "ТЕСТОВАЯ МОДЕЛЬ")

        history = db.get_calculation_history()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["id"], calculation_id)
        self.assertEqual(history[0]["input_params"], {"shift_hours": 3})
        self.assertEqual(history[0]["results"], {"personnel": 12})

    def test_save_and_read_calculation(self):
        calculation_id = db.save_calculation(
            "Паспортный контроль",
            "PK-01",
            "Основной расчет",
            {"checkpoint": "Тестовый КПП", "shift_hours": 2},
            {"personnel": 8},
        )

        history = db.get_calculation_history()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["id"], calculation_id)
        self.assertEqual(history[0]["app_name"], "Паспортный контроль")
        self.assertEqual(history[0]["input_params"]["checkpoint"], "Тестовый КПП")
        self.assertEqual(history[0]["results"]["personnel"], 8)

        all_calculations = db.get_all_calculations()
        self.assertEqual(len(all_calculations), 1)
        self.assertEqual(all_calculations[0]["id"], calculation_id)

    def test_delete_removes_only_selected_calculation(self):
        first_id = db.save_calculation("Первый", "A", "Тест", {}, {"value": 1})
        second_id = db.save_calculation("Второй", "B", "Тест", {}, {"value": 2})

        db.delete_calculation(first_id)

        history = db.get_calculation_history()
        self.assertEqual([item["id"] for item in history], [second_id])


    def test_personnel_dictionary_is_created_with_expected_defaults(self):
        personnel = db.get_personnel_dict()
        self.assertGreater(len(personnel), 0)

        by_code = {item["role_code"]: item for item in personnel}
        self.assertEqual(by_code["tspk_engineer"]["quantity"], 2)
        self.assertEqual(by_code["tspk_engineer"]["calculation_type"], "per_checkpoint")
        self.assertEqual(by_code["tspk_engineer"]["functional_group"], "technical_maintenance")
        self.assertEqual(by_code["document_control_in"]["functional_group"], "passport_control")
        self.assertEqual(by_code["vehicle_inspection_senior"]["functional_group"], "vehicle_inspection")
        self.assertEqual(by_code["tspk_senior_technician"]["quantity"], 2)
        self.assertEqual(by_code["vehicle_inspection_junior"]["quantity"], 2)
        self.assertFalse(by_code["canine_inspector"]["is_active"])
        self.assertFalse(by_code["security_systems_operator"]["is_active"])
        self.assertEqual(by_code["rpm_operator"]["rule_params"]["directions"], ["in", "out"])

        active = db.get_personnel_dict(include_inactive=False)
        self.assertTrue(all(item["is_active"] for item in active))
        self.assertLess(len(active), len(personnel))

    def test_personnel_dictionary_changes_survive_reinitialization(self):
        personnel = db.get_personnel_dict()
        engineer = next(item for item in personnel if item["role_code"] == "tspk_engineer")
        engineer["position_name"] = "Инженер ТСПК (изменено)"
        db.save_personnel_dict(personnel)

        db.init_db()

        saved = next(
            item for item in db.get_personnel_dict()
            if item["role_code"] == "tspk_engineer"
        )
        self.assertEqual(saved["position_name"], "Инженер ТСПК (изменено)")
        self.assertEqual(saved["functional_group"], "technical_maintenance")

    def test_personnel_dictionary_can_be_reset_without_changing_other_data(self):
        personnel = db.get_personnel_dict()
        personnel[0]["position_name"] = "Временное название"
        db.save_personnel_dict(personnel)
        tspk_before = db.get_tspk_dict()
        calculation_id = db.save_calculation("Тест", "T-1", "Тест", {}, {"value": 7})

        db.reset_personnel_to_default()

        restored = db.get_personnel_dict()
        self.assertEqual(restored[0]["position_name"], "Начальник КПП")
        self.assertGreater(len(restored), 0)
        self.assertEqual(db.get_tspk_dict(), tspk_before)
        self.assertEqual(db.get_calculation_history()[0]["id"], calculation_id)


    def test_personnel_functional_group_migrates_existing_database(self):
        with db.get_connection() as conn:
            conn.execute("DROP TABLE dict_personnel")
            conn.execute("""
                CREATE TABLE dict_personnel (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    position_name TEXT NOT NULL,
                    role_code TEXT NOT NULL UNIQUE,
                    calculation_type TEXT NOT NULL,
                    quantity REAL NOT NULL DEFAULT 1,
                    apply_shift_factor INTEGER NOT NULL DEFAULT 0,
                    condition_key TEXT,
                    rule_params TEXT NOT NULL DEFAULT '{}',
                    is_active INTEGER NOT NULL DEFAULT 1,
                    is_system INTEGER NOT NULL DEFAULT 1,
                    note TEXT,
                    sort_order INTEGER NOT NULL DEFAULT 0
                )
            """)
            conn.execute("""
                INSERT INTO dict_personnel
                (category, position_name, role_code, calculation_type)
                VALUES ('Техническая служба', 'Инженер', 'tspk_engineer', 'per_checkpoint')
            """)

        db.init_db()

        engineer = next(
            item for item in db.get_personnel_dict()
            if item["role_code"] == "tspk_engineer"
        )
        self.assertEqual(engineer["functional_group"], "technical_maintenance")
        self.assertEqual(engineer["position_name"], "Инженер")

    def test_personnel_dictionary_rejects_duplicate_role_codes(self):
        personnel = db.get_personnel_dict()
        personnel.append(dict(personnel[0]))
        with self.assertRaises(ValueError):
            db.save_personnel_dict(personnel)

    def test_save_dictionary_and_reset_to_defaults(self):
        defaults = db.get_tspk_dict()
        self.assertGreater(len(defaults), 0)
        default_model = defaults[0]["selected_model"]

        changed = [dict(item) for item in defaults]
        changed[0]["selected_model"] = "ИЗМЕНЕННАЯ МОДЕЛЬ"
        db.save_tspk_dict(pd.DataFrame(changed))

        self.assertEqual(
            db.get_tspk_dict()[0]["selected_model"], "ИЗМЕНЕННАЯ МОДЕЛЬ"
        )

        db.reset_tspk_to_default()

        restored = db.get_tspk_dict()
        self.assertEqual(len(restored), len(defaults))
        self.assertEqual(restored[0]["selected_model"], default_model)

        passport_atlas = next(
            item
            for item in restored
            if item["equipment_name"] == "Электронные атласы паспортов"
        )
        self.assertEqual(passport_atlas["selected_model"], "Regula Passport")


if __name__ == "__main__":
    unittest.main()
