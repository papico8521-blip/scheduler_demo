from dataclasses import dataclass
import random

@dataclass
class Orders:
    seed: int = 42
    count: int = 10
    product_count:int = 20
    product_over_lap: bool = True
    product_select:str = "連続"           # "連続" or "ランダム"
    priority:str = "連続"                 # "連続"or "ランダム"
    quantity:tuple = (100, 500, 20)
    work_diameter:tuple = (50, 100, 10)
    work_length:tuple = (30, 50, 5)

class Generetor:
    def __init__(self, orders):
        self.setting = orders

    def load(self):
        setting = self.setting

        if setting.product_select not in ("連続", "ランダム"):
            raise ValueError(
                "product_select は '連続' または 'ランダム' で指定してください。"
            )
        if setting.priority not in ("連続", "ランダム"):
            raise ValueError(
                "priority は '連続' または 'ランダム' で指定してください。"
            )

        random.seed(setting.seed)

        orders = { i + 1 : {
            "受注ID": i + 1,
            "生産数": random.randrange(*setting.quantity),
            "優先度": i + 1,
            } 
            for i in range(setting.count)
        }

        products = [p+1 for p in range(setting.product_count)]

        work_size = {p: {
            "dia": random.randrange(*setting.work_diameter),
            "len": random.randrange(*setting.work_length),
            } 
            for p in products
        }

        match setting.product_select:
            case "連続":
                count = 1
                for order in orders.values():
                    order["製品ID"] = count
                    order["ワーク直径"] = work_size[count]["dia"]
                    order["ワーク長さ"] = work_size[count]["len"]
                    count += 1
                    if count > setting.product_count:
                        count = 1 

            case "ランダム":
                for order in orders.values():
                    order["製品ID"] = random.choice(products)
                    order["ワーク直径"] = work_size[order["製品ID"]]["dia"]
                    order["ワーク長さ"] = work_size[order["製品ID"]]["len"]

        match setting.priority:
            case "ランダム":
                prioritys = [p+1 for p in range(setting.count)]
                count = 1
                while prioritys:
                    select = random.choice(prioritys)
                    orders[count]["優先度"] = select
                    prioritys.remove(select)
                    count += 1

        
        return orders

