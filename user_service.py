# user_service.py (VERSIÓN COMPLETA FINAL - Con Edit/Delete)
import requests
import streamlit as st
import pandas as pd
import uuid
import db_service # Necesario para obtener listas de roles/sucursales
import json
from db_config import AUTH_ENDPOINT, POSTGREST_ENDPOINT, get_headers, SUPABASE_KEY
import auth # Necesario para obtener el token del admin logueado y rol

# --- Funciones de Lectura y Conversión ---

def get_all_users_with_details():
    """Obtiene todos los usuarios con sus roles y sucursales asignadas usando PostgREST."""
    token = st.session_state.get('token')
    # Consulta: Obtener profile, role_name, y branch_name a través de JOINs
    # Include role_id and branch_id for editing
    url = f"{POSTGREST_ENDPOINT}/profiles?select=id,username,email,phone_number,role_id,branch_id,roles(role_name),branches(name)"

    try:
        response = requests.get(url, headers=get_headers(token))
        response.raise_for_status()
        data = response.json()
        if not data: return pd.DataFrame()

        df = pd.DataFrame(data)
        # Aplanar los datos de relación
        df['role_name'] = df['roles'].apply(lambda x: x.get('role_name') if isinstance(x, dict) else None)
        df['branch_name'] = df['branches'].apply(lambda x: x.get('name') if isinstance(x, dict) else 'N/A')
        # Return all necessary columns including IDs for editing
        return df[['id', 'username', 'email', 'role_name', 'branch_name', 'phone_number', 'role_id', 'branch_id']]

    except Exception as e:
        st.error(f"Error al obtener usuarios: {e}")
        return pd.DataFrame()


# --- Funciones de Creación de Usuarios ---

def create_user_profile(email: str, username: str, password: str, role_id: int, branch_id: int = None, phone_number: str = None):
    """
    Crea un usuario en Supabase Auth y su perfil correspondiente.
    """
    token = st.session_state.get('token')
    if not token: st.error("Se requiere autenticación."); return False

    try:
        # 1. Registrar usuario en Auth
        auth_url = f"{AUTH_ENDPOINT}/signup"
        auth_payload = {"email": email, "password": password}
        auth_response = requests.post(auth_url, headers=get_headers(), json=auth_payload) # Use anon key
        auth_response.raise_for_status()
        auth_data = auth_response.json(); user_data = auth_data.get('user', auth_data); user_id = user_data.get('id')
        if not user_id: raise Exception("No se obtuvo ID del usuario creado en Auth.")

        # 2. Crear el perfil en 'profiles'
        profile_url = f"{POSTGREST_ENDPOINT}/profiles"
        profile_payload = {
            'id': user_id, 'email': email, 'username': username,
            'role_id': role_id, 'branch_id': branch_id,
            'phone_number': phone_number # Include phone number if provided
        }
        profile_response = requests.post(profile_url, headers=get_headers(token), data=json.dumps(profile_payload)) # Use admin token
        profile_response.raise_for_status()

        st.success(f"Usuario **{username}** ({email}) creado.")
        return True

    except requests.exceptions.HTTPError as err:
        try: error_data = err.response.json(); error_msg = error_data.get('msg', error_data.get('message', str(err)))
        except: error_msg = str(err.response.text)
        if 'email address is already taken' in error_msg: st.error("Error: Correo ya registrado.")
        elif 'Password should be at least 6 characters' in error_msg: st.error("Error: Contraseña debe tener al menos 6 caracteres.")
        else: st.error(f"Error al crear usuario: {error_msg}")
        return False
    except Exception as e: st.error(f"Error inesperado al crear usuario: {e}"); return False

# --- ¡NUEVO! Funciones de Edición y Eliminación ---

def update_user_profile(user_id: str, username: str, role_id: int, branch_id: int = None, phone_number: str = None):
    """Actualiza los datos del perfil de un usuario en la tabla 'profiles'."""
    payload = {
        'username': username,
        'role_id': role_id,
        'branch_id': branch_id,
        'phone_number': phone_number
        # Email cannot be updated here easily, requires Auth endpoint
    }
    # Use the generic update_entry from db_service
    if db_service.update_entry('profiles', user_id, payload, id_column='id'):
        st.success(f"Perfil del usuario {username} actualizado.")
        return True
    else:
        # Error message is handled by update_entry
        return False

def delete_user_profile(user_id: str):
    """Elimina SÓLO el perfil de usuario de la tabla 'profiles'. Auth user remains."""
    # Use the generic delete_entry from db_service
    if db_service.delete_entry('profiles', user_id, id_column='id'):
        st.success(f"Perfil del usuario ID {user_id} eliminado.")
        st.warning("¡Importante! La cuenta de autenticación (Auth) de este usuario aún existe. Debe eliminarse manualmente desde el panel de Supabase para una eliminación completa.")
        return True
    else:
        # Error message is handled by delete_entry
        return False


# --- Renderización del Módulo de Streamlit (ACTUALIZADO CON EDIT/DELETE) ---

def render_user_management():
    """Módulo de Streamlit para la gestión de usuarios (Solo Admin)."""

    if auth.get_user_role() != 'Admin':
        st.error("Acceso denegado. Solo administradores pueden gestionar usuarios.")
        return

    st.header("🔑 Gestión de Usuarios")

    # Obtener datos maestros
    roles = db_service.get_roles()
    branches = db_service.get_branches()
    role_options = {r['role_name']: r['id'] for r in roles}
    branch_options = {b['name']: b['id'] for b in branches}
    # Add None option for branches if needed
    branch_options_with_none = {"Ninguna / N/A": None}
    branch_options_with_none.update(branch_options)


    tab_create, tab_view_edit = st.tabs(["Crear Nuevo Usuario", "Ver / Editar / Eliminar Usuarios"])

    # --- TAB CREAR USUARIO ---
    with tab_create:
        st.subheader("Crear Nuevo Usuario")
        with st.form("new_user_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                input_username = st.text_input("Nombre Completo")
                input_email = st.text_input("Correo Electrónico (Login)")
                input_password = st.text_input("Contraseña Inicial (Mín. 6 caracteres)", type="password")
                input_phone = st.text_input("Teléfono (Opcional)")
            with col2:
                # Ensure role_options is not empty
                if not role_options:
                    st.error("Error: No se pudieron cargar los roles. Vaya a Configuración.")
                    st.stop() # Stop execution in this form
                selected_role_name = st.selectbox("Rol", options=list(role_options.keys()))

                selected_branch_name = None
                # Allow branch selection only if roles requiring it are selected
                if selected_role_name in ["Creator", "Cashier"]: # Adjust role names if different
                    if not branch_options:
                        st.warning("No hay sucursales creadas. Vaya a Configuración.")
                    else:
                        selected_branch_name = st.selectbox("Sucursal Asignada", options=list(branch_options.keys()))

            submitted_create = st.form_submit_button("Crear Usuario", type="primary")

            if submitted_create:
                role_id = role_options.get(selected_role_name)
                branch_id = branch_options.get(selected_branch_name) if selected_branch_name else None
                phone_number = input_phone if input_phone else None

                # Validation
                error = False
                if not input_email or '@' not in input_email: st.error("Ingrese un correo válido."); error = True
                if not input_username: st.error("Ingrese Nombre Completo."); error = True
                if not role_id: st.error("Seleccione un Rol válido."); error = True
                if not input_password or len(input_password) < 6: st.error("Ingrese Contraseña (mín. 6 caracteres)."); error = True
                # Branch validation depends on role
                if selected_role_name in ["Creator", "Cashier"] and not branch_id and branch_options:
                     st.error(f"Rol '{selected_role_name}' requiere una Sucursal Asignada."); error = True

                if not error:
                    if create_user_profile(input_email, input_username, input_password, role_id, branch_id, phone_number):
                        st.rerun() # Refresh list on success

    # --- TAB VER / EDITAR / ELIMINAR ---
    with tab_view_edit:
        st.subheader("Usuarios del Sistema")
        df_users = get_all_users_with_details()

        if not df_users.empty:
            # Display basic list first
            st.dataframe(df_users[['username', 'email', 'role_name', 'branch_name', 'phone_number']], use_container_width=True, hide_index=True)
            st.divider()
            st.markdown("#### Editar / Eliminar Usuario")

            # Create an expander for each user
            for index, user_row in df_users.iterrows():
                user_id = user_row['id']
                with st.expander(f"{user_row['username']} ({user_row['email']})"):
                    # Use unique form key for each user
                    edit_form_key = f"edit_user_form_{user_id}"
                    with st.form(edit_form_key):
                        st.write(f"**ID:** {user_id}") # Display ID for reference
                        edit_username = st.text_input("Nombre Completo", value=user_row['username'], key=f"uname_{user_id}")
                        edit_phone = st.text_input("Teléfono", value=user_row.get('phone_number') or "", key=f"phone_{user_id}")

                        # Role Selection
                        current_role_index = 0 # Default index
                        role_names_list = list(role_options.keys())
                        if user_row['role_name'] in role_names_list:
                            current_role_index = role_names_list.index(user_row['role_name'])
                        edit_role_name = st.selectbox("Rol", options=role_names_list, index=current_role_index, key=f"role_{user_id}")

                        # Branch Selection (conditional)
                        edit_branch_name = None
                        current_branch_id = user_row.get('branch_id')
                        branch_names_list = list(branch_options_with_none.keys()) # Include "Ninguna"
                        current_branch_index = 0 # Default to "Ninguna"
                        # Find the index corresponding to the current branch_id
                        for i, name in enumerate(branch_names_list):
                            if branch_options_with_none[name] == current_branch_id:
                                current_branch_index = i
                                break

                        if edit_role_name in ["Creator", "Cashier"]: # Show branch only for relevant roles
                            edit_branch_display_name = st.selectbox(
                                "Sucursal Asignada",
                                options=branch_names_list,
                                index=current_branch_index,
                                key=f"branch_{user_id}"
                            )
                            # Get the actual ID based on the selected display name
                            edit_branch_id = branch_options_with_none[edit_branch_display_name]
                        else:
                            edit_branch_id = None # Set branch to None if role doesn't require it
                            st.caption("Rol no requiere sucursal.")


                        # Action Buttons
                        cols_buttons = st.columns(2)
                        with cols_buttons[0]:
                            submitted_edit = st.form_submit_button("Guardar Cambios", type="primary", key=f"save_{user_id}")
                        with cols_buttons[1]:
                            submitted_delete = st.form_submit_button("Eliminar Usuario", key=f"delete_{user_id}")

                        if submitted_edit:
                            edit_role_id = role_options.get(edit_role_name)
                            phone_number_to_save = edit_phone if edit_phone else None
                            # Basic validation
                            if not edit_username: st.error("Nombre no puede estar vacío.")
                            elif not edit_role_id: st.error("Rol inválido.")
                            elif edit_role_name in ["Creator", "Cashier"] and edit_branch_id is None and branch_options:
                                st.error("Rol requiere una sucursal.")
                            else:
                                if update_user_profile(user_id, edit_username, edit_role_id, edit_branch_id, phone_number_to_save):
                                    st.rerun() # Refresh list

                        if submitted_delete:
                            st.warning("¡Esta acción eliminará el PERFIL del usuario, pero NO su cuenta de autenticación (Auth)!")
                            st.warning("La cuenta Auth debe eliminarse manualmente en Supabase.")
                            confirm_delete_key = f"confirm_del_user_{user_id}"
                            # Use session state for delete confirmation
                            if confirm_delete_key not in st.session_state: st.session_state[confirm_delete_key] = False
                            st.session_state[confirm_delete_key] = st.checkbox("Confirmar eliminación del perfil", key=f"cb_{confirm_delete_key}", value=st.session_state[confirm_delete_key])
                            if st.session_state[confirm_delete_key]:
                                if delete_user_profile(user_id):
                                    st.session_state[confirm_delete_key] = False # Reset state
                                    st.rerun() # Refresh list


        else:
            st.info("No hay usuarios registrados o no se pudieron cargar.")
