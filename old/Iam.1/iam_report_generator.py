"""
OpenSearch IAM Report Generator - Export HTML/PDF Professionale
===============================================================

Genera report esecutivi in HTML/PDF con grafici, KPI e analisi

pip install jinja2 plotly kaleido python-dateutil
"""

from datetime import datetime, timedelta
from typing import Dict, List, Any
from opensearchpy import OpenSearch
import json
from pathlib import Path


class IamReportGenerator:
    """Genera report professionali sulle richieste IAM"""

    def __init__(self, os_client: OpenSearch):
        self.os_client = os_client
        self.report_data = {}

    def fetch_dashboard_data(self, index_name='iam-richieste', days=30) -> Dict:
        """Estrae tutti i dati necessari per il report"""
        print(f"📊 Estrazione dati report (ultimi {days} giorni)...")

        data = {
            'report_date': datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
            'period': f'Ultimi {days} giorni',
            'index': index_name
        }

        # Metriche principali
        response = self.os_client.count(index=index_name)
        total = response['count']
        data['total_requests'] = total

        # KPI
        response = self.os_client.search(
            index=index_name,
            body={
                'size': 0,
                'aggs': {
                    'completate': {'filter': {'term': {'is_completed': True}}},
                    'fallite': {'filter': {'term': {'is_failed': True}}},
                    'in_attesa': {'filter': {'term': {'is_pending': True}}},
                    'tempo_medio': {'avg': {'field': 'ore_elaborazione'}},
                    'tempo_max': {'max': {'field': 'ore_elaborazione'}},
                    'unique_users': {'cardinality': {'field': 'FK_UTENTE'}},
                    'unique_types': {'cardinality': {'field': 'FK_TIPO_RICHIESTA'}}
                }
            }
        )

        aggs = response['aggregations']
        data['kpis'] = {
            'success_rate': round((aggs['completate']['doc_count'] / total * 100), 2) if total > 0 else 0,
            'failure_rate': round((aggs['fallite']['doc_count'] / total * 100), 2) if total > 0 else 0,
            'pending_rate': round((aggs['in_attesa']['doc_count'] / total * 100), 2) if total > 0 else 0,
            'completed': aggs['completate']['doc_count'],
            'failed': aggs['fallite']['doc_count'],
            'pending': aggs['in_attesa']['doc_count'],
            'avg_processing_time': round(aggs['tempo_medio']['value'] or 0, 2),
            'max_processing_time': round(aggs['tempo_max']['value'] or 0, 2),
            'unique_users': aggs['unique_users']['value'],
            'unique_types': aggs['unique_types']['value']
        }

        # Distribuzione per stato
        response = self.os_client.search(
            index=index_name,
            body={
                'size': 0,
                'aggs': {
                    'by_stato': {
                        'terms': {'field': 'STATO', 'size': 20}
                    }
                }
            }
        )
        data['stato_distribution'] = [
            {'stato': b['key'], 'count': b['doc_count']}
            for b in response['aggregations']['by_stato']['buckets']
        ]

        # Top operazioni
        response = self.os_client.search(
            index=index_name,
            body={
                'size': 0,
                'aggs': {
                    'top_ops': {
                        'terms': {'field': 'FK_NOME_OPERAZIONE', 'size': 15},
                        'aggs': {
                            'success': {'filter': {'term': {'is_completed': True}}},
                            'errors': {'filter': {'term': {'is_failed': True}}}
                        }
                    }
                }
            }
        )
        data['top_operations'] = [
            {
                'operation': b['key'] or 'N/A',
                'count': b['doc_count'],
                'success': b['success']['doc_count'],
                'errors': b['errors']['doc_count'],
                'success_rate': round((b['success']['doc_count'] / b['doc_count'] * 100), 2) if b[
                                                                                                    'doc_count'] > 0 else 0
            }
            for b in response['aggregations']['top_ops']['buckets']
        ]

        # Top utenti
        response = self.os_client.search(
            index=index_name,
            body={
                'size': 0,
                'aggs': {
                    'top_users': {
                        'terms': {'field': 'FK_UTENTE', 'size': 20},
                        'aggs': {
                            'success': {'filter': {'term': {'is_completed': True}}},
                            'errors': {'filter': {'term': {'is_failed': True}}},
                            'avg_time': {'avg': {'field': 'ore_elaborazione'}}
                        }
                    }
                }
            }
        )
        data['top_users'] = [
            {
                'user': b['key'],
                'count': b['doc_count'],
                'success': b['success']['doc_count'],
                'errors': b['errors']['doc_count'],
                'success_rate': round((b['success']['doc_count'] / b['doc_count'] * 100), 2) if b[
                                                                                                    'doc_count'] > 0 else 0,
                'avg_time': round(b['avg_time']['value'] or 0, 2)
            }
            for b in response['aggregations']['top_users']['buckets']
        ]

        # Timeline
        response = self.os_client.search(
            index=index_name,
            body={
                'size': 0,
                'aggs': {
                    'timeline': {
                        'date_histogram': {'field': 'DATA_CREAZIONE', 'fixed_interval': '1d'},
                        'aggs': {
                            'success': {'filter': {'term': {'is_completed': True}}},
                            'errors': {'filter': {'term': {'is_failed': True}}}
                        }
                    }
                }
            }
        )
        data['timeline'] = [
            {
                'date': b['key_as_string'][:10],
                'total': b['doc_count'],
                'success': b['success']['doc_count'],
                'errors': b['errors']['doc_count']
            }
            for b in response['aggregations']['timeline']['buckets'][-30:]  # Ultimi 30 giorni
        ]

        # Tipi richiesta
        response = self.os_client.search(
            index=index_name,
            body={
                'size': 0,
                'aggs': {
                    'by_type': {
                        'terms': {'field': 'FK_TIPO_RICHIESTA', 'size': 15},
                        'aggs': {
                            'success': {'filter': {'term': {'is_completed': True}}},
                            'errors': {'filter': {'term': {'is_failed': True}}},
                            'avg_time': {'avg': {'field': 'ore_elaborazione'}}
                        }
                    }
                }
            }
        )
        data['request_types'] = [
            {
                'type': b['key'],
                'count': b['doc_count'],
                'success': b['success']['doc_count'],
                'errors': b['errors']['doc_count'],
                'success_rate': round((b['success']['doc_count'] / b['doc_count'] * 100), 2) if b[
                                                                                                    'doc_count'] > 0 else 0,
                'avg_time': round(b['avg_time']['value'] or 0, 2)
            }
            for b in response['aggregations']['by_type']['buckets']
        ]

        # Richieste lente (top 10)
        response = self.os_client.search(
            index=index_name,
            body={
                'size': 10,
                'query': {'match_all': {}},
                'sort': [{'ore_elaborazione': 'desc'}]
            }
        )
        data['slow_requests'] = [
            {
                'id': hit['_source']['ID_RICHIESTA'],
                'user': hit['_source'].get('FK_UTENTE', 'N/A'),
                'type': hit['_source'].get('FK_TIPO_RICHIESTA', 'N/A'),
                'operation': hit['_source'].get('FK_NOME_OPERAZIONE', 'N/A'),
                'state': hit['_source'].get('STATO', 'N/A'),
                'time_hours': round(hit['_source'].get('ore_elaborazione', 0), 2),
                'created': hit['_source'].get('DATA_CREAZIONE', 'N/A')[:10]
            }
            for hit in response['hits']['hits']
        ]

        # Errori recenti (top 10)
        response = self.os_client.search(
            index=index_name,
            body={
                'size': 10,
                'query': {'term': {'is_failed': True}},
                'sort': [{'DATA_CREAZIONE': 'desc'}]
            }
        )
        data['recent_errors'] = [
            {
                'id': hit['_source']['ID_RICHIESTA'],
                'user': hit['_source'].get('FK_UTENTE', 'N/A'),
                'type': hit['_source'].get('FK_TIPO_RICHIESTA', 'N/A'),
                'state': hit['_source'].get('STATO', 'N/A'),
                'note': hit['_source'].get('NOTA', 'N/A')[:100],
                'created': hit['_source'].get('DATA_CREAZIONE', 'N/A')[:10]
            }
            for hit in response['hits']['hits']
        ]

        self.report_data = data
        return data

    def generate_html_report(self, output_file='iam_report.html') -> str:
        """Genera report HTML"""
        if not self.report_data:
            print("✗ Nessun dato disponibile. Esegui fetch_dashboard_data() prima.")
            return ""

        print(f"📄 Generazione report HTML...")

        html_content = f"""
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Report IAM - {self.report_data['report_date']}</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #333;
            padding: 20px;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
            text-align: center;
        }}
        .header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
        }}
        .header p {{
            font-size: 1.1em;
            opacity: 0.9;
        }}
        .content {{
            padding: 40px;
        }}
        .report-info {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 40px;
            padding: 20px;
            background: #f8f9fa;
            border-radius: 8px;
        }}
        .info-item {{
            padding: 15px;
            background: white;
            border-left: 4px solid #667eea;
            border-radius: 4px;
        }}
        .info-item strong {{
            color: #667eea;
            display: block;
            margin-bottom: 5px;
        }}
        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }}
        .kpi-card {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 25px;
            border-radius: 8px;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.2);
            text-align: center;
        }}
        .kpi-card .value {{
            font-size: 2.5em;
            font-weight: bold;
            margin: 10px 0;
        }}
        .kpi-card .label {{
            font-size: 0.9em;
            opacity: 0.9;
        }}
        .kpi-card .unit {{
            font-size: 1em;
            opacity: 0.8;
        }}
        .section {{
            margin-bottom: 40px;
        }}
        .section-title {{
            font-size: 1.8em;
            color: #667eea;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 3px solid #667eea;
        }}
        .chart-container {{
            background: white;
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 30px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }}
        th {{
            background: #667eea;
            color: white;
            padding: 15px;
            text-align: left;
            font-weight: 600;
        }}
        td {{
            padding: 12px 15px;
            border-bottom: 1px solid #e0e0e0;
        }}
        tr:hover {{
            background: #f8f9fa;
        }}
        .success {{
            color: #28a745;
            font-weight: bold;
        }}
        .warning {{
            color: #ffc107;
            font-weight: bold;
        }}
        .error {{
            color: #dc3545;
            font-weight: bold;
        }}
        .footer {{
            text-align: center;
            padding: 20px;
            background: #f8f9fa;
            color: #666;
            border-top: 1px solid #e0e0e0;
            margin-top: 40px;
        }}
        .grid-2 {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 30px;
        }}
        @media print {{
            body {{
                background: white;
                padding: 0;
            }}
            .container {{
                box-shadow: none;
                border-radius: 0;
            }}
            .page-break {{
                page-break-after: always;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 Report Monitoraggio IAM</h1>
            <p>Analisi Richieste Sistema IAM</p>
            <p style="font-size: 0.9em; margin-top: 10px;">Generato il {self.report_data['report_date']}</p>
        </div>

        <div class="content">
            <!-- INFO GENERALI -->
            <div class="report-info">
                <div class="info-item">
                    <strong>Periodo Analizzato</strong>
                    {self.report_data['period']}
                </div>
                <div class="info-item">
                    <strong>Indice OpenSearch</strong>
                    {self.report_data['index']}
                </div>
                <div class="info-item">
                    <strong>Totale Richieste</strong>
                    {self.report_data['total_requests']:,}
                </div>
                <div class="info-item">
                    <strong>Utenti Attivi</strong>
                    {self.report_data['kpis']['unique_users']}
                </div>
            </div>

            <!-- KPI PRINCIPALI -->
            <div class="section">
                <h2 class="section-title">🎯 KPI Principali</h2>
                <div class="kpi-grid">
                    <div class="kpi-card">
                        <div class="label">Success Rate</div>
                        <div class="value">{self.report_data['kpis']['success_rate']:.1f}%</div>
                        <div class="unit">{self.report_data['kpis']['completed']} richieste</div>
                    </div>
                    <div class="kpi-card">
                        <div class="label">Failure Rate</div>
                        <div class="value">{self.report_data['kpis']['failure_rate']:.1f}%</div>
                        <div class="unit">{self.report_data['kpis']['failed']} fallimenti</div>
                    </div>
                    <div class="kpi-card">
                        <div class="label">In Elaborazione</div>
                        <div class="value">{self.report_data['kpis']['pending']}</div>
                        <div class="unit">{self.report_data['kpis']['pending_rate']:.1f}% del totale</div>
                    </div>
                    <div class="kpi-card">
                        <div class="label">Tempo Medio Elaborazione</div>
                        <div class="value">{self.report_data['kpis']['avg_processing_time']:.1f}h</div>
                        <div class="unit">Max: {self.report_data['kpis']['max_processing_time']:.1f}h</div>
                    </div>
                </div>
            </div>

            <!-- DISTRIBUZIONI -->
            <div class="section">
                <h2 class="section-title">📈 Distribuzioni Principali</h2>
                <div class="grid-2">
                    <div class="chart-container">
                        <h3>Stato delle Richieste</h3>
                        <table>
                            <tr>
                                <th>Stato</th>
                                <th>Conteggio</th>
                                <th>Percentuale</th>
                            </tr>
"""

        total_stato = sum(s['count'] for s in self.report_data['stato_distribution'])
        for stato in self.report_data['stato_distribution']:
            pct = (stato['count'] / total_stato * 100) if total_stato > 0 else 0
            html_content += f"""
                            <tr>
                                <td>{stato['stato']}</td>
                                <td>{stato['count']}</td>
                                <td>{pct:.1f}%</td>
                            </tr>
"""

        html_content += """
                        </table>
                    </div>

                    <div class="chart-container">
                        <h3>Top 10 Operazioni</h3>
                        <table>
                            <tr>
                                <th>Operazione</th>
                                <th>Richieste</th>
                                <th>Success Rate</th>
                            </tr>
"""

        for op in self.report_data['top_operations'][:10]:
            status_class = 'success' if op['success_rate'] >= 90 else (
                'warning' if op['success_rate'] >= 80 else 'error')
            html_content += f"""
                            <tr>
                                <td>{op['operation'][:40]}</td>
                                <td>{op['count']}</td>
                                <td class="{status_class}">{op['success_rate']:.1f}%</td>
                            </tr>
"""

        html_content += """
                        </table>
                    </div>
                </div>
            </div>

            <!-- TOP UTENTI -->
            <div class="section">
                <h2 class="section-title">👥 Top Utenti Attivi</h2>
                <div class="chart-container">
                    <table>
                        <tr>
                            <th>Utente</th>
                            <th>Richieste</th>
                            <th>Completate</th>
                            <th>Errori</th>
                            <th>Success Rate</th>
                            <th>Tempo Medio (h)</th>
                        </tr>
"""

        for user in self.report_data['top_users'][:15]:
            status_class = 'success' if user['success_rate'] >= 90 else (
                'warning' if user['success_rate'] >= 80 else 'error')
            html_content += f"""
                        <tr>
                            <td><strong>{user['user']}</strong></td>
                            <td>{user['count']}</td>
                            <td>{user['success']}</td>
                            <td>{user['errors']}</td>
                            <td class="{status_class}">{user['success_rate']:.1f}%</td>
                            <td>{user['avg_time']:.2f}</td>
                        </tr>
"""

        html_content += """
                    </table>
                </div>
            </div>

            <!-- RICHIESTE LENTE -->
            <div class="section">
                <h2 class="section-title">🐢 Richieste Lente (Top 10)</h2>
                <div class="chart-container">
                    <table>
                        <tr>
                            <th>ID Richiesta</th>
                            <th>Utente</th>
                            <th>Tipo</th>
                            <th>Operazione</th>
                            <th>Stato</th>
                            <th>Tempo (ore)</th>
                        </tr>
"""

        for req in self.report_data['slow_requests']:
            html_content += f"""
                        <tr>
                            <td><strong>{req['id']}</strong></td>
                            <td>{req['user']}</td>
                            <td>{req['type']}</td>
                            <td>{req['operation']}</td>
                            <td>{req['state']}</td>
                            <td class="warning">{req['time_hours']:.1f}h</td>
                        </tr>
"""

        html_content += """
                    </table>
                </div>
            </div>

            <!-- ERRORI RECENTI -->
            <div class="section">
                <h2 class="section-title">❌ Errori Recenti (Top 10)</h2>
                <div class="chart-container">
                    <table>
                        <tr>
                            <th>ID Richiesta</th>
                            <th>Utente</th>
                            <th>Tipo</th>
                            <th>Stato</th>
                            <th>Note</th>
                            <th>Data</th>
                        </tr>
"""

        for err in self.report_data['recent_errors']:
            html_content += f"""
                        <tr>
                            <td><strong>{err['id']}</strong></td>
                            <td>{err['user']}</td>
                            <td>{err['type']}</td>
                            <td class="error">{err['state']}</td>
                            <td>{err['note']}</td>
                            <td>{err['created']}</td>
                        </tr>
"""

        html_content += """
                    </table>
                </div>
            </div>

            <!-- FOOTER -->
            <div class="footer">
                <p>Report generato automaticamente da OpenSearch IAM Analysis System</p>
                <p style="font-size: 0.9em; margin-top: 10px;">
                    © """ + datetime.now().strftime("%Y") + """ - Sistema di Monitoraggio IAM
                </p>
            </div>
        </div>
    </div>

    <script>
        // Stampa automatica (opzionale)
        // window.print();
    </script>
</body>
</html>
"""

        # Scrivi file
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)

        print(f"✓ Report HTML salvato: {output_file}")
        return output_file

    def generate_csv_export(self, output_file='iam_data_export.csv') -> str:
        """Esporta dati in CSV"""
        if not self.report_data:
            print("✗ Nessun dato disponibile.")
            return ""

        print(f"📄 Generazione export CSV...")

        import csv

        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)

            # KPI
            writer.writerow(['KPI SUMMARY'])
            writer.writerow(['Metrica', 'Valore'])
            for key, value in self.report_data['kpis'].items():
                writer.writerow([key, value])

            writer.writerow([])
            writer.writerow(['TOP OPERAZIONI'])
            writer.writerow(['Operazione', 'Richieste', 'Completate', 'Errori', 'Success Rate'])
            for op in self.report_data['top_operations']:
                writer.writerow([op['operation'], op['count'], op['success'], op['errors'], op['success_rate']])

            writer.writerow([])
            writer.writerow(['TOP UTENTI'])
            writer.writerow(['Utente', 'Richieste', 'Completate', 'Errori', 'Success Rate', 'Tempo Medio'])
            for user in self.report_data['top_users']:
                writer.writerow([user['user'], user['count'], user['success'], user['errors'], user['success_rate'],
                                 user['avg_time']])

        print(f"✓ CSV salvato: {output_file}")
        return output_file


def main():
    """Genera report completo"""
    print("=" * 70)
    print("📊 OPENSEARCH IAM REPORT GENERATOR")
    print("=" * 70 + "\n")

    try:
        # Connessione OpenSearch
        os_client = OpenSearch(
            hosts=[{'host': 'localhost', 'port': 9200}],
            http_auth=('admin', 'admin'),
            use_ssl=False,
            verify_certs=False,
            ssl_show_warn=False
        )

        # Crea generator
        generator = IamReportGenerator(os_client)

        # Estrae dati
        print("\n1️⃣  Estrazione dati dal sistema...\n")
        generator.fetch_dashboard_data('iam-richieste', days=30)

        # Genera report
        print("\n2️⃣  Generazione report...\n")
        html_file = generator.generate_html_report('iam_report_' + datetime.now().strftime('%Y%m%d_%H%M%S') + '.html')
        csv_file = generator.generate_csv_export('iam_data_' + datetime.now().strftime('%Y%m%d_%H%M%S') + '.csv')

        print("\n" + "=" * 70)
        print("✅ REPORT GENERATI!")
        print("=" * 70)
        print(f"\n📄 HTML: {html_file}")
        print(f"📊 CSV:  {csv_file}")
        print(f"\n💡 Suggerimenti:")
        print(f"   - Apri il file HTML nel browser")
        print(f"   - Usa Ctrl+P per stampare come PDF")
        print(f"   - Importa il CSV in Excel per ulteriori analisi")

    except Exception as e:
        print(f"\n✗ Errore: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()