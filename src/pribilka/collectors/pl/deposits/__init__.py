from pribilka.collectors.pl.deposits.bankier import BankierDepositParser
from pribilka.collectors.pl.deposits.ing import IngDepositParser
from pribilka.collectors.pl.deposits.mbank import MBankDepositParser
from pribilka.collectors.pl.deposits.pko import PkoDepositParser
from pribilka.collectors.pl.deposits.santander import SantanderDepositParser
from pribilka.collectors.pl.deposits.velobank import VeloBankDepositParser

# Direct bank scrapers first; aggregator last (dedupe prefers bank-native IDs).
PL_DEPOSIT_PARSERS = [
    PkoDepositParser,
    IngDepositParser,
    MBankDepositParser,
    SantanderDepositParser,
    VeloBankDepositParser,
    BankierDepositParser,
]
