"""
Traccar Framework - Versione Finale Completa
===========================================

Framework Python completo per l'API Traccar con tutti i manager
e gestione corretta di tutti gli errori.
"""

import requests
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Union
import time

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('TraccarFramework')


class TraccarException(Exception):
    """Eccezione personalizzata per errori Traccar"""
    def __init__(self, message: str, status_code: int = None, response_text: str = None):
        self.message = message
        self.status_code = status_code
        self.response_text = response_text
        super().__init__(self._format_message())

    def _format_message(self):
        parts = [self.message]
        if self.status_code:
            parts.append(f"HTTP {self.status_code}")
        if self.response_text:
            preview = self.response_text[:200] + "..." if len(self.response_text) > 200 else self.response_text
            parts.append(f"Response: {preview}")
        return " | ".join(parts)


class TraccarClient:
    """Client Traccar con gestione corretta dei Media Type"""

    def __init__(self, host: str, port: int = 8082, protocol: str = "http",
                 username: str = "", password: str = "", token: str = "",
                 debug: bool = False, timeout: int = 30):

        self.host = host
        self.port = port
        self.protocol = protocol
        self.username = username
        self.password = password
        self.token = token
        self.debug = debug
        self.timeout = timeout

        self.base_url = f"{protocol}://{host}:{port}/api"

        # Crea sessione
        self.session = requests.Session()
        self.session.timeout = timeout

        # Setup autenticazione
        self._setup_auth()

        if debug:
            logger.setLevel(logging.DEBUG)

    def _setup_auth(self):
        """Configura autenticazione"""
        if self.token:
            self.session.headers.update({
                'Authorization': f'Bearer {self.token}'
            })
        elif self.username and self.password:
            self.session.auth = (self.username, self.password)

        # Headers base (senza Content-Type fisso per evitare errori 415)
        self.session.headers.update({
            'Accept': 'application/json',
            'User-Agent': 'TraccarPythonClient/1.0'
        })

    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Effettua richiesta HTTP con gestione corretta dei Content-Type"""

        if not endpoint.startswith('/'):
            endpoint = '/' + endpoint
        url = self.base_url + endpoint

        # Gestisci headers per tipo di richiesta
        headers = kwargs.pop('headers', {})

        # Per richieste JSON, aggiungi Content-Type appropriato
        if 'json' in kwargs and kwargs['json'] is not None:
            headers['Content-Type'] = 'application/json'

        if self.debug:
            logger.debug(f"🔄 {method.upper()} {url}")
            if 'params' in kwargs:
                logger.debug(f"   Params: {kwargs['params']}")
            if 'json' in kwargs:
                logger.debug(f"   JSON: {kwargs['json']}")
            if 'data' in kwargs:
                logger.debug(f"   Data: {kwargs['data']}")
            logger.debug(f"   Headers: {headers}")

        try:
            response = self.session.request(
                method, url,
                timeout=self.timeout,
                headers=headers,
                **kwargs
            )

            if self.debug:
                logger.debug(f"   Status: {response.status_code}")
                logger.debug(f"   Response Headers: {dict(response.headers)}")
                logger.debug(f"   Content-Length: {len(response.content)}")
                if response.content:
                    preview = response.text[:200] if len(response.text) > 200 else response.text
                    logger.debug(f"   Content: {repr(preview)}")

            return response

        except requests.exceptions.Timeout:
            raise TraccarException(f"Timeout dopo {self.timeout}s per {url}")
        except requests.exceptions.ConnectionError as e:
            raise TraccarException(f"Errore di connessione: {str(e)}")
        except requests.exceptions.RequestException as e:
            raise TraccarException(f"Errore richiesta: {str(e)}")

    def _handle_response(self, response: requests.Response) -> Any:
        """Gestisce la risposta con parsing robusto"""

        # Controlla status code
        if response.status_code >= 400:
            error_msg = f"HTTP {response.status_code}"

            try:
                if response.content:
                    content_type = response.headers.get('content-type', '').lower()
                    if 'json' in content_type:
                        error_data = response.json()
                        if isinstance(error_data, dict) and 'message' in error_data:
                            error_msg = error_data['message']
                    else:
                        # Per errori HTML o text
                        error_msg = response.text[:300] if response.text else "Nessun contenuto"

            except Exception:
                error_msg = f"HTTP {response.status_code} - Errore nel parsing della risposta"

            raise TraccarException(
                error_msg,
                status_code=response.status_code,
                response_text=response.text
            )

        # Gestisci 204 No Content
        if response.status_code == 204 or not response.content:
            return True if response.status_code == 204 else {}

        # Parse JSON
        try:
            return response.json()
        except json.JSONDecodeError as e:
            # Debug dettagliato per errori JSON
            content_type = response.headers.get('content-type', 'unknown')
            content_preview = response.text[:300] if response.text else "[empty]"

            raise TraccarException(
                f"Errore parsing JSON: {str(e)}. Content-Type: {content_type}. Content: {repr(content_preview)}",
                status_code=response.status_code,
                response_text=response.text
            )

    def get(self, endpoint: str, params: Dict = None) -> Any:
        """GET request"""
        response = self._make_request("GET", endpoint, params=params)
        return self._handle_response(response)

    def post(self, endpoint: str, data: Dict = None, json_data: Dict = None, params: Dict = None) -> Any:
        """POST request con supporto per form-data e JSON"""
        if json_data:
            response = self._make_request("POST", endpoint, json=json_data, params=params)
        else:
            # Per form data (come login)
            response = self._make_request("POST", endpoint, data=data, params=params)
        return self._handle_response(response)

    def put(self, endpoint: str, data: Dict = None) -> Any:
        """PUT request"""
        response = self._make_request("PUT", endpoint, json=data)
        return self._handle_response(response)

    def delete(self, endpoint: str, params: Dict = None) -> bool:
        """DELETE request"""
        response = self._make_request("DELETE", endpoint, params=params)
        return response.status_code in [204, 200]


class SessionManager:
    """Gestione delle sessioni Traccar"""

    def __init__(self, client: TraccarClient):
        self.client = client

    def login(self, email: str, password: str) -> Dict:
        """Crea una nuova sessione con form-data"""
        data = {
            'email': email,
            'password': password
        }
        # Usa form-data per il login, non JSON
        return self.client.post("/session", data=data)

    def get_session(self, token: str = None) -> Dict:
        """Ottieni informazioni sulla sessione corrente"""
        params = {'token': token} if token else {}
        return self.client.get("/session", params)

    def logout(self) -> bool:
        """Chiudi la sessione corrente"""
        return self.client.delete("/session")


class DeviceManager:
    """Gestione dei dispositivi"""

    def __init__(self, client: TraccarClient):
        self.client = client

    def get_device(self, device_id: int) -> Dict:
        """Ottieni singolo dispositivo per ID"""
        return self.client.get(f"/devices/{device_id}")

    def get_devices(self, all: bool = False, user_id: int = None,
                   device_id: Union[int, List[int]] = None,
                   unique_id: Union[str, List[str]] = None) -> List[Dict]:
        """Ottieni lista dei dispositivi"""
        params = {}
        if all:
            params['all'] = 'true'
        if user_id:
            params['userId'] = user_id
        if device_id:
            if isinstance(device_id, list):
                for did in device_id:
                    params[f'id'] = did
            else:
                params['id'] = device_id
        if unique_id:
            if isinstance(unique_id, list):
                for uid in unique_id:
                    params[f'uniqueId'] = uid
            else:
                params['uniqueId'] = unique_id

        return self.client.get("/devices", params)

    def create_device(self, name: str, unique_id: str, **kwargs) -> Dict:
        """Crea un nuovo dispositivo"""
        data = {
            'name': name,
            'uniqueId': unique_id,
            **kwargs
        }
        return self.client.post("/devices", json_data=data)

    def update_device(self, device_id: int, **kwargs) -> Dict:
        """Aggiorna un dispositivo"""
        return self.client.put(f"/devices/{device_id}", kwargs)

    def delete_device(self, device_id: int) -> bool:
        """Elimina un dispositivo"""
        return self.client.delete(f"/devices/{device_id}")


class PositionManager:
    """Gestione delle posizioni"""

    def __init__(self, client: TraccarClient):
        self.client = client

    def get_positions(self, device_id: int = None, from_time: datetime = None,
                      to_time: datetime = None, position_id: Union[int, List[int]] = None,
                      limit: int = None) -> List[Dict]:
        """Ottieni lista delle posizioni"""
        params = {}
        if device_id:
            params['deviceId'] = device_id
        if from_time:
            params['from'] = from_time.isoformat() + 'Z'
        if to_time:
            params['to'] = to_time.isoformat() + 'Z'
        if position_id:
            if isinstance(position_id, list):
                for pid in position_id:
                    params[f'id'] = pid
            else:
                params['id'] = position_id
        if limit:
            params['limit'] = limit  # AGGIUNTO: supporto limit

        return self.client.get("/positions", params)

class CommandManager:
    """Gestione dei comandi"""

    def __init__(self, client: TraccarClient):
        self.client = client

    def get_commands(self, all: bool = False, user_id: int = None,
                    device_id: int = None, group_id: int = None) -> List[Dict]:
        """Ottieni lista dei comandi salvati"""
        params = {}
        if all:
            params['all'] = 'true'
        if user_id:
            params['userId'] = user_id
        if device_id:
            params['deviceId'] = device_id
        if group_id:
            params['groupId'] = group_id

        return self.client.get("/commands", params)

    def create_command(self, device_id: int, command_type: str, description: str = None, **attributes) -> Dict:
        """Crea un comando salvato"""
        data = {
            'deviceId': device_id,
            'type': command_type,
            'attributes': attributes
        }
        if description:
            data['description'] = description
        return self.client.post("/commands", json_data=data)

    def update_command(self, command_id: int, **kwargs) -> Dict:
        """Aggiorna un comando salvato"""
        return self.client.put(f"/commands/{command_id}", kwargs)

    def delete_command(self, command_id: int) -> bool:
        """Elimina un comando salvato"""
        return self.client.delete(f"/commands/{command_id}")

    def get_supported_commands(self, device_id: int) -> List[Dict]:
        """Ottieni comandi supportati dal dispositivo"""
        params = {'deviceId': device_id}
        return self.client.get("/commands/send", params)

    def send_command(self, device_id: int, command_type: str, **attributes) -> Dict:
        """Invia comando al dispositivo"""
        data = {
            'deviceId': device_id,
            'type': command_type,
            'attributes': attributes
        }
        return self.client.post("/commands/send", json_data=data)

    def get_command_types(self, device_id: int = None, protocol: str = None,
                         text_channel: bool = False) -> List[Dict]:
        """Ottieni tipi di comandi disponibili"""
        params = {}
        if device_id:
            params['deviceId'] = device_id
        if protocol:
            params['protocol'] = protocol
        if text_channel:
            params['textChannel'] = 'true'

        return self.client.get("/commands/types", params)


class GroupManager:
    """Gestione dei gruppi"""

    def __init__(self, client: TraccarClient):
        self.client = client

    def get_groups(self, all: bool = False, user_id: int = None) -> List[Dict]:
        """Ottieni lista dei gruppi"""
        params = {}
        if all:
            params['all'] = 'true'
        if user_id:
            params['userId'] = user_id

        return self.client.get("/groups", params)

    def create_group(self, name: str, **kwargs) -> Dict:
        """Crea un nuovo gruppo"""
        data = {'name': name, **kwargs}
        return self.client.post("/groups", json_data=data)

    def update_group(self, group_id: int, **kwargs) -> Dict:
        """Aggiorna un gruppo"""
        return self.client.put(f"/groups/{group_id}", kwargs)

    def delete_group(self, group_id: int) -> bool:
        """Elimina un gruppo"""
        return self.client.delete(f"/groups/{group_id}")


class GeofenceManager:
    """Gestione dei geofence"""

    def __init__(self, client: TraccarClient):
        self.client = client

    def get_geofences(self, all: bool = False, user_id: int = None,
                     device_id: int = None, group_id: int = None) -> List[Dict]:
        """Ottieni lista dei geofence"""
        params = {}
        if all:
            params['all'] = 'true'
        if user_id:
            params['userId'] = user_id
        if device_id:
            params['deviceId'] = device_id
        if group_id:
            params['groupId'] = group_id

        return self.client.get("/geofences", params)

    def create_geofence(self, name: str, area: str, **kwargs) -> Dict:
        """Crea un nuovo geofence"""
        data = {
            'name': name,
            'area': area,
            **kwargs
        }
        return self.client.post("/geofences", json_data=data)

    def update_geofence(self, geofence_id: int, **kwargs) -> Dict:
        """Aggiorna un geofence"""
        return self.client.put(f"/geofences/{geofence_id}", kwargs)

    def delete_geofence(self, geofence_id: int) -> bool:
        """Elimina un geofence"""
        return self.client.delete(f"/geofences/{geofence_id}")


class ReportManager:
    """Gestione dei report"""

    def __init__(self, client: TraccarClient):
        self.client = client

    def get_summary_report(self, device_ids: List[int] = None, group_ids: List[int] = None,
                          from_time: datetime = None, to_time: datetime = None) -> List[Dict]:
        """Ottieni report riassuntivo"""
        params = {}
        if device_ids:
            for device_id in device_ids:
                params['deviceId'] = device_id
        if group_ids:
            for group_id in group_ids:
                params['groupId'] = group_id
        if from_time:
            params['from'] = from_time.isoformat() + 'Z'
        if to_time:
            params['to'] = to_time.isoformat() + 'Z'

        return self.client.get("/reports/summary", params)

    def get_trips_report(self, device_ids: List[int] = None, group_ids: List[int] = None,
                        from_time: datetime = None, to_time: datetime = None) -> List[Dict]:
        """Ottieni report dei viaggi"""
        params = {}
        if device_ids:
            for device_id in device_ids:
                params['deviceId'] = device_id
        if group_ids:
            for group_id in group_ids:
                params['groupId'] = group_id
        if from_time:
            params['from'] = from_time.isoformat() + 'Z'
        if to_time:
            params['to'] = to_time.isoformat() + 'Z'

        return self.client.get("/reports/trips", params)

    def get_stops_report(self, device_ids: List[int] = None, group_ids: List[int] = None,
                        from_time: datetime = None, to_time: datetime = None) -> List[Dict]:
        """Ottieni report delle soste"""
        params = {}
        if device_ids:
            for device_id in device_ids:
                params['deviceId'] = device_id
        if group_ids:
            for group_id in group_ids:
                params['groupId'] = group_id
        if from_time:
            params['from'] = from_time.isoformat() + 'Z'
        if to_time:
            params['to'] = to_time.isoformat() + 'Z'

        return self.client.get("/reports/stops", params)

    def get_events_report(self, device_ids: List[int] = None, group_ids: List[int] = None,
                         event_types: List[str] = None, from_time: datetime = None,
                         to_time: datetime = None) -> List[Dict]:
        """Ottieni report degli eventi"""
        params = {}
        if device_ids:
            for device_id in device_ids:
                params['deviceId'] = device_id
        if group_ids:
            for group_id in group_ids:
                params['groupId'] = group_id
        if event_types:
            for event_type in event_types:
                params['type'] = event_type
        if from_time:
            params['from'] = from_time.isoformat() + 'Z'
        if to_time:
            params['to'] = to_time.isoformat() + 'Z'

        return self.client.get("/reports/events", params)

    def get_route_report(self, device_ids: List[int] = None, group_ids: List[int] = None,
                        from_time: datetime = None, to_time: datetime = None) -> List[Dict]:
        """Ottieni report del percorso (tutte le posizioni)"""
        params = {}
        if device_ids:
            for device_id in device_ids:
                params['deviceId'] = device_id
        if group_ids:
            for group_id in group_ids:
                params['groupId'] = group_id
        if from_time:
            params['from'] = from_time.isoformat() + 'Z'
        if to_time:
            params['to'] = to_time.isoformat() + 'Z'

        return self.client.get("/reports/route", params)

    def get_trips(self, device_ids: List[int] = None, group_ids: List[int] = None,
                  from_time: datetime = None, to_time: datetime = None) -> List[Dict]:
        """Ottieni report dei viaggi (alias per get_trips_report)"""
        return self.get_trips_report(device_ids, group_ids, from_time, to_time)

    def get_summary(self, device_ids: List[int] = None, group_ids: List[int] = None,
                    from_time: datetime = None, to_time: datetime = None) -> List[Dict]:
        """Ottieni report riepilogativo (alias per get_summary_report)"""
        return self.get_summary_report(device_ids, group_ids, from_time, to_time)


class NotificationManager:
    """Gestione delle notifiche"""

    def __init__(self, client: TraccarClient):
        self.client = client

    def get_notifications(self, all: bool = False, user_id: int = None,
                         device_id: int = None, group_id: int = None) -> List[Dict]:
        """Ottieni lista delle notifiche"""
        params = {}
        if all:
            params['all'] = 'true'
        if user_id:
            params['userId'] = user_id
        if device_id:
            params['deviceId'] = device_id
        if group_id:
            params['groupId'] = group_id

        return self.client.get("/notifications", params)

    def create_notification(self, notification_type: str, **kwargs) -> Dict:
        """Crea una nuova notifica"""
        data = {'type': notification_type, **kwargs}
        return self.client.post("/notifications", json_data=data)

    def update_notification(self, notification_id: int, **kwargs) -> Dict:
        """Aggiorna una notifica"""
        return self.client.put(f"/notifications/{notification_id}", kwargs)

    def delete_notification(self, notification_id: int) -> bool:
        """Elimina una notifica"""
        return self.client.delete(f"/notifications/{notification_id}")

    def get_notification_types(self) -> List[Dict]:
        """Ottieni tipi di notifiche disponibili"""
        return self.client.get("/notifications/types")

    def test_notification(self) -> bool:
        """Invia notifica di test all'utente corrente"""
        try:
            result = self.client.post("/notifications/test", json_data={})
            return True
        except TraccarException:
            return False


class UserManager:
    """Gestione degli utenti"""

    def __init__(self, client: TraccarClient):
        self.client = client

    def get_users(self, user_id: str = None) -> List[Dict]:
        """Ottieni lista degli utenti"""
        params = {}
        if user_id:
            params['userId'] = user_id
        return self.client.get("/users", params)

    def create_user(self, name: str, email: str, password: str, **kwargs) -> Dict:
        """Crea un nuovo utente"""
        data = {
            'name': name,
            'email': email,
            'password': password,
            **kwargs
        }
        return self.client.post("/users", json_data=data)

    def update_user(self, user_id: int, **kwargs) -> Dict:
        """Aggiorna un utente"""
        return self.client.put(f"/users/{user_id}", kwargs)

    def delete_user(self, user_id: int) -> bool:
        """Elimina un utente"""
        return self.client.delete(f"/users/{user_id}")


class PermissionManager:
    """Gestione dei permessi"""

    def __init__(self, client: TraccarClient):
        self.client = client

    def link_objects(self, **kwargs) -> bool:
        """Collega un oggetto a un altro oggetto"""
        try:
            self.client.post("/permissions", json_data=kwargs)
            return True
        except TraccarException:
            return False

    def unlink_objects(self, **kwargs) -> bool:
        """Scollega un oggetto da un altro oggetto"""
        try:
            self.client.delete("/permissions", params=kwargs)
            return True
        except TraccarException:
            return False


class EventManager:
    """Gestione degli eventi"""

    def __init__(self, client: TraccarClient):
        self.client = client

    def get_event(self, event_id: int) -> Dict:
        """Ottieni un singolo evento"""
        return self.client.get(f"/events/{event_id}")


class StatisticsManager:
    """Gestione delle statistiche"""

    def __init__(self, client: TraccarClient):
        self.client = client

    def get_statistics(self, from_time: datetime, to_time: datetime) -> List[Dict]:
        """Ottieni statistiche del server"""
        params = {
            'from': from_time.isoformat() + 'Z',
            'to': to_time.isoformat() + 'Z'
        }
        return self.client.get("/statistics", params)


class ServerManager:
    """Gestione del server"""

    def __init__(self, client: TraccarClient):
        self.client = client

    def get_server_info(self) -> Dict:
        """Ottieni informazioni del server"""
        return self.client.get("/server")


class TraccarAPI:
    """
    Classe principale del framework Traccar
    Integra tutti i manager per un accesso unificato all'API
    """

    def __init__(self, host: str, username: str = "", password: str = "",
                 port: int = 8082, protocol: str = "http", token: str = "",
                 debug: bool = False):
        """
        Inizializza il client Traccar

        Args:
            host: Hostname del server Traccar
            username: Username per l'autenticazione
            password: Password per l'autenticazione
            port: Porta del server (default: 8082)
            protocol: Protocollo http/https (default: http)
            token: Token di autenticazione alternativo
            debug: Abilita debug logging
        """

        self.client = TraccarClient(
            host=host,
            port=port,
            protocol=protocol,
            username=username,
            password=password,
            token=token,
            debug=debug
        )

        # Inizializza tutti i manager
        self.session = SessionManager(self.client)
        self.devices = DeviceManager(self.client)
        self.positions = PositionManager(self.client)
        self.commands = CommandManager(self.client)
        self.groups = GroupManager(self.client)
        self.geofences = GeofenceManager(self.client)
        self.notifications = NotificationManager(self.client)
        self.reports = ReportManager(self.client)
        self.server = ServerManager(self.client)
        self.users = UserManager(self.client)
        self.permissions = PermissionManager(self.client)
        self.events = EventManager(self.client)
        self.statistics = StatisticsManager(self.client)

    def test_connection(self) -> bool:
        """Test connessione completo"""
        print(f"\n🧪 TEST CONNESSIONE TRACCAR")
        print(f"Server: {self.client.base_url}")
        print(f"Auth: {'Basic' if self.client.username else 'Token' if self.client.token else 'None'}")
        print("=" * 50)

        try:
            # 1. Test endpoint server (pubblico)
            print("1. Test endpoint /api/server...")
            server_info = self.server.get_server_info()

            print(f"   ✅ Server raggiungibile")
            print(f"   🏷️ Version: {server_info.get('version', 'unknown')}")
            print(f"   📝 Registration: {server_info.get('registration', 'unknown')}")

            # 2. Test autenticazione con metodo corretto
            if self.client.username and self.client.password:
                print("\n2. Test autenticazione con session login...")
                try:
                    # Usa session login invece di GET /session che può dare 415
                    session_info = self.session.login(self.client.username, self.client.password)

                    print(f"   ✅ Login riuscito!")
                    print(f"   👤 Utente: {session_info.get('name', 'unknown')}")
                    print(f"   📧 Email: {session_info.get('email', 'unknown')}")
                    print(f"   🔑 Admin: {session_info.get('administrator', False)}")

                    # 3. Test endpoint con autenticazione
                    print("\n3. Test endpoint dispositivi...")
                    devices = self.devices.get_devices()
                    print(f"   ✅ Dispositivi accessibili: {len(devices)}")

                    print(f"\n✅ CONNESSIONE E AUTENTICAZIONE RIUSCITE!")
                    return True

                except TraccarException as e:
                    print(f"   ❌ Autenticazione fallita: {e}")

                    # Fallback: prova con Basic Auth diretto
                    print("   🔄 Tentativo con Basic Auth diretto...")
                    try:
                        devices = self.devices.get_devices()
                        print(f"   ✅ Basic Auth funzionante - Dispositivi: {len(devices)}")
                        return True
                    except TraccarException as e2:
                        print(f"   ❌ Basic Auth fallito: {e2}")
                        return False
            else:
                print("\n2. Nessuna autenticazione configurata")
                print("   ⚠️ Solo endpoint pubblici disponibili")
                return True

        except TraccarException as e:
            print(f"\n❌ ERRORE TRACCAR: {e}")
            return False
        except Exception as e:
            print(f"\n❌ ERRORE GENERICO: {type(e).__name__}: {e}")
            return False


# Esempi di utilizzo
def example_basic_usage():
    """Esempio di utilizzo base del framework"""

    print("=== ESEMPIO BASE ===")

    # Inizializza il client
    traccar = TraccarAPI(
        host="torraccia.iliadboxos.it",
        port=58082,
        username="dspeziale@gmail.com",
        password="Elisa2025!",
        debug=False  # Meno verboso per l'esempio
    )

    try:
        # Test connessione
        if not traccar.test_connection():
            print("❌ Impossibile connettersi al server")
            return

        print("✅ Connesso al server Traccar")

        # Informazioni server
        server_info = traccar.server.get_server_info()
        print(f"Server version: {server_info.get('version')}")
        print(f"Registration enabled: {server_info.get('registration', False)}")

        # Lista dispositivi
        devices = traccar.devices.get_devices()
        print(f"\n📱 Dispositivi trovati: {len(devices)}")

        for device in devices[:3]:  # Primi 3 dispositivi
            print(f"- {device['name']} (ID: {device['id']})")
            print(f"  UniqueID: {device['uniqueId']}")
            print(f"  Status: {device['status']}")
            print(f"  Last Update: {device.get('lastUpdate', 'N/A')}")

        # Posizioni se ci sono dispositivi
        if devices:
            print(f"\n📍 Posizioni per primo dispositivo...")
            device_id = devices[0]['id']
            positions = traccar.positions.get_positions(device_id=device_id)
            print(f"Posizioni trovate: {len(positions)}")

            if positions:
                latest = positions[-1]
                print(f"Ultima posizione:")
                print(f"  Timestamp: {latest.get('deviceTime', latest.get('fixTime'))}")
                print(f"  Coordinate: {latest.get('latitude', 0):.6f}, {latest.get('longitude', 0):.6f}")
                print(f"  Velocità: {latest.get('speed', 0):.1f} nodi")

    except TraccarException as e:
        print(f"❌ Errore: {e}")
    except Exception as e:
        print(f"❌ Errore generale: {type(e).__name__}: {e}")


def example_device_management():
    """Esempio di gestione dispositivi"""

    print("\n=== GESTIONE DISPOSITIVI ===")

    traccar = TraccarAPI(
        host="torraccia.iliadboxos.it",
        port=58082,
        username="dspeziale@gmail.com",
        password="Elisa2025!",
        debug=False
    )

    try:
        # Test connessione veloce
        server_info = traccar.server.get_server_info()
        print(f"Connesso al server Traccar v{server_info.get('version')}")

        # Lista dispositivi esistenti
        devices = traccar.devices.get_devices()
        print(f"Dispositivi esistenti: {len(devices)}")

        for i, device in enumerate(devices, 1):
            print(f"{i}. {device['name']} (ID: {device['id']}, Status: {device['status']})")

        print("✅ Gestione dispositivi completata")

    except TraccarException as e:
        print(f"❌ Errore nella gestione dispositivi: {e}")
    except Exception as e:
        print(f"❌ Errore generale: {type(e).__name__}: {e}")


def example_reports():
    """Esempio di generazione report"""

    print("\n=== GENERAZIONE REPORT ===")

    traccar = TraccarAPI(
        host="torraccia.iliadboxos.it",
        port=58082,
        username="dspeziale@gmail.com",
        password="Elisa2025!",
        debug=False
    )

    try:
        # Test connessione veloce
        server_info = traccar.server.get_server_info()
        print(f"Connesso al server Traccar v{server_info.get('version')}")

        devices = traccar.devices.get_devices()

        if not devices:
            print("Nessun dispositivo trovato per i report")
            return

        device_ids = [device['id'] for device in devices[:2]]  # Primi 2 dispositivi

        # Periodo report: ultima settimana
        from_time = datetime.now() - timedelta(days=7)
        to_time = datetime.now()

        print(f"📊 Generazione report dal {from_time.date()} al {to_time.date()}")
        print(f"Dispositivi: {[d['name'] for d in devices[:2]]}")

        # Report riassuntivo
        print("\n📈 Report Riassuntivo:")
        try:
            summary = traccar.reports.get_summary_report(
                device_ids=device_ids,
                from_time=from_time,
                to_time=to_time
            )

            if summary:
                for item in summary:
                    print(f"\nDispositivo: {item.get('deviceName', 'N/A')}")
                    print(f"  Distanza: {item.get('distance', 0):.2f} metri")
                    print(f"  Velocità max: {item.get('maxSpeed', 0):.1f} nodi")
                    print(f"  Velocità media: {item.get('averageSpeed', 0):.1f} nodi")
                    print(f"  Carburante: {item.get('spentFuel', 0):.2f} litri")
                    print(f"  Ore motore: {item.get('engineHours', 0)} ore")
            else:
                print("  Nessun dato nel periodo selezionato")

        except TraccarException as e:
            print(f"  ❌ Errore report riassuntivo: {e}")

        # Report viaggi
        print("\n🚗 Report Viaggi:")
        try:
            trips = traccar.reports.get_trips_report(
                device_ids=device_ids,
                from_time=from_time,
                to_time=to_time
            )

            if trips:
                for i, trip in enumerate(trips[:5], 1):  # Primi 5 viaggi
                    print(f"\n{i}. Viaggio - {trip.get('deviceName', 'N/A')}:")
                    print(f"  Da: {trip.get('startAddress', 'N/A')}")
                    print(f"  A: {trip.get('endAddress', 'N/A')}")
                    print(f"  Inizio: {trip.get('startTime', 'N/A')}")
                    print(f"  Fine: {trip.get('endTime', 'N/A')}")
                    print(f"  Distanza: {trip.get('distance', 0):.2f} metri")
                    print(f"  Durata: {trip.get('duration', 0)} minuti")
                    print(f"  Velocità media: {trip.get('averageSpeed', 0):.1f} nodi")
            else:
                print("  Nessun viaggio nel periodo selezionato")

        except TraccarException as e:
            print(f"  ❌ Errore report viaggi: {e}")

        # Report soste
        print("\n⏸️ Report Soste:")
        try:
            stops = traccar.reports.get_stops_report(
                device_ids=device_ids,
                from_time=from_time,
                to_time=to_time
            )

            if stops:
                for i, stop in enumerate(stops[:5], 1):  # Prime 5 soste
                    print(f"\n{i}. Sosta - {stop.get('deviceName', 'N/A')}:")
                    print(f"  Posizione: {stop.get('address', 'N/A')}")
                    print(f"  Coordinate: {stop.get('lat', 0):.6f}, {stop.get('lon', 0):.6f}")
                    print(f"  Inizio: {stop.get('startTime', 'N/A')}")
                    print(f"  Fine: {stop.get('endTime', 'N/A')}")
                    print(f"  Durata: {stop.get('duration', 0)} minuti")
                    print(f"  Carburante: {stop.get('spentFuel', 0):.2f} litri")
            else:
                print("  Nessuna sosta nel periodo selezionato")

        except TraccarException as e:
            print(f"  ❌ Errore report soste: {e}")

        print("\n✅ Report completati")

    except TraccarException as e:
        print(f"❌ Errore nei report: {e}")
    except Exception as e:
        print(f"❌ Errore generale: {type(e).__name__}: {e}")


if __name__ == "__main__":
    print("🚀 TRACCAR FRAMEWORK COMPLETO - VERSIONE FINALE")
    print("=" * 60)

    try:
        example_basic_usage()
        example_device_management()
        example_reports()

        print("\n🎉 TUTTI GLI ESEMPI COMPLETATI CON SUCCESSO!")

    except KeyboardInterrupt:
        print("\n⏹️ Esempi interrotti dall'utente")
    except Exception as e:
        print(f"\n💥 ERRORE CRITICO: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()