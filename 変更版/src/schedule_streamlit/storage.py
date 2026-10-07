"""SQLiteへの入力データ・実行結果の保存。"""

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path


DEFAULT_DB = Path(__file__).resolve().parents[2] / "schedule.sqlite3"


@contextmanager
def connect(path=DEFAULT_DB):
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize(path=DEFAULT_DB):
    with connect(path) as connection:
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS datasets (
                id INTEGER PRIMARY KEY,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                seed INTEGER NOT NULL,
                order_count INTEGER NOT NULL,
                product_count INTEGER NOT NULL,
                product_select TEXT NOT NULL,
                priority TEXT NOT NULL,
                overlap INTEGER NOT NULL,
                factory_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS orders (
                dataset_id INTEGER NOT NULL REFERENCES datasets(id),
                order_id INTEGER NOT NULL,
                payload TEXT NOT NULL,
                PRIMARY KEY (dataset_id, order_id)
            );
            CREATE TABLE IF NOT EXISTS products (
                dataset_id INTEGER NOT NULL REFERENCES datasets(id),
                product_id INTEGER NOT NULL,
                payload TEXT NOT NULL,
                PRIMARY KEY (dataset_id, product_id)
            );
            CREATE TABLE IF NOT EXISTS processes (
                dataset_id INTEGER NOT NULL REFERENCES datasets(id),
                order_id INTEGER NOT NULL,
                process_id INTEGER NOT NULL,
                payload TEXT NOT NULL,
                PRIMARY KEY (dataset_id, order_id, process_id)
            );
            CREATE TABLE IF NOT EXISTS stops (
                id INTEGER PRIMARY KEY,
                dataset_id INTEGER NOT NULL REFERENCES datasets(id),
                resource_type TEXT NOT NULL,
                resource_id INTEGER NOT NULL,
                start_time INTEGER NOT NULL,
                end_time INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS blocks (
                id INTEGER PRIMARY KEY,
                dataset_id INTEGER NOT NULL REFERENCES datasets(id),
                block_type TEXT NOT NULL,
                start_time INTEGER NOT NULL,
                end_time INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY,
                dataset_id INTEGER NOT NULL REFERENCES datasets(id),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                trial_count INTEGER NOT NULL,
                elapsed REAL NOT NULL,
                best_makespan INTEGER NOT NULL,
                best_trial INTEGER NOT NULL,
                violation_count INTEGER NOT NULL,
                settings_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS trials (
                run_id INTEGER NOT NULL REFERENCES runs(id),
                trial_number INTEGER NOT NULL,
                seed INTEGER NOT NULL,
                makespan INTEGER NOT NULL,
                elapsed REAL NOT NULL,
                violation_count INTEGER NOT NULL,
                violations_json TEXT NOT NULL,
                PRIMARY KEY (run_id, trial_number)
            );
            CREATE TABLE IF NOT EXISTS assignments (
                run_id INTEGER NOT NULL REFERENCES runs(id),
                order_id INTEGER NOT NULL,
                process_id INTEGER NOT NULL,
                payload TEXT NOT NULL,
                PRIMARY KEY (run_id, order_id, process_id)
            );
        """)


def save_dataset(config, factory, orders, tasks, products, path=DEFAULT_DB):
    with connect(path) as connection:
        cursor = connection.execute(
            """INSERT INTO datasets
            (seed, order_count, product_count, product_select, priority, overlap, factory_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (config["seed"], config["order_count"], config["product_count"],
             config["product_select"], config["priority"], int(config["overlap"]),
             json.dumps(factory, ensure_ascii=False)),
        )
        dataset_id = cursor.lastrowid
        connection.executemany(
            "INSERT INTO orders VALUES (?, ?, ?)",
            [(dataset_id, key, json.dumps(value, ensure_ascii=False))
             for key, value in orders.items()],
        )
        connection.executemany(
            "INSERT INTO products VALUES (?, ?, ?)",
            [(dataset_id, key, json.dumps(value, ensure_ascii=False))
             for key, value in products.items()],
        )
        connection.executemany(
            "INSERT INTO processes VALUES (?, ?, ?, ?)",
            [(dataset_id, order_id, process_id, json.dumps(process, ensure_ascii=False))
             for order_id, order in tasks.items()
             for process_id, process in order["工程情報"].items()],
        )
    return dataset_id


def list_datasets(path=DEFAULT_DB):
    with connect(path) as connection:
        return [dict(row) for row in connection.execute(
            "SELECT * FROM datasets ORDER BY id DESC"
        )]


def load_dataset(dataset_id, path=DEFAULT_DB):
    with connect(path) as connection:
        row = connection.execute(
            "SELECT * FROM datasets WHERE id = ?", (dataset_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"データセットID {dataset_id} がありません")
        metadata = dict(row)
        factory = json.loads(metadata["factory_json"])
        orders = {
            item["order_id"]: json.loads(item["payload"])
            for item in connection.execute(
                "SELECT * FROM orders WHERE dataset_id = ? ORDER BY order_id", (dataset_id,)
            )
        }
        products = {
            item["product_id"]: json.loads(item["payload"])
            for item in connection.execute(
                "SELECT * FROM products WHERE dataset_id = ? ORDER BY product_id", (dataset_id,)
            )
        }
        for product in products.values():
            product["工程構成"] = {
                int(process_id): process
                for process_id, process in product["工程構成"].items()
            }
        tasks = {order_id: {"受注情報": order, "工程情報": {}}
                 for order_id, order in orders.items()}
        for item in connection.execute(
            "SELECT * FROM processes WHERE dataset_id = ? ORDER BY order_id, process_id",
            (dataset_id,),
        ):
            tasks[item["order_id"]]["工程情報"][item["process_id"]] = json.loads(
                item["payload"]
            )
        return metadata, factory, orders, tasks, products


def load_conditions(dataset_id, path=DEFAULT_DB):
    with connect(path) as connection:
        stops = [dict(row) for row in connection.execute(
            "SELECT resource_type, resource_id, start_time, end_time "
            "FROM stops WHERE dataset_id = ? ORDER BY resource_type, resource_id, start_time",
            (dataset_id,),
        )]
        blocks = [dict(row) for row in connection.execute(
            "SELECT block_type, start_time, end_time "
            "FROM blocks WHERE dataset_id = ? "
            "ORDER BY CASE block_type WHEN 'setup' THEN 0 ELSE 1 END, start_time",
            (dataset_id,),
        )]
    return stops, blocks


def save_conditions(dataset_id, stops, blocks, path=DEFAULT_DB):
    with connect(path) as connection:
        connection.execute("DELETE FROM stops WHERE dataset_id = ?", (dataset_id,))
        connection.execute("DELETE FROM blocks WHERE dataset_id = ?", (dataset_id,))
        connection.executemany(
            "INSERT INTO stops (dataset_id, resource_type, resource_id, start_time, end_time) "
            "VALUES (?, ?, ?, ?, ?)",
            [(dataset_id, row["resource_type"], row["resource_id"],
              row["start_time"], row["end_time"]) for row in stops],
        )
        connection.executemany(
            "INSERT INTO blocks (dataset_id, block_type, start_time, end_time) "
            "VALUES (?, ?, ?, ?)",
            [(dataset_id, row["block_type"], row["start_time"], row["end_time"])
             for row in blocks],
        )


def save_run(dataset_id, result, stops, blocks, path=DEFAULT_DB):
    best = result["best"]
    with connect(path) as connection:
        cursor = connection.execute(
            """INSERT INTO runs
            (dataset_id, trial_count, elapsed, best_makespan, best_trial,
             violation_count, settings_json) VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (dataset_id, len(result["trials"]), result["elapsed"], best["makespan"],
             best["trial_number"], best["violation_count"],
             json.dumps({"stops": stops, "blocks": blocks}, ensure_ascii=False)),
        )
        run_id = cursor.lastrowid
        connection.executemany(
            "INSERT INTO trials VALUES (?, ?, ?, ?, ?, ?, ?)",
            [(run_id, row["trial_number"], row["seed"], row["makespan"],
              row["elapsed"], row["violation_count"],
              json.dumps(row["violations"], ensure_ascii=False))
             for row in result["trials"]],
        )
        connection.executemany(
            "INSERT INTO assignments VALUES (?, ?, ?, ?)",
            [(run_id, row["order_id"], row["process_id"],
              json.dumps(row, ensure_ascii=False)) for row in best["assignments"]],
        )
    return run_id


def list_runs(dataset_id, path=DEFAULT_DB):
    with connect(path) as connection:
        return [dict(row) for row in connection.execute(
            "SELECT id, created_at, trial_count, elapsed, best_makespan, best_trial, "
            "violation_count FROM runs WHERE dataset_id = ? ORDER BY id DESC",
            (dataset_id,),
        )]


def load_run(run_id, path=DEFAULT_DB):
    with connect(path) as connection:
        row = connection.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        if row is None:
            raise ValueError(f"実行ID {run_id} がありません")
        run = dict(row)
        trials = [dict(item) for item in connection.execute(
            "SELECT * FROM trials WHERE run_id = ? ORDER BY trial_number", (run_id,)
        )]
        assignments = [json.loads(item["payload"]) for item in connection.execute(
            "SELECT payload FROM assignments WHERE run_id = ? ORDER BY order_id, process_id",
            (run_id,),
        )]
    return run, trials, assignments, json.loads(run["settings_json"])
