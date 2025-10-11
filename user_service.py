# user_service.py
from db_config import get_supabase_client
import streamlit as st
import pandas as pd
import uuid
import db_service

supabase = get_supabase_client()

# --- Funciones de CRUD de Usuarios ---

def get_all_users_with_branches():
    """Obtiene todos los usuarios con sus roles y sucursales asignadas."""
    try:
        # Obtenemos profile, role_name, y branch_name
        response = supabase.from_('profiles').select('*, roles(role_name), branches(name)').execute()
        
        # Procesar para aplanar el diccionario
        data = response.data
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
    Crea un usuario en Supabase Auth y su perfil correspondiente en la tabla 'profiles'.
    """
    try:
        # Generar una contraseña temporal (debe ser segura)
        temp_password = str(uuid.uuid4())
        
        # 1. Registrar usuario en Auth
        auth_response = supabase.auth.sign_up({
            "email": email,
            "password": temp_password,
        })
        
        if not auth_response.user:
            raise Exception("Fallo en la creación de usuario en Auth.")
            
        user_id = auth_response.user.id
        
        # 2. Crear el perfil en la tabla 'profiles'
        data, count = supabase.from_('profiles').insert([
            {
                'id': user_id,
                'email': email,
                'username': username,
                'role_id': role_id,
                'branch_id': branch_id
            }
        ]).execute()
        
        if count == 0:
            # En un sistema real, aquí llamaríamos a una función de Admin para borrar el usuario de Auth
            # si falla la inserción del perfil.
            st.error("Error al guardar el perfil. El usuario fue creado, pero está incompleto.")
            return False

        st.success(f"Usuario **{username}** ({email}) creado exitosamente.")
        st.info(f"Contraseña temporal generada: **{temp_password}**. El usuario deberá iniciar sesión y cambiarla.")
        return True

    except Exception as e:
        error_message = str(e)
        if "Email already registered" in error_message:
             st.error("Error: Este correo electrónico ya está registrado.")
        else:
            st.error(f"Error al crear usuario: {error_message}")
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
