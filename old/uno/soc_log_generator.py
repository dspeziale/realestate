"""
SOC Security Operations Center - Log Generator e Case Study
===========================================================

Simula raccolta di log da:
- Web Server (Apache/Nginx)
- Firewall
- Router
- Proxy

Con case study realistici per operatore SOC
"""

from opensearchpy import OpenSearch, helpers
from datetime import datetime, timedelta
import random
import json
from typing import List, Dict
import ipaddress


class LogGenerator:
    """Generatore di log realistici per SOC"""

    def __init__(self):
        self.internal_ips = ['10.0.1.0/24', '10.0.2.0/24', '192.168.1.0/24']
        self.malicious_ips = [
            '203.0.113.50', '203.0.113.51', '203.0.113.52',
            '198.51.100.100', '198.51.100.101'
        ]
        self.block_ips = ['10.0.1.50']  # IP interno compromesso

    def generate_webserver_logs(self, count=500) -> List[Dict]:
        """Genera log di web server (Apache/Nginx)"""
        logs = []
        now = datetime.now()
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Safari/537.36',
            'curl/7.68.0',
            'sqlmap/1.5.2',  # Tool di attacco
            'nikto/2.1.5'  # Tool di attacco
        ]

        paths = [
            '/', '/index.html', '/api/users', '/api/login', '/admin',
            '/admin.php', '/wp-admin', '/phpmyadmin',  # Percorsi risky
            '/config.php', '/database.yml', '/.env',
            '/upload', '/upload.php', '/shell.php',
            '/static/js/app.js', '/images/logo.png', '/css/style.css'
        ]

        for i in range(count):
            offset = random.randint(0, 60)
            timestamp = now - timedelta(minutes=offset)

            # Distribuisci attacchi
            is_attack = random.random() < 0.15  # 15% attacchi
            if is_attack:
                client_ip = random.choice(self.malicious_ips + self.block_ips)
                path = random.choice(['/admin.php', '/upload.php', '/../../../etc/passwd',
                                      '/config.php', '/?id=1 OR 1=1'])
                status = random.choice([403, 404, 500])
                user_agent = random.choice(['sqlmap/1.5.2', 'nikto/2.1.5'])
            else:
                client_ip = f"10.0.1.{random.randint(10, 200)}"
                path = random.choice(paths)
                status = random.choices([200, 301, 404], weights=[85, 10, 5])[0]
                user_agent = random.choice(user_agents[:3])

            response_time = random.randint(50, 5000) if not is_attack else random.randint(5000, 30000)

            log = {
                'timestamp': timestamp.isoformat(),
                'source_type': 'webserver',
                'server_ip': '10.0.1.20',
                'server_port': 80,
                'client_ip': client_ip,
                'client_port': random.randint(1024, 65535),
                'method': random.choice(['GET', 'POST', 'PUT', 'DELETE']),
                'path': path,
                'status_code': status,
                'response_bytes': random.randint(100, 50000),
                'response_time_ms': response_time,
                'user_agent': user_agent,
                'referer': random.choice(['https://google.com', 'https://internal.company.com', '-']),
                'is_suspicious': is_attack
            }
            logs.append(log)

        return logs

    def generate_firewall_logs(self, count=400) -> List[Dict]:
        """Genera log di firewall"""
        logs = []
        now = datetime.now()

        protocols = ['TCP', 'UDP', 'ICMP']
        actions = ['ALLOW', 'DENY', 'DROP']
        rules = ['RULE_INBOUND_WEB', 'RULE_OUTBOUND_DNS', 'RULE_VPN_ACCESS',
                 'RULE_SUSPICIOUS_PORT', 'RULE_BOTNET_IPS']

        for i in range(count):
            offset = random.randint(0, 60)
            timestamp = now - timedelta(minutes=offset)

            # 20% di attività sospetta
            is_suspicious = random.random() < 0.20

            if is_suspicious:
                src_ip = random.choice(self.malicious_ips)
                action = random.choice(['DENY', 'DROP'])
                dst_port = random.choice([22, 3389, 445, 139])  # Porte pericolose
                rule = 'RULE_SUSPICIOUS_PORT'
            else:
                src_ip = f"10.0.{random.randint(1, 2)}.{random.randint(10, 200)}"
                action = 'ALLOW'
                dst_port = random.choice([80, 443, 53, 25])
                rule = random.choice(rules[:-1])

            log = {
                'timestamp': timestamp.isoformat(),
                'source_type': 'firewall',
                'src_ip': src_ip,
                'dst_ip': '10.0.1.0' if random.random() > 0.7 else f"203.0.113.{random.randint(1, 254)}",
                'src_port': random.randint(1024, 65535),
                'dst_port': dst_port,
                'protocol': random.choice(protocols),
                'action': action,
                'bytes_in': random.randint(100, 100000),
                'bytes_out': random.randint(100, 100000),
                'duration_sec': random.randint(1, 3600),
                'rule_name': rule,
                'is_suspicious': is_suspicious
            }
            logs.append(log)

        return logs

    def generate_router_logs(self, count=300) -> List[Dict]:
        """Genera log di router"""
        logs = []
        now = datetime.now()

        interfaces = ['eth0', 'eth1', 'wan0', 'vpn0']
        log_types = ['interface_up', 'interface_down', 'bgp_neighbor', 'dhcp_lease',
                     'route_change', 'cpu_high', 'memory_high', 'packet_loss']

        for i in range(count):
            offset = random.randint(0, 60)
            timestamp = now - timedelta(minutes=offset)

            is_alert = random.random() < 0.15
            log_type = random.choice(log_types)

            if is_alert and log_type in ['cpu_high', 'memory_high', 'packet_loss']:
                severity = 'WARNING'
                value = random.randint(80, 99)
            else:
                severity = random.choice(['INFO', 'INFO', 'INFO', 'WARNING'])
                value = random.randint(0, 100)

            log = {
                'timestamp': timestamp.isoformat(),
                'source_type': 'router',
                'router_hostname': 'ROUTER-01',
                'interface': random.choice(interfaces),
                'log_type': log_type,
                'severity': severity,
                'message': f"{log_type} event on {random.choice(interfaces)}",
                'value': value,
                'threshold': 80 if 'high' in log_type else 0,
                'is_alert': is_alert
            }
            logs.append(log)

        return logs

    def generate_proxy_logs(self, count=600) -> List[Dict]:
        """Genera log di proxy (Squid/FortiGate)"""
        logs = []
        now = datetime.now()

        categories = ['news', 'social-media', 'shopping', 'streaming', 'malware',
                      'phishing', 'command-control', 'blocked', 'allowed']
        blocked_sites = ['malicious.ru', 'botnet-c2.com', 'exploit-kit.net']
        dangerous_domains = ['.ru', '.cn', '.kr']

        for i in range(count):
            offset = random.randint(0, 60)
            timestamp = now - timedelta(minutes=offset)

            client_ip = f"10.0.1.{random.randint(10, 200)}"

            # 25% richieste bloccate
            is_blocked = random.random() < 0.25

            if is_blocked:
                domain = random.choice(blocked_sites)
                category = random.choice(['malware', 'phishing', 'command-control', 'blocked'])
                action = 'BLOCKED'
                reason = random.choice(['Malware detected', 'Phishing site', 'C2 communication', 'Policy'])
            else:
                ending = random.choice(['.com', '.it'] + dangerous_domains)
                domain = f"{''.join(random.choices('abcdefghijk', k=5))}{ending}"
                category = random.choice(['news', 'social-media', 'shopping', 'allowed'])
                action = 'ALLOWED'
                reason = None

            bytes_sent = random.randint(1000, 100000)
            bytes_recv = random.randint(1000, 500000)

            log = {
                'timestamp': timestamp.isoformat(),
                'source_type': 'proxy',
                'client_ip': client_ip,
                'domain': domain,
                'url': f"https://{domain}/{''.join(random.choices('abc', k=5))}",
                'method': random.choice(['GET', 'POST']),
                'status_code': 200 if action == 'ALLOWED' else 403,
                'category': category,
                'action': action,
                'reason': reason,
                'bytes_sent': bytes_sent,
                'bytes_recv': bytes_recv,
                'response_time_ms': random.randint(100, 5000),
                'is_blocked': is_blocked
            }
            logs.append(log)

        return logs


class SOCAnalyzer:
    """Analizzatore SOC con query di investigazione"""

    def __init__(self, host='localhost', port=9200):
        self.client = OpenSearch(
            hosts=[{'host': host, 'port': port}],
            http_auth=('admin', 'admin'),
            use_ssl=False,
            verify_certs=False,
            ssl_show_warn=False,
            timeout=30,
            max_retries=3,
            retry_on_timeout=True
        )

        try:
            info = self.client.info()
            print(f"✓ Connesso a OpenSearch {info['version']['number']}")
        except Exception as e:
            print(f"✗ Errore: {e}")
            raise

    def create_soc_indices(self):
        """Crea gli indici per il SOC"""
        indices = {
            'soc-webserver-logs': {
                'properties': {
                    'timestamp': {'type': 'date'},
                    'source_type': {'type': 'keyword'},
                    'server_ip': {'type': 'ip'},
                    'client_ip': {'type': 'ip'},
                    'method': {'type': 'keyword'},
                    'path': {'type': 'text', 'fields': {'keyword': {'type': 'keyword'}}},
                    'status_code': {'type': 'integer'},
                    'response_time_ms': {'type': 'integer'},
                    'user_agent': {'type': 'text'},
                    'is_suspicious': {'type': 'boolean'}
                }
            },
            'soc-firewall-logs': {
                'properties': {
                    'timestamp': {'type': 'date'},
                    'source_type': {'type': 'keyword'},
                    'src_ip': {'type': 'ip'},
                    'dst_ip': {'type': 'ip'},
                    'src_port': {'type': 'integer'},
                    'dst_port': {'type': 'integer'},
                    'protocol': {'type': 'keyword'},
                    'action': {'type': 'keyword'},
                    'rule_name': {'type': 'keyword'},
                    'is_suspicious': {'type': 'boolean'}
                }
            },
            'soc-router-logs': {
                'properties': {
                    'timestamp': {'type': 'date'},
                    'source_type': {'type': 'keyword'},
                    'router_hostname': {'type': 'keyword'},
                    'interface': {'type': 'keyword'},
                    'log_type': {'type': 'keyword'},
                    'severity': {'type': 'keyword'},
                    'value': {'type': 'integer'},
                    'is_alert': {'type': 'boolean'}
                }
            },
            'soc-proxy-logs': {
                'properties': {
                    'timestamp': {'type': 'date'},
                    'source_type': {'type': 'keyword'},
                    'client_ip': {'type': 'ip'},
                    'domain': {'type': 'keyword'},
                    'url': {'type': 'text'},
                    'category': {'type': 'keyword'},
                    'action': {'type': 'keyword'},
                    'is_blocked': {'type': 'boolean'}
                }
            }
        }

        for index_name, mapping in indices.items():
            try:
                if self.client.indices.exists(index=index_name):
                    self.client.indices.delete(index=index_name)
                self.client.indices.create(
                    index=index_name,
                    body={'mappings': mapping}
                )
                print(f"✓ Indice '{index_name}' creato")
            except Exception as e:
                print(f"✗ Errore: {e}")

    def insert_logs(self, logs: List[Dict], index_name: str):
        """Inserisce log in bulk"""
        actions = [
            {'_index': index_name, '_source': log}
            for log in logs
        ]
        success, failed = helpers.bulk(
            self.client, actions, raise_on_error=False, refresh=True
        )
        print(f"✓ Inseriti {success} log in '{index_name}'")
        return success

    # ========== CASE STUDY SOC ==========

    def case_study_1_ddos_detection(self):
        """Case Study 1: Rilevamento potenziale DDoS da firewall"""
        print("\n" + "=" * 70)
        print("CASE STUDY 1: Rilevamento Potenziale DDoS da Firewall")
        print("=" * 70)

        # Query: Troppe connessioni da singolo IP in breve tempo
        response = self.client.search(
            index='soc-firewall-logs',
            body={
                'query': {
                    'bool': {
                        'must': [
                            {'range': {'timestamp': {'gte': 'now-60m'}}},
                            {'term': {'action': 'DENY'}}
                        ]
                    }
                },
                'size': 0,
                'aggs': {
                    'top_attackers': {
                        'terms': {
                            'field': 'src_ip',
                            'size': 10
                        },
                        'aggs': {
                            'connection_count': {
                                'value_count': {'field': 'src_ip'}
                            }
                        }
                    }
                }
            }
        )

        print("\n🚨 IP che generano più DENY:")
        for bucket in response['aggregations']['top_attackers']['buckets']:
            print(f"  • {bucket['key']}: {bucket['doc_count']} connessioni negate")

        # Dettagli dei tentativi
        details = self.client.search(
            index='soc-firewall-logs',
            body={
                'query': {
                    'bool': {
                        'must': [
                            {'term': {'action': 'DENY'}},
                            {'term': {'src_ip': '203.0.113.50'}}
                        ]
                    }
                },
                'size': 5,
                'sort': [{'timestamp': 'desc'}]
            }
        )

        print("\n📋 Dettagli ultimi attacchi da 203.0.113.50:")
        for hit in details['hits']['hits']:
            doc = hit['_source']
            print(f"  {doc['timestamp']} → {doc['dst_ip']}:{doc['dst_port']} "
                  f"({doc['protocol']}) [{doc['rule_name']}]")

    def case_study_2_data_exfiltration(self):
        """Case Study 2: Rilevamento potenziale data exfiltration"""
        print("\n" + "=" * 70)
        print("CASE STUDY 2: Rilevamento Potenziale Data Exfiltration")
        print("=" * 70)

        # IP interno che fa traffico anomalo verso esterno
        response = self.client.search(
            index='soc-proxy-logs',
            body={
                'query': {
                    'bool': {
                        'must': [
                            {'range': {'timestamp': {'gte': 'now-2h'}}},
                            {'term': {'action': 'BLOCKED'}}
                        ]
                    }
                },
                'size': 0,
                'aggs': {
                    'suspicious_clients': {
                        'terms': {
                            'field': 'client_ip',
                            'size': 10
                        },
                        'aggs': {
                            'blocked_attempts': {
                                'sum': {'field': 'bytes_sent'}
                            }
                        }
                    }
                }
            }
        )

        print("\n🚨 IP interni con più tentativi di accesso a siti bloccati:")
        for bucket in response['aggregations']['suspicious_clients']['buckets']:
            print(f"  • {bucket['key']}: {bucket['doc_count']} tentativi")

        # Tentativo di comunicazione con C2
        c2_check = self.client.search(
            index='soc-proxy-logs',
            body={
                'query': {
                    'terms': {'category': ['command-control', 'malware']}
                },
                'size': 10
            }
        )

        print(f"\n⚠️  Accessi a C2/Malware (ultimi {len(c2_check['hits']['hits'])}):")
        for hit in c2_check['hits']['hits']:
            doc = hit['_source']
            print(f"  • {doc['client_ip']} → {doc['domain']} | {doc['reason']}")

    def case_study_3_web_attack(self):
        """Case Study 3: Rilevamento attacco web (SQL injection, RFI)"""
        print("\n" + "=" * 70)
        print("CASE STUDY 3: Rilevamento Attacco Web (SQLi, RFI)")
        print("=" * 70)

        # Query: Ricerca log sospetti da webserver
        suspicious = self.client.search(
            index='soc-webserver-logs',
            body={
                'query': {
                    'bool': {
                        'must': [
                            {'term': {'is_suspicious': True}}
                        ]
                    }
                },
                'size': 0,
                'aggs': {
                    'attack_by_ip': {
                        'terms': {'field': 'client_ip', 'size': 10},
                        'aggs': {
                            'attack_paths': {
                                'terms': {'field': 'path.keyword', 'size': 5}
                            }
                        }
                    }
                }
            }
        )

        print("\n🎯 Attacchi web per IP sorgente:")
        for ip_bucket in suspicious['aggregations']['attack_by_ip']['buckets']:
            print(f"\n  • IP: {ip_bucket['key']} ({ip_bucket['doc_count']} attacchi)")
            print("    Percorsi attaccati:")
            for path_bucket in ip_bucket['attack_paths']['buckets']:
                print(f"      - {path_bucket['key']} ({path_bucket['doc_count']}x)")

        # Risposta anomale (500, 403)
        response_codes = self.client.search(
            index='soc-webserver-logs',
            body={
                'query': {
                    'terms': {'status_code': [403, 404, 500]}
                },
                'size': 0,
                'aggs': {
                    'by_status': {
                        'terms': {'field': 'status_code'}
                    }
                }
            }
        )

        print("\n📊 Status code sospetti:")
        for bucket in response_codes['aggregations']['by_status']['buckets']:
            print(f"  • {bucket['key']}: {bucket['doc_count']} richieste")

    def case_study_4_insider_threat(self):
        """Case Study 4: Rilevamento insider threat - IP interno compromesso"""
        print("\n" + "=" * 70)
        print("CASE STUDY 4: Rilevamento Insider Threat (IP Compromesso)")
        print("=" * 70)

        compromised_ip = '10.0.1.50'

        # Attività del compromised IP su webserver
        web_activity = self.client.search(
            index='soc-webserver-logs',
            body={
                'query': {'term': {'client_ip': compromised_ip}},
                'size': 10,
                'sort': [{'timestamp': 'desc'}]
            }
        )

        print(f"\n🔴 ALLERTA: Attività da IP COMPROMESSO {compromised_ip}")
        print(f"\nRichieste al web server (ultimi {len(web_activity['hits']['hits'])}):")
        for hit in web_activity['hits']['hits']:
            doc = hit['_source']
            print(f"  {doc['timestamp']} → {doc['method']} {doc['path']} "
                  f"[{doc['status_code']}]")

        # Timeline attività
        timeline = self.client.search(
            index='soc-firewall-logs',
            body={
                'query': {'term': {'src_ip': compromised_ip}},
                'size': 0,
                'aggs': {
                    'activity_timeline': {
                        'date_histogram': {
                            'field': 'timestamp',
                            'fixed_interval': '5m'
                        }
                    }
                }
            }
        )

        print(f"\n📈 Timeline attività (ultimi 60 min):")
        for bucket in timeline['aggregations']['activity_timeline']['buckets'][-12:]:
            count = bucket['doc_count']
            bar = '█' * min(count, 50)
            print(f"  {bucket['key_as_string']}: {bar} {count}")

    def case_study_5_router_anomaly(self):
        """Case Study 5: Anomalia su router (CPU/Memory spike)"""
        print("\n" + "=" * 70)
        print("CASE STUDY 5: Anomalia su Router (Performance Spike)")
        print("=" * 70)

        # Alert router
        alerts = self.client.search(
            index='soc-router-logs',
            body={
                'query': {'term': {'severity': 'WARNING'}},
                'size': 10,
                'sort': [{'timestamp': 'desc'}]
            }
        )

        print(f"\n⚠️  Alert ricevuti: {len(alerts['hits']['hits'])}")
        for hit in alerts['hits']['hits']:
            doc = hit['_source']
            print(f"  • {doc['timestamp']}: {doc['log_type']} = {doc['value']}% "
                  f"(threshold: {doc['threshold']}%)")

        # Tipologie alert
        alert_types = self.client.search(
            index='soc-router-logs',
            body={
                'query': {'term': {'is_alert': True}},
                'size': 0,
                'aggs': {
                    'by_type': {
                        'terms': {'field': 'log_type'}
                    }
                }
            }
        )

        print("\n📊 Tipo di alert:")
        for bucket in alert_types['aggregations']['by_type']['buckets']:
            print(f"  • {bucket['key']}: {bucket['doc_count']}")

    def correlation_analysis(self):
        """Analisi correlazione tra eventi di diversi source"""
        print("\n" + "=" * 70)
        print("ANALISI CORRELAZIONE: Multi-Source Incident Investigation")
        print("=" * 70)

        # Trova IP che compaiono su più source con attività sospetta
        print("\n🔗 IP che compaiono su MULTIPLI SOURCE come sospetti:")

        # Webserver
        web_suspicious = self.client.search(
            index='soc-webserver-logs',
            body={
                'query': {'term': {'is_suspicious': True}},
                'size': 0,
                'aggs': {'ips': {'terms': {'field': 'client_ip', 'size': 10}}}
            }
        )

        web_ips = {b['key'] for b in web_suspicious['aggregations']['ips']['buckets']}

        # Firewall
        fw_suspicious = self.client.search(
            index='soc-firewall-logs',
            body={
                'query': {'term': {'is_suspicious': True}},
                'size': 0,
                'aggs': {'ips': {'terms': {'field': 'src_ip', 'size': 10}}}
            }
        )

        fw_ips = {b['key'] for b in fw_suspicious['aggregations']['ips']['buckets']}

        # Intersezione
        correlated_ips = web_ips & fw_ips

        if correlated_ips:
            print(f"\n🚨 CORRELAZIONE TROVATA! IP in ENTRAMBI i log:")
            for ip in correlated_ips:
                print(f"\n  ◆ {ip}")
                # Dettagli web
                web = self.client.search(
                    index='soc-webserver-logs',
                    body={'query': {'term': {'client_ip': ip}}, 'size': 3}
                )
                print(f"    Web server: {len(web['hits']['hits'])} attacchi")
                # Dettagli fw
                fw = self.client.search(
                    index='soc-firewall-logs',
                    body={'query': {'term': {'src_ip': ip}}, 'size': 3}
                )
                print(f"    Firewall: {len(fw['hits']['hits'])} tentativi bloccati")
        else:
            print("\n✓ Nessuna correlazione rilevata tra webserver e firewall")


def main():
    """Esegui il setup completo del SOC"""

    print("=" * 70)
    print("SOC SECURITY OPERATIONS CENTER - Setup Completo")
    print("=" * 70)

    # 1. Genera log
    print("\n1️⃣  Generazione log da multipli source...")
    gen = LogGenerator()

    webserver_logs = gen.generate_webserver_logs(500)
    firewall_logs = gen.generate_firewall_logs(400)
    router_logs = gen.generate_router_logs(300)
    proxy_logs = gen.generate_proxy_logs(600)

    print(f"   ✓ Web Server: {len(webserver_logs)} log")
    print(f"   ✓ Firewall: {len(firewall_logs)} log")
    print(f"   ✓ Router: {len(router_logs)} log")
    print(f"   ✓ Proxy: {len(proxy_logs)} log")

    # 2. Connetti a OpenSearch
    print("\n2️⃣  Connessione a OpenSearch...")
    analyzer = SOCAnalyzer()

    # 3. Crea indici
    print("\n3️⃣  Creazione indici...")
    analyzer.create_soc_indices()

    # 4. Inserisci log
    print("\n4️⃣  Inserimento log...")
    analyzer.insert_logs(webserver_logs, 'soc-webserver-logs')
    analyzer.insert_logs(firewall_logs, 'soc-firewall-logs')
    analyzer.insert_logs(router_logs, 'soc-router-logs')
    analyzer.insert_logs(proxy_logs, 'soc-proxy-logs')

    # 5. Esegui case study
    print("\n5️⃣  Esecuzione Case Study SOC...\n")

    analyzer.case_study_1_ddos_detection()
    analyzer.case_study_2_data_exfiltration()
    analyzer.case_study_3_web_attack()
    analyzer.case_study_4_insider_threat()
    analyzer.case_study_5_router_anomaly()
    analyzer.correlation_analysis()

    print("\n" + "=" * 70)
    print("✅ SETUP COMPLETATO!")
    print("=" * 70)
    print("\n📊 Accedi a OpenSearch Dashboards:")
    print("   👉 http://localhost:5601")
    print("\n📌 Indici creati:")
    print("   • soc-webserver-logs")
    print("   • soc-firewall-logs")
    print("   • soc-router-logs")
    print("   • soc-proxy-logs")
    print("\n💡 Prossimi step:")
    print("   1. Crea Index Pattern per ogni indice (Management → Index Patterns)")
    print("   2. Esplora i dati in Discover")
    print("   3. Crea visualizzazioni personalizzate")
    print("   4. Assembla un dashboard di monitoring SOC")


if __name__ == "__main__":
    main()