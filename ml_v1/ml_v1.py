import argparse
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
INPUT_DIR = ROOT / "output_csv"
OUTPUT_DIR = ROOT / "output_gantt"
STOPS_PATH = INPUT_DIR / "stops.csv"


def draw_stops(axis, stops_df, resource_type):
    """Draw resource-specific and global stop periods behind schedule bars."""
    stop_colors = {
        "machine": (1.0, 0.0, 0.0),
        "worker": (1.0, 0.0, 0.0),
        "setup": "pink",
        "process": "gray",
    }

    for row in stops_df.itertuples(index=False):
        if row.stop == resource_type:
            axis.barh(
                row.id,
                row.end - row.start,
                left=row.start,
                color=stop_colors[row.stop],
                edgecolor="black",
                height=0.7,
                zorder=1,
            )
        elif row.stop in ("setup", "process"):
            axis.axvspan(
                row.start,
                row.end,
                color=stop_colors[row.stop],
                alpha=0.65,
                zorder=10 if row.stop == "process" else 1,
            )
        else:
            continue


def save_gantt(df, output_path, stops_df=None):
    required = {
        "order_id", "process_id", "machine_id", "worker_id",
        "start_time", "setup_end_time", "end_time",
    }
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns: {', '.join(sorted(missing))}")
    if df.empty:
        raise ValueError("Schedule is empty")

    machine_ids = sorted(df["machine_id"].unique())
    worker_ids = sorted(df["worker_id"].unique())
    if stops_df is not None:
        machine_ids = sorted(set(machine_ids) | set(
            stops_df.loc[stops_df["stop"] == "machine", "id"]
        ))
        worker_ids = sorted(set(worker_ids) | set(
            stops_df.loc[stops_df["stop"] == "worker", "id"]
        ))

    figure, (machine_ax, worker_ax) = plt.subplots(
        2, 1, sharex=True, figsize=(16, 10), constrained_layout=True
    )
    try:
        if stops_df is not None:
            draw_stops(machine_ax, stops_df, "machine")
            draw_stops(worker_ax, stops_df, "worker")

        for row in df.itertuples(index=False):
            label = f"O{row.order_id}-P{row.process_id}"
            setup_width = row.setup_end_time - row.start_time
            process_width = row.end_time - row.setup_end_time
            machine_ax.barh(row.machine_id, setup_width, left=row.start_time,
                            color="tab:orange", edgecolor="black", height=0.7,
                            zorder=2)
            machine_ax.barh(row.machine_id, process_width, left=row.setup_end_time,
                            color="skyblue", edgecolor="black", height=0.7,
                            zorder=2)
            worker_ax.barh(row.worker_id, setup_width, left=row.start_time,
                           color="tab:orange", edgecolor="black", height=0.7,
                           zorder=2)
            if row.end_time - row.start_time >= 300:
                machine_ax.text((row.start_time + row.end_time) / 2, row.machine_id,
                                label, ha="center", va="center", fontsize=7)

        for ax, resource_ids, resource_name, title in (
            (machine_ax, machine_ids, "Machine", "Machine Schedule"),
            (worker_ax, worker_ids, "Worker", "Worker Setup Schedule"),
        ):
            ax.set_yticks(resource_ids)
            ax.set_yticklabels([f"{resource_name} {i}" for i in resource_ids])
            ax.set_title(title)
            ax.grid(axis="x", linestyle="--", alpha=0.35)
            ax.set_axisbelow(True)

        legend_handles = [
            Patch(facecolor="tab:orange", edgecolor="black", label="Setup"),
            Patch(facecolor="skyblue", edgecolor="black", label="Process"),
        ]
        if stops_df is not None:
            legend_handles.extend([
                Patch(facecolor=(1.0, 0.0, 0.0), edgecolor="black",
                      label="Machine / Worker Stop"),
                Patch(facecolor="pink", edgecolor="black", alpha=0.65,
                      label="Setup Stop"),
                Patch(facecolor="gray", edgecolor="black", alpha=0.65,
                      label="Process Stop"),
            ])
        machine_ax.legend(handles=legend_handles, loc="upper right")
        worker_ax.set_xlabel("Time (min)")
        figure.savefig(output_path, dpi=150)
    finally:
        plt.close(figure)


def main():
    parser = argparse.ArgumentParser(description="Save a Gantt chart for each schedule CSV")
    parser.add_argument("--format", choices=("png", "pdf"), default="png")
    args = parser.parse_args()

    csv_files = sorted(INPUT_DIR.glob("seed_*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in {INPUT_DIR}")

    OUTPUT_DIR.mkdir(exist_ok=True)
    stops_df = None
    if STOPS_PATH.exists():
        stops_df = pd.read_csv(STOPS_PATH)
        required_stop_columns = {"id", "start", "end", "stop"}
        missing = required_stop_columns - set(stops_df.columns)
        if missing:
            raise ValueError(
                f"Missing columns in {STOPS_PATH}: {', '.join(sorted(missing))}"
            )

    for csv_path in csv_files:
        df = pd.read_csv(csv_path)
        output_path = OUTPUT_DIR / f"{csv_path.stem}.{args.format}"
        save_gantt(df, output_path, stops_df)
        print(f"Saved: {output_path}")


if __name__ == "__main__":
    main()
