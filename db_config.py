# db_config.py
from supabase import create_client, Client
import streamlit as st
import os

# --- TUS CREDENCIALES DE SUPABASE ---
# ADVERTENCIA: En producción, estas claves deben estar en st.secrets o variables de entorno
# para protegerlas. Las usamos aquí para la funcionalidad del demo.
SUPABASE_URL = "https://jdfumtexhluvdajbwkma.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImpkZnVtdGV4aGx1dmRhamJ3a21hIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjAyMDE0NDQsImV4cHAiOjIwNzU3Nzc0NDR9.qKrGQY3cccdY1pCrNUkMXbww2x0D23drKGLlw0oRn-k"

@st.cache_resource
def init_supabase() -> Client:
    """Inicializa y cachea el cliente de Supabase."""
    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        return supabase
    except Exception as e:
        st.error(f"Error al conectar con Supabase. Verifique las credenciales: {e}")
        st.stop()

# Cliente global
supabase = init_supabase()

def get_supabase_client() -> Client:
    """Función para obtener el cliente cacheado."""
    return supabase
