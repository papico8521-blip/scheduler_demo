from dataclasses import dataclass
from pprint import pprint
import random

@dataclass
class Tasks:
    seed: int = 42
    max_process: int = 3
    cutting_setup_time: int = 30    # 長さ1Mに付き2分   材料運搬時間
    cutting_time_dia: tuple = (1,1)         # ワーク直径1mmに対して１秒追加  直径1mm切断=1秒
    cutting_time_len: tuple = (10,1)        # ワーク長さ10mmに対して１秒追加  自動搬送時間
    setup_time:tuple = (30, 90, 10)
    proc_time:tuple = (3,10, 1)
    release_time:tuple = (0, 0, 0)
    process_over_lap: bool = True
    over_lap_buff:int = 1

class Generetor:
    def __init__(self, tasks, factory, orders):
        self.tasks = tasks
        self.factory = factory
        self.orders = orders

    def load(self):
        setting = self.tasks
        factory = self.factory
        orders = self.orders

        random.seed(setting.seed)

        product_list = sorted(
            list(
                set([v["製品ID"]for v in orders.values()])
                )
            )
        

        tasks = {p:{} for p in product_list}

        for v in tasks.values():
            max_p = random.randint(1, setting.max_process)
            for i in range(max_p):
                v[i+1] = {
                    "タイプ": "CNC加工",
                    "段取時間": random.randrange(*setting.setup_time),
                    "加工時間": random.randrange(*setting.proc_time),
                    "マシン候補": sorted(list(range(factory.cutting_machine + 1, factory.cutting_machine + factory.cnc_machine+1))),
                    "ワーカー候補": sorted(list(range(1, factory.cnc_worker+1))),
                    "次工程オーバーラップ": setting.process_over_lap
                    }

        result = {}
        for k, v in orders.items():
            # key
            p_k = 1
            result[k] = {}

            cutting_time = int(v["ワーク直径"] / setting.cutting_time_dia[0] * setting.cutting_time_dia[1])
            send_time = int(v["ワーク長さ"] / setting.cutting_time_len[0] * setting.cutting_time_len[1])
            cutting_time = cutting_time + send_time

            match setting.release_time:
                case (0,0,0):
                    release_time = 0
                case _:
                    release_time = random.randrange(*setting.release_time)
                

            # value
            result[k]["受注情報"] = v
            result[k]["工程情報"] = {}
            result[k]["工程情報"][p_k]={
                "タイプ": "材料切断",
                "段取時間": setting.cutting_setup_time,
                "総加工時間": (cutting_time * v["生産数"]) // 60,
                "マシン候補": sorted(list(range(1, factory.cutting_machine+1))),
                "ワーカー候補": sorted(list(range(1, factory.cnc_worker+1))),
                "次工程オーバーラップ": setting.process_over_lap,
                "単加工時間": cutting_time,
                "単体単位": "sec",
                "着手可能時間": release_time,
                "オーバーラップバッファ": setting.over_lap_buff
                }
            
            p_k += 1
            max_proc = max(tasks[v["製品ID"]])
            for i in range(1, max_proc+1):
                result[k]["工程情報"][p_k] = {
                    "タイプ": tasks[v["製品ID"]][i]["タイプ"],
                    "段取時間": tasks[v["製品ID"]][i]["段取時間"],
                    "総加工時間": tasks[v["製品ID"]][i]["加工時間"] * v["生産数"],
                    "マシン候補": tasks[v["製品ID"]][i]["マシン候補"],
                    "ワーカー候補": tasks[v["製品ID"]][i]["ワーカー候補"],
                    "単加工時間": tasks[v["製品ID"]][i]["加工時間"],
                    "単体単位": "min",
                    "次工程オーバーラップ": setting.process_over_lap,
                    "着手可能時間": release_time,
                    "オーバーラップバッファ": setting.over_lap_buff
                }
                p_k += 1

        return result, tasks