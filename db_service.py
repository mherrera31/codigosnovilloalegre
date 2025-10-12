# db_service.py (ACTUALIZADO para usar requests)
import requests
import streamlit as st
import pandas as pd
import json
import auth
from db_config import POSTGREST_ENDPOINT, get_headers
import auth

# --- Funciones de Lectura General ---

def get_data_table(table_name: str, select_params: str = '*'):
    """Obtiene datos de una tabla específica."""
    
    # 1. OBTENER EL TOKEN DEL USUARIO LOGUEADO
    token = st.session_state.get('token')
    
    # 2. Generar URL
    url = f"{POSTGREST_ENDPOINT}/{table_name}?select={select_params}"
    
    try:
        # 3. Llamar con las cabeceras que contienen el token
        response = requests.get(url, headers=get_headers(token))
        response.raise_for_status() 
        return response.json()
    except Exception as e:
        st.error(f"Error al cargar datos de {table_name}: {e}")
        return []

def get_branches():
    """Obtiene la lista de sucursales."""
    return get_data_table('branches')

def get_roles():
    """Obtiene la lista de roles."""
    return get_data_table('roles')

# --- Funciones de Creación (Administración de Metadata) ---

def create_entry(table_name: str, payload: dict):
    """Función genérica para crear una entrada en cualquier tabla."""
    url = f"{POSTGREST_ENDPOINT}/{table_name}"
    
    # La creación debe usar el token del Admin
    token = st.session_state.get('token') 
    if not token:
        st.error("Se requiere autenticación para esta acción.")
        return False
        
    try:
        # Usamos la cabecera 'Prefer' para obtener el objeto creado en la respuesta
        headers = get_headers(token)
        headers['Prefer'] = 'return=representation' 
        
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        
        return True
    except requests.exceptions.HTTPError as err:
        st.error(f"Error al crear en {table_name}: {err.response.json().get('message', str(err))}")
        return False
    except Exception as e:
        st.error(f"Error inesperado al crear: {e}")
        return False


def create_branch(name: str, address: str):
    """Inserta una nueva sucursal."""
    if create_entry('branches', {'name': name, 'address': address}):
        st.success(f"Sucursal '{name}' creada con éxito.")
        return True
    return False

def create_issuer(name: str):
    """Inserta un nuevo emisor."""
    if create_entry('issuers', {'issuer_name': name}):
        st.success(f"Emisor '{name}' creado con éxito.")
        return True
    return False

def create_promo(type_name: str, is_percentage: bool, is_cash_value: bool, is_product: bool, value: float, description: str):
    """Inserta un nuevo tipo de promoción."""
    payload = {
        'type_name': type_name, 
        'is_percentage': is_percentage, 
        'is_cash_value': is_cash_value, 
        'is_product': is_product, 
        'value': value, 
        'description': description
    }
    if create_entry('promos', payload):
        st.success(f"Promoción '{type_name}' creada con éxito.")
        return True
    return False

def render_config_management():
    """Módulo de Streamlit para la gestión de datos maestros (Solo Admin)."""
    import streamlit as st
    import pandas as pd
    import auth # Necesario para chequear el rol

    # Control de acceso por rol
    if auth.get_user_role() != 'Admin':
        st.error("Acceso denegado. Solo los administradores pueden configurar.")
        return

    st.header("⚙️ Configuración de Datos Maestros")
    
    tab_branch, tab_issuer, tab_promo = st.tabs(["Sucursales", "Emisores", "Promociones"])

    # ------------------
    # TABLA SUCURSALES
    # ------------------
    with tab_branch:
        st.subheader("Administrar Sucursales")
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### Crear Nueva Sucursal")
            with st.form("branch_form"):
                branch_name = st.text_input("Nombre de la Sucursal")
                branch_address = st.text_area("Dirección")
                
                submitted = st.form_submit_button("Crear Sucursal", type="primary")
                if submitted and branch_name:
                    if create_branch(branch_name, branch_address):
                        st.rerun()
                elif submitted and not branch_name:
                    st.warning("El nombre de la sucursal es obligatorio.")
        
        with col2:
            st.markdown("---")
            st.markdown("#### Sucursales Existentes (Editar / Eliminar)")
            branches_data = get_branches()
            
            if branches_data:
                for branch in branches_data:
                    # Usar un expander para cada registro para editar
                    with st.expander(f"Sucursal ID {branch['id']} - {branch['name']}"):
                        
                        # Formulario de Edición
                        with st.form(f"edit_branch_{branch['id']}"):
                            new_name = st.text_input("Nombre", value=branch['name'], key=f"name_{branch['id']}")
                            new_address = st.text_area("Dirección", value=branch['address'], key=f"address_{branch['id']}")
                            
                            col_b1, col_b2 = st.columns(2)
                            with col_b1:
                                save_button = st.form_submit_button("Guardar Cambios", type="primary")
                            with col_b2:
                                # Botón de Eliminar (dentro del formulario para evitar reruns accidentales)
                                delete_button = st.form_submit_button("Eliminar Sucursal", type="secondary")
                                
                            if save_button:
                                if update_entry('branches', branch['id'], {'name': new_name, 'address': new_address}):
                                    st.success("Sucursal actualizada.")
                                    st.rerun()
                                    
                            if delete_button:
                                if delete_entry('branches', branch['id']):
                                    st.success("Sucursal eliminada.")
                                    st.rerun()
        
            else:
                st.info("No hay sucursales registradas.")


    # ------------------
    # TABLA EMISORES
    # ------------------
    with tab_issuer:
        st.subheader("Administrar Emisores")
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### Crear Nuevo Emisor")
            with st.form("issuer_form"):
                issuer_name = st.text_input("Nombre del Emisor (Ej: Marketing, Gerencia)")
                
                submitted = st.form_submit_button("Crear Emisor", type="primary")
                if submitted and issuer_name:
                    if create_issuer(issuer_name):
                        st.rerun()
                elif submitted and not issuer_name:
                    st.warning("El nombre del emisor es obligatorio.")

        with col2:
            st.markdown("#### Emisores Existentes")
            issuers_data = get_issuers()
            if issuers_data:
                df_issuers = pd.DataFrame(issuers_data)
                df_issuers.rename(columns={'issuer_name': 'Nombre'}, inplace=True)
                st.dataframe(df_issuers, use_container_width=True)
            else:
                st.info("No hay emisores registrados.")


    # ------------------
    # TABLA PROMOCIONES (PROMOS)
    # ------------------
    with tab_promo:
        st.subheader("Administrar Tipos de Promoción/Descuento")
        
        with st.form("promo_form"):
            col1, col2, col3 = st.columns(3)
            with col1:
                promo_name = st.text_input("Nombre de la Promoción (Ej: 20% Bebidas)")
                promo_value = st.number_input("Valor Numérico (20 para 20%, 5000 para ₡5000)", min_value=0.0, format="%.2f")
            with col2:
                # Usamos radio buttons para asegurar que solo se elija un tipo de valor
                value_type = st.radio("Tipo de Valor", ["Porcentaje", "Valor Fijo", "Producto de Regalo"])
                
                is_percentage = value_type == "Porcentaje"
                is_cash_value = value_type == "Valor Fijo"
                is_product = value_type == "Producto de Regalo"
                
            with col3:
                promo_description = st.text_area("Descripción Detallada del Beneficio")
            
            submitted = st.form_submit_button("Crear Promoción", type="primary")
            if submitted and promo_name and promo_description:
                if create_promo(promo_name, is_percentage, is_cash_value, is_product, promo_value, promo_description):
                    st.rerun()
            elif submitted:
                st.warning("El nombre y la descripción de la promoción son obligatorios.")

        st.markdown("---")
        st.markdown("#### Promociones Existentes")
        promos_data = get_promos()
        if promos_data:
            df_promos = pd.DataFrame(promos_data)
            st.dataframe(df_promos, use_container_width=True)
        else:
            st.info("No hay promociones registradas.")

def update_entry(table_name: str, id_value: any, payload: dict, id_column: str = 'id'):
    """Función genérica para actualizar una entrada por ID."""
    token = st.session_state.get('token')
    if not token:
        st.error("Se requiere autenticación para esta acción.")
        return False

    # Sintaxis de PostgREST para actualizar: table?id_column=eq.id_value
    url = f"{POSTGREST_ENDPOINT}/{table_name}?{id_column}=eq.{id_value}"
    
    try:
        response = requests.patch(url, headers=get_headers(token), data=json.dumps(payload))
        response.raise_for_status()
        return True
    except requests.exceptions.HTTPError as err:
        st.error(f"Error al actualizar en {table_name}: {err.response.json().get('message', str(err))}")
        return False

def delete_entry(table_name: str, id_value: any, id_column: str = 'id'):
    """Función genérica para eliminar una entrada por ID."""
    token = st.session_state.get('token')
    if not token:
        st.error("Se requiere autenticación para esta acción.")
        return False

    url = f"{POSTGREST_ENDPOINT}/{table_name}?{id_column}=eq.{id_value}"
    
    try:
        response = requests.delete(url, headers=get_headers(token))
        response.raise_for_status()
        return True
    except requests.exceptions.HTTPError as err:
        st.error(f"Error al eliminar en {table_name}: {err.response.json().get('message', str(err))}")
        return False
