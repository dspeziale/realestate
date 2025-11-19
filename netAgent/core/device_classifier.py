# device_classifier.py
import re

class DeviceClassifier:
    """Classifica i dispositivi in base a MAC, hostname, porte aperte e OS"""

    # Mappatura vendor per OUI
    VENDOR_KEYWORDS = {
        'apple': 'Apple',
        'cisco': 'Cisco',
        'dell': 'Dell',
        'hp': 'HP',
        'lenovo': 'Lenovo',
        'samsung': 'Samsung',
        'xiaomi': 'Xiaomi',
        'huawei': 'Huawei',
        'microsoft': 'Microsoft',
        'google': 'Google',
        'amazon': 'Amazon',
        'asus': 'ASUS',
        'd-link': 'D-Link',
        'tp-link': 'TP-Link',
        'netgear': 'Netgear',
        'linksys': 'Linksys',
        'intel': 'Intel',
        'qualcomm': 'Qualcomm',
        'broadcom': 'Broadcom'
    }

    # Mappatura tipi di dispositivo
    DEVICE_TYPES = {
        'router': ['router', 'gateway', 'edge', 'core'],
        'switch': ['switch', 'switching'],
        'access_point': ['access point', 'wireless', 'wifi', 'ap'],
        'printer': ['printer', 'print', 'hp laserjet', 'epson', 'canon'],
        'nas': ['nas', 'synology', 'qnap', 'storage', 'diskstation'],
        'camera': ['camera', 'ip-camera', 'surveillance', 'dvr', 'nvr'],
        'iot': ['iot', 'smart', 'philips hue', 'nest', 'ring', 'arlo'],
        'phone': ['iphone', 'android', 'mobile', 'phone', 'smartphone'],
        'tablet': ['tablet', 'ipad'],
        'laptop': ['laptop', 'notebook', 'macbook', 'thinkpad'],
        'desktop': ['desktop', 'pc', 'workstation'],
        'server': ['server', 'datacenter', 'rackmount'],
        'tv': ['tv', 'television', 'smarttv', 'roku', 'fire tv'],
        'game': ['playstation', 'xbox', 'nintendo']
    }

    # Porte comuni per classificazione
    COMMON_PORTS = {
        'web_server': [80, 443, 8080, 8443],
        'ssh_server': [22],
        'ftp_server': [21, 20],
        'telnet_server': [23],
        'smtp_server': [25, 587],
        'dns_server': [53],
        'dhcp_server': [67, 68],
        'database_server': [3306, 5432, 1433, 1521],
        'file_server': [139, 445, 2049],
        'printer': [515, 631, 9100],
        'media_server': [32400, 8200, 8096]
    }

    @classmethod
    def classify_device(cls, mac, hostname, ports_open, os_info, vendor_from_oui):
        """Classifica il tipo di dispositivo"""
        device_type = "Unknown"
        vendor = vendor_from_oui or "Unknown"

        # Combina tutte le informazioni per l'analisi
        search_text = ""
        if hostname:
            search_text += hostname.lower() + " "
        if os_info:
            search_text += os_info.lower() + " "
        if vendor_from_oui:
            search_text += vendor_from_oui.lower() + " "

        # Determina il vendor dall'OUI o da altre informazioni
        vendor = cls._determine_vendor(mac, vendor_from_oui, search_text)

        # Determina il tipo di dispositivo
        device_type = cls._determine_device_type(search_text, ports_open, vendor)

        return device_type, vendor

    @classmethod
    def _determine_vendor(cls, mac, vendor_from_oui, search_text):
        """Determina il vendor del dispositivo"""
        if vendor_from_oui:
            return vendor_from_oui

        # Cerca keyword nel vendor OUI
        for keyword, vendor_name in cls.VENDOR_KEYWORDS.items():
            if vendor_from_oui and keyword in vendor_from_oui.lower():
                return vendor_name

        # Cerca keyword nelle altre informazioni
        for keyword, vendor_name in cls.VENDOR_KEYWORDS.items():
            if keyword in search_text:
                return vendor_name

        return "Unknown"

    @classmethod
    def _determine_device_type(cls, search_text, ports_open, vendor):
        """Determina il tipo di dispositivo"""
        # Analizza le porte aperte
        port_based_type = cls._classify_by_ports(ports_open)
        if port_based_type != "Unknown":
            return port_based_type

        # Analizza il testo (hostname, OS, vendor)
        for device_type, keywords in cls.DEVICE_TYPES.items():
            for keyword in keywords:
                if keyword in search_text:
                    return device_type.replace('_', ' ').title()

        # Fallback basato sul vendor
        if "apple" in vendor.lower():
            if "iphone" in search_text:
                return "Phone"
            elif "ipad" in search_text:
                return "Tablet"
            elif "macbook" in search_text:
                return "Laptop"
            else:
                return "Computer"

        return "Generic Device"

    @classmethod
    def _classify_by_ports(cls, ports_open):
        """Classifica in base alle porte aperte"""
        if not ports_open:
            return "Unknown"

        open_ports = []
        # Estrai numeri di porta dalla stringa
        port_matches = re.findall(r'(\d+)/', ports_open)
        open_ports = [int(port) for port in port_matches if port.isdigit()]

        # Controlla pattern di porte specifiche
        for port_type, ports in cls.COMMON_PORTS.items():
            common_ports_found = [port for port in open_ports if port in ports]
            if common_ports_found:
                if port_type == 'web_server':
                    return "Web Server"
                elif port_type == 'ssh_server':
                    return "Server"
                elif port_type == 'printer':
                    return "Printer"
                elif port_type == 'media_server':
                    return "Media Server"
                elif port_type in ['ftp_server', 'file_server']:
                    return "File Server"
                elif port_type == 'database_server':
                    return "Database Server"

        # Se ha molte porte aperte, probabilmente è un server
        if len(open_ports) > 5:
            return "Server"

        return "Unknown"