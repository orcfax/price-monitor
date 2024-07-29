"""Collection of feeds and price deviations to monitor for."""

from dataclasses import dataclass


@dataclass
class Feed:
    name: str
    deviation: float = 2.0  # 2% default.


feeds_to_monitor = [
    # Feed names are always upper-case.
    Feed("ADA-USD", 1.0),
    Feed(
        "ADA-IUSD",
    ),
    Feed(
        "ADA-USDM",
    ),
    Feed(
        "ADA-DJED",
    ),
    Feed(
        "SHEN-ADA",
    ),
    Feed(
        "MIN-ADA",
    ),
    Feed(
        "FACT-ADA",
    ),
    Feed(
        "LQ-ADA",
    ),
    Feed(
        "SNEK-ADA",
    ),
    Feed(
        "LENFI-ADA",
    ),
    Feed(
        "HUNT-ADA",
    ),
    Feed(
        "IBTC-ADA",
    ),
    Feed(
        "IETH-ADA",
    ),
]


def get_deviation(feed_id: str):
    """Retrieve deviation for a given price pair."""
    for feed in feeds_to_monitor:
        if feed.name != feed_id:
            continue
        return feed.deviation
