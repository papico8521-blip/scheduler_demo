import csv

class DataChanger:
    def __init__(self):
        self.col= [
            "seed",
        ]

    def save_to_csv(self,
                    seed,
                    result,
                    stop_machine_or_worker,
                    stop_setup,
                    stop_process):
        schedule = []
        col = []
        for key,values in result.items():
            col = list(values.keys())
            buff = []
            for v in values.values():
                #schedule.append(v)
                buff.append(v)
            schedule.append(buff)

        if seed == 0:
            stops = []
            stops_col = ["id","start","end","stop"]
            if stop_machine_or_worker:
                stops = stops + [list(s) for s in stop_machine_or_worker]

            if stop_setup:
                stops = stops + [[0,s[0],s[1],"setup"] for s in stop_setup]
                 
            if stop_process:
                stops = stops + [[0,s[0],s[1],"process"] for s in stop_process]

            if stops:
                stops = [stops_col] + stops
                with open(f'output_csv/stops.csv', 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerows(stops)

        with open(f'output_csv/seed_{seed}.csv', 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(col)
            writer.writerows(schedule)

        # pass

if __name__ == "__main__":
    pass