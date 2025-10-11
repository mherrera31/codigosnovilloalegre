# user_service.py (ACTUALIZADO)
import requests # NUEVO
import streamlit as st
import pandas as pd
import uuid
import db_service
from db_config import AUTH_ENDPOINT, POSTGREST_ENDPOINT, get_headers, SUPABASE_KEY # NUEVO

# --- Funciones de CRUD de Usuarios ---

def get_all_users_with_branches():
    """Obtiene todos los usuarios con sus roles y sucursales asignadas."""
    
    # Debe usar el token de la sesión del Admin para la autorización
    token = st.session_state.get('token')
    
    # Consulta: Obtener profiles con join a roles y branches
    url = f"{POSTGREST_ENDPOINT}/profiles?select=id,username,email,phone_number,roles(role_name),branches(name)"
    
    try:
        response = requests.get(url, headers=get_headers(token))
        response.raise_for_status()
        
        data = response.json()
        
        if data:
            df = pd.DataFrame(data)
            # Aplanar los datos de relación
            df['role_name'] = df['roles'].apply(lambda x: x['role_name'] if isinstance(x, dict) else None)
            df['branch_name'] = df['branches'].apply(lambda x: x['name'] if isinstance(x, dict) else 'N/A')
            return df[['id', 'username', 'email', 'role_name', 'branch_name', 'phone_number']]
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"Error al obtener usuarios: {e}")
        return pd.DataFrame()


def create_user_profile(email: str, username: str, role_id: int, branch_id: int = None, phone_number: str = None):
    """
    Crea un usuario en Supabase Auth y su perfil correspondiente.
    """
    token = st.session_state.get('token')
    if not token:
        st.error("Se requiere autenticación para esta acción.")
        return False

    try:
        # 1. Generar Contraseña Temporal y Registrar en Auth (sign_up)
        temp_password = str(uuid.uuid4())
        auth_url = f"{AUTH_ENDPOINT}/signup"
        auth_payload = {"email": email, "password": temp_password}
        
        # Las llamadas a /signup y /token deben usar la clave anónima (sin el token JWT del Admin)
        auth_response = requests.post(auth_url, headers=get_headers(), json=auth_payload)
        auth_response.raise_for_status()
        
        auth_data = auth_response.json()
        user_id = auth_data['user']['id']
        
        # 2. Crear el perfil en la tabla 'profiles' (usando el token del Admin)
        profile_url = f"{POSTGREST_ENDPOINT}/profiles"
        profile_payload = {
            'id': user_id,
            'email': email,
            'username': username,
            'role_id': role_id,
            'branch_id': branch_id
        }
        
        profile_response = requests.post(
            profile_url, 
            headers=get_headers(token), 
            json=profile_payload
        )
        profile_response.raise_for_status()

        st.success(f"Usuario **{username}** ({email}) creado exitosamente.")
        st.info(f"Contraseña temporal generada: **{temp_password}**. El usuario deberá iniciar sesión y cambiarla.")
        return True

    except requests.exceptions.HTTPError as err:
        error_data = err.response.json()
        # Manejar errores de Auth y PostgREST
        if 'email address is already taken' in str(error_data):
             st.error("Error: Este correo electrónico ya está registrado.")
        elif 'duplicate key value violates unique constraint' in str(error_data):
             st.error("Error: Ya existe un perfil con esta información.")
        else:
            st.error(f"Error al crear usuario: {error_data.get('msg', error_data.get('message', str(err)))}")
        return False
    except Exception as e:
        st.error(f"Error inesperado al crear usuario: {e}")
        return False

# --- Renderización del Módulo (Para mantener el app.py limpio) ---

def render_user_management():
    """Módulo de Streamlit para la gestión de usuarios (Solo Admin)."""
    
    # Control de acceso por rol (Doble chequeo)
    if auth.get_user_role() != 'Admin':
        st.error("Acceso denegado. Solo los administradores pueden gestionar usuarios.")
        return

    st.header("🔑 Módulo de Gestión de Usuarios")
    
    # Obtener datos maestros para los selectboxes
    roles = db_service.get_roles()
    branches = db_service.get_branches()
    
    role_options = {r['role_name']: r['id'] for r in roles}
    branch_options = {b['name']: b['id'] for b in branches}

    tab1, tab2 = st.tabs(["Crear Nuevo Usuario", "Ver Todos los Usuarios"])

    with tab1:
        st.subheader("Crear Nuevo Usuario")
        with st.form("new_user_form"):
            col1, col2 = st.columns(2)
            with col1:
                input_username = st.text_input("Nombre Completo")
                input_email = st.text_input("Correo Electrónico (será el nombre de usuario)")
            with col2:
                selected_role_name = st.selectbox("Rol", options=list(role_options.keys()))
                
                # Mostrar selector de sucursal solo para roles de Creator y Cashier
                selected_branch_name = None
                if selected_role_name in ["Creator", "Cashier"]:
                    selected_branch_name = st.selectbox("Sucursal Asignada", options=list(branch_options.keys()))
                
            submitted = st.form_submit_button("Crear y Notificar Usuario", type="primary")

            if submitted:
                role_id = role_options.get(selected_role_name)
                branch_id = branch_options.get(selected_branch_name) if selected_branch_name else None
                
                if input_email and input_username and role_id:
                    create_user_profile(input_email, input_username, role_id, branch_id)
                else:
                    st.warning("El nombre, correo y rol son obligatorios.")

    with tab2:
        st.subheader("Lista de Usuarios del Sistema")
        df_users = get_all_users_with_branches()
        if not df_users.empty:
            st.dataframe(df_users, use_container_width=True)
        else:
            st.info("No hay usuarios registrados.")
