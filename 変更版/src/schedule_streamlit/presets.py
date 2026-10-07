"""停止時間補助設定のプリセット生成。"""


MINUTES_PER_DAY = 24 * 60
REFERENCE_HOUR = 9
LUNCH_START = (12 - REFERENCE_HOUR) * 60
LUNCH_END = (13 - REFERENCE_HOUR) * 60
NIGHT_START = (17 - REFERENCE_HOUR) * 60


def _time_ranges(day_count, lunch, night):
    if int(day_count) < 1:
        raise ValueError("日数は1以上で指定してください")
    if not lunch and not night:
        raise ValueError("昼休みまたは夜間休止を選択してください")
    intervals = []
    for day in range(int(day_count)):
        day_offset = day * MINUTES_PER_DAY
        if lunch:
            intervals.append((day_offset + LUNCH_START, day_offset + LUNCH_END))
        if night:
            intervals.append((day_offset + NIGHT_START, day_offset + MINUTES_PER_DAY))
    return intervals


def build_stop_presets(resource_type, resource_ids, day_count, lunch, night):
    """9:00基準で、昼休み・夜間休止の停止時間を生成する。"""
    if resource_type not in ("machine", "worker"):
        raise ValueError("対象種別はmachineまたはworkerを指定してください")
    resource_ids = [int(value) for value in resource_ids]
    if not resource_ids or any(value < 1 for value in resource_ids):
        raise ValueError("対象IDは1以上で指定してください")
    return [
        {"resource_type": resource_type, "resource_id": resource_id,
         "start_time": start_time, "end_time": end_time}
        for resource_id in resource_ids
        for start_time, end_time in _time_ranges(day_count, lunch, night)
    ]


def build_setup_block_presets(day_count, lunch, night):
    """全作業者共通の段取ブロック行を生成する。"""
    return [
        {"block_type": "setup", "start_time": start_time, "end_time": end_time}
        for start_time, end_time in _time_ranges(day_count, lunch, night)
    ]
