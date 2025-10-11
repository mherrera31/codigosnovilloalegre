# db_service.py
from db_config import supabase
import streamlit as st
import pandas as pd

# --- Funciones de Lectura General ---

def get_data_table(table_name: str):
    """Obtiene todos los datos de una tabla específica."""
    try:
        response = supabase.from_(table_name).select('*').execute()
        return response.data
    except Exception as e:
        st.error(f"Error al cargar datos de {table_name}: {e}")
        return []

def get_branches():
    """Obtiene la lista de sucursales."""
    return get_data_table('branches')

def get_roles():
    """Obtiene la lista de roles."""
    return get_data_table('roles')

def get_issuers():
    """Obtiene la lista de emisores."""
    return get_data_table('issuers')

def get_promos():
    """Obtiene la lista de promociones."""
    return get_data_table('promos')

# --- Funciones de Creación (Administración de Metadata) ---

def create_branch(name: str, address: str):
    """Inserta una nueva sucursal."""
    try:
        data, count = supabase.from_('branches').insert({'name': name, 'address': address}).execute()
        if count:
            st.success(f"Sucursal '{name}' creada con éxito.")
            return True
        return False
    except Exception as e:
        st.error(f"Error al crear sucursal: {e}")
        return False

def create_issuer(name: str):
    """Inserta un nuevo emisor."""
    try:
        data, count = supabase.from_('issuers').insert({'issuer_name': name}).execute()
        if count:
            st.success(f"Emisor '{name}' creado con éxito.")
            return True
        return False
    except Exception as e:
        st.error(f"Error al crear emisor: {e}")
        return False

def create_promo(type_name: str, is_percentage: bool, is_cash_value: bool, is_product: bool, value: float, description: str):
    """Inserta un nuevo tipo de promoción."""
    try:
        data, count = supabase.from_('promos').insert({
            'type_name': type_name, 
            'is_percentage': is_percentage, 
            'is_cash_value': is_cash_value, 
            'is_product': is_product, 
            'value': value, 
            'description': description
        }).execute()
        if count:
            st.success(f"Promoción '{type_name}' creada con éxito.")
            return True
        return False
    except Exception as e:
        st.error(f"Error al crear promoción: {e}")
        return False
