#
# EXCEL_REPORT_GENERATOR_SIMPLE.py - Versione semplificata senza errori stili
# Copyright 2025 TIM SPA
# Author Daniele Speziale
# Filename: Complex/Core/excel_report_generator_simple.py
# Created 30/09/25
# Description: Versione robusta senza conflitti StyleProxy
#
import logging
import pandas as pd
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils.dataframe import dataframe_to_rows
from Complex.Core.database_manager import DatabaseManager


class SimpleExcelReportGenerator:
    """Generatore Excel semplificato che evita errori StyleProxy"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.db_manager = DatabaseManager(config)
        self.logger = logging.getLogger(__name__)

        # Directory
        self.output_directory = Path(config.get('execution', {}).get('excel_output_directory', 'reports'))
        self.output_directory.mkdir(parents=True, exist_ok=True)
        self.query_directory = Path(config.get('execution', {}).get('query_directory', 'queries'))
        self.reports_query_directory = Path(
            config.get('execution', {}).get('reports_query_directory', 'reports/queries'))

    def _get_query_directory_for_type(self, sheet_config: Dict[str, Any]) -> Path:
        """Determina directory corretta"""
        query_type = sheet_config.get('query_type', 'report')
        return self.reports_query_directory if query_type == 'report' else self.query_directory

    def resolve_sql(self, sheet_config: Dict[str, Any]) -> str:
        """Risolve SQL da file o inline"""
        sheet_name = sheet_config.get('name', 'unnamed')

        if 'sql' in sheet_config:
            if isinstance(sheet_config['sql'], list):
                return ' '.join(line.strip() for line in sheet_config['sql'])
            return sheet_config['sql']

        elif 'sql_file' in sheet_config:
            sql_filename = sheet_config['sql_file']
            query_dir = self._get_query_directory_for_type(sheet_config)
            sql_file = query_dir / sql_filename

            if not sql_file.exists():
                fallback_dir = self.query_directory if query_dir == self.reports_query_directory else self.reports_query_directory
                fallback_file = fallback_dir / sql_filename
                if fallback_file.exists():
                    sql_file = fallback_file

            if not sql_file.exists():
                raise FileNotFoundError(f"File SQL non trovato: {sql_file}")

            with open(sql_file, 'r', encoding='utf-8') as f:
                sql = f.read()

            self.logger.info(f"EXCEL: SQL caricato da {sql_file.name} per foglio [{sheet_name}]")
            return sql

        else:
            raise ValueError(f"Nessuna sorgente SQL per foglio [{sheet_name}]")

    def execute_query(self, database_name: str, sql: str) -> pd.DataFrame:
        """Esegue query e restituisce DataFrame"""
        self.logger.info(f"EXCEL: Esecuzione query su [{database_name}]")

        with self.db_manager.get_connection(database_name) as conn:
            return pd.read_sql(sql, conn)

    def apply_simple_formatting(self, worksheet, df: pd.DataFrame, has_description: bool = False):
        """Applica formattazione semplice senza conflitti di stili"""
        try:
            # Offset per descrizione
            start_row = 1 #3 if has_description else 1
            header_row = start_row

            # Formatta header
            for col_num in range(1, len(df.columns) + 1):
                cell = worksheet.cell(row=header_row, column=col_num)
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
                cell.alignment = Alignment(horizontal="center")

            # Auto-ridimensiona colonne
            for col_num in range(1, len(df.columns) + 1):
                column_letter = worksheet.cell(row=1, column=col_num).column_letter
                max_length = 15  # Lunghezza di base

                # Calcola lunghezza massima
                for row_num in range(start_row, len(df) + start_row + 1):
                    cell_value = str(worksheet.cell(row=row_num, column=col_num).value or "")
                    max_length = max(max_length, len(cell_value))

                # Imposta larghezza colonna
                adjusted_width = min(max_length + 2, 50)
                worksheet.column_dimensions[column_letter].width = adjusted_width

            # Blocca prima riga
            freeze_cell = worksheet.cell(row=header_row + 1, column=1)
            worksheet.freeze_panes = freeze_cell

            self.logger.info("EXCEL: Formattazione semplice applicata con successo")

        except Exception as e:
            self.logger.warning(f"EXCEL: Errore formattazione (continuando senza): {e}")

    def generate_report(self, report_config: Dict[str, Any]) -> Dict[str, Any]:
        """Genera report Excel con approccio semplificato"""
        report_name = report_config.get('name', 'report')
        sheets = report_config.get('sheets', [])

        if not sheets:
            raise ValueError(f"Report [{report_name}] senza fogli")

        self.logger.info(f"EXCEL: Generazione report [{report_name}] con {len(sheets)} fogli")

        # Crea workbook
        wb = Workbook()
        wb.remove(wb.active)

        # Proprietà documento base
        properties = report_config.get('properties', {})
        if 'title' in properties:
            wb.properties.title = properties['title']
        if 'author' in properties:
            wb.properties.creator = properties['author']
        wb.properties.created = datetime.now()

        results = {
            'report_name': report_name,
            'sheets_created': [],
            'errors': []
        }

        # Genera fogli
        for sheet_config in sheets:
            sheet_name = sheet_config.get('name', 'Sheet')
            database_name = sheet_config.get('database')

            if not database_name:
                error_msg = f"Database mancante per foglio [{sheet_name}]"
                results['errors'].append(error_msg)
                continue

            try:
                # Risolvi ed esegui query
                sql = self.resolve_sql(sheet_config)
                df = self.execute_query(database_name, sql)

                # Crea foglio
                ws = wb.create_sheet(title=sheet_name[:31])

                # Aggiungi descrizione se presente
                description = sheet_config.get('description')
                has_description = bool(description)

                # if description:
                #     ws.append([description])
                #     ws.append([])  # Riga vuota
                #     desc_cell = ws['A1']
                #     desc_cell.font = Font(bold=True, italic=True)

                # Scrivi dati
                for r in dataframe_to_rows(df, index=False, header=True):
                    ws.append(r)

                # Applica formattazione semplice
                if len(df) > 0:
                    self.apply_simple_formatting(ws, df, has_description)

                self.logger.info(f"EXCEL: Foglio [{sheet_name}] creato - {len(df)} righe")
                results['sheets_created'].append({
                    'name': sheet_name,
                    'rows': len(df),
                    'columns': len(df.columns)
                })

            except Exception as e:
                error_msg = f"Errore foglio [{sheet_name}]: {str(e)}"
                self.logger.error(error_msg)
                results['errors'].append(error_msg)

        # Salva file
        if results['sheets_created']:
            filename = f"{report_name}.xlsx"
            filepath = self.output_directory / filename

            wb.save(filepath)
            self.logger.info(f"EXCEL: Report salvato in [{filepath}]")

            results['filepath'] = str(filepath)
            results['success'] = True
        else:
            results['success'] = False

        return results

    def generate_all_reports(self) -> List[Dict[str, Any]]:
        """Genera tutti i report configurati"""
        excel_reports = self.config.get('excel_reports', [])

        if not excel_reports:
            self.logger.warning("Nessun report Excel configurato")
            return []

        self.logger.info(f"EXCEL: Generazione {len(excel_reports)} report")

        results = []
        for report_config in excel_reports:
            if not report_config.get('enabled', True):
                self.logger.info(f"EXCEL: Report [{report_config.get('name')}] disabilitato")
                continue

            try:
                result = self.generate_report(report_config)
                results.append(result)
            except Exception as e:
                self.logger.error(f"EXCEL: Errore report: {e}")
                results.append({
                    'report_name': report_config.get('name', 'unknown'),
                    'success': False,
                    'errors': [str(e)]
                })

        return results


# Alias per compatibilità
ExcelReportGenerator = SimpleExcelReportGenerator