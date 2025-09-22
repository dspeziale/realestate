# core/services/cache_manager.py
"""
Cache Manager Service - Gestione centralizzata delle cache
Coordina pulizia automatica e ottimizzazioni per tutti i servizi cache
"""

import threading
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger('CacheManager')


@dataclass
class CacheServiceInfo:
    """Informazioni su un servizio cache registrato"""
    name: str
    service_instance: Any
    cleanup_method: str
    optimize_method: str = None
    stats_method: str = None
    last_cleanup: Optional[datetime] = None
    last_optimization: Optional[datetime] = None


class CacheManager:
    """Manager centralizzato per tutti i servizi cache"""

    def __init__(self, cleanup_interval_hours: int = 24):
        self.cleanup_interval_hours = cleanup_interval_hours
        self.registered_services: Dict[str, CacheServiceInfo] = {}
        self.cleanup_thread = None
        self.running = False
        self._lock = threading.Lock()

    def register_service(self, name: str, service_instance: Any,
                         cleanup_method: str = 'cleanup_cache',
                         optimize_method: str = None,
                         stats_method: str = 'get_statistics'):
        """Registra un servizio cache per gestione automatica"""
        with self._lock:
            self.registered_services[name] = CacheServiceInfo(
                name=name,
                service_instance=service_instance,
                cleanup_method=cleanup_method,
                optimize_method=optimize_method,
                stats_method=stats_method
            )
            logger.info(f"🔧 Servizio cache registrato: {name}")

    def unregister_service(self, name: str):
        """Rimuove un servizio cache dalla gestione"""
        with self._lock:
            if name in self.registered_services:
                del self.registered_services[name]
                logger.info(f"🗑️ Servizio cache rimosso: {name}")

    def start_automatic_cleanup(self):
        """Avvia thread per pulizia automatica"""
        if self.running:
            return

        self.running = True
        self.cleanup_thread = threading.Thread(
            target=self._cleanup_loop,
            daemon=True,
            name='CacheManagerCleanup'
        )
        self.cleanup_thread.start()
        logger.info(f"🔄 Cache manager avviato (intervallo: {self.cleanup_interval_hours}h)")

    def stop_automatic_cleanup(self):
        """Ferma thread di pulizia automatica"""
        self.running = False
        if self.cleanup_thread and self.cleanup_thread.is_alive():
            self.cleanup_thread.join(timeout=5)
        logger.info("⏹️ Cache manager fermato")

    def _cleanup_loop(self):
        """Loop principale per pulizia automatica"""
        while self.running:
            try:
                self.cleanup_all_services()

                # Ottimizzazione settimanale
                if datetime.now().weekday() == 0:  # Lunedì
                    self.optimize_all_services()

            except Exception as e:
                logger.error(f"❌ Errore nel cleanup automatico: {e}")

            # Attendi prossimo ciclo
            for _ in range(self.cleanup_interval_hours * 3600):  # Secondi
                if not self.running:
                    break
                time.sleep(1)

    def cleanup_all_services(self) -> Dict[str, Any]:
        """Esegue pulizia su tutti i servizi registrati"""
        results = {}

        with self._lock:
            services_copy = dict(self.registered_services)

        logger.info("🧹 Avvio pulizia cache per tutti i servizi...")

        for name, service_info in services_copy.items():
            try:
                cleanup_method = getattr(service_info.service_instance, service_info.cleanup_method)
                deleted_count = cleanup_method()

                service_info.last_cleanup = datetime.now()
                results[name] = {
                    'success': True,
                    'deleted_entries': deleted_count,
                    'timestamp': service_info.last_cleanup.isoformat()
                }

                logger.info(f"✅ {name}: {deleted_count} entry rimosse")

            except Exception as e:
                logger.error(f"❌ Errore pulizia {name}: {e}")
                results[name] = {
                    'success': False,
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                }

        total_deleted = sum(r.get('deleted_entries', 0) for r in results.values() if r.get('success'))
        logger.info(f"🧹 Pulizia completata: {total_deleted} entry totali rimosse")

        return results

    def optimize_all_services(self) -> Dict[str, Any]:
        """Esegue ottimizzazione su tutti i servizi che la supportano"""
        results = {}

        with self._lock:
            services_copy = dict(self.registered_services)

        logger.info("⚡ Avvio ottimizzazione cache per tutti i servizi...")

        for name, service_info in services_copy.items():
            if not service_info.optimize_method:
                continue

            try:
                optimize_method = getattr(service_info.service_instance, service_info.optimize_method)
                optimize_method()

                service_info.last_optimization = datetime.now()
                results[name] = {
                    'success': True,
                    'timestamp': service_info.last_optimization.isoformat()
                }

                logger.info(f"✅ {name}: ottimizzazione completata")

            except Exception as e:
                logger.error(f"❌ Errore ottimizzazione {name}: {e}")
                results[name] = {
                    'success': False,
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                }

        return results

    def get_all_statistics(self) -> Dict[str, Any]:
        """Raccoglie statistiche da tutti i servizi registrati"""
        stats = {}

        with self._lock:
            services_copy = dict(self.registered_services)

        for name, service_info in services_copy.items():
            if not service_info.stats_method:
                continue

            try:
                stats_method = getattr(service_info.service_instance, service_info.stats_method)
                service_stats = stats_method()

                stats[name] = {
                    'statistics': service_stats,
                    'last_cleanup': service_info.last_cleanup.isoformat() if service_info.last_cleanup else None,
                    'last_optimization': service_info.last_optimization.isoformat() if service_info.last_optimization else None,
                    'cleanup_method': service_info.cleanup_method,
                    'optimize_method': service_info.optimize_method
                }

            except Exception as e:
                logger.error(f"❌ Errore raccolta statistiche {name}: {e}")
                stats[name] = {
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                }

        return {
            'services': stats,
            'manager_info': {
                'cleanup_interval_hours': self.cleanup_interval_hours,
                'running': self.running,
                'registered_services_count': len(self.registered_services),
                'timestamp': datetime.now().isoformat()
            }
        }

    def cleanup_service(self, service_name: str) -> Dict[str, Any]:
        """Esegue pulizia su un servizio specifico"""
        with self._lock:
            if service_name not in self.registered_services:
                return {
                    'success': False,
                    'error': f'Servizio {service_name} non registrato'
                }

            service_info = self.registered_services[service_name]

        try:
            cleanup_method = getattr(service_info.service_instance, service_info.cleanup_method)
            deleted_count = cleanup_method()

            service_info.last_cleanup = datetime.now()

            logger.info(f"✅ Pulizia {service_name}: {deleted_count} entry rimosse")

            return {
                'success': True,
                'service': service_name,
                'deleted_entries': deleted_count,
                'timestamp': service_info.last_cleanup.isoformat()
            }

        except Exception as e:
            logger.error(f"❌ Errore pulizia {service_name}: {e}")
            return {
                'success': False,
                'service': service_name,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }

    def optimize_service(self, service_name: str) -> Dict[str, Any]:
        """Esegue ottimizzazione su un servizio specifico"""
        with self._lock:
            if service_name not in self.registered_services:
                return {
                    'success': False,
                    'error': f'Servizio {service_name} non registrato'
                }

            service_info = self.registered_services[service_name]

        if not service_info.optimize_method:
            return {
                'success': False,
                'error': f'Servizio {service_name} non supporta ottimizzazione'
            }

        try:
            optimize_method = getattr(service_info.service_instance, service_info.optimize_method)
            optimize_method()

            service_info.last_optimization = datetime.now()

            logger.info(f"✅ Ottimizzazione {service_name} completata")

            return {
                'success': True,
                'service': service_name,
                'timestamp': service_info.last_optimization.isoformat()
            }

        except Exception as e:
            logger.error(f"❌ Errore ottimizzazione {service_name}: {e}")
            return {
                'success': False,
                'service': service_name,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }

    def get_service_info(self) -> List[Dict[str, Any]]:
        """Ottieni informazioni sui servizi registrati"""
        with self._lock:
            services_info = []

            for name, service_info in self.registered_services.items():
                services_info.append({
                    'name': name,
                    'cleanup_method': service_info.cleanup_method,
                    'optimize_method': service_info.optimize_method,
                    'stats_method': service_info.stats_method,
                    'last_cleanup': service_info.last_cleanup.isoformat() if service_info.last_cleanup else None,
                    'last_optimization': service_info.last_optimization.isoformat() if service_info.last_optimization else None
                })

            return services_info

    def __del__(self):
        """Cleanup quando il manager viene distrutto"""
        self.stop_automatic_cleanup()


# Singleton instance per uso globale
cache_manager = CacheManager()