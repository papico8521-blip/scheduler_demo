from setting import order_setting, factory_setting, task_setting
from output_datas import excel_exchanger
from time_slot import create_time_slot
from time_slot import schedule_builder
from reference_datas import reference_datas, data_shuffle
from visualizer.schedule_visualizer import ScheduleVisualizer
from evaluation import evaluate_schedule

from pprint import pprint
from copy import deepcopy

import time,sys

def main(
        display=False,
        excel_output=False,
        loop_count=10,
        visualize=False,
        real_time_gant=False,
        stop_datas=None,
        setup_block=None,
        proc_block=None,
        ):

    # -----------------------
    # テストデータ設定・生成
    # -----------------------

    orders = order_setting.Orders(
        count = 10,
        product_count = 5,
        product_select="連続",
        priority = "連続",
    )

    orders = order_setting.Generetor(orders).load()

    factory = factory_setting.Factory()

    tasks = task_setting.Tasks()
    tasks, task_summary= task_setting.Generetor(
        tasks=tasks,
        factory=factory,
        orders=orders
        ).load()

    # --------------
    # デバッグ出力
    # --------------
    # print出力
    if display:
        pprint(orders)
        pprint(factory)
        pprint(tasks)

    # エクセル出力
    if excel_output:

        datas = {
            "orders" : orders,
            "factory" : factory,
            "tasks": tasks,
            "task_summary": task_summary
            }
        
        output = excel_exchanger.DataChanger()
        output.save_to_excel(datas)
        del datas

    # ----------------------
    # タイムスロット生成
    # ----------------------
    slot_maker = create_time_slot.SlotMaker(factory=factory, tasks=tasks)
    worker_slot_master, machine_slot_master = slot_maker.load(slot=1)
    worker_setup_block_master, machine_proc_block_master = (
        slot_maker.create_block_slots(
            slot=1,
            setup_block=setup_block,
            proc_block=proc_block,
        )
    )

    # -----------------------
    # 強制停止区間挿入
    # -----------------------
    
    if stop_datas:
        for stop in stop_datas:
            machine_slot_master = slot_maker.add_stop_section(
                index=stop[0],
                slot=machine_slot_master,
                start=stop[1],
                end=stop[2]
                )

    # ------------------------------------
    # ソルバー投入/探索用データ生成
    # ------------------------------------
    reference_master = reference_datas.create(tasks, display=display)

    # -------------------------
    # ループ開始
    # -------------------------
    #input("\n[エンター]キーを押すとスケジューリングを実行します\n")
    start_time = time.perf_counter()

    # loop - start
    schedule_results = []
    best_schedules = []

    real_time_visualizer = ScheduleVisualizer() if visualize else None

    for i in range(loop_count):

        # データシャッフル
        reference = deepcopy(reference_master)
        solve_list = reference["solve_list"]
        solve_list = data_shuffle.shuffle(
            solve_list,
            seed=i,
            prio_mix=True,
            n=0.5,
            cutting_shuffle=True,
            )

        schedule_state = schedule_builder.create_schedule(
            reference=reference,
            solve_list=solve_list,
            worker_slot_master=worker_slot_master,
            machine_slot_master=machine_slot_master,
            seed=i,
            worker_setup_block_master=worker_setup_block_master,
            machine_proc_block_master=machine_proc_block_master,
        )
        evaluation = evaluate_schedule.evaluate_schedule(schedule_state)
        schedule_state["evaluation"] = evaluation
        schedule_results.append(schedule_state)

        previous_best = (
            best_schedules[0]["makespan"]
            if best_schedules
            else None
        )
        best_schedules.append({
            "makespan": evaluation["makespan"],
            "schedule_state": schedule_state,
        })
        best_schedules.sort(key=lambda result: result["makespan"])
        del best_schedules[3:]

        is_best_updated = (
            previous_best is None
            or evaluation["makespan"] < previous_best
        )
        best_label = " ---- [ best更新 ] " if is_best_updated else ""
        print(
            f"[{i+1}/{loop_count}] "
            f"makespan: {evaluation['makespan']} 分{best_label}"
        )

        if display:
            pprint(schedule_state["assignments"])

        if real_time_gant:
            if real_time_visualizer is not None:
                real_time_visualizer.real_time_gant(
                    best_schedule=best_schedules[0]["schedule_state"],
                    comparison_schedule=schedule_state,
                    display=True,
                )


    end_time = time.perf_counter()

    print(f"処理時間: {end_time - start_time:.6f} 秒")
    print(f"1回平均時間: {(end_time - start_time) / loop_count:.6f} 秒")

    visualizer = ScheduleVisualizer()
    visualizer.display_gant_v1(best_schedules[0]["schedule_state"])

    return {
        "schedule_results": schedule_results,
        "best_schedules": best_schedules,
        "orders": orders,
        "stop_datas": stop_datas
    }


if __name__ == "__main__":

    print("\n---サンプル処理開始---\n")

    stop_datas = []
 
    setup_block = []
    start_time = 0
    for i in range(12):
        start_time += 3
        setup_block.append((start_time * 60, (start_time + 1) * 60))
        start_time += 5
        setup_block.append((start_time * 60, (start_time + 16) * 60))
        start_time += 16
        
    proc_block = []
    # start_time = 0
    # for i in range(3):
    #     start_time += 3
    #     proc_block.append((start_time * 60, (start_time + 1) * 60))
    #     start_time += 5
    #     proc_block.append((start_time * 60, (start_time + 16) * 60))
    #     start_time += 16

    result = main(
            display = False,
            excel_output = True,
            visualize = True,
            loop_count = 1000,
            real_time_gant = False,
            stop_datas=stop_datas,
            setup_block=setup_block,
            proc_block=proc_block,
            )

    output = excel_exchanger.DataChanger()
    output.save_to_excel_best(
        result,
        path="スケジュール結果.xlsx",
    )

    print("処理完了")
