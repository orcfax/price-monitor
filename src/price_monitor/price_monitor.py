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


VALIDATOR_URI: Final[str] = os.environ.get("ORCFAX_VALIDATOR")
FEED_ID: Final[str] = "ADA-USD"
POLLING_TIME: Final[str] = 60


def price_request_msg() -> str:
    """Return a price request message to send to the websocket."""
    return json.dumps({"feed_ids": [FEED_ID]})


def get_user_agent() -> str:
    """Return a user-agent string to connect to the monitor websocket."""
    return "orcfax-price-monitor/0.0.0"


def _retry_logging(retry_state):
    """Provide some logging about tenacity retry attempts."""
    logger.info(
        "attempting connection to validator websocket '%s' (tries: %s)",
        f"{VALIDATOR_URI}",
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
async def connect_to_websocket(msg_to_send: str, local: bool):
    """Connect to the websocket and parse the response."""
    validator_connection = f"{VALIDATOR_URI}"
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
            return json.loads(msg)
    except websockets.exceptions.InvalidURI as err:
        logger.error(
            "ensure 'ORCFAX_VALIDATOR' environment variable is set: %s (`export ORCFAX_VALIDATOR=wss://`)",
            err,
        )
        sys.exit(1)
    except websockets.exceptions.ConnectionClosedError as err:
        logger.warning("closed connection error, attempting exponential retry: %s", err)
        raise err
    except json.decoder.JSONDecodeError as err:
        logger.error("error decoding server response: %s", err)
    return {}


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
    msg_to_send = price_request_msg()
    try:
        while True:
            logger.info("request for prices: %s", msg_to_send)
            data = await connect_to_websocket(msg_to_send, local)
            values = []
            if data.get("error"):
                logger.error("error in websocket response: %s", data.get("error"))
                time.sleep(POLLING_TIME)
                continue
            data = data.get("data", [])
            for item in data:
                values = item.get(FEED_ID, [])
            logger.info("received: %s", values)
            deviation = determine_deviation(values)
            logger.info("deviation (%%) calculated as: %s", deviation)
            if deviation >= 1.0:
                logger.info("deviation greater than 1%% requesting new price on-chain")
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
