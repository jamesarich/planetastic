# Planetastic: An ADSB to Meshtastic Connector
**v2.1.0**

This project provides a Python script, `planetastic.py`, that connects a local ADSB receiver (like `dump1090`) to a Meshtastic network. It listens for aircraft data and broadcasts selected information to your personal mesh or local network.

## How It Works

The script connects to a running `dump1090` instance, which is responsible for receiving and demodulating ADSB signals from an SDR. It reads the parsed aircraft data stream (in SBS-1 format), which is often fragmented across multiple messages for a single aircraft.

To handle this, the script maintains a persistent **SQLite database** (`planetastic.db`) of all aircraft it has seen. As new messages arrive, the script updates the corresponding aircraft's record with the latest information. It will only broadcast an update for an aircraft once its record contains both a callsign and a position.

The script can output the aggregated data in two independent ways:

1.  **To a Meshtastic Device:** Formats a concise text message and sends it to a connected Meshtastic device (either local via USB/Serial or remote via TCP).
2.  **To the Local Network via MUDP:** Broadcasts each aircraft's information as a `TextMessage` from a single, static gateway node. This allows other applications on the network to see the stream of aircraft data.

Additionally, a local **Web Dashboard** is available to visualize all tracked aircraft in real-time.

These outputs can be used independently or together.

To avoid spamming the network, the script keeps track of each aircraft and only sends an update for a specific aircraft periodically. By default, this interval is 5 minutes (300 seconds), but it can be changed with the `--update-interval` argument.

## Prerequisites

1.  **A functional ADSB receiver.** You need an SDR (like an RTL-SDR dongle) and software to decode the signals. This script is designed to work with `dump1090`. We recommend using a modern fork like [dump1090-fa](https://github.com/flightaware/dump1090) or [readsb](https://github.com/wiedehopf/readsb). Your `dump1090` instance must be configured to provide an SBS-1 BaseStation output stream (usually on port `30003`).

2.  **A Meshtastic device (Optional).** If you want to send messages to the Meshtastic network, you need a compatible LoRa radio connected locally via USB or accessible over your network.

3.  **Python 3.11 or later.**

## Installation

1.  **Clone this repository.**
3.  **Install the package and dependencies:**
    ```bash
    pip install .
    ```
    *Alternatively, you can just install the requirements:* `pip install -r requirements.txt`

## Usage

Run the script from your terminal. All settings can be controlled by command-line arguments or a configuration file.

### Configuration File

A `config.yaml.example` file is included in the repository. You can copy this file to `config.yaml` and edit it to set your preferred defaults.

```bash
cp config.yaml.example config.yaml
```

Then, run the script with the `--config` argument to specify the file's path:
```bash
python planetastic.py --config /path/to/your/config.yaml
```

Any command-line argument will override the values in the configuration file. For example, to use the config file but broadcast to a different MUDP port, you could run:
```bash
python planetastic.py --config /path/to/your/config.yaml --mudp-port 9000
```

### Command-Line Arguments

You can see all available arguments by running:
```bash
python planetastic.py --help
```

-   `--config`: Path to a YAML configuration file.
-   `--dump1090-host`: The hostname or IP of the `dump1090` instance.
-   `--dump1090-port`: The port for the `dump1090` SBS-1 stream.
-   `--meshtastic-host`: The hostname or IP of a network-connected Meshtastic device.
-   `--meshtastic-port`: The TCP port for the network-connected Meshtastic device.
-   `--no-meshtastic`: Disables all attempts to connect to a physical Meshtastic device.
-   `--mudp`: Enable MUDP broadcasting to the local network.
-   `--mudp-host`: The MUDP multicast group address.
-   `--mudp-port`: The MUDP multicast port.
-   `--mudp-node-id`, `--mudp-node-longname`, `--mudp-node-shortname`: Set the static identity for MUDP broadcasts.
-   `--update-interval`: Seconds before sending a new update for the same aircraft.
-   `--home-lat`, `--home-lon`: Your station's position (required for geofencing).
-   `--radius`: Maximum broadcast distance in km.
-   `--min-alt`, `--max-alt`: Altitude range filter in feet.
-   `--web-port`: The port for the local web dashboard (default: 8080).
-   `--debug`: Enable debug logging to print raw data from dump1090.

### Examples

**Default behavior (send to local Meshtastic device):**
```bash
python planetastic.py
```

**Broadcast to MUDP only, with updates every 60 seconds:**
```bash
python planetastic.py --no-meshtastic --mudp --update-interval 60
```

**Send to a remote Meshtastic device only:**
```bash
python planetastic.py --meshtastic-host 192.168.1.200
```

**Send to a local Meshtastic device AND broadcast via MUDP:**
```bash
python planetastic.py --mudp
```

**Only broadcast aircraft within 50km and below 10,000ft:**
```bash
python planetastic.py --home-lat 51.5 --home-lon -0.1 --radius 50 --max-alt 10000
```

### Hot Reloading
If you use a configuration file (`--config config.yaml`), the script will monitor it for changes. Updating filtering settings like `radius`, `min_alt`, or `max_alt` in the YAML file will be reflected in the running script within 10 seconds, without requiring a restart.

## Docker Deployment

You can run Planetastic as a Docker container for easy deployment on servers or Raspberry Pis.

### Using Docker Compose
1. Ensure you have `config.yaml` set up in the project directory.
2. Run:
   ```bash
   docker-compose up -d
   ```
This will mount your config file and persist the database to your local machine.

### Environment Variables
For containerized deployments, you can also use environment variables to override defaults:

| Variable | Description | Default |
| :--- | :--- | :--- |
| `DUMP1090_HOST` | Hostname of the dump1090 instance. | `localhost` |
| `DUMP1090_PORT` | Port for the SBS-1 stream. | `30003` |
| `MESHTASTIC_HOST` | IP/Hostname of a remote Meshtastic device. | - |
| `MESHTASTIC_PORT` | Port for the remote Meshtastic device. | `4403` |

## Troubleshooting

### "Connection refused" or No Data
If you see a "Connection refused" error, or if the script connects but no packets are processed, it usually indicates an issue with the `dump1090` data stream.

-   Ensure your `dump1090` (or equivalent) instance is running.
-   Check that you are using the correct hostname and port.
-   Verify that `dump1090` is configured to provide an SBS-1 (BaseStation) data stream on the specified port.
-   Run this script with the `--debug` flag to see the raw data being received from `dump1090`. If you see raw data but no output, it's likely because the messages being received do not contain both a callsign and a position, which are required for the script to broadcast an update. The debug log will show messages being skipped for this reason.

### No Meshtastic Device Found
If the script reports "No local Meshtastic device found", it means it could not detect a device connected via USB.
-   Ensure your device is properly connected.
-   If your device is network-connected, you must specify its IP address using the `--meshtastic-host` argument.

## Acknowledgements

This project is built upon the great work of the following open-source projects:

-   [Meshtastic Python](https://github.com/meshtastic/python-meshtastic) for communication with Meshtastic devices.
-   [MUDP](https://github.com/pdxlocations/mudp) for providing a simple way to broadcast Meshtastic-compatible UDP packets.
