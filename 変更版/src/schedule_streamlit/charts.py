"""Streamlit向けの結果グラフ。"""

import plotly.graph_objects as go


def gantt(assignments, stops, blocks, resource_type):
    """分単位の横棒で、機械または作業者の占有区間を表示する。"""
    is_machine = resource_type == "machine"
    figure = go.Figure()
    for row in assignments:
        resource_id = row["machine_id"] if is_machine else row["worker_id"]
        label = f"{'機械' if is_machine else '作業者'} {resource_id}"
        parts = [
            ("段取", row["start_time"], row["setup_end_time"], "#f59e0b"),
        ]
        if is_machine:
            parts.append(("加工（ブロック中断を含む）", row["setup_end_time"],
                          row["end_time"], "#3b82f6"))
        for part_name, start, end, color in parts:
            if end <= start:
                continue
            figure.add_trace(go.Bar(
                x=[end - start], base=[start], y=[label], orientation="h",
                name=part_name, marker_color=color, showlegend=False,
                customdata=[[row["order_id"], row["process_id"], start, end]],
                hovertemplate=(
                    "受注 %{customdata[0]} / 工程 %{customdata[1]}<br>"
                    + part_name + ": %{customdata[2]}～%{customdata[3]} 分<extra></extra>"
                ),
            ))
    for stop in stops:
        if stop["resource_type"] != resource_type:
            continue
        start, end = stop["start_time"], stop["end_time"]
        figure.add_trace(go.Bar(
            x=[end - start], base=[start],
            y=[f"{'機械' if is_machine else '作業者'} {stop['resource_id']}"],
            orientation="h", name="停止", marker_color="#ef4444", opacity=0.65,
            showlegend=False, hovertemplate=f"停止: {start}～{end} 分<extra></extra>",
        ))
    for block in blocks:
        if block["block_type"] == "setup":
            color = "#ec4899"
            opacity = 0.20
        elif block["block_type"] == "process" and is_machine:
            color = "#ef4444"
            opacity = 0.12
        else:
            continue
        figure.add_vrect(
            x0=block["start_time"], x1=block["end_time"],
            fillcolor=color, opacity=opacity, line_width=0, layer="below",
        )
    figure.update_layout(
        title="機械別" if is_machine else "作業者別",
        xaxis_title="開始からの経過時間（分）",
        yaxis_title="", barmode="overlay", height=450,
        margin=dict(l=10, r=10, t=45, b=35),
    )
    return figure


def trial_chart(trials):
    figure = go.Figure(go.Scatter(
        x=[row["trial_number"] for row in trials],
        y=[row["makespan"] for row in trials],
        mode="lines+markers",
    ))
    figure.update_layout(
        xaxis_title="試行番号", yaxis_title="Makespan（分）",
        height=300, margin=dict(l=10, r=10, t=10, b=35),
    )
    return figure
