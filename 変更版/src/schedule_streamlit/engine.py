"""既存のデータ生成・通常探索を呼び出す境界。"""

import contextlib
import io
import sys
from pathlib import Path
from time import perf_counter

from .validation import validate_schedule


PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from evaluation import evaluate_schedule
from reference_datas import data_shuffle, reference_datas
from setting import factory_setting, order_setting, task_setting
from time_slot import create_time_slot, schedule_builder


def generate(config):
    """既存の乱数設定とデータ構造でダミーデータを作る。"""
    if config["order_count"] < 1 or config["product_count"] < 1:
        raise ValueError("受注数と製品数は1以上で指定してください")
    orders_setting = order_setting.Orders(
        seed=config["seed"],
        count=config["order_count"],
        product_count=config["product_count"],
        product_select=config["product_select"],
        priority=config["priority"],
        product_over_lap=config["overlap"],
    )
    orders = order_setting.Generetor(orders_setting).load()
    factory = factory_setting.Factory()
    tasks_setting = task_setting.Tasks(seed=config["seed"], process_over_lap=config["overlap"])
    tasks, templates = task_setting.Generetor(
        tasks=tasks_setting, factory=factory, orders=orders
    ).load()
    products = {}
    for order in orders.values():
        product_id = order["製品ID"]
        products[product_id] = {
            "製品ID": product_id,
            "ワーク直径": order["ワーク直径"],
            "ワーク長さ": order["ワーク長さ"],
            "工程構成": templates[product_id],
        }
    factory_data = {
        "cutting_machine": factory.cutting_machine,
        "cnc_machine": factory.cnc_machine,
        "cnc_worker": factory.cnc_worker,
    }
    return factory_data, orders, tasks, products


def horizon_for(tasks):
    """既存SlotMakerと同じホライズンを返す。"""
    return sum(
        process["段取時間"] + process["総加工時間"]
        for order in tasks.values()
        for process in order["工程情報"].values()
    )


def run_trials(factory_data, tasks, trial_count, stops, blocks):
    if trial_count < 1:
        raise ValueError("実行回数は1以上で指定してください")
    factory = factory_setting.Factory(**factory_data)
    slot_maker = create_time_slot.SlotMaker(factory=factory, tasks=tasks)
    with contextlib.redirect_stdout(io.StringIO()):
        worker_slots, machine_slots = slot_maker.load(slot=1)
        worker_blocks, machine_blocks = slot_maker.create_block_slots(
            slot=1,
            setup_block=[(row["start_time"], row["end_time"])
                         for row in blocks if row["block_type"] == "setup"],
            proc_block=[(row["start_time"], row["end_time"])
                        for row in blocks if row["block_type"] == "process"],
        )
        reference = reference_datas.create(tasks, display=False)
    for row in stops:
        target = machine_slots if row["resource_type"] == "machine" else worker_slots
        slot_maker.add_stop_section(
            row["resource_id"], target, row["start_time"], row["end_time"]
        )

    started = perf_counter()
    trials = []
    best = None
    for index in range(trial_count):
        trial_started = perf_counter()
        solve_list = data_shuffle.shuffle(
            reference["solve_list"], seed=index, prio_mix=True, n=0.5,
            cutting_shuffle=False,
        )
        state = schedule_builder.create_schedule(
            reference=reference,
            solve_list=solve_list,
            worker_slot_master=worker_slots,
            machine_slot_master=machine_slots,
            seed=index,
            worker_setup_block_master=worker_blocks,
            machine_proc_block_master=machine_blocks,
        )
        evaluation = evaluate_schedule.evaluate_schedule(state)
        validation = validate_schedule(
            state["assignments"], tasks, factory_data, stops, blocks,
            machine_slots.shape[1],
        )
        row = {
            "trial_number": index + 1,
            "seed": index,
            "makespan": evaluation["makespan"],
            "elapsed": perf_counter() - trial_started,
            "violation_count": validation["violation_count"],
            "violations": validation["violations"],
        }
        trials.append(row)
        if best is None or row["makespan"] < best["makespan"]:
            best = {
                **row,
                "assignments": list(state["assignments"].values()),
            }
    return {"trials": trials, "best": best, "elapsed": perf_counter() - started}
