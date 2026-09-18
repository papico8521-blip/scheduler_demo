import numpy as np

from time_slot import serach_time


def _get_previous_key(schedule_state, order_id, process_id):
    """同一受注内の直前工程キーを返す。"""
    if process_id <= 1:
        return None
    return (order_id, process_id - 1)


def _get_total_duration(reference, key):
    """次工程の段取＋総加工時間を分単位で返す。"""
    return reference["setup"][key] + reference["proc_total"][key]


def _get_earliest_start(reference, schedule_state, key):
    """工程順序とオーバーラップ条件から探索開始時刻を決める。"""
    order_id, process_id = key
    earliest_start = reference["release"][key]
    previous_key = _get_previous_key(schedule_state, order_id, process_id)

    if previous_key is None:
        return earliest_start

    previous_schedule = schedule_state["assignments"][previous_key]
    if previous_schedule["over_lap"]:
        base_ready_time = (
            previous_schedule["start_time"]
            + reference["over_lap_buff"][previous_key]
        )
        next_total_duration = _get_total_duration(reference, key)
        next_end_time = base_ready_time + next_total_duration

        if next_end_time < previous_schedule["end_time"]:
            predecessor_ready_time = (
                previous_schedule["end_time"] - next_total_duration
            )
        else:
            predecessor_ready_time = base_ready_time
    else:
        predecessor_ready_time = previous_schedule["end_time"]

    return max(earliest_start, predecessor_ready_time)


def _reserve_slots(schedule_state, assignment):
    """確定した割当を機械・作業者のタイムスロットへ反映する。"""
    start_time = assignment["start_time"]
    setup_end_time = assignment["setup_end_time"]
    end_time = assignment["end_time"]

    schedule_state["worker_slots"][
        assignment["worker_id"], start_time:setup_end_time
    ] = 1
    schedule_state["machine_slots"][
        assignment["machine_id"], start_time:end_time
    ] = 1


def create_schedule(
    reference,
    solve_list,
    worker_slot_master,
    machine_slot_master,
    seed,
    worker_setup_block_master=None,
    machine_proc_block_master=None,
):
    """ソルバー投入順に工程を割り当て、schedule_stateを生成する。"""
    if worker_setup_block_master is None:
        worker_setup_block_master = np.zeros_like(worker_slot_master)
    if machine_proc_block_master is None:
        machine_proc_block_master = np.zeros_like(machine_slot_master)

    schedule_state = {
        "worker_slots": worker_slot_master.copy(),
        "machine_slots": machine_slot_master.copy(),
        "worker_setup_block": worker_setup_block_master,
        "machine_proc_block": machine_proc_block_master,
        "assignments": {},
    }
    rng = np.random.default_rng(seed)

    for solve_key in solve_list:
        order_id = solve_key[1]
        process_id = solve_key[3]
        key = (order_id, process_id)

        setup_time = reference["setup"][key]
        process_time = reference["proc_total"][key]
        earliest_start = _get_earliest_start(
            reference,
            schedule_state,
            key,
        )

        result = serach_time.search_first_assignment(
            machine_slots=schedule_state["machine_slots"],
            worker_slots=schedule_state["worker_slots"],
            machine_candidates=reference["machine_candidate"][key],
            worker_candidates=reference["worker_candidate"][key],
            setup_time=setup_time,
            process_time=process_time,
            earliest_start=earliest_start,
            rng=rng,
            worker_setup_block=schedule_state["worker_setup_block"],
            machine_proc_block=schedule_state["machine_proc_block"],
        )

        if result is None:
            raise RuntimeError(
                f"工程を割り当てられる空き時間がありません: {key}"
            )

        machine_id, worker_id, start_time = result
        process_end_time = serach_time._find_process_end_time(
            machine_slots=schedule_state["machine_slots"][machine_id],
            machine_proc_block=schedule_state["machine_proc_block"][machine_id],
            process_start=start_time + setup_time,
            process_time=process_time,
        )
        if process_end_time is None:
            raise RuntimeError(
                f"procを割り当てられる空き時間がありません: {key}"
            )

        assignment = {
            "order_id": order_id,
            "process_id": process_id,
            "product_id": reference["product_id"][key],
            "machine_id": machine_id,
            "worker_id": worker_id,
            "start_time": start_time,
            "setup_end_time": start_time + setup_time,
            "end_time": process_end_time,
            "setup_time": setup_time,
            "process_time": process_time,
            "release_time": earliest_start,
            "over_lap": reference["over_lap"][key],
            "over_lap_buff": reference["over_lap_buff"][key],
        }
        schedule_state["assignments"][key] = assignment
        _reserve_slots(schedule_state, assignment)

    return schedule_state
