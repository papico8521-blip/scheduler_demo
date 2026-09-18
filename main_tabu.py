from collections import deque
from copy import deepcopy
from pprint import pprint
import random
from time import perf_counter

from evaluation import evaluate_schedule
from output_datas import excel_exchanger
from reference_datas import data_shuffle, reference_datas
from setting import factory_setting, order_setting, task_setting
from time_slot import create_time_slot, schedule_builder
from visualizer.schedule_visualizer import ScheduleVisualizer


def _task_key(solve_key):
    """タブー判定用の工程キーを返す。"""
    return solve_key[1], solve_key[3]


def _create_neighbor_sequences(solve_list, random_generator, neighbor_count):
    """隣接する異なる受注の工程を入れ替えた近傍を生成する。"""
    candidate_positions = []
    for position in range(len(solve_list) - 1):
        current = solve_list[position]
        next_item = solve_list[position + 1]
        if current[1] != next_item[1]:
            candidate_positions.append(position)

    random_generator.shuffle(candidate_positions)
    neighbors = []
    for position in candidate_positions[:neighbor_count]:
        neighbor = solve_list.copy()
        move = (
            _task_key(neighbor[position]),
            _task_key(neighbor[position + 1]),
        )
        neighbor[position], neighbor[position + 1] = (
            neighbor[position + 1],
            neighbor[position],
        )
        neighbors.append((move, neighbor))
    return neighbors


def _add_best_schedule(best_schedules, schedule_state, makespan):
    """探索中の上位3スケジュールを更新する。"""
    best_schedules.append({
        "makespan": makespan,
        "schedule_state": schedule_state,
    })
    best_schedules.sort(key=lambda result: result["makespan"])
    del best_schedules[3:]


def _evaluate_sequence(
    reference,
    solve_list,
    worker_slot_master,
    machine_slot_master,
    seed,
):
    """投入順からスケジュールを生成して評価する。"""
    schedule_state = schedule_builder.create_schedule(
        reference=reference,
        solve_list=solve_list,
        worker_slot_master=worker_slot_master,
        machine_slot_master=machine_slot_master,
        seed=seed,
    )
    evaluation = evaluate_schedule.evaluate_schedule(schedule_state)
    schedule_state["evaluation"] = evaluation
    return schedule_state, evaluation["makespan"]


def _search_tabu(
    reference,
    initial_solve_list,
    worker_slot_master,
    machine_slot_master,
    seed,
    iteration_count,
    tabu_tenure,
    neighbor_count,
):
    """投入順の近傍をタブーサーチで探索する。"""
    if iteration_count <= 0:
        raise ValueError("iteration_count は1以上で指定してください。")
    if tabu_tenure <= 0:
        raise ValueError("tabu_tenure は1以上で指定してください。")
    if neighbor_count <= 0:
        raise ValueError("neighbor_count は1以上で指定してください。")

    random_generator = random.Random(seed)
    current_sequence = initial_solve_list.copy()
    current_state, current_makespan = _evaluate_sequence(
        reference,
        current_sequence,
        worker_slot_master,
        machine_slot_master,
        seed=seed,
    )
    best_schedules = []
    _add_best_schedule(best_schedules, current_state, current_makespan)
    best_makespan = current_makespan
    tabu_list = deque(maxlen=tabu_tenure)
    accepted_states = [current_state]

    for iteration in range(iteration_count):
        candidate_results = []
        neighbors = _create_neighbor_sequences(
            current_sequence,
            random_generator,
            neighbor_count,
        )

        for move, neighbor_sequence in neighbors:
            neighbor_state, neighbor_makespan = _evaluate_sequence(
                reference,
                neighbor_sequence,
                worker_slot_master,
                machine_slot_master,
                seed=seed,
            )
            _add_best_schedule(
                best_schedules,
                neighbor_state,
                neighbor_makespan,
            )

            is_tabu = move in tabu_list
            passes_aspiration = neighbor_makespan < best_makespan
            if not is_tabu or passes_aspiration:
                candidate_results.append(
                    (neighbor_makespan, move, neighbor_sequence, neighbor_state)
                )

        if not candidate_results:
            break

        candidate_results.sort(key=lambda result: result[0])
        current_makespan, selected_move, current_sequence, current_state = (
            candidate_results[0]
        )
        tabu_list.append(selected_move)
        accepted_states.append(current_state)

        if current_makespan < best_makespan:
            best_makespan = current_makespan
            print(
                f"[tabu {iteration + 1}/{iteration_count}] "
                f"makespan: {current_makespan} 分 ---- [ best更新 ]"
            )

    return accepted_states, best_schedules


def main(
    display=False,
    excel_output=False,
    visualize=False,
    loop_count=1,
    iteration_count=50,
    tabu_tenure=10,
    neighbor_count=20,
):
    """タブーサーチによるスケジュール生成を実行する。"""
    orders = order_setting.Orders(
        count=10,
        product_count=5,
        product_select="連続",
        priority="連続",
    )
    orders = order_setting.Generetor(orders).load()

    factory = factory_setting.Factory()
    tasks, task_summary = task_setting.Generetor(
        tasks=task_setting.Tasks(),
        factory=factory,
        orders=orders,
    ).load()

    if display:
        pprint(orders)
        pprint(factory)
        pprint(tasks)

    if excel_output:
        datas = {
            "orders": orders,
            "factory": factory,
            "tasks": tasks,
            "task_summary": task_summary,
        }
        excel_exchanger.DataChanger().save_to_excel(datas)

    slot_maker = create_time_slot.SlotMaker(factory=factory, tasks=tasks)
    worker_slot_master, machine_slot_master = slot_maker.load(slot=1)
    reference_master = reference_datas.create(tasks, display=display)

    start_time = perf_counter()
    schedule_results = []
    best_schedules = []

    for trial in range(loop_count):
        reference = deepcopy(reference_master)
        solve_list = data_shuffle.shuffle(
            reference["solve_list"],
            seed=trial,
            prio_mix=True,
            n=0.5,
        )
        accepted_states, trial_best_schedules = _search_tabu(
            reference=reference,
            initial_solve_list=solve_list,
            worker_slot_master=worker_slot_master,
            machine_slot_master=machine_slot_master,
            seed=trial,
            iteration_count=iteration_count,
            tabu_tenure=tabu_tenure,
            neighbor_count=neighbor_count,
        )
        schedule_results.extend(accepted_states)
        best_schedules.extend(trial_best_schedules)
        best_schedules.sort(key=lambda result: result["makespan"])
        del best_schedules[3:]

    elapsed = perf_counter() - start_time
    print(f"処理時間: {elapsed:.6f} 秒")
    print(f"1回平均時間: {elapsed / loop_count:.6f} 秒")

    if visualize and best_schedules:
        ScheduleVisualizer().display_gant_v1(
            best_schedules[0]["schedule_state"]
        )

    return {
        "schedule_results": schedule_results,
        "best_schedules": best_schedules,
    }


if __name__ == "__main__":
    print("\n---タブーサーチ処理開始---\n")
    main(
        display=False,
        excel_output=False,
        visualize=True,
        loop_count=2,
        iteration_count=50,
        tabu_tenure=10,
        neighbor_count=20,
    )
    print("処理完了")
