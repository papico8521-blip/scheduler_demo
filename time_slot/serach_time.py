import numpy as np


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
):
    """機械と作業者を同時に使用できる最初の開始時刻を探す。"""
    machine_duration = setup_time + process_time
    worker_duration = setup_time

    if machine_id >= machine_slots.shape[0]:
        raise IndexError(f"machine_id={machine_id} は範囲外です。")
    if worker_id >= worker_slots.shape[0]:
        raise IndexError(f"worker_id={worker_id} は範囲外です。")

    if machine_duration == 0 and worker_duration == 0:
        return min(max(earliest_start, 0), machine_slots.shape[1])

    machine_available = _find_continuous_free_starts(
        machine_slots[machine_id],
        machine_duration,
    )
    worker_available = _find_continuous_free_starts(
        worker_slots[worker_id],
        worker_duration,
    )

    available_starts = machine_available & worker_available
    if earliest_start < 0:
        earliest_start = 0
    candidate_starts = np.flatnonzero(available_starts)
    candidate_starts = candidate_starts[candidate_starts >= earliest_start]
    if candidate_starts.size == 0:
        return None
    return int(candidate_starts[0])


def search_first_assignment(
    machine_slots,
    worker_slots,
    machine_candidates,
    worker_candidates,
    setup_time,
    process_time,
    earliest_start,
    rng,
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
            )
            if start_time is not None:
                return machine_id, worker_id, start_time

    return None
