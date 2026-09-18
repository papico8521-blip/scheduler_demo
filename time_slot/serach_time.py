import numpy as np


def _build_block_intervals(block_slots):
    """禁止スロット配列を連続区間のリストへ変換する。"""
    block_indices = np.flatnonzero(block_slots == 1)
    if block_indices.size == 0:
        return []

    interval_starts = np.r_[
        block_indices[0],
        block_indices[1:][np.diff(block_indices) > 1],
    ]
    interval_ends = np.r_[
        block_indices[:-1][np.diff(block_indices) > 1],
        block_indices[-1],
    ] + 1
    return list(zip(interval_starts.tolist(), interval_ends.tolist()))


def _find_continuous_free_start(slots, duration, earliest_start):
    """指定時刻以降で、連続して空いている最初の開始時刻を探す。"""
    if duration == 0:
        return min(max(earliest_start, 0), slots.shape[0])

    available_starts = _find_continuous_free_starts(slots, duration)
    if earliest_start < 0:
        earliest_start = 0

    candidate_starts = np.flatnonzero(available_starts)
    candidate_starts = candidate_starts[candidate_starts >= earliest_start]
    if candidate_starts.size == 0:
        return None
    return int(candidate_starts[0])


def _find_continuous_free_starts(slots, duration):
    """連続して空いている開始時刻を真偽値配列で返す。"""
    if duration < 0:
        raise ValueError("duration は0以上で指定してください。")

    horizon = slots.shape[0]
    if duration == 0:
        return np.ones(horizon, dtype=bool)
    if duration > horizon:
        return np.zeros(horizon, dtype=bool)

    # タイムスロット本体はint8だが、長時間の連続判定で
    # 累積和がオーバーフローしないようint32へ変換する。
    free_slots = (slots == 0).astype(np.int32)
    cumulative_free_slots = np.cumsum(free_slots, dtype=np.int32)
    window_totals = cumulative_free_slots[duration - 1:].copy()
    window_totals[1:] -= cumulative_free_slots[:-duration]
    available_starts = np.zeros(horizon, dtype=bool)
    available_starts[:window_totals.size] = window_totals == duration
    return available_starts


def search_assignment_time(
    machine_slots,
    worker_slots,
    machine_id,
    worker_id,
    setup_time,
    process_time,
    earliest_start,
    worker_setup_block=None,
    machine_proc_block=None,
):
    """機械と作業者を同時に使用できる最初の開始時刻を探す。"""
    machine_duration = setup_time + process_time
    worker_duration = setup_time

    if machine_id >= machine_slots.shape[0]:
        raise IndexError(f"machine_id={machine_id} は範囲外です。")
    if worker_id >= worker_slots.shape[0]:
        raise IndexError(f"worker_id={worker_id} は範囲外です。")

    if machine_duration == 0 and worker_duration == 0:
        if earliest_start >= machine_slots.shape[1]:
            return None
        return max(earliest_start, 0)

    worker_slot = worker_slots[worker_id]
    if worker_setup_block is not None:
        worker_slot = np.maximum(
            worker_slot,
            worker_setup_block[worker_id],
        )
    worker_available = _find_continuous_free_starts(
        worker_slot,
        setup_time,
    )

    has_proc_block = (
        machine_proc_block is not None
        and np.any(machine_proc_block[machine_id] == 1)
    )

    if not has_proc_block:
        # proc禁止区間がない場合は、従来どおり機械の連続空きを一度に判定する。
        machine_available = _find_continuous_free_starts(
            machine_slots[machine_id],
            machine_duration,
        )
        available_starts = machine_available & worker_available
        if earliest_start < 0:
            earliest_start = 0
        candidate_starts = np.flatnonzero(available_starts)
        candidate_starts = candidate_starts[candidate_starts >= earliest_start]
        if candidate_starts.size == 0:
            return None
        return int(candidate_starts[0])

    proc_block_slots = machine_proc_block[machine_id]
    proc_block_intervals = _build_block_intervals(proc_block_slots)
    machine_available = _find_continuous_free_starts(
        machine_slots[machine_id],
        setup_time,
    )

    available_starts = machine_available & worker_available
    if earliest_start < 0:
        earliest_start = 0

    candidate_starts = np.flatnonzero(available_starts)
    candidate_starts = candidate_starts[candidate_starts >= earliest_start]
    for start_time in candidate_starts:
        setup_end_time = int(start_time) + setup_time
        if (
            machine_proc_block is not None
            and setup_end_time < machine_proc_block.shape[1]
            and machine_proc_block[machine_id, setup_end_time] == 1
        ):
            continue

        end_time = _find_process_end_time(
            machine_slots=machine_slots[machine_id],
            machine_proc_block=(
                None
                if machine_proc_block is None
                else proc_block_slots
            ),
            proc_block_intervals=proc_block_intervals,
            process_start=setup_end_time,
            process_time=process_time,
        )
        if end_time is not None:
            return int(start_time)

    return None


def _find_process_end_time_minute(
    machine_slots,
    machine_proc_block,
    process_start,
    process_time,
):
    """禁止区間中の停止を考慮したproc終了時刻を探す。"""
    horizon = machine_slots.shape[0]
    elapsed_process_time = 0
    current_time = process_start

    while elapsed_process_time < process_time:
        if current_time >= horizon:
            return None
        if machine_slots[current_time] == 1:
            return None
        if (
            machine_proc_block is not None
            and machine_proc_block[current_time] == 1
        ):
            current_time += 1
            continue
        elapsed_process_time += 1
        current_time += 1

    return current_time


def _find_process_end_time(
    machine_slots,
    machine_proc_block,
    process_start,
    process_time,
    proc_block_intervals=None,
):
    """proc禁止区間をまとめて飛ばし、proc終了時刻を探す。"""
    horizon = machine_slots.shape[0]
    if process_time <= 0:
        return process_start

    if machine_proc_block is None:
        proc_block_intervals = []
    elif proc_block_intervals is None:
        proc_block_intervals = _build_block_intervals(machine_proc_block)

    remaining_process_time = process_time
    current_time = process_start

    for block_start, block_end in proc_block_intervals:
        if block_end <= current_time:
            continue

        if block_start > current_time:
            available_end = min(block_start, horizon)
            available_time = available_end - current_time
            if remaining_process_time <= available_time:
                process_end = current_time + remaining_process_time
                if np.any(machine_slots[current_time:process_end] == 1):
                    return None
                return process_end
            if np.any(machine_slots[current_time:available_end] == 1):
                return None
            remaining_process_time -= available_time
            current_time = available_end

        if current_time < block_end:
            blocked_end = min(block_end, horizon)
            if np.any(machine_slots[current_time:blocked_end] == 1):
                return None
            current_time = blocked_end
            if current_time >= horizon and remaining_process_time > 0:
                return None

    if current_time >= horizon:
        return None
    if current_time + remaining_process_time > horizon:
        return None
    if np.any(
        machine_slots[current_time:current_time + remaining_process_time] == 1
    ):
        return None
    return current_time + remaining_process_time


def search_first_assignment(
    machine_slots,
    worker_slots,
    machine_candidates,
    worker_candidates,
    setup_time,
    process_time,
    earliest_start,
    rng,
    worker_setup_block=None,
    machine_proc_block=None,
):
    """候補をランダム順に確認し、最初に割当可能な組み合わせを返す。"""
    shuffled_machines = list(machine_candidates)
    shuffled_workers = list(worker_candidates)
    rng.shuffle(shuffled_machines)
    rng.shuffle(shuffled_workers)

    for machine_id in shuffled_machines:
        for worker_id in shuffled_workers:
            start_time = search_assignment_time(
                machine_slots=machine_slots,
                worker_slots=worker_slots,
                machine_id=machine_id,
                worker_id=worker_id,
                setup_time=setup_time,
                process_time=process_time,
                earliest_start=earliest_start,
                worker_setup_block=worker_setup_block,
                machine_proc_block=machine_proc_block,
            )
            if start_time is not None:
                return machine_id, worker_id, start_time

    return None
