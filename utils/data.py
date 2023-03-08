from abc import abstractmethod
import dataclasses
import string


@dataclasses.dataclass
class RentData:
    ID: str
    URL: str


@dataclasses.dataclass
class RentFilters:
    LOW_COST_ROUBLES: int = 19_000
    UP_COST_ROUBLES: int = 29_500

    MIN_AREA_SQUARE_METERS: int = 32

    ROOM_1: bool = True
    ROOM_2: bool = True
    ROOM_3: bool = False

    CURRENT_DAY_PUBLISHING: bool = True

    def __post_init__(self):
        assert self.LOW_COST_ROUBLES < self.UP_COST_ROUBLES
        assert self.MIN_AREA_SQUARE_METERS > 5

    @abstractmethod
    def get_filter_string(self) -> str:
        ...


class FlatRentFilters(RentFilters):
    @staticmethod
    def _convert_to_robles_to_thousands(*, roubles: int) -> float:
        roubles_in_thousands = round(roubles / 1000, 1)
        return roubles_in_thousands

    def get_filter_string(self) -> str:
        cost_template = string.Template("price=$COST")
        room_count_template = string.Template("room_count=$ROOM")
        total_area_template = string.Template("total_area=$TOTAL_AREA")
        current_day_publishing_template = string.Template("date_publisher=$DAY")
        filter_string = '&'.join(
            filter(
                lambda x: x != '',
                (
                    cost_template.substitute(COST=self._convert_to_robles_to_thousands(roubles=self.LOW_COST_ROUBLES)),
                    cost_template.substitute(COST=self._convert_to_robles_to_thousands(roubles=self.UP_COST_ROUBLES)),
                    room_count_template.substitute(ROOM='1') if self.ROOM_1 else '',
                    room_count_template.substitute(ROOM='2') if self.ROOM_2 else '',
                    room_count_template.substitute(ROOM='3') if self.ROOM_3 else '',
                    total_area_template.substitute(TOTAL_AREA=self.MIN_AREA_SQUARE_METERS),
                    total_area_template.substitute(TOTAL_AREA=80),
                    current_day_publishing_template.substitute(DAY="day") if self.CURRENT_DAY_PUBLISHING else '',
                )
            )
        )

        return filter_string


class LasVegasRentFilters(RentFilters):
    def get_filter_string(self) -> str:
        ...
