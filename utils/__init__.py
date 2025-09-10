# Copyright 2025 SILICONDEV SPA
# Filename: utils/__init__.py
# Description: Utils package initialization

from .decorators import admin_required, active_user_required, verified_user_required
from .template_helpers import register_template_filters, register_context_processors
from .db_helper import (
    execute_query, execute_select, execute_select_one, execute_insert,
    execute_update, execute_delete, execute_script, get_table_info,
    get_table_count, table_exists, get_database_info,
    get_all_users, get_user_by_email, get_all_properties,
    get_properties_by_agent, get_all_auctions, get_active_auctions,
    get_user_bids, DatabaseHelper
)

__all__ = [
    'admin_required',
    'active_user_required',
    'verified_user_required',
    'register_template_filters',
    'register_context_processors',
    'execute_query',
    'execute_select',
    'execute_select_one',
    'execute_insert',
    'execute_update',
    'execute_delete',
    'execute_script',
    'get_table_info',
    'get_table_count',
    'table_exists',
    'get_database_info',
    'get_all_users',
    'get_user_by_email',
    'get_all_properties',
    'get_properties_by_agent',
    'get_all_auctions',
    'get_active_auctions',
    'get_user_bids',
    'DatabaseHelper'
]