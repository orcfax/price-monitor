"""Request price updates from an Orcfax websocket to trigger a request
for a new value to be put on-chain if a threshold is passed.

The code connects to the websocket and calculates the price delta
between the last published value and the last unpublished value. If
the deviation threshold is met it pushes on-chain.

Once a calculation is complete the websocket disconnects and the script
waits a configured time-period before connecting and requesting the
data again.

The script can eventually be extended to enable other price-feed
lookups.
"""

import argparse
import asyncio
import json
import logging
import logging.handlers
import os
import ssl
import sys
import time
from typing import Final

import certifi

# pylint: disable=E0401
import websockets
from tenacity import retry, wait_exponential

try:
    import feeds_to_monitor
except ModuleNotFoundError:
    try:
        from src.price_monitor import feeds_to_monitor
    except ModuleNotFoundError:
        from price_monitor import feeds_to_monitor


logging.basicConfig(
    format="%(asctime)-15s %(levelname)s :: %(filename)s:%(lineno)s:%(funcName)s() :: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level="INFO",
    handlers=[
        logging.handlers.WatchedFileHandler("monitor.log"),
        logging.StreamHandler(),
    ],
)

logger = logging.getLogger(__name__)


# NB. this all needs re-writing. We need a better way of providing these
# arguments for multi-feed monitoring.
ADA_USD_VALIDATION = "ADAUSD-ee4eed14-ffc2-11ed-9f67-67fb68ae3988"
VALIDATOR_URI: Final[str] = os.environ.get("ORCFAX_VALIDATOR")
MONITOR_URI: Final[str] = f"{VALIDATOR_URI}price_monitor/"
VALIDATION_REQUEST_URI: Final[str] = f"{VALIDATOR_URI}validate_on_demand/"

# Seconds after which to request current price off-chain.
POLLING_TIME: Final[str] = 60


def price_request_msg() -> str:
    """Return a price request message to send to the websocket."""
    feeds = [feed.name for feed in feeds_to_monitor.feeds_to_monitor]
    return json.dumps({"feed_ids": feeds})


def get_user_agent() -> str:
    """Return a user-agent string to connect to the monitor websocket."""
    return "orcfax-price-monitor/0.0.0"


def _retry_logging(retry_state):
    """Provide some logging about tenacity retry attempts."""
    logger.info(
        "attempting connection to validator websocket '%s' (tries: %s)",
        f"{MONITOR_URI}",
        retry_state.attempt_number,
    )


def determine_deviation(values: list[float]) -> float:
    """Determine if there is a percentage deviation between two numbers
    for a given threshold, default=0.1  (1%).
    """
    if not values:
        # There are no values to compare.
        return 0.0
    percentage = 100 - min(values[0], values[1]) / max(values[0], values[1]) * 100
    return percentage


@retry(wait=wait_exponential(multiplier=1, min=4, max=30), after=_retry_logging)
async def connect_to_websocket(ws_uri: str, msg_to_send: str, local: bool):
    """Connect to the websocket and parse the response."""
    validator_connection = ws_uri
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    if local:
        ssl_context = None
    try:
        # pylint: disable=E1101
        async with websockets.connect(
            validator_connection,
            user_agent_header=get_user_agent(),
            ssl=ssl_context,
        ) as websocket:
            logger.info("connected to websocket")
            await websocket.send(msg_to_send)
            logger.info(msg_to_send)
            msg = await websocket.recv()
            try:
                return json.loads(msg)
            except json.JSONDecodeError:
                pass
            return msg
    except websockets.exceptions.InvalidURI as err:
        logger.error(
            "ensure 'ORCFAX_VALIDATOR' environment variable is set: %s (`export ORCFAX_VALIDATOR=wss://`)",
            err,
        )
        sys.exit(1)
    except TypeError as err:
        logger.error("ensure data is sent as JSON: %s", err)
    except (
        websockets.exceptions.ConnectionClosedError,
        websockets.exceptions.InvalidStatusCode,
    ) as err:
        logger.warning(
            "closed connection error '%s', attempting exponential retry: %s",
            ws_uri,
            err,
        )
        if ws_uri == MONITOR_URI:
            # Only raise an exception if the problem exists with the
            # monitor function.
            raise err
    except json.decoder.JSONDecodeError as err:
        logger.error("json error decoding server response '%s': %s", msg, err)
    except websockets.exceptions.ConnectionClosedOK as err:
        logger.error("connection to: '%s' made: %s", ws_uri, err)
    return {}


async def request_new_prices(pairs_to_request: dict, local: bool):
    """Send a validation request to the server to ask for a new price
    to be placed on-chain.
    """
    validate_uri = f"{VALIDATION_REQUEST_URI}"
    await connect_to_websocket(validate_uri, pairs_to_request, local)
    return


async def price_monitor(local: bool = False):
    """Passively wait for the datum to broadcast and then publish via
    COOP.

    Example response:

    ```json
        {
            "error": null,
            "data": [{
                "ADA-USD": [0.256395, 0.256463]
            }]
        }
    ```
    """
    monitor_uri = MONITOR_URI
    feeds = price_request_msg()
    try:
        while True:
            data = await connect_to_websocket(monitor_uri, feeds, local)
            values = []
            if data.get("error"):
                logger.error("error in websocket response: %s", data.get("error"))
                time.sleep(POLLING_TIME)
                continue
            price_pairs = data.get("data", [])
            pairs_to_request = []
            for price_pair in price_pairs:
                pair = list(price_pair.keys())[0]
                values = list(price_pair.values())[0]
                deviation = determine_deviation(values)
                if not deviation:
                    continue
                logger.info(
                    "'%s' deviation calculated as: '%s' from %s",
                    pair,
                    deviation,
                    values,
                )
                feed_deviation = feeds_to_monitor.get_deviation(pair)
                if deviation >= feed_deviation:
                    pairs_to_request.append(pair)
                    logger.info(
                        "deviation: %s '%s' greater than %s%% requesting new price on-chain",
                        values,
                        deviation,
                        feed_deviation,
                    )
            if not pairs_to_request:
                logger.info(
                    "not requesting any updated pairs... polling in '%s' seconds",
                    POLLING_TIME,
                )
                time.sleep(POLLING_TIME)
                continue
            req = json.dumps({"feeds": pairs_to_request})
            await request_new_prices(req, local)
            time.sleep(POLLING_TIME)
    except KeyboardInterrupt:
        print("", file=sys.stderr)
        logger.info("exiting...")


def main():
    """Primary entry point of this script."""

    parser = argparse.ArgumentParser(
        prog="price monitor",
        description="monitors prices and requests a value be put on-chain if a threshold is passed",
        epilog="for more information visit https://orcfax.io",
    )

    parser.add_argument(
        "--local",
        help="run code locally without ssl",
        required=False,
        action="store_true",
    )

    args = parser.parse_args()
    asyncio.run(price_monitor(args.local))


if __name__ == "__main__":
    main()
