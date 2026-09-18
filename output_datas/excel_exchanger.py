import pandas as pd
from copy import deepcopy

class DataChanger:
    def __init__(self):
        pass

    def save_to_excel_best(self, result, path="スケジュール結果.xlsx"):
        """main()のbest_schedules先頭の結果をExcelへ出力する。"""
        try:
            best_schedule = result["best_schedules"][0]
        except (KeyError, IndexError, TypeError) as error:
            raise ValueError(
                "best_schedulesに出力可能なスケジュールがありません。"
            ) from error

        schedule_state = best_schedule["schedule_state"]
        assignments = schedule_state["assignments"].values()
        schedule_rows = [
            {
                "受注ID": assignment["order_id"],
                "製品ID": assignment["product_id"],
                "工程ID": assignment["process_id"],
                "機械ID": assignment["machine_id"],
                "作業者ID": assignment["worker_id"],
                "着手可能時間": assignment["release_time"],
                "開始時間": assignment["start_time"],
                "段取完了時間": assignment["setup_end_time"],
                "終了時間": assignment["end_time"],
                "段取時間": assignment["setup_time"],
                "総加工時間": assignment["process_time"],
                "オーバーラップ": assignment["over_lap"],
                "オーバーラップバッファ": assignment["over_lap_buff"],
            }
            for assignment in assignments
        ]

        for s in schedule_rows:
            s["生産数"]=result["orders"][s["受注ID"]]["生産数"]
            s["優先度"]=result["orders"][s["受注ID"]]["優先度"]

        if result["stop_datas"]:
            for s in result["stop_datas"]:
                s = {
                    "受注ID":"強制停止",
                    "機械ID": s[0],
                    "開始時間": s[1],
                    "終了時間": s[2],
                }
                schedule_rows.append(s)

        schedule_df = pd.DataFrame(schedule_rows)
        evaluation_df = pd.DataFrame([
            {
                "評価項目": "makespan",
                "値": best_schedule["makespan"],
                "単位": "分",
            }
        ])

        try:
            with pd.ExcelWriter(path) as writer:
                schedule_df.to_excel(
                    writer,
                    sheet_name="スケジュール",
                    index=False,
                )
                evaluation_df.to_excel(
                    writer,
                    sheet_name="評価",
                    index=False,
                )
        except Exception as error:
            raise ValueError(
                "スケジュール結果のエクスポートに失敗しました。"
            ) from error


    def save_to_excel(self, datas):

        # DataFrame前処理
        # 受注情報
        orders = [o for o in datas["orders"].values()]
        df = pd.DataFrame(orders)
        df = df[["受注ID","製品ID","生産数","優先度","ワーク直径","ワーク長さ"]]
        datas["orders"] = df.copy()

        # ファクトリ情報はFactory設定から生成する。
        factory_setting = datas["factory"]
        worker_ids = list(range(1, factory_setting.cnc_worker + 1))
        factory = [
            {
                "工場ID": factory_setting_id,
                "機械タイプ": machine_type,
                "機械ID": machine_id,
                "作業者ID": worker_ids,
            }
            for factory_setting_id in range(1, factory_setting.count + 1)
            for machine_type, machine_start, machine_count in (
                ("切断機", 1, factory_setting.cutting_machine),
                (
                    "CNC加工機",
                    factory_setting.cutting_machine + 1,
                    factory_setting.cnc_machine,
                ),
            )
            for machine_id in range(machine_start, machine_start + machine_count)
        ]

        df = pd.DataFrame(factory)
        datas["factory"] = df.copy()

        # タスク情報
        tasks = []
        for v in datas["tasks"].values():
            buff_a = v["受注情報"]
            for k,vv in v["工程情報"].items():
                buff_b = {
                    "工程NO": k,
                    "タイプ": vv["タイプ"],
                    "マシン候補": vv["マシン候補"],
                    "ワーカー候補": vv["ワーカー候補"],
                    "段取時間": vv["段取時間"],
                    "単加工時間":vv["単加工時間"],
                    "単体単位":vv["単体単位"],
                    "総加工時間":vv["総加工時間"],
                    "次工程オーバーラップ":vv["次工程オーバーラップ"],
                    "オーバラップバッファ":vv["オーバーラップバッファ"],
                    "着手可能時間":vv["着手可能時間"]
                }

                buff_c = deepcopy(buff_a | buff_b)
                tasks.append(buff_c)

        df["段取時間単位"] = "min"
        df["総加工時間単位"] = "min"
        df = pd.DataFrame(tasks)

        datas["tasks"] = df.copy()

        try:
            datas["orders"].to_excel("./受注一覧.xlsx", index=False)
            datas["factory"].to_excel("./工場情報.xlsx", index=False)
            datas["tasks"].to_excel("./工程情報.xlsx", index=False)
        except:
            raise(ValueError("エクスポートに失敗-エクセルファイルを閉じてください"))


if __name__ == "__main__":
    pass
