# db_service.py (VERSIÓN CORREGIDA - REPORTES)
import requests
import streamlit as st
import pandas as pd
import json
import uuid 
import auth 
from db_config import POSTGREST_ENDPOINT, get_headers
from datetime import datetime, timedelta


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
        # st.error(f"Error al cargar datos de {table_name}: {e}") 
        return []

def get_branches():
    """Obtiene la lista de sucursales."""
    return get_data_table('branches')

def get_roles():
    """Obtiene la lista de roles."""
    return get_data_table('roles')

# --- RENOMBRADO: get_issuers -> get_types (AHORA SE LLAMA 'types')
def get_types():
    """Obtiene la lista de tipos/emisores (ahora 'types')."""
    return get_data_table('types')

def get_promos():
    """Obtiene la lista de promociones."""
    return get_data_table('promos')

# --- NUEVAS FUNCIONES PARA VALIDEZ Y RESTRICCIONES ---

def get_validity_scopes():
    """Obtiene la lista de alcances de validez."""
    return get_data_table('validity_scopes')

def get_restrictions():
    """Obtiene la lista de restricciones."""
    return get_data_table('restrictions')


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
        try:
            error_msg = err.response.json().get('message', str(err))
        except:
            error_msg = str(err)
        st.error(f"Error al crear en {table_name}: {error_msg}")
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

# --- RENOMBRADO: create_issuer -> create_type
def create_type(name: str):
    """Inserta un nuevo tipo (anteriormente emisor)."""
    if create_entry('types', {'type_name': name}):
        st.success(f"Tipo/Campaña '{name}' creado con éxito.")
        return True
    return False

def create_promo(type_name: str, is_percentage: bool, is_cash_value: bool, is_product: bool, value: float, description: str):
    """Inserta un nuevo tipo de promoción/descuento."""
    payload = {
        'type_name': type_name, 
        'is_percentage': is_percentage, 
        'is_cash_value': is_cash_value, 
        'is_product': is_product, 
        'value': value, 
        'description': description
    }
    if create_entry('promos', payload):
        st.success(f"Promoción/Descuento '{type_name}' creada con éxito.")
        return True
    return False

# --- CREACION DE NUEVAS ENTIDADES DE DATOS MAESTROS
def create_validity_scope(scope_name: str):
    """Inserta un nuevo alcance de validez."""
    if create_entry('validity_scopes', {'scope_name': scope_name}):
        st.success(f"Alcance de Validez '{scope_name}' creado con éxito.")
        return True
    return False

def create_restriction(description: str):
    """Inserta una nueva restricción."""
    if create_entry('restrictions', {'restriction_description': description}):
        st.success(f"Restricción '{description}' creada con éxito.")
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
        try:
            error_msg = err.response.json().get('message', str(err))
        except:
            error_msg = str(err)
        st.error(f"Error al actualizar en {table_name}: {error_msg}")
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
        try:
            error_msg = err.response.json().get('message', str(err))
        except:
            error_msg = str(err)
        st.error(f"Error al eliminar en {table_name}: {error_msg}")
        return False

# =================================================================
# 2. FUNCIONES DE LOTE Y CUPÓN (CON LÓGICA DE PRECIO DE VENTA Y M:M)
# =================================================================

def get_next_consecutive():
    """Obtiene el último consecutivo usado para los cupones y retorna el siguiente."""
    token = st.session_state.get('token')
    
    # 1. Obtener el último consecutivo usado en la tabla COUPONS
    url = f"{POSTGREST_ENDPOINT}/coupons?select=consecutive&order=consecutive.desc&limit=1"
    
    try:
        response = requests.get(url, headers=get_headers(token))
        response.raise_for_status()
        data = response.json()
        
        # El campo 'consecutive' en la BD es INT
        last_consecutive = int(data[0]['consecutive']) if data and data[0]['consecutive'] else 0
        return last_consecutive + 1
    except Exception as e:
        # Fallback al consecutivo 1
        return 1 

# --- FUNCIÓN DE CÁLCULO DE VALOR DE VENTA INDIVIDUAL ---
def calculate_sale_value(base_value: float, promo_data: dict):
    """Calcula el valor de venta (precio pagado por la compañía) por cupón individual."""
    
    descount_value = promo_data['value'] # Valor de Promos: monto fijo o porcentaje
    
    if promo_data['is_percentage']:
        # Descuento = Valor Base * (Porcentaje / 100)
        discount = base_value * (descount_value / 100.0)
    elif promo_data['is_cash_value']:
        # Descuento es el monto fijo de 'value'
        # Asumimos que el 'value' de la promoción es el descuento en COLONES/USD (según el contexto)
        discount = descount_value 
    else: # is_product o no definido, no hay descuento de precio (la empresa paga el valor base)
        discount = 0.0
        
    sale_value = base_value - discount
    return round(max(0.0, sale_value), 2) # Aseguramos 2 decimales y no negativo

# --- FUNCIÓN CENTRAL DE CREACIÓN DE LOTE ---
def create_coupon_batch(
    count: int, 
    promo_data: dict, 
    value_crc: float, 
    value_usd: float, 
    type_id: int, 
    months_valid: int, 
    branch_names: list, 
    scope_ids: list, 
    restriction_ids: list, 
    user_id: str
):
    """Genera un lote completo de cupones, insertando en BATCHES y COUPONS, y sus relaciones M:M."""
    token = st.session_state.get('token')
    if not token: 
        st.error("Se requiere autenticación para crear el lote.")
        return None

    try:
        # 1. Preparar datos maestros y fechas
        branches = get_branches()
        branch_options = {b['name']: b['id'] for b in branches}
        allowed_branch_ids = [str(branch_options[name]) for name in branch_names if name in branch_options]
        
        start_consecutive = get_next_consecutive()
        end_consecutive = start_consecutive + count - 1
        batch_uuid = str(uuid.uuid4())
        
        # Cálculo de Fecha de Expiración
        expiration_date = (datetime.now() + timedelta(days=months_valid * 30)).strftime("%Y-%m-%d")

        # 2. CALCULAR VALORES INDIVIDUALES Y TOTALES
        
        # Valores Individuales (para guardar en BATCHES como base)
        sale_value_crc = calculate_sale_value(value_crc, promo_data)
        sale_value_usd = calculate_sale_value(value_usd, promo_data)
        
        # Valores Totales (para guardar en BATCHES)
        total_ref_value_crc = round(value_crc * count, 2)
        total_ref_value_usd = round(value_usd * count, 2)
        total_sale_value_crc = round(sale_value_crc * count, 2)
        total_sale_value_usd = round(sale_value_usd * count, 2)

        # 3. Insertar Lote (BATCHES)
        batch_payload = {
            'id': batch_uuid,
            'batch_name': f"{promo_data['type_name']}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{batch_uuid[:4]}",
            'json_qrs': {'count': count, 'promo_description': promo_data['description']},
            'consecutive_start': start_consecutive,
            'consecutive_end': end_consecutive,
            'branch_ids': allowed_branch_ids,
            'expiration_date': expiration_date,
            'type_id': type_id, 
            'created_by_user_id': user_id,
            
            # Valores Individuales (base de cálculo)
            'sale_value_basis_crc': sale_value_crc, 
            'sale_value_basis_usd': sale_value_usd,  
            
            # Valores Totales (Nuevas columnas solicitadas)
            'total_ref_value_crc': total_ref_value_crc,
            'total_ref_value_usd': total_ref_value_usd,
            'total_sale_value_crc': total_sale_value_crc,
            'total_sale_value_usd': total_sale_value_usd
        }
        
        if not create_entry('batches', batch_payload):
            raise Exception("Fallo al crear el lote (BATCHES).")

        # 4. Preparar e Insertar Cupones (COUPONS) y relaciones M:M
        coupon_entries = []
        coupon_scopes_entries = []
        coupon_restrictions_entries = []

        for i in range(count):
            coupon_uuid = str(uuid.uuid4())
            consecutive = start_consecutive + i
            
            # Datos del Cupón
            coupon_entries.append({
                'id': coupon_uuid,
                'batch_id': batch_uuid,
                'consecutive': consecutive,
                'promo_type_id': promo_data['id'],
                'branch_permissions': allowed_branch_ids,
                'base_value_colones': value_crc,
                'base_value_dolares': value_usd,
                'expiration_date': expiration_date,
                'creation_date': datetime.now().strftime("%Y-%m-%d %H:%M:%S") 
            })
            
            # Datos de Relación M:M
            for scope_id in scope_ids:
                coupon_scopes_entries.append({
                    'coupon_id': coupon_uuid,
                    'scope_id': scope_id
                })
            
            for restriction_id in restriction_ids:
                coupon_restrictions_entries.append({
                    'coupon_id': coupon_uuid,
                    'restriction_id': restriction_id
                })
        
        # Inserción de Cupones
        coupon_url = f"{POSTGREST_ENDPOINT}/coupons"
        coupon_response = requests.post(coupon_url, headers=get_headers(token), data=json.dumps(coupon_entries))
        coupon_response.raise_for_status()

        # Inserción de Scopes M:M (si existen)
        if coupon_scopes_entries:
            scope_url = f"{POSTGREST_ENDPOINT}/coupon_scopes"
            scope_response = requests.post(scope_url, headers=get_headers(token), data=json.dumps(coupon_scopes_entries))
            scope_response.raise_for_status()

        # Inserción de Restricciones M:M (si existen)
        if coupon_restrictions_entries:
            restriction_url = f"{POSTGREST_ENDPOINT}/coupon_restrictions"
            restriction_response = requests.post(restriction_url, headers=get_headers(token), data=json.dumps(coupon_restrictions_entries))
            restriction_response.raise_for_status()


        return coupon_entries

    except requests.exceptions.HTTPError as err:
        try:
            error_msg = err.response.json().get('message', str(err))
        except:
            error_msg = str(err)
        st.error(f"Error al generar lote: {error_msg}")
        return None
    except Exception as e:
        st.error(f"Error inesperado en la creación del lote: {e}")
        return None


# =================================================================
# 3. FUNCIONES DE REPORTES (Actualizado para el nuevo nombre de tabla)
# =================================================================

def get_activity_report(filters: str):
    """Obtiene el reporte de actividad de cupones con joins para mostrar en la tabla."""
    token = st.session_state.get('token')
    
    # ¡¡CAMBIO!!: Se expande el SELECT para traer toda la info solicitada
    select_params = (
        "id,consecutive,is_redeemed,redemption_date,invoice_number,creation_date,expiration_date,"
        "base_value_colones,base_value_dolares,"
        "batch:batch_id(*,type:types(type_name))," # Trae todo de batches, y anida el tipo
        "branch:redemption_branch_id(name),"
        "user:redeemed_by_user_id(username)"
    )
    
    select_params = select_params.replace(' ', '')

    url = f"{POSTGREST_ENDPOINT}/coupons?select={select_params}"

    all_params = []
    if filters:
        all_params.append(filters)
        
    all_params.append("order=creation_date.desc")

    url_final = url + "&" + "&".join(all_params)

    try:
        response = requests.get(url_final, headers=get_headers(token))
        response.raise_for_status()
        data = response.json()
        
        if data:
            df = pd.DataFrame(data)
            
            # Aplanamiento de datos (¡¡ACTUALIZADO!!)
            df['Sucursal Canje'] = df['branch'].apply(lambda x: x['name'] if x else 'N/A')
            df['Canjeado Por'] = df['user'].apply(lambda x: x['username'] if x else 'N/A')
            df['Tipo/Campaña'] = df['batch'].apply(lambda x: x['type']['type_name'] if (x and x.get('type')) else 'N/A')
            
            # Nuevas columnas del Lote
            df['Lote (Batch Name)'] = df['batch'].apply(lambda x: x['batch_name'] if x else 'N/A')
            df['Venta Lote (CRC)'] = df['batch'].apply(lambda x: x['total_sale_value_crc'] if x else 0.0)
            df['Ref. Lote (CRC)'] = df['batch'].apply(lambda x: x['total_ref_value_crc'] if x else 0.0)
            
            df['is_redeemed'] = df['is_redeemed'].astype(bool)

            # Reordenar columnas para el reporte
            column_order = [
                'id', 'consecutive', 'is_redeemed', 'creation_date', 'expiration_date',
                'base_value_colones', 'base_value_dolares', 
                'Tipo/Campaña', 'Lote (Batch Name)', 'Venta Lote (CRC)', 'Ref. Lote (CRC)',
                'redemption_date', 'invoice_number', 'Sucursal Canje', 'Canjeado Por'
            ]
            
            # Filtrar solo las columnas que existen en el DF (por si alguna falla)
            final_columns = [col for col in column_order if col in df.columns]
            return df[final_columns]
        
        return pd.DataFrame()
        
    # ¡¡CAMBIO CRÍTICO!!: Mostrar el error en la app en lugar de fallar en silencio
    except requests.exceptions.HTTPError as e:
        try:
            error_msg = e.response.json().get('message', str(e))
        except:
            error_msg = str(e)
        st.error(f"Error al cargar el reporte (HTTP): {error_msg}")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Error inesperado al cargar el reporte: {e}")
        return pd.DataFrame()
        

# =================================================================
# 4. RENDERIZACIÓN DE LA INTERFAZ DE CONFIGURACIÓN (CRUD COMPLETO)
# (Esta función permanece sin cambios funcionales desde la última versión)
# =================================================================

def render_config_management():
    """Módulo de Streamlit para la gestión de datos maestros (Solo Admin)."""
    import streamlit as st
    import pandas as pd
    import auth 

    if auth.get_user_role() != 'Admin':
        st.error("Acceso denegado. Solo los administradores pueden configurar.")
        return

    st.header("⚙️ Configuración de Datos Maestros")
    
    # CAMBIO: Renombrado de tab_issuer a tab_type
    tab_branch, tab_type, tab_promo, tab_validity, tab_restriction = st.tabs([
        "Sucursales", 
        "Tipos/Campañas", 
        "Promociones/Descuentos",
        "Validez de Cupón",
        "Restricciones"
    ])

    # ------------------
    # TABLA SUCURSALES (CRUD)
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
                            st.error("Si elimina, es irreversible.") 
                            if st.button("Confirmar Eliminación", key=f"confirm_del_b{branch['id']}"):
                                if delete_entry('branches', branch['id']):
                                    st.success("Sucursal eliminada.")
                                    st.rerun()

        else:
            st.info("No hay sucursales para editar.")

    # ------------------
    # TABLA TIPOS/CAMPAÑAS (CRUD) - RENOMBRADO
    # ------------------
    with tab_type:
        st.subheader("Administrar Tipos/Campañas de Cupón")
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### Crear Nuevo Tipo/Campaña")
            with st.form("type_form"):
                type_name = st.text_input("Nombre del Tipo/Campaña (Ej: Marketing, Venta Corporativa)")
                
                submitted = st.form_submit_button("Crear Tipo/Campaña", type="primary")
                if submitted and type_name:
                    if create_type(type_name): # CAMBIO: llama a create_type
                        st.rerun()
                elif submitted and not type_name:
                    st.warning("El nombre es obligatorio.")

        with col2:
            st.markdown("#### Lista Completa")
            types_data = get_types() # CAMBIO: llama a get_types
            if types_data:
                df_types = pd.DataFrame(types_data)
                df_types.rename(columns={'type_name': 'Nombre'}, inplace=True) # CAMBIO: Renombre de columna
                st.dataframe(df_types, width='stretch')
            else:
                st.info("No hay Tipos/Campañas registradas.")
                
        st.markdown("---")
        st.markdown("#### Editar / Eliminar Tipos/Campañas")
        
        if types_data:
            for type_item in types_data:
                with st.expander(f"Tipo ID {type_item['id']} - {type_item['type_name']}"):
                    with st.form(f"edit_type_{type_item['id']}"):
                        # CAMBIO: Renombre de columna
                        new_name = st.text_input("Nombre", value=type_item['type_name'], key=f"name_t{type_item['id']}")
                        
                        col_i1, col_i2 = st.columns(2)
                        with col_i1:
                            save_button = st.form_submit_button("Guardar Cambios", type="primary")
                        with col_i2:
                            delete_button = st.form_submit_button("Eliminar Tipo", type="secondary")
                        
                        if save_button:
                            if update_entry('types', type_item['id'], {'type_name': new_name}):
                                st.success("Tipo/Campaña actualizado.")
                                st.rerun()
                                
                        if delete_button:
                            st.error("Si elimina, es irreversible.") 
                            if st.button("Confirmar Eliminación", key=f"confirm_del_t{type_item['id']}"):
                                if delete_entry('types', type_item['id']):
                                    st.success("Tipo/Campaña eliminado.")
                                    st.rerun()


    # ------------------
    # TABLA PROMOCIONES/DESCUENTOS (CRUD)
    # ------------------
    with tab_promo:
        st.subheader("Administrar Tipos de Promoción/Descuento (Valor de Venta)")
        
        # --- Formulario de Creación ---
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
                promo_description = st.text_area("Descripción Detallada del Beneficio (Aplica al canje)")
            
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
                # Determinar el tipo de valor actual para el radio button
                current_type = ("Porcentaje" if promo['is_percentage'] else 
                                "Valor Fijo" if promo['is_cash_value'] else 
                                "Producto de Regalo")
                
                with st.expander(f"Promo ID {promo['id']} - {promo['type_name']}"):
                    with st.form(f"edit_promo_{promo['id']}"):
                        
                        col_e1, col_e2 = st.columns(2)
                        with col_e1:
                            e_name = st.text_input("Nombre", value=promo['type_name'], key=f"p_name_{promo['id']}")
                            e_desc = st.text_area("Descripción", value=promo['description'], key=f"p_desc_{promo['id']}")
                            e_value = st.number_input("Valor Numérico", value=promo['value'], min_value=0.0, format="%.2f", key=f"p_val_{promo['id']}")
                        with col_e2:
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

    # ------------------
    # TABLA VALIDEZ DE CUPÓN (CRUD) - NUEVA
    # ------------------
    with tab_validity:
        st.subheader("Administrar Alcances de Validez de Cupón")
        
        scopes_data = get_validity_scopes()
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### Crear Nuevo Alcance de Validez")
            with st.form("scope_form"):
                scope_name = st.text_input("Nombre del Alcance (Ej: Solo en Comida, Solo en Bebidas)")
                submitted = st.form_submit_button("Crear Alcance", type="primary")
                if submitted and scope_name:
                    if create_validity_scope(scope_name):
                        st.rerun()
                elif submitted and not scope_name:
                    st.warning("El nombre del alcance es obligatorio.")
        
        with col2:
            st.markdown("#### Lista Completa")
            if scopes_data:
                df_scopes = pd.DataFrame(scopes_data)
                df_scopes.rename(columns={'scope_name': 'Nombre del Alcance'}, inplace=True)
                st.dataframe(df_scopes, width='stretch')
            else:
                st.info("No hay alcances registrados.")

        st.markdown("---")
        st.markdown("#### Editar / Eliminar Alcances")
        
        if scopes_data:
            for scope in scopes_data:
                with st.expander(f"Alcance ID {scope['id']} - {scope['scope_name']}"):
                    with st.form(f"edit_scope_{scope['id']}"):
                        new_name = st.text_input("Nombre", value=scope['scope_name'], key=f"name_s{scope['id']}")
                        
                        col_s1, col_s2 = st.columns(2)
                        with col_s1:
                            save_button = st.form_submit_button("Guardar Cambios", type="primary")
                        with col_s2:
                            delete_button = st.form_submit_button("Eliminar Alcance", type="secondary")
                            
                        if save_button:
                            if update_entry('validity_scopes', scope['id'], {'scope_name': new_name}):
                                st.success("Alcance actualizado.")
                                st.rerun()
                                
                        if delete_button:
                            st.error("Si elimina, es irreversible.") 
                            if st.button("Confirmar Eliminación", key=f"confirm_del_s{scope['id']}"):
                                if delete_entry('validity_scopes', scope['id']):
                                    st.success("Alcance eliminado.")
                                    st.rerun()

    # ------------------
    # TABLA RESTRICCIONES (CRUD) - NUEVA
    # ------------------
    with tab_restriction:
        st.subheader("Administrar Restricciones de Cupón")
        
        restrictions_data = get_restrictions()
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### Crear Nueva Restricción")
            with st.form("restriction_form"):
                restriction_description = st.text_area("Descripción de la Restricción (Ej: No Válido en Feriados, Solo Lunes a Miércoles)")
                submitted = st.form_submit_button("Crear Restricción", type="primary")
                if submitted and restriction_description:
                    if create_restriction(restriction_description):
                        st.rerun()
                elif submitted and not restriction_description:
                    st.warning("La descripción de la restricción es obligatoria.")
        
        with col2:
            st.markdown("#### Lista Completa")
            if restrictions_data:
                df_restrictions = pd.DataFrame(restrictions_data)
                df_restrictions.rename(columns={'restriction_description': 'Descripción de la Restricción'}, inplace=True)
                st.dataframe(df_restrictions, width='stretch')
            else:
                st.info("No hay restricciones registradas.")

        st.markdown("---")
        st.markdown("#### Editar / Eliminar Restricciones")
        
        if restrictions_data:
            for restriction in restrictions_data:
                with st.expander(f"Restricción ID {restriction['id']}"):
                    with st.form(f"edit_restriction_{restriction['id']}"):
                        new_desc = st.text_area("Descripción", value=restriction['restriction_description'], key=f"desc_r{restriction['id']}")
                        
                        col_r1, col_r2 = st.columns(2)
                        with col_r1:
                            save_button = st.form_submit_button("Guardar Cambios", type="primary")
                        with col_r2:
                            delete_button = st.form_submit_button("Eliminar Restricción", type="secondary")
                            
                        if save_button:
                            if update_entry('restrictions', restriction['id'], {'restriction_description': new_desc}):
                                st.success("Restricción actualizada.")
                                st.rerun()
                                
                        if delete_button:
                            st.error("Si elimina, es irreversible.") 
                            if st.button("Confirmar Eliminación", key=f"confirm_del_r{restriction['id']}"):
                                if delete_entry('restrictions', restriction['id']):
                                    st.success("Restricción eliminada.")
                                    st.rerun()
