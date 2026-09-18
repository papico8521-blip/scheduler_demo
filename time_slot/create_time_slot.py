import numpy as np
import sys

class SlotMaker:
    def __init__(self, factory, tasks):
        self.factory = factory
        self.tasks = tasks

    def load(self, slot=1):
        horizon = self._calculate_horizon()

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

    def create_block_slots(self, slot=1, setup_block=None, proc_block=None):
        """全作業者・全機械共通の禁止区間マスクを生成する。"""
        horizon = int(self._calculate_horizon() // slot)
        worker_count = self.factory.cnc_worker + 1
        machine_count = self.factory.cutting_machine + self.factory.cnc_machine + 1
        worker_setup_block = np.zeros((worker_count, horizon), dtype=np.int8)
        machine_proc_block = np.zeros((machine_count, horizon), dtype=np.int8)

        self._apply_global_blocks(
            worker_setup_block,
            setup_block or [],
            "setup_block",
        )
        self._apply_global_blocks(
            machine_proc_block,
            proc_block or [],
            "proc_block",
        )
        return worker_setup_block, machine_proc_block

    def _calculate_horizon(self):
        """全工程の段取＋総加工時間から区間長を計算する。"""
        horizon = 0
        for order_data in self.tasks.values():
            for process_data in order_data["工程情報"].values():
                horizon += process_data["段取時間"]
                horizon += process_data["総加工時間"]
        return horizon

    @staticmethod
    def _apply_global_blocks(slot, blocks, block_name):
        """全資源へ共通禁止区間を設定する。"""
        horizon = slot.shape[1]
        for start, end in blocks:
            if not 0 <= start < end <= horizon:
                raise ValueError(
                    f"{block_name}は0 <= start < end <= {horizon}で指定してください。"
                )
            slot[1:, start:end] = 1

    def add_stop_section(self, index, slot, start, end):
        # 強制停止区間設定
        slot[index][start:end] = 1
        #print(slot[index][start-2:end+2])
        return slot

if __name__ == "__main__":
    pass
