"""Streamlitの画面入口。変更版ディレクトリから起動する。"""

import json
from importlib import reload
from statistics import mean

import pandas as pd
import streamlit as st

from schedule_streamlit import charts, engine, presets, storage
from schedule_streamlit.validation import validate_conditions

# Streamlitは画面だけを再実行するため、補助設定と描画の定義も更新する。
reload(presets)
reload(charts)


def _rows(frame):
    return frame.to_dict("records")


def _merge_stop_rows(rows):
    merged = []
    seen = set()
    for row in rows:
        key = (
            row["resource_type"], row["resource_id"],
            row["start_time"], row["end_time"],
        )
        if key not in seen:
            merged.append(row)
            seen.add(key)
    return merged


def _merge_block_rows(rows):
    merged = []
    seen = set()
    for row in rows:
        key = row["block_type"], row["start_time"], row["end_time"]
        if key not in seen:
            merged.append(row)
            seen.add(key)
    return merged


def _condition_editor(dataset_id, factory, tasks):
    saved_stops, saved_blocks = storage.load_conditions(dataset_id)
    draft_key = f"condition_draft_{dataset_id}"
    draft = st.session_state.get(draft_key)
    stops = draft["stops"] if draft is not None else saved_stops
    blocks = draft["blocks"] if draft is not None else saved_blocks
    pending_stops = st.session_state.pop(f"pending_stops_{dataset_id}", None)
    pending_blocks = st.session_state.pop(f"pending_blocks_{dataset_id}", None)
    if pending_stops is not None:
        stops = pending_stops
        st.session_state.pop(f"machine_stops_{dataset_id}", None)
        st.session_state.pop(f"worker_stops_{dataset_id}", None)
    if pending_blocks is not None:
        blocks = pending_blocks
        st.session_state.pop(f"setup_{dataset_id}", None)
        st.session_state.pop(f"process_{dataset_id}", None)
    if pending_stops is not None or pending_blocks is not None:
        st.session_state[draft_key] = {"stops": stops, "blocks": blocks}
    horizon = engine.horizon_for(tasks)
    st.caption(f"時刻の単位は分。現在のホライズンは 0～{horizon} 分です。")
    block_columns = ["start_time", "end_time"]
    machine_stop_frame = pd.DataFrame(
        [
            {
                "resource_id": row["resource_id"],
                "start_time": row["start_time"],
                "end_time": row["end_time"],
            }
            for row in stops if row["resource_type"] == "machine"
        ],
        columns=["resource_id", *block_columns],
    )
    worker_stop_frame = pd.DataFrame(
        [
            {
                "resource_id": row["resource_id"],
                "start_time": row["start_time"],
                "end_time": row["end_time"],
            }
            for row in stops if row["resource_type"] == "worker"
        ],
        columns=["resource_id", *block_columns],
    )
    setup_frame = pd.DataFrame(
        [b for b in blocks if b["block_type"] == "setup"], columns=["block_type", *block_columns]
    )[block_columns]
    process_frame = pd.DataFrame(
        [b for b in blocks if b["block_type"] == "process"], columns=["block_type", *block_columns]
    )[block_columns]
    st.subheader("機械の停止時間")
    machine_stop_input = st.data_editor(
        machine_stop_frame, num_rows="dynamic", hide_index=True,
        key=f"machine_stops_{dataset_id}",
        column_config={
            "resource_id": st.column_config.SelectboxColumn(
                "機械ID", options=list(range(1, factory["cutting_machine"] + factory["cnc_machine"] + 1)),
                required=True,
            ),
            "start_time": st.column_config.NumberColumn("開始（分）", step=1, required=True),
            "end_time": st.column_config.NumberColumn("終了（分）", step=1, required=True),
        },
    )
    st.subheader("作業者の停止時間")
    worker_stop_input = st.data_editor(
        worker_stop_frame, num_rows="dynamic", hide_index=True,
        key=f"worker_stops_{dataset_id}",
        column_config={
            "resource_id": st.column_config.SelectboxColumn(
                "作業者ID", options=list(range(1, factory["cnc_worker"] + 1)),
                required=True,
            ),
            "start_time": st.column_config.NumberColumn("開始（分）", step=1, required=True),
            "end_time": st.column_config.NumberColumn("終了（分）", step=1, required=True),
        },
    )
    st.subheader("段取ブロック（全作業者）")
    setup_input = st.data_editor(
        setup_frame, num_rows="dynamic", hide_index=True, key=f"setup_{dataset_id}",
    )
    st.subheader("加工ブロック（全機械）")
    process_input = st.data_editor(
        process_frame, num_rows="dynamic", hide_index=True, key=f"process_{dataset_id}",
    )
    input_blocks = (
        [{"block_type": "setup", **row} for row in _rows(setup_input)]
        + [{"block_type": "process", **row} for row in _rows(process_input)]
    )
    input_stops = (
        [{"resource_type": "machine", **row} for row in _rows(machine_stop_input)]
        + [{"resource_type": "worker", **row} for row in _rows(worker_stop_input)]
    )
    valid_stops, valid_blocks, errors = validate_conditions(
        input_stops, input_blocks, factory, horizon
    )
    if errors:
        for message in errors:
            st.error(message)
    if st.button("停止・ブロック設定を保存", disabled=bool(errors)):
        storage.save_conditions(dataset_id, valid_stops, valid_blocks)
        st.success("設定を保存しました")
    return valid_stops, valid_blocks, errors


def _stop_preset_page(dataset_id, factory, tasks, stops, blocks, input_errors):
    """停止時間の目安を使って既存の停止時間表へ行を追加する。"""
    horizon = engine.horizon_for(tasks)
    st.subheader("停止時間補助設定")
    st.caption("9:00をhorizon 0分として、参考となる停止時間を追加します。")
    stop_mode = st.radio(
        "停止種別", ["operation", "setup"], horizontal=True,
        format_func=lambda value: (
            "稼働停止（選択した機械・作業者を停止）"
            if value == "operation" else "段取のみ停止（全作業者共通）"
        ),
        key=f"preset_stop_mode_{dataset_id}",
    )
    operation_stop = stop_mode == "operation"
    setup_stop = stop_mode == "setup"
    if operation_stop:
        resource_type = st.selectbox(
            "対象種別", ["machine", "worker"],
            format_func=lambda value: "機械" if value == "machine" else "作業者",
            key=f"preset_resource_type_{dataset_id}",
        )
        resource_count = (
            factory["cutting_machine"] + factory["cnc_machine"]
            if resource_type == "machine" else factory["cnc_worker"]
        )
        resource_scope = st.selectbox(
            "対象範囲", ["individual", "all"],
            format_func=lambda value: (
                f"選択した{'機械' if resource_type == 'machine' else '作業者'}"
                if value == "individual"
                else f"{'機械' if resource_type == 'machine' else '作業者'}全体"
            ),
            key=f"preset_resource_scope_{dataset_id}",
        )
        resource_ids = list(range(1, resource_count + 1))
        if resource_scope == "individual":
            resource_id = st.selectbox(
                "対象ID", resource_ids,
                format_func=lambda value: f"{('機械' if resource_type == 'machine' else '作業者')} {value}",
                key=f"preset_resource_id_{dataset_id}",
            )
            selected_resource_ids = [resource_id]
        else:
            selected_resource_ids = resource_ids
            st.info(
                f"{('機械' if resource_type == 'machine' else '作業者')} "
                f"{len(selected_resource_ids)}件すべてに追加します。"
            )
    day_count = st.number_input(
        "追加する日数", min_value=1, value=1, step=1,
        key=f"preset_day_count_{dataset_id}",
    )
    st.write("追加対象")
    lunch = st.checkbox("昼休み（12:00～13:00）", value=True,
                        key=f"preset_lunch_{dataset_id}")
    night = st.checkbox("夜間休止（17:00～翌日9:00）", value=True,
                        key=f"preset_night_{dataset_id}")
    preview_stops = presets.build_stop_presets(
        resource_type, selected_resource_ids, day_count, lunch, night
    ) if operation_stop and (lunch or night) else []
    preview_blocks = presets.build_setup_block_presets(
        day_count, lunch, night
    ) if setup_stop and (lunch or night) else []
    if preview_stops:
        st.caption("稼働停止 → 機械・作業者の停止時間表")
        st.dataframe(pd.DataFrame(preview_stops), hide_index=True, width="stretch")
    if preview_blocks:
        st.caption("段取のみ停止 → 段取ブロック表（全作業者）")
        st.dataframe(pd.DataFrame(preview_blocks), hide_index=True, width="stretch")
    merged_stops = _merge_stop_rows(stops + preview_stops)
    merged_blocks = _merge_block_rows(blocks + preview_blocks)
    _, _, preview_errors = validate_conditions(
        merged_stops, merged_blocks, factory, horizon
    ) if preview_stops or preview_blocks else ([], [], [])
    if preview_stops or preview_blocks:
        st.caption(
            f"入力可能範囲: 0～{horizon}分。"
        )
    for error in preview_errors:
        st.error(error)
    if st.button(
        "停止・ブロック設定へ追加", type="primary",
        disabled=bool(input_errors or preview_errors) or not (preview_stops or preview_blocks),
        key=f"add_presets_{dataset_id}",
    ):
        st.session_state[f"pending_stops_{dataset_id}"] = merged_stops
        st.session_state[f"pending_blocks_{dataset_id}"] = merged_blocks
        st.session_state[f"preset_message_{dataset_id}"] = (
            "停止・ブロック設定に追加しました。内容を確認して保存してください。"
        )
        st.rerun()
    message = st.session_state.pop(f"preset_message_{dataset_id}", None)
    if message:
        st.success(message)
    st.divider()
    st.subheader("停止時間の目安")
    st.markdown(
        """
        `horizon = 0` は午前9:00です。入力単位は分です。

        | 時刻 | horizon |
        |---|---:|
        | 9:00 | 0 |
        | 12:00 | 180 |
        | 13:00 | 240 |
        | 17:00 | 480 |
        | 翌日9:00 | 1440 |

        昼休みは `n × 1440 + 180 ～ n × 1440 + 240`、夜間休止は
        `n × 1440 + 480 ～ (n + 1) × 1440` です。`n=0`が初日です。
        """
    )


def _display_results(dataset_id):
    runs = storage.list_runs(dataset_id)
    if not runs:
        st.info("このデータセットの実行履歴はまだありません。")
        return
    st.dataframe(pd.DataFrame(runs), hide_index=True, width="stretch")
    run_ids = [row["id"] for row in runs]
    default_run = st.session_state.get("latest_run_id")
    selected_run = st.selectbox(
        "表示する実行", run_ids,
        index=run_ids.index(default_run) if default_run in run_ids else 0,
        format_func=lambda value: f"実行 #{value}",
        key=f"run_select_{dataset_id}",
    )
    run, trials, assignments, settings = storage.load_run(selected_run)
    if not settings["blocks"]:
        st.info(
            "この実行履歴には段取・加工ブロックが記録されていません。"
            "設定を保存して再実行すると、ガントチャートに禁止時間が表示されます。"
        )
    else:
        setup_count = sum(block["block_type"] == "setup" for block in settings["blocks"])
        process_count = sum(block["block_type"] == "process" for block in settings["blocks"])
        st.caption(
            f"この実行に保存されたブロック: 段取 {setup_count} 件、加工 {process_count} 件。"
            "設定変更後のチャートは、通常探索を再実行すると更新されます。"
        )
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("最良Makespan", f"{run['best_makespan']} 分")
    col2.metric("平均Makespan", f"{mean(t['makespan'] for t in trials):.1f} 分")
    col3.metric("最悪Makespan", f"{max(t['makespan'] for t in trials)} 分")
    col4.metric("制約違反数", run["violation_count"])
    st.caption(
        f"最良試行: {run['best_trial']} / {run['trial_count']}、"
        f"割当工程: {len(assignments)}、実行時間: {run['elapsed']:.3f} 秒、"
        f"1回平均: {run['elapsed'] / run['trial_count']:.3f} 秒"
    )
    st.plotly_chart(charts.trial_chart(trials), width="stretch")
    st.subheader("各試行")
    trial_rows = [{
        "試行": t["trial_number"], "探索seed": t["seed"],
        "Makespan（分）": t["makespan"], "実行時間（秒）": t["elapsed"],
        "制約違反数": t["violation_count"],
    } for t in trials]
    st.dataframe(pd.DataFrame(trial_rows), hide_index=True, width="stretch")
    best_trial = next(t for t in trials if t["trial_number"] == run["best_trial"])
    violations = json.loads(best_trial["violations_json"])
    if violations:
        st.error("最良試行に制約違反があります")
        st.dataframe(pd.DataFrame({"違反内容": violations}), hide_index=True)
    st.subheader("最良スケジュール")
    assignment_frame = pd.DataFrame(assignments).sort_values(
        ["start_time", "order_id", "process_id"]
    )
    st.dataframe(assignment_frame, hide_index=True, width="stretch")
    st.download_button(
        "最良スケジュールをCSVダウンロード",
        assignment_frame.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"schedule_run_{selected_run}.csv", mime="text/csv",
    )
    st.plotly_chart(
        charts.gantt(assignments, settings["stops"], settings["blocks"], "machine"),
        width="stretch",
    )
    st.plotly_chart(
        charts.gantt(assignments, settings["stops"], settings["blocks"], "worker"),
        width="stretch",
    )
    st.caption(
        "ピンク帯は段取禁止時間（両チャートに表示、全作業者に適用）。"
        "赤い横棒は個別停止、薄い赤帯は加工ブロック（機械のみ）。"
        "加工ブロック中は処理を中断します。"
    )


def main():
    st.set_page_config(page_title="スケジューリングサンプル", layout="wide")
    storage.initialize()
    st.title("スケジューリングサンプル")
    st.sidebar.header("ダミーデータ生成")
    with st.sidebar.form("generation"):
        seed = st.number_input("乱数シード", min_value=0, value=42, step=1)
        order_count = st.number_input("受注数", min_value=1, value=10, step=1)
        product_count = st.number_input("製品数", min_value=1, value=5, step=1)
        product_select = st.selectbox("製品選択方式", ["連続", "ランダム"])
        priority = st.selectbox("優先度方式", ["連続", "ランダム"])
        overlap = st.checkbox("工程オーバーラップ", value=True)
        reset = st.form_submit_button("ダミーデータを生成・リセット")
    if reset:
        config = dict(
            seed=int(seed), order_count=int(order_count), product_count=int(product_count),
            product_select=product_select, priority=priority, overlap=overlap,
        )
        try:
            factory, orders, tasks, products = engine.generate(config)
            new_id = storage.save_dataset(config, factory, orders, tasks, products)
            st.session_state["dataset_select"] = new_id
            st.session_state.pop("latest_run_id", None)
            st.rerun()
        except (ValueError, RuntimeError) as error:
            st.error(f"ダミーデータ生成に失敗しました: {error}")
    datasets = storage.list_datasets()
    if not datasets:
        st.info("左側の設定を選び、ダミーデータを生成してください。")
        return
    dataset_ids = [row["id"] for row in datasets]
    if st.session_state.get("dataset_select") not in dataset_ids:
        st.session_state["dataset_select"] = dataset_ids[0]
    dataset_id = st.selectbox(
        "使用するデータセット", dataset_ids,
        format_func=lambda value: (
            f"#{value} / seed {next(d['seed'] for d in datasets if d['id'] == value)}"
        ),
        key="dataset_select",
    )
    metadata, factory, orders, tasks, products = storage.load_dataset(dataset_id)
    st.caption(
        f"seed {metadata['seed']}・受注 {metadata['order_count']} 件・"
        f"製品候補 {metadata['product_count']} 種・"
        f"製品選択 {metadata['product_select']}・優先度 {metadata['priority']}・"
        f"オーバーラップ {'有効' if metadata['overlap'] else '無効'}"
    )
    data_tab, condition_tab, preset_tab, run_tab, result_tab = st.tabs(
        ["ダミーデータ", "停止・ブロック設定", "停止時間補助設定",
         "スケジューリング", "結果・履歴"]
    )
    with data_tab:
        st.subheader("受注")
        st.dataframe(pd.DataFrame(orders.values()), hide_index=True, width="stretch")
        st.subheader("受注で使用する製品")
        product_rows = [{key: value for key, value in product.items() if key != "工程構成"}
                        for product in products.values()]
        st.dataframe(pd.DataFrame(product_rows), hide_index=True, width="stretch")
        st.subheader("工程")
        process_rows = [
            {"受注ID": order_id, "工程ID": process_id, **process}
            for order_id, order in tasks.items()
            for process_id, process in order["工程情報"].items()
        ]
        st.dataframe(pd.DataFrame(process_rows), hide_index=True, width="stretch")
        st.caption(
            f"切断機械 {factory['cutting_machine']} 台、CNC機械 {factory['cnc_machine']} 台、"
            f"作業者 {factory['cnc_worker']} 人"
        )
    with condition_tab:
        stops, blocks, errors = _condition_editor(dataset_id, factory, tasks)
    with preset_tab:
        _stop_preset_page(dataset_id, factory, tasks, stops, blocks, errors)
    with run_tab:
        trial_count = st.number_input("実行回数", min_value=1, value=10, step=1)
        if errors:
            st.warning("停止・ブロック設定の入力を修正してください。")
        if st.button("通常探索を実行", disabled=bool(errors), type="primary"):
            try:
                with st.spinner("スケジューリング中..."):
                    result = engine.run_trials(factory, tasks, int(trial_count), stops, blocks)
                    storage.save_conditions(dataset_id, stops, blocks)
                    run_id = storage.save_run(dataset_id, result, stops, blocks)
                st.session_state["latest_run_id"] = run_id
                st.session_state[f"run_select_{dataset_id}"] = run_id
                st.success(f"実行 #{run_id} を保存しました。結果・履歴タブで確認できます。")
            except (RuntimeError, ValueError, IndexError) as error:
                st.error(f"実行できませんでした: {error}")
                st.caption("停止・ブロック時間やホライズンを確認してください。")
    with result_tab:
        _display_results(dataset_id)


if __name__ == "__main__":
    main()
