# user_service.py (VERSIÓN COMPLETA FINAL - Llama Edge Functions)
import requests
import streamlit as st
import pandas as pd
import uuid
import db_service # Necesario para obtener listas de roles/sucursales
import json
# Importar la URL base de tu proyecto Supabase
from db_config import SUPABASE_URL, POSTGREST_ENDPOINT, get_headers
import auth # Necesario para obtener el token del admin logueado y rol

# --- Funciones de Lectura (Sin cambios) ---

def get_all_users_with_details():
    """Obtiene todos los usuarios con sus roles y sucursales asignadas usando PostgREST."""
    token = st.session_state.get('token')
    url = f"{POSTGREST_ENDPOINT}/profiles?select=id,username,email,phone_number,role_id,branch_id,roles(role_name),branches(name)"
    try:
        response = requests.get(url, headers=get_headers(token))
        response.raise_for_status()
        data = response.json()
        if not data: return pd.DataFrame()
        df = pd.DataFrame(data)
        df['role_name'] = df['roles'].apply(lambda x: x.get('role_name') if isinstance(x, dict) else None)
        df['branch_name'] = df['branches'].apply(lambda x: x.get('name') if isinstance(x, dict) else 'N/A')
        return df[['id', 'username', 'email', 'role_name', 'branch_name', 'phone_number', 'role_id', 'branch_id']]
    except Exception as e:
        st.error(f"Error al obtener usuarios: {e}")
        return pd.DataFrame()


# --- Función de Creación (Llama a Edge Function 'create-user') ---

def create_user_profile(email: str, username: str, password: str, role_id: int, branch_id: int = None, phone_number: str = None):
    """
    Llama a la Edge Function 'create-user' para crear Auth user y profile.
    """
    admin_token = st.session_state.get('token') # Token del usuario Admin logueado en Streamlit
    if not admin_token:
        st.error("Se requiere autenticación de administrador.")
        return False

    # URL de tu Edge Function (ajusta si es necesario)
    function_url = f"{SUPABASE_URL}/functions/v1/create-user"

    payload = {
        "email": email,
        "password": password,
        "username": username,
        "role_id": role_id,
        "branch_id": branch_id,
        "phone_number": phone_number if phone_number else None
    }

    headers = {
        'Authorization': f'Bearer {admin_token}', # Autentica la llamada a la función
        'Content-Type': 'application/json'
    }

    try:
        response = requests.post(function_url, headers=headers, json=payload)
        response.raise_for_status() # Lanza error para 4xx/5xx

        response_data = response.json()
        st.success(f"Usuario **{username}** ({email}) creado y confirmado exitosamente. ID: {response_data.get('userId', 'N/A')}")
        return True

    except requests.exceptions.HTTPError as err:
        try:
            error_data = err.response.json()
            error_msg = error_data.get('error', str(err)) # Edge function devuelve 'error'
            st.error(f"Error al crear usuario ({err.response.status_code}): {error_msg}")
        except Exception:
            st.error(f"Error HTTP {err.response.status_code} al llamar a la función: {err.response.text}")
        return False
    except Exception as e:
        st.error(f"Error inesperado llamando a la función 'create-user': {e}")
        return False

# --- Función de Actualización (Sigue usando API REST para perfiles) ---

def update_user_profile(user_id: str, username: str, role_id: int, branch_id: int = None, phone_number: str = None):
    """Actualiza los datos del perfil de un usuario en la tabla 'profiles'."""
    payload = {
        'username': username,
        'role_id': role_id,
        'branch_id': branch_id,
        'phone_number': phone_number if phone_number else None
    }
    if db_service.update_entry('profiles', user_id, payload, id_column='id'):
        st.success(f"Perfil del usuario {username} actualizado.")
        return True
    return False # Error manejado en update_entry

# --- Función de Eliminación (Llama a Edge Function 'delete-user') ---

def delete_user_auth_and_profile(user_id: str):
    """
    Llama a la Edge Function 'delete-user' para eliminar Auth user y profile.
    """
    admin_token = st.session_state.get('token')
    if not admin_token:
        st.error("Se requiere autenticación de administrador.")
        return False

    function_url = f"{SUPABASE_URL}/functions/v1/delete-user"

    payload = { "user_id": user_id }
    headers = {
        'Authorization': f'Bearer {admin_token}',
        'Content-Type': 'application/json'
    }

    try:
        response = requests.post(function_url, headers=headers, json=payload) # Usar POST según diseño de función
        response.raise_for_status()

        response_data = response.json()
        st.success(f"Proceso de eliminación para usuario ID {user_id} completado.")
        st.info(f"Mensaje de la función: {response_data.get('message', 'Sin mensaje adicional')}")
        # Puede que necesites revisar los logs de Supabase si hubo errores parciales (ej: solo se borró Auth)
        return True

    except requests.exceptions.HTTPError as err:
        try:
            error_data = err.response.json()
            error_msg = error_data.get('error', str(err))
            st.error(f"Error al eliminar usuario ({err.response.status_code}): {error_msg}")
        except Exception:
            st.error(f"Error HTTP {err.response.status_code} al llamar a la función: {err.response.text}")
        return False
    except Exception as e:
        st.error(f"Error inesperado llamando a la función 'delete-user': {e}")
        return False


# --- Renderización del Módulo de Streamlit (Llama a delete_user_auth_and_profile) ---

def render_user_management():
    """Módulo de Streamlit para la gestión de usuarios (Solo Admin)."""

    if auth.get_user_role() != 'Admin':
        st.error("Acceso denegado. Solo administradores pueden gestionar usuarios.")
        return

    st.header("🔑 Gestión de Usuarios")

    # Obtener datos maestros
    roles = db_service.get_roles()
    branches = db_service.get_branches()
    role_options = {r['role_name']: r['id'] for r in roles if r.get('role_name')}
    branch_options = {b['name']: b['id'] for b in branches if b.get('name')}
    branch_options_with_none = {"Ninguna / N/A": None}
    branch_options_with_none.update(branch_options)

    tab_create, tab_view_edit = st.tabs(["Crear Nuevo Usuario", "Ver / Editar / Eliminar Usuarios"])

    # --- TAB CREAR USUARIO ---
    with tab_create:
        st.subheader("Crear Nuevo Usuario (Confirmado Directamente)")
        if 'create_user_form_key_counter' not in st.session_state: st.session_state['create_user_form_key_counter'] = 0
        create_form_key = f"new_user_form_{st.session_state['create_user_form_key_counter']}"

        with st.form(create_form_key, clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                input_username = st.text_input("Nombre Completo")
                input_email = st.text_input("Correo Electrónico (Login)")
                input_password = st.text_input("Contraseña Inicial (Mín. 6 caracteres)", type="password")
                input_phone = st.text_input("Teléfono (Opcional)")
            with col2:
                if not role_options: st.error("Error: No se cargaron roles."); role_names_list_create = []
                else: role_names_list_create = list(role_options.keys())
                selected_role_name = st.selectbox("Rol", options=role_names_list_create)
                selected_branch_name = None
                if selected_role_name in ["Creator", "Cashier"]:
                    if not branch_options: st.warning("No hay sucursales creadas.")
                    else: selected_branch_name = st.selectbox("Sucursal Asignada", options=list(branch_options.keys()))

            submitted_create = st.form_submit_button("Crear Usuario", type="primary")

            if submitted_create:
                role_id = role_options.get(selected_role_name)
                branch_id = branch_options.get(selected_branch_name) if selected_branch_name else None
                phone_number = input_phone if input_phone else None
                error = False # Validation flag
                if not input_email or '@' not in input_email: st.error("Ingrese correo válido."); error = True
                if not input_username: st.error("Ingrese Nombre."); error = True
                if not role_id: st.error("Seleccione Rol."); error = True
                if not input_password or len(input_password) < 6: st.error("Contraseña (mín. 6 caracteres)."); error = True
                if selected_role_name in ["Creator", "Cashier"] and not branch_id and branch_options: st.error(f"Rol '{selected_role_name}' requiere Sucursal."); error = True

                if not error:
                    if create_user_profile(input_email, input_username, input_password, role_id, branch_id, phone_number):
                        st.session_state['create_user_form_key_counter'] += 1
                        st.rerun()

    # --- TAB VER / EDITAR / ELIMINAR ---
    with tab_view_edit:
        st.subheader("Usuarios del Sistema")
        df_users = get_all_users_with_details()

        if not df_users.empty:
            st.dataframe(
                df_users[['username', 'email', 'role_name', 'branch_name', 'phone_number']].rename(columns={'username': 'Nombre', 'email': 'Correo', 'role_name':'Rol', 'branch_name':'Sucursal', 'phone_number':'Teléfono'}),
                use_container_width=True, hide_index=True
            )
            st.divider()
            st.markdown("#### Editar / Eliminar Usuario")

            for index, user_row in df_users.iterrows():
                user_id = user_row['id']
                with st.expander(f"{user_row['username']} ({user_row['email']})", key=f"exp_user_{user_id}"):
                    edit_form_key = f"edit_user_form_{user_id}"
                    with st.form(edit_form_key):
                        st.caption(f"**ID:** `{user_id}`")
                        edit_username = st.text_input("Nombre Completo", value=user_row['username'], key=f"uname_{user_id}")
                        edit_phone = st.text_input("Teléfono", value=user_row.get('phone_number') or "", key=f"phone_{user_id}")

                        # Role Selection
                        current_role_index = 0; role_names_list_edit = list(role_options.keys())
                        if user_row['role_name'] in role_names_list_edit: current_role_index = role_names_list_edit.index(user_row['role_name'])
                        edit_role_name = st.selectbox("Rol", options=role_names_list_edit, index=current_role_index, key=f"role_{user_id}")

                        # Branch Selection
                        edit_branch_name = None; current_branch_id = user_row.get('branch_id'); branch_names_list_edit = list(branch_options_with_none.keys()); current_branch_index = 0
                        for i, name in enumerate(branch_names_list_edit):
                            if branch_options_with_none[name] == current_branch_id: current_branch_index = i; break
                        if edit_role_name in ["Creator", "Cashier"]:
                            edit_branch_display_name = st.selectbox("Sucursal Asignada", options=branch_names_list_edit, index=current_branch_index, key=f"branch_{user_id}")
                            edit_branch_id = branch_options_with_none[edit_branch_display_name]
                        else: edit_branch_id = None; st.caption("Rol no requiere sucursal.")

                        # Action Buttons
                        cols_buttons = st.columns(2)
                        with cols_buttons[0]: submitted_edit = st.form_submit_button("Guardar Cambios", type="primary", key=f"save_{user_id}")
                        with cols_buttons[1]: submitted_delete = st.form_submit_button("Eliminar Usuario (Auth y Perfil)", key=f"delete_{user_id}") # Changed label

                        if submitted_edit:
                            edit_role_id = role_options.get(edit_role_name)
                            phone_to_save = edit_phone if edit_phone else None
                            # Validation before update
                            if not edit_username: st.error("Nombre vacío.")
                            elif not edit_role_id: st.error("Rol inválido.")
                            elif edit_role_name in ["Creator", "Cashier"] and edit_branch_id is None and branch_options: st.error("Rol requiere sucursal.")
                            else:
                                if update_user_profile(user_id, edit_username, edit_role_id, edit_branch_id, phone_to_save): st.rerun()

                        if submitted_delete:
                            st.warning("¡Esta acción eliminará la cuenta de Autenticación y el Perfil del usuario!")
                            confirm_delete_key = f"confirm_del_user_{user_id}"
                            if confirm_delete_key not in st.session_state: st.session_state[confirm_delete_key] = False
                            st.session_state[confirm_delete_key] = st.checkbox("Confirmar eliminación COMPLETA del usuario", key=f"cb_{confirm_delete_key}", value=st.session_state[confirm_delete_key])
                            if st.session_state[confirm_delete_key]:
                                # --- LLAMAR A LA NUEVA FUNCIÓN DE ELIMINACIÓN ---
                                if delete_user_auth_and_profile(user_id):
                                    st.session_state[confirm_delete_key] = False # Reset state
                                    st.rerun() # Refresh list
        else:
            st.info("No hay usuarios registrados o no se pudieron cargar.")
