# price monitor

Monitor prices for a given feed identifier and potentially trigger an action,
e.g. price update on-chain.

## Environment

The script needs a single environment variable set so that it can connect to
the validator node.

```env
export ORCFAX_VALIDATOR=ws://<ip>:<port>/ws/
```

The price monitor will connect to the `/price_monitor/' websocket of the
validator.

## Connecting

The price monitor will need to connec to `ssl` in production. If the monitor
is being used locally, a `--local` flag can be used.

Other command line arguments can be viewed using `--help`.

## Running

The script can be run from the repository, e.g.:

```sh
python price_monitor.py --help
```

or once installed via the package with:

```sh
price-monitor --help
```

## Polling

Polling is hard-coded at 60 seconds. At time of writing the validator is only
receiving updated prices from sources every 60 seconds.

## Persitence

The price-monitor script uses Python tenacity for persisttence. This could be
replaced with a service if desired. Tenacity provides us with a very robust
reconnection approach in any regard.

## Output

Logging will be visible to the user as follows:

<!-- markdownlint-disable -->

```log
2024-07-30 17:13:23 INFO :: price_monitor.py:113:connect_to_websocket() :: {"feed_ids": ["ADA-USD", "ADA-IUSD", "ADA-USDM", "ADA-DJED", "SHEN-ADA", "MIN-ADA", "FACT-ADA", "LQ-ADA", "SNEK-ADA", "LENFI-ADA", "HUNT-ADA", "IBTC-ADA", "IETH-ADA"]}
2024-07-30 17:13:23 INFO :: price_monitor.py:190:price_monitor() :: 'ADA-USD' deviation calculated as: '0.0673535061241779' from [0.4006, 0.40087]
2024-07-30 17:13:23 INFO :: price_monitor.py:190:price_monitor() :: 'ADA-USDM' deviation calculated as: '0.22193163625698276' from [0.408227, 0.409135]
2024-07-30 17:13:23 INFO :: price_monitor.py:190:price_monitor() :: 'ADA-DJED' deviation calculated as: '0.4586888495850445' from [0.411608, 0.40972]
2024-07-30 17:13:23 INFO :: price_monitor.py:190:price_monitor() :: 'LQ-ADA' deviation calculated as: '0.14010614670573318' from [2.131955, 2.128968]
2024-07-30 17:13:23 INFO :: price_monitor.py:190:price_monitor() :: 'HUNT-ADA' deviation calculated as: '0.002714113389629347' from [0.331591, 0.3316]
2024-07-30 17:13:23 INFO :: price_monitor.py:206:price_monitor() :: not requesting any updated pairs... polling in '60' seconds
```

<!-- markdownlint-enable -->

All configured feeds will be requested from the validator and those with
upgraded prices are returned.

If the deviation is worked out to be greater than or equal to a given
threshold a new price will be requested from the validator via the
`validate_on_demand/` endpoint of the validator.
