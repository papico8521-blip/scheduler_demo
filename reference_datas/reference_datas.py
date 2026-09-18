from pprint import pprint


def create(datas, display=True):

    def create_dict(datas, col):
        d = {}
        match col:
            case "着手可能時間" | "マシン候補" | "ワーカー候補" | "段取時間" | "オーバーラップバッファ"\
                | "総加工時間" | "次工程オーバーラップ" | "タイプ" | "単体単位" | "単加工時間":
                for k, v in datas.items():
                    for kk, vv in v["工程情報"].items():
                        key = (k, kk)
                        d[key] = vv[col]
                return d

            case "製品ID" | "ワーク直径" | "ワーク長さ" | "生産数":
                for k, v in datas.items():
                    item = v["受注情報"][col]
                    for kk, vv in v["工程情報"].items():
                        key = (k, kk)
                        d[key] = item
                return d

            case "solve":
                solve_list = []
                for k, v in datas.items():
                    order_id = v["受注情報"]["受注ID"]
                    product_id = v["受注情報"]["製品ID"]
                    prio = v["受注情報"]["優先度"]
                    for kk, vv in v["工程情報"].items():
                        process_id = kk
                        solve_list.append((prio, order_id, product_id, process_id))

                solve_list = sorted(solve_list, key=lambda x: (x[0], x[1], x[3]))
                
                return solve_list

    print(" < タイプ_dict作成 >")
    type_dict = create_dict(datas, col="タイプ")

    print(" < 着手/完了時間記録_dict作成 > ")
    release = create_dict(datas, col="着手可能時間")
  
    print(" < マシン候補_dict作成 > ")
    machine_candidate = create_dict(datas, col="マシン候補")

    print(" < ワーカー候補_dict作成 > ")
    worker_candidate = create_dict(datas, col="ワーカー候補")

    print(" < 段取時間_dict作成 >")
    setup = create_dict(datas, col="段取時間")

    print(" < 加工時間_dict作成 >")
    proc = create_dict(datas, col="総加工時間")
    
    print(" < 製品ID_dict作成 >")
    product_id = create_dict(datas, col="製品ID")

    print(" < ワークサイズ_dict作成 >")
    work_size_dia = create_dict(datas, col="ワーク直径")
    work_size_len = create_dict(datas, col="ワーク長さ")

    print(" < 生産数_dict作成 >")
    quantity = create_dict(datas, col="生産数")

    print(" < 次工程オーバーラップ_dict作成 >")
    over_lap = create_dict(datas, col="次工程オーバーラップ")
    over_lap_buff = create_dict(datas, col="オーバーラップバッファ")

    print(" < 単体加工時間_dict作成 >")
    proc_onece = create_dict(datas, col="単加工時間")
    proc_onece_unit = create_dict(datas, col="単体単位")

    print(" < solve_key_dict作成 >")
    solve_key = create_dict(datas, col="solve")

    reference_dict = {
        "product_id": product_id,
        "tyep": type_dict,
        "work_size_dia": work_size_dia,
        "work_size_len": work_size_len,
        "quantity": quantity,
        "over_lap": over_lap,
        "over_lap_buff": over_lap_buff,
        "machine_candidate": machine_candidate,
        "worker_candidate": worker_candidate,
        "setup": setup,
        "proc_total": proc,
        "proc_once": proc_onece,
        "proc_once_unit": proc_onece_unit,
        "release": release,
        "solve_list":solve_key
    }

    if display:
        for k,v in reference_dict.items():
            print(f"\n ----- {k} -----")
            pprint(v)
            input("next キー")
        
    print(reference_dict.keys())

    return reference_dict

if __name__ == "__main__":
    pass