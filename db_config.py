# db_config.py (USANDO REQUESTS para evitar errores de dependencia)
import streamlit as st
import os

# --- TUS CREDENCIALES DE SUPABASE ---
# NOTA: Los caracteres '|' en el Project ID no son comunes. 
# Si tu URL es https://jdfumtexhluvdajbwkma.supabase.co, el Project REF es 'jdfumtexhluvdajbwkma'.
SUPABASE_REF = "jdfumtexhluvdajbwkma"
SUPABASE_URL = f"https://{SUPABASE_REF}.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImpkZnVtdGV4aGx1dmRhamJ3a21hIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjAyMDE0NDQsImV4cHAiOjIwNzU3Nzc0NDR9.qKrGQY3cccdY1pCrNUkMXbww2x0D23drKGLlw0oRn-k"

# Endpoints de la API REST
AUTH_ENDPOINT = f"{SUPABASE_URL}/auth/v1"
POSTGREST_ENDPOINT = f"{SUPABASE_URL}/rest/v1"

@st.cache_data
def get_headers(token: str = None):
    """Genera las cabeceras base para las peticiones HTTP."""
    headers = {
        "Content-Type": "application/json",
        "apikey": SUPABASE_KEY,
        "Accept": "application/json"
    }
    # Si hay un token de usuario logueado, se incluye para peticiones autenticadas
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers

# Nota: Ya no necesitamos init_supabase() ni get_supabase_client()
# ya que usamos requests directamente en auth.py y db_service.py.
