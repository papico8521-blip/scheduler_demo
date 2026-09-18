from dataclasses import dataclass
import random

@dataclass
class Factory:
    seed: int = 42
    count: int = 1
    cutting_machine: int = 1
    cnc_machine: int = 3
    cnc_worker:int = 3
