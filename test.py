from abc import abstractmethod, ABC
from typing import Tuple, Optional
import dataclasses
import string
import re

import requests
import selenium.webdriver.ie.webdriver
from bs4 import BeautifulSoup, SoupStrainer
from selenium import webdriver


@dataclasses.dataclass
class RentData:
    ID: str
    URL: str


@dataclasses.dataclass
class _RentFilters:
    # Подразумевается, что эти значения измеряются в тысячах
    LOW_COST: int = 19_000
    UP_COST: int = 29_500

    ROOM_1: bool = True
    ROOM_2: bool = True
    ROOM_3: bool = False

    @abstractmethod
    def get_filter_string(self) -> str:
        ...


class _FlatRentFilters(_RentFilters):
    def get_filter_string(self) -> str:
        cost_template = string.Template("price=$COST")
        room_count_template = string.Template("room_count=$ROOM")
        filters_active_template = string.Template("filters-active=$FILTERS_ACTIVE")
        filter_string = '&'.join(
            filter(
                lambda x: x != '',
                (
                    cost_template.substitute(COST=19),
                    cost_template.substitute(COST=self.UP_COST / 1000),
                    room_count_template.substitute(ROOM='1') if self.ROOM_1 else '',
                    room_count_template.substitute(ROOM='2') if self.ROOM_2 else '',
                    room_count_template.substitute(ROOM='3') if self.ROOM_3 else '',
                    filters_active_template.substitute(
                        FILTERS_ACTIVE=1 + any((self.ROOM_1, self.ROOM_2, self.ROOM_3)))
                )
            )
        )

        return filter_string+"#content-view"


class _LasVegasRentFilters(_RentFilters):
    def get_filter_string(self) -> str:
        ...


class IOfferDataParser(ABC):
    @abstractmethod
    def __call__(self) -> Tuple[RentData, ...]:
        ...


class _OfferDataParser(IOfferDataParser):
    def __init__(self, *,
                 filters: _RentFilters,
                 rent_name: str,
                 rent_subject: str,
                 id_prefix: str,
                 url: str):
        self.__url_template = string.Template("$URL/$RENT_NAME/$RENT_SUBJECT/?$FILTERS")
        self.__filters = filters

        self.__rent_name = rent_name
        self.__rent_subject = rent_subject
        self.__id_prefix = id_prefix
        self.__url = url

    @property
    def url_template(self) -> string.Template:
        return self.__url_template

    @property
    def url(self) -> str:
        return self.__url

    @property
    def rent_name(self) -> str:
        return self.__rent_name

    @property
    def rent_subject(self) -> str:
        return self.__rent_subject

    @property
    def id_prefix(self) -> str:
        return self.__id_prefix

    @property
    def filters(self) -> _RentFilters:
        return self.__filters

    @abstractmethod
    def _extract_rent_data(self, *, driver: webdriver.ie.webdriver.WebDriver) -> Tuple[RentData, ...]:
        ...

    def __call__(self) -> Tuple[RentData, ...]:
        url_with_filters = self.url_template.substitute(
            URL=self.url,
            RENT_NAME=self.rent_name,
            RENT_SUBJECT=self.rent_subject,
            FILTERS=self.filters.get_filter_string()
        )
        driver = webdriver.Op()
        driver.get(url_with_filters)
        return self._extract_rent_data(driver=driver)


class FlatApartmentRentParser(_OfferDataParser):
    def __init__(self):
        super().__init__(
            filters=_FlatRentFilters(),
            rent_name="rent",
            rent_subject="apartments",
            id_prefix="FL",
            url="https://anflat.ru")

    def _extract_rent_data(self, *, driver: webdriver.ie.webdriver.WebDriver) -> Tuple[RentData, ...]:
        results = driver.find_elements_by_xpath('//div[@class="catalog-card"]')


class LasVegasApartmentRentParser(_OfferDataParser):
    def __init__(self):
        super().__init__(
            filters=_LasVegasRentFilters(),
            id_prefix="LV",
            rent_name="arenda",
            rent_subject="kvartira",
            url="https://anlasvegas.ru")

    def _extract_rent_data(self, *, driver: webdriver.Chrome) -> Tuple[RentData, ...]:
        ...


if __name__ == "__main__":
    fp = FlatApartmentRentParser()
    res = fp()
