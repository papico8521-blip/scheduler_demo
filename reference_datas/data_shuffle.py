import random


def _move_cutting_processes_to_front(datas):
    """工程NO1をランダム化してリストの先頭へ移動する。"""
    cutting_processes = [data for data in datas if data[3] == 1]
    other_processes = [data for data in datas if data[3] != 1]
    random.shuffle(cutting_processes)
    return cutting_processes + other_processes


def shuffle(datas, seed, prio_mix=True, n=0.5, cutting_shuffle=True):
    """工程順序を維持しながらソルバー投入順をシャッフルする。"""

    random.seed(seed)

    if not 0 <= n <= 1:
        raise ValueError("n は 0.0 以上 1.0 以下で指定してください。")

    result = []
    priority_results = []

    # 優先度ごとに分ける。
    priority_datas = {}
    for data in datas:
        priority = data[0]
        if priority not in priority_datas:
            priority_datas[priority] = []
        priority_datas[priority].append(data)

    # 優先度の高い順ではなく、元の並びで使われている優先度順に処理する。
    # solve_list は通常、優先度の昇順で作られているため、sorted() を使う。
    priority_list = sorted(priority_datas)
    for priority in priority_list:
        current_datas = priority_datas[priority]
        current_result = []

        # ノードをタプルそのものではなく、current_datas の添字で管理する。
        # これにより、同じ値のタプルが複数存在しても区別できる。
        next_nodes = {}
        indegree = {}

        for node in range(len(current_datas)):
            next_nodes[node] = []
            indegree[node] = 0

        # 同一受注ID内で、datas に登場した順番の工程を依存関係にする。
        # 例: A-1, A-2, A-3 -> A-1 -> A-2 -> A-3
        order_nodes = {}
        for node, data in enumerate(current_datas):
            order_id = data[1]
            if order_id not in order_nodes:
                order_nodes[order_id] = []
            order_nodes[order_id].append(node)

        for nodes in order_nodes.values():
            for before, after in zip(nodes, nodes[1:]):
                next_nodes[before].append(after)
                indegree[after] += 1

        # 入次数0のノードから、ランダムに1件ずつ選ぶ。
        candidates = []
        for node in range(len(current_datas)):
            if indegree[node] == 0:
                candidates.append(node)

        shuffled_count = 0
        while candidates:
            candidate_index = random.randrange(len(candidates))
            node = candidates.pop(candidate_index)
            current_result.append(current_datas[node])
            shuffled_count += 1

            for next_node in next_nodes[node]:
                indegree[next_node] -= 1
                if indegree[next_node] == 0:
                    candidates.append(next_node)

        # 工程順の依存関係に循環があれば、トポロジカルソートできない。
        if shuffled_count != len(current_datas):
            raise ValueError(
                f"優先度 {priority} の工程順に循環依存があります。"
            )
        
        priority_results.append(current_result)

    if not prio_mix:
        for priority_result in priority_results:
            result.extend(priority_result)
        if cutting_shuffle:
            result = _move_cutting_processes_to_front(result)
        return result

    priority_index = 0
    while priority_index < len(priority_results):
        # 隣接する2グループを n の確率で混合する。
        if (
            priority_index + 1 < len(priority_results)
            and random.random() < n
        ):
            # print(
            #     f"prio-mix実行 {priority_list[priority_index]} - "
            #     f"{priority_list[priority_index + 1]}"
            # )

            left = priority_results[priority_index].copy()
            right = priority_results[priority_index + 1].copy()

            # 各グループの順序を維持したまま、先頭候補だけをランダムに選ぶ。
            while left or right:
                if not left:
                    result.append(right.pop(0))
                elif not right:
                    result.append(left.pop(0))
                elif random.randrange(2) == 0:
                    result.append(left.pop(0))
                else:
                    result.append(right.pop(0))

            # 混合した2グループは消費する。
            priority_index += 2
        else:
            # スルーした場合は1グループだけ消費するため、
            # 次の判定で後ろのグループを再利用できる。
            result.extend(priority_results[priority_index])
            priority_index += 1

    if cutting_shuffle:
        result = _move_cutting_processes_to_front(result)

    return result


if __name__ == "__main__":
    pass
