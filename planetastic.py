"""
Planetastic: An ADSB to Meshtastic Connector
Version: 2.1.0
Author: James Rich <james.a.rich@gmail.com>
License: GPL-3.0-or-later
"""
import socket
import time
import argparse
import yaml
import os
try:
    import meshtastic
    import meshtastic.serial_interface
    import meshtastic.tcp_interface
except ImportError:
    meshtastic = None

try:
    from mudp import conn, node, send_text_message
except ImportError:
    conn = None
    node = None
    send_text_message = None

from db import DatabaseManager
from web import DashboardServer
from utils import calculate_distance

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# --- Constants ---
CONNECT_ATTEMPT_DELAY = 5
CONNECT_ATTEMPT_LIMIT = 10
DB_FILENAME = "planetastic.db"

# --- SBS-1 Message Fields ---
SBS1_FIELDS = [
    "message_type",
    "transmission_type",
    "session_id",
    "aircraft_id",
    "hex_ident",
    "flight_id",
    "generated_date",
    "generated_time",
    "logged_date",
    "logged_time",
    "callsign",
    "altitude",
    "ground_speed",
    "track",
    "lat",
    "lon",
    "vertical_rate",
    "squawk",
    "alert",
    "emergency",
    "spi",
    "is_on_ground",
]

@dataclass
class Config:
    dump1090_host: str
    dump1090_port: int
    meshtastic_host: Optional[str]
    meshtastic_port: int
    no_meshtastic: bool
    mudp: bool
    mudp_host: str
    mudp_port: int
    mudp_node_id: str
    mudp_node_longname: str
    mudp_node_shortname: str
    update_interval: int
    home_lat: Optional[float]
    home_lon: Optional[float]
    radius: Optional[float]
    min_alt: Optional[int]
    max_alt: Optional[int]
    web_port: int
    debug: bool
    config_path: Optional[str] = None

def setup_config() -> Config:
    """
    Sets up the configuration, loading defaults from a config file if specified.
    """
    conf_parser = argparse.ArgumentParser(description="A connector between dump1090 and Meshtastic.", add_help=False)
    conf_parser.add_argument('--config', help='Path to a YAML configuration file.')
    args, remaining_argv = conf_parser.parse_known_args()

    config_data = {}
    if args.config and os.path.exists(args.config):
        with open(args.config, 'r') as f:
            config_data = yaml.safe_load(f) or {}

    parser = argparse.ArgumentParser(parents=[conf_parser])
    parser.add_argument('--dump1090-host', default=config_data.get('dump1090_host', os.environ.get('DUMP1090_HOST', 'localhost')))
    parser.add_argument('--dump1090-port', type=int, default=config_data.get('dump1090_port', int(os.environ.get('DUMP1090_PORT', '30003'))))
    parser.add_argument('--meshtastic-host', default=config_data.get('meshtastic_host', os.environ.get('MESHTASTIC_HOST')))
    parser.add_argument('--meshtastic-port', type=int, default=config_data.get('meshtastic_port', int(os.environ.get('MESHTASTIC_PORT', '4403'))))
    parser.add_argument('--no-meshtastic', action='store_true', default=config_data.get('no_meshtastic', False))
    parser.add_argument('--mudp', action='store_true', default=config_data.get('mudp', False))
    parser.add_argument('--mudp-host', default=config_data.get('mudp_host', '224.0.0.69'))
    parser.add_argument('--mudp-port', type=int, default=config_data.get('mudp_port', 4403))
    parser.add_argument('--update-interval', type=int, default=config_data.get('update_interval', 300))
    parser.add_argument('--mudp-node-id', default=config_data.get('mudp_node_id', '!adsb-gw'))
    parser.add_argument('--mudp-node-longname', default=config_data.get('mudp_node_longname', 'ADSB Gateway'))
    parser.add_argument('--mudp-node-shortname', default=config_data.get('mudp_node_shortname', 'ADSB'))
    parser.add_argument('--home-lat', type=float, default=config_data.get('home_lat'))
    parser.add_argument('--home-lon', type=float, default=config_data.get('home_lon'))
    parser.add_argument('--radius', type=float, default=config_data.get('radius'))
    parser.add_argument('--min-alt', type=int, default=config_data.get('min_alt'))
    parser.add_argument('--max-alt', type=int, default=config_data.get('max_alt'))
    parser.add_argument('--web-port', type=int, default=config_data.get('web_port', 8080))
    parser.add_argument('--debug', action='store_true', default=config_data.get('debug', False))
    parser.add_argument('--version', action='version', version='Planetastic 2.1.0')

    ns = parser.parse_args(remaining_argv)
    
    if ns.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")

    return Config(
        dump1090_host=ns.dump1090_host,
        dump1090_port=ns.dump1090_port,
        meshtastic_host=ns.meshtastic_host,
        meshtastic_port=ns.meshtastic_port,
        no_meshtastic=ns.no_meshtastic,
        mudp=ns.mudp,
        mudp_host=ns.mudp_host,
        mudp_port=ns.mudp_port,
        mudp_node_id=ns.mudp_node_id,
        mudp_node_longname=ns.mudp_node_longname,
        mudp_node_shortname=ns.mudp_node_shortname,
        update_interval=ns.update_interval,
        home_lat=ns.home_lat,
        home_lon=ns.home_lon,
        radius=ns.radius,
        min_alt=ns.min_alt,
        max_alt=ns.max_alt,
        web_port=ns.web_port,
        debug=ns.debug,
        config_path=args.config
    )

async def config_watcher(config: Config) -> None:
    """
    Background task that monitors the configuration file for changes.
    """
    if not config.config_path or not os.path.exists(config.config_path):
        return

    last_mtime = os.path.getmtime(config.config_path)
    while True:
        await asyncio.sleep(10)
        try:
            current_mtime = os.path.getmtime(config.config_path)
            if current_mtime > last_mtime:
                logger.info(f"Config file {config.config_path} changed. Reloading settings...")
                with open(config.config_path, 'r') as f:
                    new_data = yaml.safe_load(f) or {}
                    config.radius = new_data.get('radius', config.radius)
                    config.min_alt = new_data.get('min_alt', config.min_alt)
                    config.max_alt = new_data.get('max_alt', config.max_alt)
                    config.home_lat = new_data.get('home_lat', config.home_lat)
                    config.home_lon = new_data.get('home_lon', config.home_lon)
                    config.update_interval = new_data.get('update_interval', config.update_interval)
                    config.debug = new_data.get('debug', config.debug)
                    if config.debug: logging.getLogger().setLevel(logging.DEBUG)
                    else: logging.getLogger().setLevel(logging.INFO)
                last_mtime = current_mtime
                logger.info("Settings reloaded successfully.")
        except Exception as e:
            logger.error(f"Error reloading config: {e}")

async def connect_to_dump1090(host: str, port: int) -> AsyncGenerator[str, None]:
    """
    Async generator for lines from the dump1090 stream.
    """
    attempts = 0
    while attempts < CONNECT_ATTEMPT_LIMIT:
        try:
            logger.info(f"Connecting to dump1090 at {host}:{port}...")
            reader, writer = await asyncio.open_connection(host, port)
            logger.info(f"Connected to dump1090.")
            while True:
                data = await reader.read(4096)
                if not data: break
                for line in data.decode('utf-8', errors='ignore').splitlines():
                    yield line
        except (OSError, asyncio.CancelledError) as e:
            if isinstance(e, asyncio.CancelledError): raise
            logger.error(f"Connection error: {e}")
            attempts += 1
            await asyncio.sleep(CONNECT_ATTEMPT_DELAY)
        finally:
            if 'writer' in locals():
                writer.close()
                await writer.wait_closed()
    logger.error("Could not connect to dump1090 after multiple attempts.")

async def process_adsb_message(message: str, config: Config, db: DatabaseManager, last_sent: Dict[str, float], interface: Any) -> None:
    """
    Processes a single message and broadcasts if necessary.
    """
    parsed = parse_adsb_message(message)
    if not parsed or 'hex_ident' not in parsed: return

    hex_ident = parsed['hex_ident']
    aircraft = await db.update_aircraft(hex_ident, parsed)

    # Filtering
    if aircraft.get('lat') is None or aircraft.get('callsign') is None: return
    
    alt = aircraft.get('altitude', 0)
    if config.min_alt is not None and alt < config.min_alt: return
    if config.max_alt is not None and alt > config.max_alt: return

    if config.radius is not None and config.home_lat is not None and config.home_lon is not None:
        if calculate_distance(config.home_lat, config.home_lon, aircraft['lat'], aircraft['lon']) > config.radius:
            return

    # Broadcast
    now = time.time()
    is_emergency = aircraft.get('squawk') in [7500, 7600, 7700]
    
    if is_emergency or hex_ident not in last_sent or (now - last_sent[hex_ident]) > config.update_interval:
        msg = format_meshtastic_message(aircraft)
        if is_emergency: msg = f"🆘ALERT: {msg}"
        
        if interface:
            logger.info(f"Sending to Meshtastic: {msg}")
            await asyncio.to_thread(interface.sendText, msg)
        
        if config.mudp:
            # Try standalone function first, then connection method
            sender = send_text_message or (conn.send_text_message if conn and hasattr(conn, 'send_text_message') else None)
            if sender:
                logger.info(f"Broadcasting to MUDP: {msg}")
                await asyncio.to_thread(sender, msg)
            else:
                logger.warning("MUDP enabled but send_text_message function not found.")
            
        if not interface and not config.mudp:
            logger.info(f"Output (simulated): {msg}")

        last_sent[hex_ident] = now

def format_meshtastic_message(data: Dict[str, Any]) -> str:
    callsign = str(data.get('callsign', 'N/A')).strip()
    alt = data.get('altitude', 0)
    lat = data.get('lat', 0.0)
    lon = data.get('lon', 0.0)
    lat_str = f"{abs(lat):.2f}{'N' if lat >= 0 else 'S'}"
    lon_str = f"{abs(lon):.2f}{'E' if lon >= 0 else 'W'}"
    return f"✈️{callsign} {alt}ft {lat_str}/{lon_str}"

def parse_adsb_message(message_str: str) -> Optional[Dict[str, Any]]:
    parts = message_str.strip().split(',')
    if len(parts) != 22 or parts[0] != 'MSG': return None
    
    raw = {key: (val if val else None) for key, val in zip(SBS1_FIELDS, parts)}
    try:
        data = {
            'hex_ident': raw['hex_ident'],
            'callsign': raw['callsign'],
            'altitude': int(raw['altitude']) if raw['altitude'] else None,
            'ground_speed': int(raw['ground_speed']) if raw['ground_speed'] else None,
            'track': int(raw['track']) if raw['track'] else None,
            'lat': float(raw['lat']) if raw['lat'] else None,
            'lon': float(raw['lon']) if raw['lon'] else None,
            'vertical_rate': int(raw['vertical_rate']) if raw['vertical_rate'] else None,
            'squawk': int(raw['squawk']) if raw['squawk'] else None,
            'alert': bool(int(raw['alert'])) if raw['alert'] else None,
            'emergency': bool(int(raw['emergency'])) if raw['emergency'] else None,
        }
        return data
    except (ValueError, TypeError):
        return None

async def main() -> None:
    config = setup_config()
    db = DatabaseManager(DB_FILENAME)
    await db.init_db()

    interface = None
    if not config.no_meshtastic and meshtastic:
        try:
            if config.meshtastic_host:
                interface = await asyncio.to_thread(meshtastic.tcp_interface.TCPInterface, hostname=config.meshtastic_host, portNumber=config.meshtastic_port)
            else:
                interface = await asyncio.to_thread(meshtastic.serial_interface.SerialInterface)
            logger.info("Connected to Meshtastic device.")
        except Exception as e:
            logger.warning(f"Could not connect to Meshtastic: {e}")

    if config.mudp and conn:
        logger.info(f"Initializing MUDP at {config.mudp_host}:{config.mudp_port}")
        await asyncio.to_thread(conn.setup_multicast, config.mudp_host, config.mudp_port)
        node.node_id = config.mudp_node_id
        node.long_name = config.mudp_node_longname
        node.short_name = config.mudp_node_shortname

    dash = DashboardServer(db, port=config.web_port)
    await dash.start()
    asyncio.create_task(config_watcher(config))

    last_sent: Dict[str, float] = {}
    try:
        async for line in connect_to_dump1090(config.dump1090_host, config.dump1090_port):
            await process_adsb_message(line, config, db, last_sent, interface)
    except asyncio.CancelledError:
        logger.info("Shutting down...")
    finally:
        if interface:
            await asyncio.to_thread(interface.close)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
