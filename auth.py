# auth.py (ACTUALIZADO para usar requests)
import requests
import streamlit as st
from db_config import AUTH_ENDPOINT, POSTGREST_ENDPOINT, SUPABASE_KEY, get_headers

def sign_in(email, password):
    """
    Intenta iniciar sesión usando Supabase Auth a través de llamadas requests.
    """
    url = f"{AUTH_ENDPOINT}/token?grant_type=password"
    payload = {"email": email, "password": password}
    
    try:
        response = requests.post(url, headers=get_headers(), json=payload)
        response.raise_for_status() # Lanza un error para códigos 4xx/5xx

        auth_data = response.json()
        token = auth_data['access_token']
        user_id = auth_data['user']['id']
        
        # 1. Guardar token y datos básicos en la sesión
        st.session_state['logged_in'] = True
        st.session_state['token'] = token
        st.session_state['user_id'] = user_id
        st.session_state['user'] = auth_data['user']
        
        # 2. Consultar el perfil (rol y sucursal) usando el token
        profile_response = requests.get(
            f"{POSTGREST_ENDPOINT}/profiles?id=eq.{user_id}&select=*,roles(role_name)", 
            headers=get_headers(token)
        )
        profile_response.raise_for_status()

        profile_data = profile_response.json()
        
        if profile_data:
            profile = profile_data[0]
            
            # 3. Guardar estado completo en la sesión
            st.session_state['user_role'] = profile['roles']['role_name']
            st.session_state['branch_id'] = profile['branch_id']
            st.session_state['username'] = profile['username']
            
            st.success(f"Bienvenido, {profile['username']} ({profile['roles']['role_name']}).")
            st.rerun() 
        else:
            st.error("Su cuenta no tiene un perfil asignado. Contacte al administrador.")
            sign_out() # Forzar logout
            
    except requests.exceptions.HTTPError as err:
        if err.response.status_code == 400:
             st.error("Credenciales inválidas. Revise su email y contraseña.")
        else:
            st.error(f"Error de conexión o autenticación: {err}")
    except Exception as e:
        st.error(f"Error inesperado durante el login: {e}")


def sign_out():
    """Cierra la sesión limpiando el estado (no requiere llamada a la API en este modelo)."""
    st.session_state.clear()
    st.session_state['logged_in'] = False
    st.rerun()

# (El resto de las funciones de auth.py quedan igual)
# get_current_user, is_authenticated, get_user_role, login_ui
