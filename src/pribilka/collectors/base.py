from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import timedelta

from pribilka.models.enums import AssetClass, CountryCode


@dataclass
class CollectorConfig:
    asset_class: AssetClass
    country: CountryCode
    source_name: str
    refresh_interval: timedelta


class BaseCollector(ABC):
    def __init__(self, config: CollectorConfig):
        self.config = config

    @abstractmethod
    def collect(self) -> list[dict]:
        """Fetch raw records from external source. Each dict is one instrument."""

    @property
    def asset_class(self) -> AssetClass:
        return self.config.asset_class

    @property
    def country(self) -> CountryCode:
        return self.config.country
