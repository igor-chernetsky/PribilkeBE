from pribilka.collectors.bond_collector import PolandBondCollector
from pribilka.collectors.deposit_collector import PolandDepositCollector
from pribilka.collectors.fx_collector import NbpFxCollector
from pribilka.collectors.gold_collector import PolandGoldCollector
from pribilka.collectors.macro_collector import PolandMacroCollector

ALL_COLLECTORS = [
    PolandDepositCollector,
    PolandBondCollector,
    NbpFxCollector,
    PolandGoldCollector,
    PolandMacroCollector,
]
