import socket
import time
import argparse
import yaml
import os
import meshtastic
import meshtastic.serial_interface
import meshtastic.tcp_interface
try:
    from mudp import conn, node, send_text_message
except ImportError:
    conn = None
    node = None
    send_text_message = None


# --- Constants ---
CONNECT_ATTEMPT_DELAY = 5
CONNECT_ATTEMPT_LIMIT = 10

# --- SBS-1 Message Fields ---
SBS1_FIELDS = [
    'message_type', 'transmission_type', 'session_id', 'aircraft_id',
    'hex_ident', 'flight_id', 'generated_date', 'generated_time',
    'logged_date', 'logged_time', 'callsign', 'altitude',
    'ground_speed', 'track', 'lat', 'lon', 'vertical_rate',
    'squawk', 'alert', 'emergency', 'spi', 'is_on_ground'
]

def setup_args():
    """
    Sets up the command-line arguments, loading defaults from a config file if specified.
    """
    # First, parse for the config file path
    conf_parser = argparse.ArgumentParser(description="A connector between dump1090 and Meshtastic.", add_help=False)
    conf_parser.add_argument('--config', help='Path to a YAML configuration file.')
    args, remaining_argv = conf_parser.parse_known_args()

    config = {}
    if args.config:
        if os.path.exists(args.config):
            with open(args.config, 'r') as f:
                config = yaml.safe_load(f)
        else:
            print(f"Warning: Config file not found at {args.config}")

    # Now, parse all arguments, using config file values as defaults
    parser = argparse.ArgumentParser(parents=[conf_parser])
    parser.add_argument('--dump1090-host', default=config.get('dump1090_host', 'localhost'), help='The hostname or IP address of the dump1090 instance.')
    parser.add_argument('--dump1090-port', type=int, default=config.get('dump1090_port', 30003), help='The port for the dump1090 SBS-1 stream.')
    parser.add_argument('--meshtastic-host', default=config.get('meshtastic_host'), help='The hostname or IP address of the Meshtastic device.')
    parser.add_argument('--meshtastic-port', type=int, default=config.get('meshtastic_port', 4403), help='The TCP port of the Meshtastic device (default: 4403).')
    parser.add_argument('--no-meshtastic', action='store_true', default=config.get('no_meshtastic', False), help='Run without connecting to Meshtastic (for debugging).')
    parser.add_argument('--mudp', action='store_true', default=config.get('mudp', False), help='Enable MUDP broadcasting to the local network.')
    parser.add_argument('--mudp-host', default=config.get('mudp_host', '224.0.0.69'), help='The MUDP multicast group address (default: 224.0.0.69).')
    parser.add_argument('--mudp-port', type=int, default=config.get('mudp_port', 4403), help='The MUDP multicast port (default: 4403).')
    # General arguments
    parser.add_argument('--update-interval', type=int, default=config.get('update_interval', 300), help='Seconds before sending a new update for the same aircraft.')
    # MUDP Node Identity Arguments
    parser.add_argument('--mudp-node-id', default=config.get('mudp_node_id', '!adsb-gw'), help='The static node ID for MUDP broadcasts.')
    parser.add_argument('--mudp-node-longname', default=config.get('mudp_node_longname', 'ADSB Gateway'), help='The static node long name for MUDP broadcasts.')
    parser.add_argument('--mudp-node-shortname', default=config.get('mudp_node_shortname', 'ADSB'), help='The static node short name for MUDP broadcasts.')

    # Set defaults from config for boolean flags, allowing command line to override
    parser.set_defaults(no_meshtastic=config.get('no_meshtastic', False))
    parser.set_defaults(mudp=config.get('mudp', False))
    parser.add_argument('--debug', action='store_true', default=config.get('debug', False), help='Enable debug logging to print raw data from dump1090.')
    parser.set_defaults(debug=config.get('debug', False))

    return parser.parse_args(remaining_argv)


def connect_to_dump1090(host, port, debug=False):
    """
    Connects to the dump1090 TCP stream and yields lines of data.
    Handles reconnection logic.
    If debug is True, prints raw data received.
    """
    conn_attempts = 0
    while conn_attempts < CONNECT_ATTEMPT_LIMIT:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((host, port))
            print(f"Connected to dump1090 at {host}:{port}")

            buffer = ""
            while True:
                data = s.recv(1024).decode('utf-8', errors='ignore')
                if not data:
                    break

                if debug:
                    print(f"DEBUG: Raw data received: {data.strip()}")

                buffer += data
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    yield line

        except socket.error as e:
            print(f"Error connecting to dump1090 at {host}:{port}: {e}")
            conn_attempts += 1
            if conn_attempts < CONNECT_ATTEMPT_LIMIT:
                print(f"Retrying in {CONNECT_ATTEMPT_DELAY} seconds...")
                time.sleep(CONNECT_ATTEMPT_DELAY)
        finally:
            if 's' in locals() and s:
                s.close()

    print("Could not connect to dump1090 after multiple attempts. Exiting.")
    return None


def process_adsb_message(message, args, aircraft_db, last_sent_time):
    """
    Processes a single ADSB message, updates the aircraft database, and broadcasts if necessary.
    """
    parsed_data = parse_adsb_message(message)

    if not parsed_data or not parsed_data.get('hex_ident'):
        if args.debug and message:
            print(f"DEBUG: Skipping unparseable or invalid message: {message}")
        return

    hex_ident = parsed_data['hex_ident']

    # Get or create the aircraft entry in our database
    aircraft = aircraft_db.get(hex_ident, {})

    # Update the aircraft's data with any new non-empty values
    for key, value in parsed_data.items():
        if value is not None and value != '':
            aircraft[key] = value

    aircraft_db[hex_ident] = aircraft # Store the updated data back

    # Now, check if this aircraft has enough data to be broadcast
    if aircraft.get('lat') and aircraft.get('callsign'):
        current_time = time.time()

        # Check rate-limiter
        if hex_ident not in last_sent_time or \
           (current_time - last_sent_time[hex_ident]) > args.update_interval:

            # Use the aggregated data from our database for the message
            aggregated_data = aircraft_db[hex_ident]

            # Send to Meshtastic device
            if args.meshtastic_interface:
                meshtastic_msg = format_meshtastic_message(aggregated_data)
                print(f"Sending to Meshtastic: {meshtastic_msg}")
                args.meshtastic_interface.sendText(meshtastic_msg)

            # Send to MUDP network
            if args.mudp and send_text_message:
                mudp_msg = format_meshtastic_message(aggregated_data)
                print(f"Broadcasting to MUDP: {mudp_msg}")
                send_text_message(mudp_msg)

            # If no output methods are active, just print to console
            if not args.meshtastic_interface and not args.mudp:
                meshtastic_msg = format_meshtastic_message(aggregated_data)
                print(f"Output (simulated): {meshtastic_msg}")

            # Update the last sent time
            last_sent_time[hex_ident] = current_time
            if args.debug:
                print(f"DEBUG: Broadcasted update for {hex_ident} ({aircraft.get('callsign').strip()})")


def format_meshtastic_message(aircraft_data):
    """
    Formats aircraft data into a concise string for Meshtastic.
    Example: "BAW123 38000ft 51.5N/0.1W"
    """
    callsign = aircraft_data.get('callsign', 'N/A').strip()
    altitude = aircraft_data.get('altitude', 0)
    lat = aircraft_data.get('lat', 0.0)
    lon = aircraft_data.get('lon', 0.0)

    # Format latitude and longitude
    lat_str = f"{abs(lat):.2f}{'N' if lat >= 0 else 'S'}"
    lon_str = f"{abs(lon):.2f}{'E' if lon >= 0 else 'W'}"

    return f"{callsign} {altitude}ft {lat_str}/{lon_str}"


def parse_adsb_message(message_str):
    """
    Parses a raw SBS-1 message string into a dictionary.
    """
    parts = message_str.strip().split(',')
    if len(parts) == 22 and parts[0] == 'MSG':
        # Create a dictionary, replacing empty strings with None
        msg_data = {key: (val if val else None) for key, val in zip(SBS1_FIELDS, parts)}

        # Clean up and type cast some fields
        for key in ['transmission_type', 'altitude', 'ground_speed', 'track', 'vertical_rate', 'squawk']:
            if msg_data.get(key):
                try:
                    msg_data[key] = int(msg_data[key])
                except (ValueError, TypeError):
                    pass # Keep as None if conversion fails

        for key in ['lat', 'lon']:
            if msg_data.get(key):
                try:
                    msg_data[key] = float(msg_data[key])
                except (ValueError, TypeError):
                    pass

        # Booleans
        for key in ['alert', 'emergency', 'spi', 'is_on_ground']:
             if msg_data.get(key):
                msg_data[key] = bool(int(msg_data[key]))

        return msg_data
    return None

def main():
    """
    Main function to run the ADSB to Meshtastic connector.
    """
    args = setup_args()
    print("Starting ADSB to Meshtastic connector...")

    last_sent_time = {}
    aircraft_db = {}

    args.meshtastic_interface = None
    if not args.no_meshtastic:
        try:
            if args.meshtastic_host:
                print(f"Attempting to connect to Meshtastic device at {args.meshtastic_host}:{args.meshtastic_port}...")
                args.meshtastic_interface = meshtastic.tcp_interface.TCPInterface(hostname=args.meshtastic_host, portNumber=args.meshtastic_port)
            else:
                print("Attempting to connect to local Meshtastic device via serial...")
                args.meshtastic_interface = meshtastic.serial_interface.SerialInterface()
            print("Successfully connected to Meshtastic device.")
        except Exception as e:
            if args.meshtastic_host:
                print(f"Warning: Could not connect to Meshtastic device at {args.meshtastic_host}. {e}")
            else:
                print("No local Meshtastic device found.")

    if args.mudp:
        if conn:
            print(f"Initializing MUDP broadcasting to {args.mudp_host}:{args.mudp_port}...")
            conn.setup_multicast(args.mudp_host, args.mudp_port)
            node.node_id = args.mudp_node_id
            node.long_name = args.mudp_node_longname
            node.short_name = args.mudp_node_shortname
            print(f"MUDP Gateway Node ID: {node.node_id}, Name: {node.long_name}")
        else:
            print("MUDP library not found. Please install it with 'pip install mudp'")
            args.mudp = False

    dump1090_stream = connect_to_dump1090(args.dump1090_host, args.dump1090_port, debug=args.debug)

    if dump1090_stream:
        try:
            for message in dump1090_stream:
                process_adsb_message(message, args, aircraft_db, last_sent_time)
        except KeyboardInterrupt:
            print("\nExiting...")
        finally:
            if args.meshtastic_interface and hasattr(args.meshtastic_interface, '_socket'):
                args.meshtastic_interface.close()

if __name__ == '__main__':
    main()
