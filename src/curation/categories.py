from typing import Literal

Weather = Literal["clear", "cloudy", "fog", "rain", "snow", "storm"]
TimeOfDay = Literal["day", "twilight", "night"]

WEATHER = ("clear", "cloudy", "fog", "rain", "snow", "storm")
TIMES = ("day", "twilight", "night")
TARGETS = {
    "clear": {"day": 60, "twilight": 40, "night": 30},
    "cloudy": {"day": 50, "twilight": 20, "night": 20},
    "rain": {"day": 40, "twilight": 10, "night": 15},
    "snow": {"day": 30, "twilight": 10, "night": 10},
    "fog": {"day": 20, "twilight": 10, "night": 5},
    "storm": {"day": 15, "twilight": 5, "night": 5},
}
