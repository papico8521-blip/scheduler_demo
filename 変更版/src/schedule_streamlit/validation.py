"""停止・ブロック入力と生成スケジュールの検証。"""

from collections import defaultdict


def _as_integer(value, label):
    if isinstance(value, bool) or value is None:
        raise ValueError(f"{label}は整数で指定してください")
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError(f"{label}は整数で指定してください") from error
    if str(value).strip() not in (str(number), f"{number}.0"):
        raise ValueError(f"{label}は整数で指定してください")
    return number


def validate_conditions(stops, blocks, factory, horizon):
    """UI入力を正規化し、同一種別・対象内の重複を確認する。"""
    clean_stops = []
    clean_blocks = []
    errors = []
    machine_count = factory["cutting_machine"] + factory["cnc_machine"]
    worker_count = factory["cnc_worker"]
    intervals = defaultdict(list)
    for number, row in enumerate(stops, 1):
        try:
            resource_type = str(row["resource_type"]).strip()
            resource_id = _as_integer(row["resource_id"], "対象ID")
            start = _as_integer(row["start_time"], "開始時刻")
            end = _as_integer(row["end_time"], "終了時刻")
            maximum = machine_count if resource_type == "machine" else worker_count
            if resource_type not in ("machine", "worker"):
                raise ValueError("対象種別はmachineまたはworkerを指定してください")
            if not 1 <= resource_id <= maximum:
                raise ValueError(f"対象IDは1～{maximum}で指定してください")
            if not 0 <= start < end <= horizon:
                raise ValueError(f"0 <= 開始 < 終了 <= {horizon}で指定してください")
            clean_stops.append(dict(resource_type=resource_type, resource_id=resource_id,
                                    start_time=start, end_time=end))
            intervals[("stop", resource_type, resource_id)].append((start, end, number))
        except (KeyError, ValueError) as error:
            errors.append(f"停止時間 {number}行目: {error}")
    for number, row in enumerate(blocks, 1):
        try:
            block_type = str(row["block_type"]).strip()
            start = _as_integer(row["start_time"], "開始時刻")
            end = _as_integer(row["end_time"], "終了時刻")
            if block_type not in ("setup", "process"):
                raise ValueError("ブロック種別はsetupまたはprocessを指定してください")
            if not 0 <= start < end <= horizon:
                raise ValueError(f"0 <= 開始 < 終了 <= {horizon}で指定してください")
            clean_blocks.append(dict(block_type=block_type, start_time=start, end_time=end))
            intervals[("block", block_type)].append((start, end, number))
        except (KeyError, ValueError) as error:
            errors.append(f"ブロック時間 {number}行目: {error}")
    for key, values in intervals.items():
        ordered = sorted(values)
        for before, after in zip(ordered, ordered[1:]):
            if after[0] < before[1]:
                errors.append(f"{key} の {before[2]}行目と{after[2]}行目が重複しています")
    return clean_stops, clean_blocks, errors


def _overlaps(start, end, interval_start, interval_end):
    return start < interval_end and interval_start < end


def validate_schedule(assignments, tasks, factory, stops, blocks, horizon):
    """既存探索の割当を独立に検証する。加工ブロックは処理の中断を許す。"""
    violations = []
    expected = {(order_id, process_id)
                for order_id, order in tasks.items()
                for process_id in order["工程情報"]}
    if isinstance(assignments, dict):
        rows = list(assignments.values())
    else:
        rows = list(assignments)
    actual = defaultdict(list)
    machine_assignments = defaultdict(list)
    worker_assignments = defaultdict(list)
    stop_by_resource = defaultdict(list)
    for stop in stops:
        stop_by_resource[(stop["resource_type"], stop["resource_id"])].append(
            (stop["start_time"], stop["end_time"])
        )
    setup_blocks = [(b["start_time"], b["end_time"]) for b in blocks
                    if b["block_type"] == "setup"]
    process_blocks = [(b["start_time"], b["end_time"]) for b in blocks
                      if b["block_type"] == "process"]
    for row in rows:
        key = row["order_id"], row["process_id"]
        actual[key].append(row)
        if key not in expected:
            violations.append(f"未知の工程 {key}")
            continue
        process = tasks[key[0]]["工程情報"][key[1]]
        start, setup_end, end = row["start_time"], row["setup_end_time"], row["end_time"]
        machine_id, worker_id = row["machine_id"], row["worker_id"]
        if start < 0 or not start <= setup_end <= end:
            violations.append(f"{key}: 開始・段取終了・終了時刻が不正")
        if end > horizon:
            violations.append(f"{key}: ホライズン超過")
        if setup_end - start != process["段取時間"]:
            violations.append(f"{key}: 段取時間が不一致")
        if start < process["着手可能時間"]:
            violations.append(f"{key}: 着手可能時間違反")
        if machine_id not in process["マシン候補"]:
            violations.append(f"{key}: 機械候補違反")
        if worker_id not in process["ワーカー候補"]:
            violations.append(f"{key}: 作業者候補違反")
        if not 1 <= machine_id <= factory["cutting_machine"] + factory["cnc_machine"]:
            violations.append(f"{key}: 機械ID範囲外")
        if not 1 <= worker_id <= factory["cnc_worker"]:
            violations.append(f"{key}: 作業者ID範囲外")
        machine_assignments[machine_id].append((start, end, key))
        worker_assignments[worker_id].append((start, setup_end, key))
        for blocked_start, blocked_end in stop_by_resource[("machine", machine_id)]:
            if _overlaps(start, end, blocked_start, blocked_end):
                violations.append(f"{key}: 機械停止時間と重複")
        for blocked_start, blocked_end in stop_by_resource[("worker", worker_id)]:
            if _overlaps(start, setup_end, blocked_start, blocked_end):
                violations.append(f"{key}: 作業者停止時間と重複")
        for blocked_start, blocked_end in setup_blocks:
            if _overlaps(start, setup_end, blocked_start, blocked_end):
                violations.append(f"{key}: 段取ブロックと重複")
        # 加工ブロック内は処理を中断する。経過時間から中断分を除いた実加工時間を確認する。
        blocked_minutes = sum(
            max(0, min(end, block_end) - max(setup_end, block_start))
            for block_start, block_end in process_blocks
        )
        if end - setup_end - blocked_minutes != process["総加工時間"]:
            violations.append(f"{key}: 実加工時間が不一致")
    for key in expected - actual.keys():
        violations.append(f"{key}: 未割当")
    for key, items in actual.items():
        if len(items) > 1:
            violations.append(f"{key}: 重複割当")
    for resource, grouped in (("機械", machine_assignments), ("作業者", worker_assignments)):
        for resource_id, intervals in grouped.items():
            ordered = sorted(intervals)
            for before, after in zip(ordered, ordered[1:]):
                if after[0] < before[1]:
                    violations.append(f"{resource}{resource_id}: {before[2]}と{after[2]}が重複")
    for (order_id, process_id), items in actual.items():
        previous = actual.get((order_id, process_id - 1))
        if process_id <= 1 or not previous or len(items) != 1 or len(previous) != 1:
            continue
        current, prior = items[0], previous[0]
        if prior["over_lap"]:
            base = prior["start_time"] + prior["over_lap_buff"]
            duration = (tasks[order_id]["工程情報"][process_id]["段取時間"]
                        + tasks[order_id]["工程情報"][process_id]["総加工時間"])
            required = max(base, prior["end_time"] - duration)
        else:
            required = prior["end_time"]
        if current["start_time"] < required:
            violations.append(f"{(order_id, process_id)}: 工程順序・オーバーラップ違反")
    return {"is_valid": not violations, "violation_count": len(violations),
            "violations": violations}
