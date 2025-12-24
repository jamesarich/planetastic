"""
Planetastic: Web Dashboard
Version: 2.1.0
Author: James Rich <james.a.rich@gmail.com>
"""
from aiohttp import web
import logging
from typing import Any
try:
    from .db import DatabaseManager
except ImportError:
    from db import DatabaseManager

logger = logging.getLogger(__name__)

# --- Dashboard Template ---
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Planetastic Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-color: #0d0f14;
            --card-bg: #1a1d24;
            --accent-color: #3b82f6;
            --text-main: #ffffff;
            --text-muted: #94a3b8;
            --success-color: #10b981;
            --alert-color: #ef4444;
        }

        body {
            font-family: 'Inter', sans-serif;
            background-color: var(--bg-color);
            color: var(--text-main);
            margin: 0;
            display: flex;
            flex-direction: column;
            min-height: 100vh;
        }

        header {
            padding: 2rem;
            background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
            border-bottom: 1px solid #334155;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        h1 {
            margin: 0;
            font-weight: 800;
            font-size: 1.5rem;
            letter-spacing: -0.025em;
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }

        .container {
            padding: 2rem;
            max-width: 1200px;
            margin: 0 auto;
            width: 100%;
            box-sizing: border-box;
        }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }

        .stat-card {
            background-color: var(--card-bg);
            padding: 1.5rem;
            border-radius: 1rem;
            border: 1px solid #334155;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }

        .stat-label {
            color: var(--text-muted);
            font-size: 0.875rem;
            font-weight: 600;
            text-transform: uppercase;
        }

        .stat-value {
            font-size: 1.75rem;
            font-weight: 800;
            margin-top: 0.5rem;
        }

        .table-container {
            background-color: var(--card-bg);
            border-radius: 1rem;
            border: 1px solid #334155;
            overflow: hidden;
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
        }

        table {
            width: 100%;
            border-collapse: collapse;
            text-align: left;
        }

        th {
            background-color: #242933;
            padding: 1rem;
            color: var(--text-muted);
            font-weight: 600;
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        td {
            padding: 1rem;
            border-bottom: 1px solid #334155;
            font-size: 0.9375rem;
        }

        tr:last-child td {
            border-bottom: none;
        }

        tr:hover td {
            background-color: #242933;
        }

        .badge {
            padding: 0.25rem 0.5rem;
            border-radius: 0.375rem;
            font-size: 0.75rem;
            font-weight: 600;
        }

        .badge-alt { background-color: rgba(59, 130, 246, 0.2); color: #60a5fa; }
        .badge-speed { background-color: rgba(16, 185, 129, 0.2); color: #34d399; }
        .badge-squawk { background-color: rgba(239, 68, 68, 0.2); color: #f87171; }

        .callsign {
            font-weight: 800;
            color: var(--accent-color);
        }

        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }

        .live-indicator {
            display: inline-block;
            width: 8px;
            height: 8px;
            background-color: var(--success-color);
            border-radius: 50%;
            margin-right: 0.5rem;
            animation: pulse 2s infinite;
        }
    </style>
</head>
<body>
    <header>
        <h1>✈️ Planetastic Gateway</h1>
        <div><span class="live-indicator"></span> LIVE TRACKER</div>
    </header>

    <div class="container">
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-label">Active Aircraft</div>
                <div id="stat-active" class="stat-value">0</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Messages Seen</div>
                <div id="stat-total" class="stat-value">0</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Current Time</div>
                <div id="stat-time" class="stat-value">--:--</div>
            </div>
        </div>

        <div class="table-container">
            <table>
                <thead>
                    <tr>
                        <th>ICAO</th>
                        <th>Callsign</th>
                        <th>Altitude</th>
                        <th>Speed</th>
                        <th>Track</th>
                        <th>Squawk</th>
                        <th>Last Seen</th>
                    </tr>
                </thead>
                <tbody id="aircraft-table">
                    <!-- Rows will be populated by JS -->
                </tbody>
            </table>
        </div>
    </div>

    <script>
        async function updateData() {
            try {
                const response = await fetch('/api/aircraft');
                const data = await response.json();
                
                const tableBody = document.getElementById('aircraft-table');
                tableBody.innerHTML = '';
                
                data.forEach(ac => {
                    const row = document.createElement('tr');
                    const lastSeen = new Date(ac.last_seen).toLocaleTimeString();
                    const callsign = ac.callsign ? ac.callsign.trim() : '---';
                    const sq = ac.squawk || '---';
                    const sqClass = [7500, 7600, 7700].includes(ac.squawk) ? 'badge badge-squawk' : '';

                    row.innerHTML = `
                        <td><code>${ac.hex_ident}</code></td>
                        <td><span class="callsign">${callsign}</span></td>
                        <td><span class="badge badge-alt">${ac.altitude || 0} ft</span></td>
                        <td><span class="badge badge-speed">${ac.ground_speed || 0} kt</span></td>
                        <td>${ac.track ? ac.track + '°' : '---'}</td>
                        <td><span class="${sqClass}">${sq}</span></td>
                        <td style="color: var(--text-muted)">${lastSeen}</td>
                    `;
                    tableBody.appendChild(row);
                });

                document.getElementById('stat-active').innerText = data.length;
                document.getElementById('stat-time').innerText = new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
            } catch (e) {
                console.error("Failed to fetch data", e);
            }
        }

        setInterval(updateData, 2000);
        updateData();
    </script>
</body>
</html>
"""

class DashboardServer:
    def __init__(self, db_manager: DatabaseManager, host: str = '0.0.0.0', port: int = 8080):
        self.db_manager = db_manager
        self.host = host
        self.port = port
        self.app = web.Application()
        self.app.add_routes([
            web.get('/', self.handle_index),
            web.get('/api/aircraft', self.handle_api)
        ])

    async def handle_index(self, request: web.Request) -> web.Response:
        return web.Response(text=DASHBOARD_HTML, content_type='text/html')

    async def handle_api(self, request: web.Request) -> web.Response:
        aircraft = await self.db_manager.get_all_aircraft()
        return web.json_response(aircraft)

    async def start(self) -> None:
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, self.host, self.port)
        await site.start()
        logger.info(f"Dashboard available at http://{self.host}:{self.port}")
