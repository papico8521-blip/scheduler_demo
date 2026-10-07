"""生成から保存・再表示までの主要経路を確認する。"""

import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from schedule_streamlit import engine, presets, storage
from schedule_streamlit.validation import validate_conditions, validate_schedule


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.config = {
            "seed": 42,
            "order_count": 3,
            "product_count": 2,
            "product_select": "連続",
            "priority": "連続",
            "overlap": True,
        }

    def test_dataset_run_and_history_round_trip(self):
        first = engine.generate(self.config)
        second = engine.generate(self.config)
        self.assertEqual(first, second)
        factory, orders, tasks, products = first
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.sqlite3"
            storage.initialize(path)
            dataset_id = storage.save_dataset(
                self.config, factory, orders, tasks, products, path
            )
            metadata, loaded_factory, loaded_orders, loaded_tasks, loaded_products = (
                storage.load_dataset(dataset_id, path)
            )
            self.assertEqual(metadata["seed"], 42)
            self.assertEqual(
                (loaded_factory, loaded_orders, loaded_tasks, loaded_products), first
            )
            result = engine.run_trials(loaded_factory, loaded_tasks, 2, [], [])
            self.assertEqual(len(result["trials"]), 2)
            self.assertEqual(result["best"]["violation_count"], 0)
            self.assertGreater(result["elapsed"], 0)
            run_id = storage.save_run(dataset_id, result, [], [], path)
            run, trials, assignments, settings = storage.load_run(run_id, path)
            self.assertEqual(run["best_makespan"], result["best"]["makespan"])
            self.assertEqual(len(trials), 2)
            self.assertEqual(len(assignments), sum(
                len(order["工程情報"]) for order in tasks.values()
            ))
            self.assertEqual(settings, {"stops": [], "blocks": []})

    def test_invalid_condition_and_schedule_detected(self):
        factory, _, tasks, _ = engine.generate(self.config)
        horizon = engine.horizon_for(tasks)
        stops = [
            dict(resource_type="machine", resource_id=1, start_time=0, end_time=10),
            dict(resource_type="machine", resource_id=1, start_time=9, end_time=20),
        ]
        _, _, errors = validate_conditions(stops, [], factory, horizon)
        self.assertTrue(any("重複" in error for error in errors))

        result = engine.run_trials(factory, tasks, 1, [], [])
        assignments = deepcopy(result["best"]["assignments"])
        assignments[0]["start_time"] = -1
        validation = validate_schedule(assignments, tasks, factory, [], [], horizon)
        self.assertFalse(validation["is_valid"])
        self.assertTrue(any("不正" in error for error in validation["violations"]))

    def test_stop_and_block_settings_round_trip(self):
        factory, orders, tasks, products = engine.generate(self.config)
        stops = [dict(resource_type="machine", resource_id=1, start_time=0, end_time=5)]
        blocks = [
            dict(block_type="setup", start_time=0, end_time=5),
            dict(block_type="process", start_time=200, end_time=220),
        ]
        clean_stops, clean_blocks, errors = validate_conditions(
            stops, blocks, factory, engine.horizon_for(tasks)
        )
        self.assertEqual(errors, [])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.sqlite3"
            storage.initialize(path)
            dataset_id = storage.save_dataset(
                self.config, factory, orders, tasks, products, path
            )
            storage.save_conditions(dataset_id, clean_stops, clean_blocks, path)
            self.assertEqual(
                storage.load_conditions(dataset_id, path), (clean_stops, clean_blocks)
            )
            result = engine.run_trials(factory, tasks, 2, clean_stops, clean_blocks)
            self.assertEqual(
                [trial["violation_count"] for trial in result["trials"]], [0, 0]
            )
            run_id = storage.save_run(dataset_id, result, clean_stops, clean_blocks, path)
            _, _, _, settings = storage.load_run(run_id, path)
            self.assertEqual(settings, {"stops": clean_stops, "blocks": clean_blocks})

    def test_generation_switches_are_applied(self):
        config = {
            **self.config,
            "product_select": "ランダム",
            "priority": "ランダム",
            "overlap": False,
        }
        factory, orders, tasks, _ = engine.generate(config)
        self.assertEqual(len(orders), config["order_count"])
        self.assertEqual(factory.keys(), {"cutting_machine", "cnc_machine", "cnc_worker"})
        self.assertTrue(all(
            not process["次工程オーバーラップ"]
            for order in tasks.values()
            for process in order["工程情報"].values()
        ))
        result = engine.run_trials(factory, tasks, 1, [], [])
        self.assertEqual(result["best"]["violation_count"], 0)

    def test_stop_presets_use_nine_am_as_zero(self):
        rows = presets.build_stop_presets("machine", [2], 2, True, True)
        self.assertEqual(rows, [
            {"resource_type": "machine", "resource_id": 2,
             "start_time": 180, "end_time": 240},
            {"resource_type": "machine", "resource_id": 2,
             "start_time": 480, "end_time": 1440},
            {"resource_type": "machine", "resource_id": 2,
             "start_time": 1620, "end_time": 1680},
            {"resource_type": "machine", "resource_id": 2,
             "start_time": 1920, "end_time": 2880},
        ])
        all_worker_rows = presets.build_stop_presets("worker", [1, 2], 1, True, False)
        self.assertEqual(all_worker_rows, [
            {"resource_type": "worker", "resource_id": 1,
             "start_time": 180, "end_time": 240},
            {"resource_type": "worker", "resource_id": 2,
             "start_time": 180, "end_time": 240},
        ])
        setup_rows = presets.build_setup_block_presets(2, True, True)
        self.assertEqual(setup_rows, [
            {"block_type": "setup", "start_time": 180, "end_time": 240},
            {"block_type": "setup", "start_time": 480, "end_time": 1440},
            {"block_type": "setup", "start_time": 1620, "end_time": 1680},
            {"block_type": "setup", "start_time": 1920, "end_time": 2880},
        ])


if __name__ == "__main__":
    unittest.main()
