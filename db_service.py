# db_service.py (VERSIÓN CORREGIDA Y REORDENADA)
import requests
import streamlit as st
import pandas as pd
import json
import auth # Importamos auth aquí para usarlo en las funciones de servicio
from db_config import POSTGREST_ENDPOINT, get_headers


# =================================================================
# 1. FUNCIONES DE LECTURA Y CRUD (GET, CREATE, UPDATE, DELETE)
# =================================================================

def get_data_table(table_name: str, select_params: str = '*'):
    """Obtiene datos de una tabla específica."""
    
    token = st.session_state.get('token')
    url = f"{POSTGREST_ENDPOINT}/{table_name}?select={select_params}"
    
    try:
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

def get_issuers():
    """Obtiene la lista de emisores."""
    return get_data_table('issuers')

def get_promos():
    """Obtiene la lista de promociones."""
    return get_data_table('promos')

# --- CREATE ---

def create_entry(table_name: str, payload: dict):
    """Función genérica para crear una entrada en cualquier tabla."""
    url = f"{POSTGREST_ENDPOINT}/{table_name}"
    
    token = st.session_state.get('token') 
    if not token:
        st.error("Se requiere autenticación para esta acción.")
        return False
        
    try:
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

# --- UPDATE ---

def update_entry(table_name: str, id_value: any, payload: dict, id_column: str = 'id'):
    """Función genérica para actualizar una entrada por ID."""
    token = st.session_state.get('token')
    if not token:
        st.error("Se requiere autenticación para esta acción.")
        return False

    url = f"{POSTGREST_ENDPOINT}/{table_name}?{id_column}=eq.{id_value}"
    
    try:
        response = requests.patch(url, headers=get_headers(token), data=json.dumps(payload))
        response.raise_for_status()
        return True
    except requests.exceptions.HTTPError as err:
        st.error(f"Error al actualizar en {table_name}: {err.response.json().get('message', str(err))}")
        return False

# --- DELETE ---

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

# =================================================================
# 2. RENDERIZACIÓN DE LA INTERFAZ DE CONFIGURACIÓN
# =================================================================

def render_config_management():
    """Módulo de Streamlit para la gestión de datos maestros (Solo Admin)."""
    
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
        
        branches_data = get_branches()
        
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
            st.markdown("#### Lista Completa")
            if branches_data:
                df_branches = pd.DataFrame(branches_data)
                st.dataframe(df_branches, width='stretch')
            else:
                st.info("No hay sucursales registradas.")


        st.markdown("---")
        st.markdown("#### Editar / Eliminar Sucursales")
        
        if branches_data:
            for branch in branches_data:
                with st.expander(f"Sucursal ID {branch['id']} - {branch['name']}"):
                    
                    with st.form(f"edit_branch_{branch['id']}"):
                        new_name = st.text_input("Nombre", value=branch['name'], key=f"name_{branch['id']}")
                        new_address = st.text_area("Dirección", value=branch['address'] if branch['address'] else "", key=f"address_{branch['id']}")
                        
                        col_b1, col_b2 = st.columns(2)
                        with col_b1:
                            save_button = st.form_submit_button("Guardar Cambios", type="primary")
                        with col_b2:
                            delete_button = st.form_submit_button("Eliminar Sucursal", type="secondary")
                            
                        if save_button:
                            if update_entry('branches', branch['id'], {'name': new_name, 'address': new_address}):
                                st.success("Sucursal actualizada.")
                                st.rerun()
                                
                        if delete_button:
                            # Confirmación simple antes de eliminar
                            st.error("Si elimina, es irreversible.") 
                            if st.button("Confirmar Eliminación", key=f"confirm_del_b{branch['id']}"):
                                if delete_entry('branches', branch['id']):
                                    st.success("Sucursal eliminada.")
                                    st.rerun()

        else:
            st.info("No hay sucursales para editar.")

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
            st.markdown("#### Lista Completa")
            issuers_data = get_issuers()
            if issuers_data:
                df_issuers = pd.DataFrame(issuers_data)
                df_issuers.rename(columns={'issuer_name': 'Nombre'}, inplace=True)
                st.dataframe(df_issuers, width='stretch')
            else:
                st.info("No hay emisores registrados.")
                
        st.markdown("---")
        st.markdown("#### Editar / Eliminar Emisores")
        
        if issuers_data:
            for issuer in issuers_data:
                with st.expander(f"Emisor ID {issuer['id']} - {issuer['issuer_name']}"):
                    with st.form(f"edit_issuer_{issuer['id']}"):
                        new_name = st.text_input("Nombre", value=issuer['issuer_name'], key=f"name_i{issuer['id']}")
                        
                        col_i1, col_i2 = st.columns(2)
                        with col_i1:
                            save_button = st.form_submit_button("Guardar Cambios", type="primary")
                        with col_i2:
                            delete_button = st.form_submit_button("Eliminar Emisor", type="secondary")
                        
                        if save_button:
                            if update_entry('issuers', issuer['id'], {'issuer_name': new_name}):
                                st.success("Emisor actualizado.")
                                st.rerun()
                                
                        if delete_button:
                            st.error("Si elimina, es irreversible.") 
                            if st.button("Confirmar Eliminación", key=f"confirm_del_i{issuer['id']}"):
                                if delete_entry('issuers', issuer['id']):
                                    st.success("Emisor eliminado.")
                                    st.rerun()


    # ------------------
    # TABLA PROMOCIONES (PROMOS)
    # ------------------
    with tab_promo:
        st.subheader("Administrar Tipos de Promoción/Descuento")
        
        # --- Formulario de Creación (Igual que antes) ---
        with st.form("promo_form"):
            col1, col2, col3 = st.columns(3)
            with col1:
                promo_name = st.text_input("Nombre de la Promoción (Ej: 20% Bebidas)")
                promo_value = st.number_input("Valor Numérico (20 para 20%, 5000 para ₡5000)", min_value=0.0, format="%.2f")
            with col2:
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
            st.dataframe(df_promos, width='stretch')
        else:
            st.info("No hay promociones registradas.")
            
        st.markdown("---")
        st.markdown("#### Editar / Eliminar Promociones")
        
        if promos_data:
            for promo in promos_data:
                with st.expander(f"Promo ID {promo['id']} - {promo['type_name']}"):
                    with st.form(f"edit_promo_{promo['id']}"):
                        
                        col_e1, col_e2 = st.columns(2)
                        with col_e1:
                            e_name = st.text_input("Nombre", value=promo['type_name'], key=f"p_name_{promo['id']}")
                            e_desc = st.text_area("Descripción", value=promo['description'], key=f"p_desc_{promo['id']}")
                            e_value = st.number_input("Valor Numérico", value=promo['value'], min_value=0.0, format="%.2f", key=f"p_val_{promo['id']}")
                        with col_e2:
                            # Recrear el radio para seleccionar el tipo actual
                            current_type = ("Porcentaje" if promo['is_percentage'] else 
                                            "Valor Fijo" if promo['is_cash_value'] else 
                                            "Producto de Regalo")
                            e_type = st.radio("Tipo de Valor", ["Porcentaje", "Valor Fijo", "Producto de Regalo"], index=["Porcentaje", "Valor Fijo", "Producto de Regalo"].index(current_type), key=f"p_type_{promo['id']}")
                            
                            e_is_p = e_type == "Porcentaje"
                            e_is_c = e_type == "Valor Fijo"
                            e_is_pr = e_type == "Producto de Regalo"

                        
                        col_p1, col_p2 = st.columns(2)
                        with col_p1:
                            save_button = st.form_submit_button("Guardar Cambios", type="primary")
                        with col_p2:
                            delete_button = st.form_submit_button("Eliminar Promoción", type="secondary")
                        
                        if save_button:
                            payload = {
                                'type_name': e_name,
                                'is_percentage': e_is_p,
                                'is_cash_value': e_is_c,
                                'is_product': e_is_pr,
                                'value': e_value,
                                'description': e_desc
                            }
                            if update_entry('promos', promo['id'], payload):
                                st.success("Promoción actualizada.")
                                st.rerun()
                                
                        if delete_button:
                            st.error("Si elimina, es irreversible.") 
                            if st.button("Confirmar Eliminación", key=f"confirm_del_p{promo['id']}"):
                                if delete_entry('promos', promo['id']):
                                    st.success("Promoción eliminada.")
                                    st.rerun()

def get_next_consecutive():
    """Obtiene el último consecutivo usado para los cupones y retorna el siguiente."""
    token = st.session_state.get('token')
    
    # 1. Obtener el último consecutivo usado en la tabla COUPONS
    url = f"{POSTGREST_ENDPOINT}/coupons?select=consecutive&order=consecutive.desc&limit=1"
    
    try:
        response = requests.get(url, headers=get_headers(token))
        response.raise_for_status()
        data = response.json()
        
        last_consecutive = data[0]['consecutive'] if data else 0
        return last_consecutive + 1
    except Exception as e:
        st.error(f"Error al obtener consecutivo. Asegure que la tabla 'coupons' exista. Error: {e}")
        return 1 # Fallback al consecutivo 1

def create_coupon_batch(count: int, description: str, promo_id: int, value_crc: float, value_usd: float, issuer_id: int, valid_days: int, branch_names: list, user_id: str, batch_name_prefix: str):
    """Genera un lote completo de cupones, insertando en BATCHES y COUPONS."""
    token = st.session_state.get('token')
    if not token: return False

    try:
        # 1. Preparar datos maestros
        branches = get_branches()
        branch_options = {b['name']: b['id'] for b in branches}
        allowed_branch_ids = [branch_options[name] for name in branch_names if name in branch_options]
        
        start_consecutive = get_next_consecutive()
        end_consecutive = start_consecutive + count - 1
        batch_uuid = str(uuid.uuid4())
        expiration_date = (datetime.now() + timedelta(days=valid_days)).strftime("%Y-%m-%d")

        # 2. Insertar Lote (BATCHES)
        batch_payload = {
            'id': batch_uuid,
            'batch_name': f"{batch_name_prefix}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{batch_uuid[:4]}",
            'json_qrs': {'count': count, 'promo_description': description}, # Usaremos un JSON simple
            'consecutive_start': start_consecutive,
            'consecutive_end': end_consecutive,
            'branch_ids': allowed_branch_ids,
            'expiration_date': expiration_date,
            'issuer_id': issuer_id,
            'created_by_user_id': user_id
        }
        if not create_entry('batches', batch_payload):
            raise Exception("Fallo al crear el lote (BATCHES).")

        # 3. Preparar e Insertar Cupones (COUPONS)
        coupon_entries = []
        for i in range(count):
            coupon_uuid = str(uuid.uuid4())
            consecutive = start_consecutive + i
            coupon_entries.append({
                'id': coupon_uuid,
                'batch_id': batch_uuid,
                'consecutive': consecutive,
                'promo_type_id': promo_id,
                'branch_permissions': allowed_branch_ids,
                'base_value_colones': value_crc,
                'base_value_dolares': value_usd,
                'expiration_date': expiration_date
            })
        
        # Insertar todos los cupones en una sola llamada para eficiencia
        coupon_url = f"{POSTGREST_ENDPOINT}/coupons"
        coupon_response = requests.post(coupon_url, headers=get_headers(token), data=json.dumps(coupon_entries))
        coupon_response.raise_for_status()

        return coupon_entries

    except requests.exceptions.HTTPError as err:
        st.error(f"Error al generar lote: {err.response.json().get('message', str(err))}")
        return None
    except Exception as e:
        st.error(f"Error inesperado en la creación del lote: {e}")
        return None
