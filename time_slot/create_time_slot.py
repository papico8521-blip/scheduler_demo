import numpy as np
import sys

class SlotMaker:
    def __init__(self, factory, tasks):
        self.factory = factory
        self.tasks = tasks

    def load(self, slot=1):
        horizon = 0
        for v in self.tasks.values():
            for k,vv in v["工程情報"].items():
                horizon += vv["段取時間"]
                horizon += vv["総加工時間"]

        print(f"スケジュール区間 : 0分～{horizon}分 (約{horizon//60}時間) " )
        print(f"スケジュール粒度設定 : {slot}分")

        horizon = int(horizon // slot)
        max_machine = self.factory.cutting_machine + self.factory.cnc_machine

        worker_slot = np.zeros(
            (self.factory.cnc_worker+1, horizon),
            dtype=np.int8
        )

        machine_slot = np.zeros(
            (max_machine+1, horizon),
            dtype=np.int8
        )

        print("---タイムスロット生成---")
        print(f"作業者ID : 1 ～ {worker_slot.shape[0]-1}")
        print(f"機械ID : 1 ～ {machine_slot.shape[0]-1}")
        print(f"スロット数 : {machine_slot.shape[1]}")

        return worker_slot, machine_slot

    def add_stop_section(self, index, slot, start, end):
        # 強制停止区間設定
        slot[index][start:end] = 1
        #print(slot[index][start-2:end+2])
        return slot

if __name__ == "__main__":
    pass