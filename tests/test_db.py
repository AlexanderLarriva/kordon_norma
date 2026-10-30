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
            {"dict_tspk", "dict_settings", "calculation_history"}.issubset(tables)
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
