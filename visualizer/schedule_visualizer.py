import matplotlib.pyplot as plt
from matplotlib.patches import Patch


class ScheduleVisualizer:
    """スケジュール結果をガントチャートで表示する。"""

    def __init__(self):
        self._real_time_figure = None
        self._real_time_axes = None

    def display_gant_v1(self, schedule_state, show=True):
        """機械と作業者のガントチャートを上下に表示する。"""
        assignments = schedule_state["assignments"]
        machine_slots = schedule_state["machine_slots"]
        worker_slots = schedule_state["worker_slots"]

        figure, axes = plt.subplots(
            2,
            1,
            sharex=True,
            figsize=(16, 10),
            constrained_layout=True,
        )
        machine_axis, worker_axis = axes

        self._setup_axis(
            axis=machine_axis,
            resource_count=machine_slots.shape[0] - 1,
            title="Machine Schedule",
            resource_label="Machine",
        )
        self._setup_axis(
            axis=worker_axis,
            resource_count=worker_slots.shape[0] - 1,
            title="Worker Schedule",
            resource_label="Worker",
        )

        for assignment in assignments.values():
            self._draw_machine_assignment(machine_axis, assignment)
            self._draw_worker_assignment(worker_axis, assignment)

        self._connect_order_setups(machine_axis, assignments, "machine_id")
        self._connect_order_setups(worker_axis, assignments, "worker_id")

        machine_axis.legend(handles=self._legend_handles(), loc="upper right")
        worker_axis.legend(handles=self._legend_handles(), loc="upper right")
        worker_axis.set_xlabel("Time (min)")

        if show:
            plt.show()

        return figure, axes

    def real_time_gant(
        self,
        best_schedule,
        comparison_schedule,
        display=True,
    ):
        """bestと比較対象のスケジュールを同じウィンドウで更新表示する。"""
        if (
            self._real_time_figure is None
            or not plt.fignum_exists(self._real_time_figure.number)
        ):
            self._real_time_figure, self._real_time_axes = plt.subplots(
                2,
                2,
                figsize=(20, 10),
                sharex="col",
                constrained_layout=True,
            )

        if display:
            plt.ion()

        for axis in self._real_time_axes.flat:
            axis.clear()

        best_machine_axis, best_worker_axis = self._real_time_axes[:, 0]
        comparison_machine_axis, comparison_worker_axis = self._real_time_axes[:, 1]

        self._draw_schedule_pair(
            best_schedule,
            best_machine_axis,
            best_worker_axis,
            "Best",
        )
        self._draw_schedule_pair(
            comparison_schedule,
            comparison_machine_axis,
            comparison_worker_axis,
            "Comparison",
        )

        self._real_time_figure.canvas.draw_idle()
        if display:
            self._real_time_figure.show()
            self._real_time_figure.canvas.flush_events()
            plt.pause(0.001)

        return self._real_time_figure, self._real_time_axes

    def _draw_schedule_pair(
        self,
        schedule_state,
        machine_axis,
        worker_axis,
        schedule_label,
    ):
        """1つのスケジュールを機械・作業者の2軸へ描画する。"""
        assignments = schedule_state["assignments"]
        machine_slots = schedule_state["machine_slots"]
        worker_slots = schedule_state["worker_slots"]
        makespan = schedule_state.get("evaluation", {}).get("makespan")
        if makespan is None and assignments:
            makespan = max(
                assignment["end_time"]
                for assignment in assignments.values()
            )
        if makespan is None:
            makespan = 0

        self._setup_axis(
            axis=machine_axis,
            resource_count=machine_slots.shape[0] - 1,
            title=f"{schedule_label} Machine (makespan: {makespan} min)",
            resource_label="Machine",
        )
        self._setup_axis(
            axis=worker_axis,
            resource_count=worker_slots.shape[0] - 1,
            title=f"{schedule_label} Worker",
            resource_label="Worker",
        )

        for assignment in assignments.values():
            self._draw_machine_assignment(machine_axis, assignment)
            self._draw_worker_assignment(worker_axis, assignment)

        self._connect_order_setups(machine_axis, assignments, "machine_id")
        self._connect_order_setups(worker_axis, assignments, "worker_id")
        machine_axis.legend(handles=self._legend_handles(), loc="upper right")
        worker_axis.legend(handles=self._legend_handles(), loc="upper right")
        worker_axis.set_xlabel("Time (min)")

    @staticmethod
    def _setup_axis(axis, resource_count, title, resource_label):
        """ガントチャートの軸を初期化する。"""
        resource_ids = list(range(1, resource_count + 1))
        axis.set_yticks(resource_ids)
        axis.set_yticklabels([f"{resource_label} {resource_id}" for resource_id in resource_ids])
        axis.set_ylabel(resource_label)
        axis.set_title(title)
        axis.grid(axis="x", linestyle="--", alpha=0.35)
        axis.set_ylim(0.5, resource_count + 0.5)

    @staticmethod
    def _draw_machine_assignment(axis, assignment):
        """機械側に段取と加工を描画する。"""
        label = f"O{assignment['order_id']}-P{assignment['process_id']}"
        axis.barh(
            assignment["machine_id"],
            assignment["setup_time"],
            left=assignment["start_time"],
            color="tab:orange",
            edgecolor="black",
            height=0.7,
            zorder=2,
        )
        axis.barh(
            assignment["machine_id"],
            assignment["process_time"],
            left=assignment["setup_end_time"],
            color="skyblue",
            edgecolor="black",
            height=0.7,
            zorder=2,
        )
        axis.text(
            assignment["start_time"]
            + (assignment["end_time"] - assignment["start_time"]) / 2,
            assignment["machine_id"],
            label,
            ha="center",
            va="center",
            fontsize=8,
        )

    @staticmethod
    def _draw_worker_assignment(axis, assignment):
        """作業者側に段取を描画する。"""
        label = f"O{assignment['order_id']}-P{assignment['process_id']}"
        axis.barh(
            assignment["worker_id"],
            assignment["setup_time"],
            left=assignment["start_time"],
            color="tab:orange",
            edgecolor="black",
            height=0.7,
            zorder=2,
        )
        axis.text(
            assignment["start_time"] + assignment["setup_time"] / 2,
            assignment["worker_id"],
            label,
            ha="center",
            va="center",
            fontsize=8,
        )

    @staticmethod
    def _connect_order_setups(axis, assignments, resource_key):
        """同一受注の段取バーを工程順に直線で接続する。"""
        order_assignments = {}
        for assignment in assignments.values():
            order_assignments.setdefault(assignment["order_id"], []).append(assignment)

        for order_id, order_items in order_assignments.items():
            sorted_items = sorted(order_items, key=lambda item: item["process_id"])
            for previous, current in zip(sorted_items, sorted_items[1:]):
                previous_center = (
                    previous["start_time"] + previous["setup_time"] / 2
                )
                current_center = current["start_time"] + current["setup_time"] / 2
                axis.plot(
                    [previous_center, current_center],
                    [previous[resource_key], current[resource_key]],
                    color="dimgray",
                    linewidth=1.0,
                    alpha=0.75,
                    zorder=1,
                )

    @staticmethod
    def _legend_handles():
        return [
            Patch(facecolor="tab:orange", edgecolor="black", label="Setup"),
            Patch(facecolor="skyblue", edgecolor="black", label="Process"),
        ]
