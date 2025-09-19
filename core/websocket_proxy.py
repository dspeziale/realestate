# websocket_proxy.py - WebSocket Proxy per Traccar

import asyncio
import websockets
import json
from flask import current_app
import logging

logger = logging.getLogger(__name__)


class TraccarWebSocketProxy:
    """Proxy WebSocket per connessione a Traccar"""

    def __init__(self, app):
        self.app = app
        self.clients = set()
        self.traccar_ws = None

    async def traccar_listener(self):
        """Ascolta il WebSocket di Traccar e redistribuisce ai client"""
        config = self.app.config['TRACCAR']

        ws_url = f"ws://{config['host']}:{config['port']}/api/socket"

        # Headers per autenticazione
        headers = {}
        if config.get('token'):
            headers['Authorization'] = f"Bearer {config['token']}"

        try:
            async with websockets.connect(ws_url, extra_headers=headers) as websocket:
                self.traccar_ws = websocket
                logger.info("✅ Connected to Traccar WebSocket")

                async for message in websocket:
                    data = json.loads(message)

                    # Redistribuisci a tutti i client connessi
                    if self.clients:
                        disconnected = set()
                        for client in self.clients:
                            try:
                                await client.send(message)
                            except websockets.ConnectionClosed:
                                disconnected.add(client)

                        # Rimuovi client disconnessi
                        self.clients -= disconnected

        except Exception as e:
            logger.error(f"❌ Traccar WebSocket error: {e}")
            self.traccar_ws = None

            # Riconnetti dopo 5 secondi
            await asyncio.sleep(5)
            asyncio.create_task(self.traccar_listener())

    async def client_handler(self, websocket, path):
        """Gestisce connessioni client"""
        self.clients.add(websocket)
        logger.info(f"📱 Client connected. Total: {len(self.clients)}")

        try:
            # Mantieni connessione attiva
            async for message in websocket:
                # Echo back per keep-alive
                await websocket.send(json.dumps({'type': 'pong'}))
        except websockets.ConnectionClosed:
            pass
        finally:
            self.clients.remove(websocket)
            logger.info(f"📴 Client disconnected. Total: {len(self.clients)}")

    async def start_server(self, host='0.0.0.0', port=5001):
        """Avvia server WebSocket proxy"""
        # Start Traccar listener
        asyncio.create_task(self.traccar_listener())

        # Start WebSocket server for clients
        async with websockets.serve(self.client_handler, host, port):
            logger.info(f"🚀 WebSocket Proxy running on ws://{host}:{port}")
            await asyncio.Future()  # Run forever


def run_websocket_proxy(app):
    """Run proxy in background thread"""
    proxy = TraccarWebSocketProxy(app)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    loop.run_until_complete(proxy.start_server())