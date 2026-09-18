def calculate_makespan(schedule_state):
    """スケジュール内の最大終了時刻をmakespanとして返す。"""
    assignments = schedule_state["assignments"].values()
    end_times = [assignment["end_time"] for assignment in assignments]
    if not end_times:
        return 0
    return max(end_times)


def evaluate_schedule(schedule_state):
    """スケジュールを評価し、比較に使用する結果を返す。"""
    return {
        "makespan": calculate_makespan(schedule_state),
    }
