import re
import string
from abc import abstractmethod, ABC
from typing import List, Union, Optional

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException
)
from selenium.webdriver.common.by import By
from selenium.webdriver.ie.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import WebDriverWait

from utils.data import (
    RentData,
    RentFilters,
    FlatRentFilters,
    LasVegasRentFilters
)


class IOfferDataParser(ABC):
    @abstractmethod
    def __call__(self) -> List[RentData]:
        ...


class _OfferDataParser(IOfferDataParser):
    def __init__(self, *,
                 rent_name: str,
                 rent_object: str,
                 id_prefix: str,
                 url: str,
                 filters: Optional[Union[RentFilters, None]]):
        self.__url_template = string.Template("$URL/$RENT_NAME/$RENT_SUBJECT/?$FILTERS")
        self.__filters = filters

        self.__rent_name = rent_name
        self.__rent_object = rent_object
        self.__id_prefix = id_prefix
        self.__url = url

    @property
    def url(self) -> str:
        return self.__url

    @property
    def url_with_filters(self) -> str:
        return self.__url_template.substitute(
            URL=self.__url,
            RENT_NAME=self.__rent_name,
            RENT_SUBJECT=self.__rent_object,
            FILTERS="" if self.__filters is None else self.__filters.get_filter_string()
        )

    @property
    def rent_name(self) -> str:
        return self.__rent_name

    @property
    def rent_object(self) -> str:
        return self.__rent_object

    @property
    def id_prefix(self) -> str:
        return self.__id_prefix

    @abstractmethod
    def _extract_request_data(self, *, driver: WebDriver) -> List[RentData]:
        ...

    def __call__(self) -> List[RentData]:
        chrome_options = webdriver.chrome.options.Options()
        chrome_options.add_argument('--blink-settings=imagesEnabled=false')
        chrome_options.add_argument("--disable-application-cache")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-infobars")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--headless")
        chrome_options.page_load_strategy = "eager"

        driver = webdriver.Chrome(options=chrome_options)
        driver.get(self.url_with_filters)
        result = self._extract_request_data(driver=driver)
        driver.quit()

        return result


class FlatOfferParser(_OfferDataParser):
    def __init__(self):
        super().__init__(
            filters=FlatRentFilters(),
            rent_name="rent",
            rent_object="apartments",
            id_prefix="FL",
            url="https://anflat.ru")

    @staticmethod
    def _push_button_until_possible(*, driver: WebDriver, timeout: float) -> None:
        html_button_class_name = "catalog-load-more-btn"
        wait = WebDriverWait(driver, timeout)

        try:
            button = wait.until(ec.element_to_be_clickable((By.CLASS_NAME, html_button_class_name)))
            while True:
                try:
                    button.click()
                except StaleElementReferenceException:
                    break
        except TimeoutException:
            ...

    def _get_object_url(self, *, ID: str) -> str:
        object_link_template = string.Template("$URL/$RENT_NAME/$RENT_OBJECT/object-$ID")
        return object_link_template.substitute(
            URL=self.url,
            RENT_NAME=self.rent_name,
            RENT_OBJECT=self.rent_object,
            ID=ID
        )

    def _extract_request_data(self, *, driver: WebDriver) -> List[RentData]:
        button_search_timeout_seconds = 10
        rent_data_list = []

        try:
            driver.find_element(By.CLASS_NAME, "catalog-none-data")
        except NoSuchElementException:
            self._push_button_until_possible(driver=driver, timeout=button_search_timeout_seconds)
            html = driver.page_source
            soup = BeautifulSoup(html, features="lxml")

            for el in soup.find_all("div", {"class": "catalog-card"}):
                for string_id in re.findall(r"ID: \S+", el.get_text(separator=" ")):
                    extracted_id = string_id.split(" ")[-1]
                    extracted_link = self._get_object_url(ID=extracted_id)
                    rent_data = RentData(ID=extracted_id, URL=extracted_link)
                    rent_data_list.append(rent_data)

        return rent_data_list


class LasVegasOfferParser(_OfferDataParser):
    def __init__(self):
        super().__init__(
            filters=LasVegasRentFilters(),
            id_prefix="LV",
            rent_name="arenda",
            rent_object="kvartira",
            url="https://anlasvegas.ru")

    def _extract_request_data(self, *, driver: webdriver.Chrome) -> List[RentData]:
        ...
