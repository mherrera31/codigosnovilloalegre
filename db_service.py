# db_service.py (VERSIÓN FINAL - Hora Costa Rica UTC-6)
import requests
import streamlit as st
import pandas as pd
import json
import uuid
import auth
from db_config import POSTGREST_ENDPOINT, get_headers
# --- CAMBIO: Importar timezone para manejar UTC-6 ---
from datetime import datetime, timedelta, date, timezone

# --- CAMBIO: Definir Zona Horaria Costa Rica (UTC-6) ---
CR_TIMEZONE = timezone(timedelta(hours=-6))

# Cache branch names for mapping in reports
@st.cache_data(ttl=300) # Cache for 5 minutes
def get_branch_name_map():
    branches = get_branches()
    # Ensure IDs are strings for consistent mapping, handle potential missing ID/Name
    return {str(b.get('id')): b.get('name', f"ID:{b.get('id')}") for b in branches if b.get('id') is not None}


# =================================================================
# 1. FUNCIONES DE LECTURA Y CRUD
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
        # Silently fail for general use, report errors contextually
        # st.error(f"Error loading {table_name}: {e}")
        return []

def get_branches():
    """Obtiene la lista de sucursales."""
    return get_data_table('branches')

def get_roles():
    """Obtiene la lista de roles."""
    return get_data_table('roles')

def get_types():
    """Obtiene la lista de tipos/emisores (ahora 'types')."""
    return get_data_table('types')

def get_promos():
    """Obtiene la lista de promociones."""
    return get_data_table('promos')

def get_validity_scopes():
    """Obtiene la lista de alcances de validez."""
    return get_data_table('validity_scopes')

def get_restrictions():
    """Obtiene la lista de restricciones."""
    return get_data_table('restrictions')

# --- CREATE ---
def create_entry(table_name: str, payload: dict, return_representation: bool = False):
    """Función genérica para crear una entrada en cualquier tabla."""
    url = f"{POSTGREST_ENDPOINT}/{table_name}"
    token = st.session_state.get('token')
    if not token:
        st.error("Se requiere autenticación para esta acción.")
        return None # Return None on failure

    try:
        headers = get_headers(token)
        if return_representation:
             headers['Prefer'] = 'return=representation' # Get the created record back

        response = requests.post(url, headers=headers, data=json.dumps(payload))
        response.raise_for_status() # Raises HTTPError for bad responses (4xx or 5xx)

        # Handle response based on status code and preference
        if return_representation and response.status_code != 204: # 204 No Content
            return response.json() # Return the created object(s)
        elif response.status_code == 201 or response.status_code == 204: # Created or No Content (success)
             return True # Generic success
        else:
             st.warning(f"Respuesta inesperada al crear en {table_name}: {response.status_code}")
             return None # Unexpected status

    except requests.exceptions.HTTPError as err:
        try:
            error_msg = err.response.json().get('message', str(err))
        except json.JSONDecodeError:
            error_msg = str(err.response.text) # Show raw text if not JSON
        except Exception:
             error_msg = str(err)
        st.error(f"Error al crear en {table_name}: {error_msg}")
        return None # Return None on failure
    except Exception as e:
        st.error(f"Error inesperado al crear en {table_name}: {e}")
        return None # Return None on failure

def create_branch(name: str, address: str):
    """Inserta una nueva sucursal."""
    result = create_entry('branches', {'name': name, 'address': address})
    if result: st.success(f"Sucursal '{name}' creada.")
    return result is not None

def create_type(name: str):
    """Inserta un nuevo tipo (anteriormente emisor)."""
    result = create_entry('types', {'type_name': name})
    if result: st.success(f"Tipo/Campaña '{name}' creado.")
    return result is not None

def create_promo(type_name: str, is_percentage: bool, is_cash_value: bool, is_product: bool, value: float, description: str):
    """Inserta un nuevo tipo de promoción/descuento."""
    payload = {'type_name': type_name, 'is_percentage': is_percentage, 'is_cash_value': is_cash_value, 'is_product': is_product, 'value': value, 'description': description}
    result = create_entry('promos', payload)
    if result: st.success(f"Promoción '{type_name}' creada.")
    return result is not None

def create_validity_scope(scope_name: str):
    """Inserta un nuevo alcance de validez."""
    result = create_entry('validity_scopes', {'scope_name': scope_name})
    if result: st.success(f"Alcance '{scope_name}' creado.")
    return result is not None

def create_restriction(description: str):
    """Inserta una nueva restricción."""
    result = create_entry('restrictions', {'restriction_description': description})
    if result: st.success(f"Restricción creada.")
    return result is not None


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
        try: error_msg = err.response.json().get('message', str(err.response.text))
        except: error_msg = str(err.response.text)
        st.error(f"Error al actualizar en {table_name}: {error_msg}")
        return False
    except Exception as e:
        st.error(f"Error inesperado al actualizar {table_name}: {e}")
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
        # Check if deletion actually happened (status code 204 No Content implies success)
        return response.status_code == 204
    except requests.exceptions.HTTPError as err:
        try: error_msg = err.response.json().get('message', str(err.response.text))
        except: error_msg = str(err.response.text)
        st.error(f"Error al eliminar en {table_name}: {error_msg}")
        return False
    except Exception as e:
        st.error(f"Error inesperado al eliminar {table_name}: {e}")
        return False

# =================================================================
# 2. FUNCIONES DE LOTE Y CUPÓN
# =================================================================

def get_next_consecutive():
    """Obtiene el último consecutivo usado."""
    token = st.session_state.get('token')
    url = f"{POSTGREST_ENDPOINT}/coupons?select=consecutive&order=consecutive.desc&limit=1"
    try:
        response = requests.get(url, headers=get_headers(token))
        response.raise_for_status()
        data = response.json()
        last = int(data[0]['consecutive']) if data and data[0]['consecutive'] is not None else 0
        return last + 1
    except Exception:
        return 1 # Fallback if error or table empty

def calculate_discount_per_coupon(base_value: float, promo_data: dict):
    """Calcula SÓLO el monto del descuento por cupón."""
    if base_value is None: base_value = 0.0 # Handle None case
    discount_v = promo_data.get('value', '0.0') # Default to string '0.0'
    try:
        discount_v = float(discount_v)
    except (ValueError, TypeError):
        discount_v = 0.0

    if promo_data.get('is_percentage'):
        discount = base_value * (discount_v / 100.0)
    elif promo_data.get('is_cash_value'):
        discount = discount_v # Direct value discount
    else: # is_product or other cases
        discount = 0.0
    return round(discount, 2)

def create_coupon_batch(
    count: int,
    asociado_comprador: str, # <-- Obligatorio ahora
    # batch_name parameter removed
    promo_data: dict,
    value_crc: float,
    value_usd: float,
    type_id: int,
    months_valid: int,
    branch_names: list, # Can be empty for "All"
    scope_ids: list, # Now mandatory
    restriction_ids: list, # Now mandatory
    user_id: str
):
    """Genera lote, cupones, relaciones M:M y RECIBO."""
    token = st.session_state.get('token')
    if not token:
        st.error("Se requiere autenticación para crear el lote.")
        return None

    try:
        # 1. Preparar datos básicos
        branches = get_branches(); branch_options = {b['name']: b['id'] for b in branches}
        allowed_branch_ids = [str(branch_options[name]) for name in branch_names if name in branch_options] # Ensure IDs are strings
        start_consecutive = get_next_consecutive(); end_consecutive = start_consecutive + count - 1
        batch_uuid = str(uuid.uuid4())
        
        # --- CAMBIO: Usar Hora Costa Rica para el vencimiento y creación ---
        now_cr = datetime.now(CR_TIMEZONE)
        expiration_date = (now_cr + timedelta(days=months_valid * 30)).strftime("%Y-%m-%d") 
        current_timestamp_iso = now_cr.isoformat() 
        # --- FIN CAMBIO ---

        # 2. Calcular valores
        total_ref_crc = round(value_crc * count, 2); total_ref_usd = round(value_usd * count, 2)
        disc_crc = calculate_discount_per_coupon(value_crc, promo_data); disc_usd = calculate_discount_per_coupon(value_usd, promo_data)
        total_disc_crc = round(disc_crc * count, 2); total_disc_usd = round(disc_usd * count, 2)
        total_sale_crc = round(total_ref_crc - total_disc_crc, 2); total_sale_usd = round(total_ref_usd - total_disc_usd, 2)
        sale_basis_crc = round(value_crc - disc_crc, 2); sale_basis_usd = round(value_usd - disc_usd, 2)

        # 3. GENERAR BATCH NAME (Siempre autogenerado con Asociado y Hora CR)
        base_name_part = f"{promo_data.get('type_name', 'Lote')}"
        base_name = f"{asociado_comprador.strip()}_{base_name_part}"
        # Usamos now_cr para el nombre del archivo
        final_batch_name = f"{base_name}_{now_cr.strftime('%Y%m%d%H%M')}_{batch_uuid[:4]}"

        # 4. Insertar Lote (Batches)
        batch_payload = {
            'id': batch_uuid, 'batch_name': final_batch_name,
            'json_qrs': {'count': count, 'promo_description': promo_data.get('description', '')},
            'consecutive_start': start_consecutive, 'consecutive_end': end_consecutive,
            'branch_ids': allowed_branch_ids if allowed_branch_ids else None,
            'expiration_date': expiration_date, 'type_id': type_id, 'created_by_user_id': user_id,
            'sale_value_basis_crc': sale_basis_crc, 'sale_value_basis_usd': sale_basis_usd,
            'total_ref_value_crc': total_ref_crc, 'total_ref_value_usd': total_ref_usd,
            'total_sale_value_crc': total_sale_crc, 'total_sale_value_usd': total_sale_usd,
            'creation_date': current_timestamp_iso
        }
        created_batch_result = create_entry('batches', batch_payload, return_representation=True)
        if not created_batch_result: raise Exception("Fallo al crear el registro del lote (batches).")
        created_batch_data = created_batch_result[0] if isinstance(created_batch_result, list) else created_batch_result

        # 5. Preparar e Insertar Cupones y Relaciones M:M
        coupon_entries, scopes_entries, restrictions_entries = [], [], []
        for i in range(count):
            c_uuid = str(uuid.uuid4()); cons = start_consecutive + i
            coupon_entries.append({'id': c_uuid, 'batch_id': batch_uuid, 'consecutive': cons, 'promo_type_id': promo_data.get('id'), 'branch_permissions': allowed_branch_ids if allowed_branch_ids else None, 'base_value_colones': value_crc, 'base_value_dolares': value_usd, 'expiration_date': expiration_date, 'creation_date': current_timestamp_iso})
            for s_id in scope_ids: scopes_entries.append({'coupon_id': c_uuid, 'scope_id': s_id})
            for r_id in restriction_ids: restrictions_entries.append({'coupon_id': c_uuid, 'restriction_id': r_id})
        headers = get_headers(token)
        requests.post(f"{POSTGREST_ENDPOINT}/coupons", headers=headers, data=json.dumps(coupon_entries)).raise_for_status()
        if scopes_entries: requests.post(f"{POSTGREST_ENDPOINT}/coupon_scopes", headers=headers, data=json.dumps(scopes_entries)).raise_for_status()
        if restrictions_entries: requests.post(f"{POSTGREST_ENDPOINT}/coupon_restrictions", headers=headers, data=json.dumps(restrictions_entries)).raise_for_status()

        # 6. Insertar Recibo
        receipt_payload = {'batch_id': batch_uuid, 'batch_name': final_batch_name, 'coupon_count': count, 'consecutive_start': start_consecutive, 'consecutive_end': end_consecutive, 'total_ref_value_crc': total_ref_crc, 'total_ref_value_usd': total_ref_usd, 'total_sale_value_crc': total_sale_crc, 'total_sale_value_usd': total_sale_usd}
        created_receipt_result = create_entry('batch_receipts', receipt_payload, return_representation=True)
        if not created_receipt_result: st.warning("El lote y los cupones se crearon, pero hubo un error al guardar el registro del recibo.")
        receipt_data = created_receipt_result[0] if isinstance(created_receipt_result, list) else created_receipt_result if isinstance(created_receipt_result, dict) else receipt_payload
        return {'batch_data': created_batch_data, 'coupon_entries': coupon_entries, 'receipt_data': receipt_data}
    except requests.exceptions.HTTPError as err:
        try: error_msg = err.response.json().get('message', str(err.response.text))
        except: error_msg = str(err)
        st.error(f"Error HTTP al generar lote: {error_msg}")
        return None
    except Exception as e: import traceback; st.error(f"Error inesperado en la creación del lote: {e}\n{traceback.format_exc()}"); return None


# =================================================================
# 3. FUNCIONES DE REPORTES
# =================================================================

def get_activity_report(filters: str):
    """Obtiene el reporte detallado de cupones individuales."""
    token = st.session_state.get('token')
    
    select_params = (
        "id,consecutive,is_redeemed,redemption_date,invoice_number,creation_date,expiration_date,"
        "base_value_colones,base_value_dolares,branch_permissions," 
        "batch:batch_id(id,batch_name,sale_value_basis_crc,sale_value_basis_usd,type:types(type_name),creator:created_by_user_id(username)),"
        "branch:redemption_branch_id(name),"
        "user:redeemed_by_user_id(username)"
    ).replace(' ', '')
    
    url = f"{POSTGREST_ENDPOINT}/coupons?select={select_params}"
    all_params = [f for f in [filters, "order=creation_date.desc"] if f]
    url_final = url + ("&" + "&".join(all_params) if all_params else "")

    try:
        response = requests.get(url_final, headers=get_headers(token)); response.raise_for_status()
        data = response.json()
        if not data: return pd.DataFrame()

        df = pd.DataFrame(data)
        branch_map = get_branch_name_map() 

        # --- Aplanamiento ---
        df['Sucursal Canje'] = df['branch'].apply(lambda x: x.get('name') if isinstance(x, dict) else 'N/A')
        df['Canjeado Por'] = df['user'].apply(lambda x: x.get('username') if isinstance(x, dict) else 'N/A')
        df['Tipo/Campaña'] = df['batch'].apply(lambda x: x.get('type', {}).get('type_name') if isinstance(x, dict) else 'N/A')
        df['Lote'] = df['batch'].apply(lambda x: x.get('batch_name') if isinstance(x, dict) else 'N/A')
        df['Creador Lote'] = df['batch'].apply(lambda x: x.get('creator', {}).get('username') if isinstance(x, dict) else 'N/A')
        df['Valor Pagado Cupón CRC'] = df['batch'].apply(lambda x: pd.to_numeric(x.get('sale_value_basis_crc'), errors='coerce') if isinstance(x, dict) else 0.0).fillna(0.0)
        df['Valor Pagado Cupón USD'] = df['batch'].apply(lambda x: pd.to_numeric(x.get('sale_value_basis_usd'), errors='coerce') if isinstance(x, dict) else 0.0).fillna(0.0)
        df['is_redeemed'] = df['is_redeemed'].astype(bool)

        # --- Mapear Sucursales Permitidas ---
        def map_branch_permissions(ids):
            if ids is None: return "Todas"
            if isinstance(ids, list):
                if not ids: return "Todas"
                return ", ".join(sorted([branch_map.get(str(bid), f"ID:{bid}") for bid in ids]))
            return "Error Formato"
        df['Sucursales Permitidas'] = df['branch_permissions'].apply(map_branch_permissions)

        # Formatear fechas
        for col in ['creation_date', 'expiration_date', 'redemption_date']:
             if col in df.columns: df[col] = pd.to_datetime(df[col], errors='coerce').dt.strftime('%Y-%m-%d %H:%M')

        # Orden final interno (nombres técnicos)
        column_order = [
            'id', 'consecutive', 'is_redeemed', 'creation_date', 'expiration_date',
            'base_value_colones', 'base_value_dolares',
            'Valor Pagado Cupón CRC', 'Valor Pagado Cupón USD',
            'Sucursales Permitidas',
            'Tipo/Campaña', 'Lote', 'Creador Lote',
            'redemption_date', 'invoice_number', 'Sucursal Canje', 'Canjeado Por'
        ]
        
        final_columns = [c for c in column_order if c in df.columns]
        df_final = df[final_columns]

        # --- RENOMBRAMIENTO FINAL (Visualización Web) ---
        rename_map = {
            'consecutive': 'Consecutivo',         # <--- CAMBIO SOLICITADO
            'is_redeemed': 'Canjeado',            # <--- Causa del error en app.py si no se actualiza allá
            'creation_date': 'Fecha de Creación',
            'expiration_date': 'Fecha de Vencimiento',
            'redemption_date': 'Dia Canjeado',    # <--- CAMBIO SOLICITADO
            'invoice_number': '# Factura',        # <--- CAMBIO SOLICITADO
            'base_value_colones': 'Valor Cupón Colones',
            'base_value_dolares': 'Valor Cupón Dólares',
            'Valor Pagado Cupón CRC': 'Valor Real Pagado CRC',
            'Valor Pagado Cupón USD': 'Valor Real Pagado USD',
            'Lote': 'Nombre de Lote'
        }
        
        return df_final.rename(columns=rename_map)

    except requests.exceptions.HTTPError as e:
        try: error = e.response.json().get('message', str(e.response.text))
        except: error = str(e); st.error(f"Error reporte cupones (HTTP): {error}"); return pd.DataFrame()
    except Exception as e: st.error(f"Error reporte cupones: {e}"); return pd.DataFrame()
        
def get_batch_report(filters: str = None):
    """Obtiene el reporte resumen de lotes."""
    token = st.session_state.get('token');
    select = ("id,batch_name,creation_date,expiration_date,consecutive_start,consecutive_end,total_ref_value_crc,total_ref_value_usd,total_sale_value_crc,total_sale_value_usd,creator:created_by_user_id(username),coupons(count)").replace(' ', '')
    url_b = f"{POSTGREST_ENDPOINT}/batches?select={select}&order=creation_date.desc"; url_r = f"{POSTGREST_ENDPOINT}/coupons?select=batch_id&is_redeemed=eq.true"
    try:
        res_b = requests.get(url_b, headers=get_headers(token)); res_b.raise_for_status(); batches_data = res_b.json()
        if not batches_data: return pd.DataFrame()
        df_b = pd.DataFrame(batches_data)
        res_r = requests.get(url_r, headers=get_headers(token)); res_r.raise_for_status(); redeemed_data = res_r.json()
        redeemed_counts = pd.DataFrame(redeemed_data)['batch_id'].value_counts().to_dict() if redeemed_data else {}
        df_b['Creador'] = df_b['creator'].apply(lambda x: x.get('username') if isinstance(x, dict) else 'N/A')
        # Robust count calculation
        df_b['Creados'] = df_b['coupons'].apply(lambda x: x[0]['count'] if isinstance(x, list) and x and 'count' in x[0] else None)
        df_b['Creados'] = df_b['Creados'].fillna(pd.to_numeric(df_b['consecutive_end'], errors='coerce') - pd.to_numeric(df_b['consecutive_start'], errors='coerce') + 1).fillna(0).astype(int)
        df_b['Canjeados'] = df_b['id'].map(redeemed_counts).fillna(0).astype(int)
        
        # --- CAMBIO: Comparar Vencimiento con fecha CR ---
        today_cr = datetime.now(CR_TIMEZONE).date() # Usar fecha local CR
        df_b['exp_date'] = pd.to_datetime(df_b['expiration_date'], errors='coerce').dt.date
        df_b['Vencido?'] = (df_b['exp_date'] < today_cr).fillna(False) 
        # --- FIN CAMBIO ---

        df_b['Creado'] = pd.to_datetime(df_b['creation_date'], errors='coerce').dt.strftime('%Y-%m-%d')
        df_b['Vence'] = pd.to_datetime(df_b['expiration_date'], errors='coerce').dt.strftime('%Y-%m-%d')
        # Ensure numeric types for formatting
        num_cols = ['total_ref_value_crc', 'total_ref_value_usd', 'total_sale_value_crc', 'total_sale_value_usd']
        for col in num_cols: df_b[col] = pd.to_numeric(df_b[col], errors='coerce').fillna(0.0)

        cols = {'id': 'ID Lote', 'batch_name': 'Nombre Lote', 'Creados': 'Creados', 'Canjeados': 'Canjeados', 'Vencido?': 'Vencido?', 'consecutive_start': 'Inicio', 'consecutive_end': 'Fin', 'total_ref_value_crc': 'Ref CRC', 'total_ref_value_usd': 'Ref USD', 'total_sale_value_crc': 'Venta CRC', 'total_sale_value_usd': 'Venta USD', 'Creador': 'Creador', 'Creado': 'Creado', 'Vence': 'Vence'}
        df_report = df_b.rename(columns=cols) # Rename first
        final_cols_lote = [c for c in cols.values() if c in df_report.columns] # Select existing columns after rename
        return df_report[final_cols_lote]
    except requests.exceptions.HTTPError as e:
        try: error = e.response.json().get('message', str(e.response.text))
        except: error = str(e); st.error(f"Error reporte lotes (HTTP): {error}"); return pd.DataFrame()
    except Exception as e: st.error(f"Error reporte lotes: {e}"); return pd.DataFrame()


def get_receipt_data(receipt_id: int):
    """Obtiene los datos guardados de un recibo por su ID (PK)."""
    token = st.session_state.get('token')
    url = f"{POSTGREST_ENDPOINT}/batch_receipts?id=eq.{receipt_id}&select=*"
    try:
        response = requests.get(url, headers=get_headers(token)); response.raise_for_status()
        data = response.json()
        return data[0] if data else None # Return the first (and only) receipt found
    except Exception as e:
        st.error(f"Error al obtener datos del recibo ID {receipt_id}: {e}")
        return None

def get_all_receipts():
    """Obtiene lista básica de todos los recibos (ID, nombre, fecha) para selección."""
    token = st.session_state.get('token')
    url = f"{POSTGREST_ENDPOINT}/batch_receipts?select=id,batch_name,created_at&order=created_at.desc"
    try:
        response = requests.get(url, headers=get_headers(token)); response.raise_for_status()
        data = response.json()
        if not data: return pd.DataFrame()

        df = pd.DataFrame(data)
        # Format date and rename for display
        df['created_at'] = pd.to_datetime(df['created_at'], errors='coerce').dt.strftime('%Y-%m-%d %H:%M')
        df.rename(columns={'id':'Recibo ID', 'batch_name':'Nombre Lote', 'created_at':'Fecha Generado'}, inplace=True)
        return df

    except Exception as e:
        st.error(f"Error al obtener lista de recibos: {e}")
        return pd.DataFrame()


# =================================================================
# 4. RENDERIZACIÓN DE LA INTERFAZ DE CONFIGURACIÓN
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

    tab_branch, tab_type, tab_promo, tab_validity, tab_restriction = st.tabs([
        "Sucursales", "Tipos/Campañas", "Promociones", "Validez", "Restricciones"
    ])

    # --- SUCURSALES ---
    with tab_branch:
        st.subheader("Administrar Sucursales")
        branches_data = get_branches()
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### Crear Nueva Sucursal")
            with st.form("branch_form_create", clear_on_submit=True):
                branch_name = st.text_input("Nombre de la Sucursal")
                branch_address = st.text_area("Dirección")
                submitted = st.form_submit_button("Crear Sucursal", type="primary")
                if submitted and branch_name:
                    if create_branch(branch_name, branch_address): st.rerun()
                elif submitted: st.warning("El nombre es obligatorio.")
        with col2:
            st.markdown("#### Lista Completa")
            if branches_data: st.dataframe(pd.DataFrame(branches_data), use_container_width=True, hide_index=True)
            else: st.info("No hay sucursales.")
        st.divider()
        st.markdown("#### Editar / Eliminar Sucursales")
        if branches_data:
            for branch in branches_data:
                form_key_edit = f"edit_branch_{branch['id']}"
                # --- ¡CORRECCIÓN AQUÍ! --- Remove key= argument from expander ---
                with st.expander(f"ID {branch['id']} - {branch.get('name', 'N/A')}"):
                    with st.form(form_key_edit):
                        new_name = st.text_input("Nombre", value=branch.get('name', ''), key=f"name_b_{branch['id']}")
                        new_address = st.text_area("Dirección", value=branch.get('address', ''), key=f"addr_b_{branch['id']}")
                        cols = st.columns(2)
                        with cols[0]: save_clicked = st.form_submit_button("Guardar Cambios", type="primary", key=f"save_b_{branch['id']}")
                        with cols[1]: delete_clicked = st.form_submit_button("Eliminar Sucursal", key=f"del_b_{branch['id']}")
                        if save_clicked:
                            if update_entry('branches', branch['id'], {'name': new_name, 'address': new_address}): st.success("Actualizado."); st.rerun()
                        if delete_clicked:
                            st.warning("¡Irreversible!")
                            confirm_key = f"del_confirm_b_{branch['id']}"
                            if confirm_key not in st.session_state: st.session_state[confirm_key] = False
                            st.session_state[confirm_key] = st.checkbox("Sí, deseo eliminar.", key=f"cb_{confirm_key}", value=st.session_state[confirm_key])
                            if st.session_state[confirm_key]:
                                if delete_entry('branches', branch['id']): st.success("Eliminado."); st.session_state[confirm_key] = False; st.rerun()
        else: st.info("No hay sucursales para editar/eliminar.")

    # --- TIPOS/CAMPAÑAS ---
    with tab_type:
        st.subheader("Administrar Tipos/Campañas de Cupón")
        types_data = get_types()
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### Crear Nuevo Tipo/Campaña")
            with st.form("type_form_create", clear_on_submit=True):
                type_name = st.text_input("Nombre (Ej: Marketing, Venta)")
                submitted = st.form_submit_button("Crear", type="primary")
                if submitted and type_name:
                    if create_type(type_name): st.rerun()
                elif submitted: st.warning("El nombre es obligatorio.")
        with col2:
            st.markdown("#### Lista Completa")
            if types_data: st.dataframe(pd.DataFrame(types_data).rename(columns={'type_name': 'Nombre'}), use_container_width=True, hide_index=True)
            else: st.info("No hay tipos/campañas registrados.")
        st.divider()
        st.markdown("#### Editar / Eliminar Tipos/Campañas")
        if types_data:
            for type_item in types_data:
                 # --- ¡CORRECCIÓN AQUÍ! --- Remove key= argument from expander ---
                with st.expander(f"ID {type_item['id']} - {type_item.get('type_name', 'N/A')}"):
                     with st.form(f"edit_type_{type_item['id']}"):
                        new_name = st.text_input("Nombre", value=type_item.get('type_name', ''), key=f"name_t_{type_item['id']}")
                        cols = st.columns(2)
                        with cols[0]: save_clicked = st.form_submit_button("Guardar", type="primary", key=f"save_t_{type_item['id']}")
                        with cols[1]: delete_clicked = st.form_submit_button("Eliminar", key=f"del_t_{type_item['id']}")
                        if save_clicked:
                            if update_entry('types', type_item['id'], {'type_name': new_name}): st.success("Actualizado."); st.rerun()
                        if delete_clicked:
                            st.warning("¡Irreversible!")
                            confirm_key = f"del_confirm_t_{type_item['id']}"
                            if confirm_key not in st.session_state: st.session_state[confirm_key] = False
                            st.session_state[confirm_key] = st.checkbox("Confirmar eliminación.", key=f"cb_{confirm_key}", value=st.session_state[confirm_key])
                            if st.session_state[confirm_key]:
                                if delete_entry('types', type_item['id']): st.success("Eliminado."); st.session_state[confirm_key] = False; st.rerun()
        else: st.info("No hay tipos/campañas para editar/eliminar.")

    # --- PROMOCIONES ---
    with tab_promo:
        st.subheader("Administrar Promociones/Descuentos")
        promos_data = get_promos()
        with st.form("promo_form_create", clear_on_submit=True):
             st.markdown("#### Crear Nueva Promoción")
             col1, col2 = st.columns([2,1])
             with col1:
                 promo_name = st.text_input("Nombre (Ej: 10% Descuento Alimentos)")
                 promo_description = st.text_area("Descripción Detallada (para canje)")
             with col2:
                 promo_value = st.number_input("Valor Numérico", min_value=0.0, format="%.2f", help="Ej: 10 para 10%, 5000 para ₡5000")
                 value_type = st.radio("Tipo de Valor", ["Porcentaje", "Valor Fijo", "Producto"], horizontal=True)
             submitted = st.form_submit_button("Crear", type="primary")
             if submitted and promo_name and promo_description:
                 is_p, is_c, is_pr = (value_type == "Porcentaje", value_type == "Valor Fijo", value_type == "Producto")
                 if create_promo(promo_name, is_p, is_c, is_pr, promo_value, promo_description): st.rerun()
             elif submitted: st.warning("Nombre y descripción son obligatorios.")
        st.divider()
        st.markdown("#### Promociones Existentes")
        if promos_data: st.dataframe(pd.DataFrame(promos_data), use_container_width=True, hide_index=True)
        else: st.info("No hay promociones registradas.")
        st.divider()
        st.markdown("#### Editar / Eliminar Promociones")
        if promos_data:
            for promo in promos_data:
                types = ["Porcentaje", "Valor Fijo", "Producto"]; idx = 0
                if promo.get('is_cash_value'): idx = 1
                elif promo.get('is_product'): idx = 2
                # --- ¡CORRECCIÓN AQUÍ! --- Remove key= argument from expander ---
                with st.expander(f"ID {promo['id']} - {promo.get('type_name', 'N/A')}"):
                    with st.form(f"edit_promo_{promo['id']}"):
                        col_e1, col_e2 = st.columns([2,1])
                        with col_e1:
                            e_name = st.text_input("Nombre", value=promo.get('type_name',''), key=f"pn_{promo['id']}")
                            e_desc = st.text_area("Descripción", value=promo.get('description',''), key=f"pd_{promo['id']}")
                        with col_e2:
                            e_value = st.number_input("Valor", value=float(promo.get('value', 0.0)), min_value=0.0, format="%.2f", key=f"pv_{promo['id']}")
                            e_type = st.radio("Tipo", types, index=idx, key=f"pt_{promo['id']}", horizontal=True)
                        is_p, is_c, is_pr = (e_type == "Porcentaje", e_type == "Valor Fijo", e_type == "Producto")
                        col_p1, col_p2 = st.columns(2)
                        with col_p1: save_button = st.form_submit_button("Guardar", type="primary", key=f"save_p_{promo['id']}")
                        with col_p2: delete_button = st.form_submit_button("Eliminar", key=f"del_p_{promo['id']}")
                        if save_button:
                            payload = {'type_name': e_name, 'is_percentage': is_p, 'is_cash_value': is_c, 'is_product': is_pr, 'value': e_value, 'description': e_desc}
                            if update_entry('promos', promo['id'], payload): st.success("Actualizado."); st.rerun()
                        if delete_button:
                            st.warning("¡Irreversible!")
                            confirm_key = f"del_confirm_p_{promo['id']}"
                            if confirm_key not in st.session_state: st.session_state[confirm_key] = False
                            st.session_state[confirm_key] = st.checkbox("Confirmar eliminación.", key=f"cb_{confirm_key}", value=st.session_state[confirm_key])
                            if st.session_state[confirm_key]:
                                if delete_entry('promos', promo['id']): st.success("Eliminado."); st.session_state[confirm_key] = False; st.rerun()
        else: st.info("No hay promociones para editar/eliminar.")

     # --- VALIDEZ ---
    with tab_validity:
        st.subheader("Administrar Alcances de Validez")
        scopes_data = get_validity_scopes()
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### Crear Nuevo Alcance")
            with st.form("scope_form_create", clear_on_submit=True):
                scope_name = st.text_input("Nombre (Ej: Solo Comida, Bebida Gratis)")
                submitted = st.form_submit_button("Crear", type="primary")
                if submitted and scope_name:
                    if create_validity_scope(scope_name): st.rerun()
                elif submitted: st.warning("El nombre es obligatorio.")
        with col2:
            st.markdown("#### Lista Completa")
            if scopes_data: st.dataframe(pd.DataFrame(scopes_data).rename(columns={'scope_name': 'Nombre'}), use_container_width=True, hide_index=True)
            else: st.info("No hay alcances registrados.")
        st.divider()
        st.markdown("#### Editar / Eliminar Alcances")
        if scopes_data:
            for scope in scopes_data:
                 # --- ¡CORRECCIÓN AQUÍ! --- Remove key= argument from expander ---
                 with st.expander(f"ID {scope['id']} - {scope.get('scope_name', 'N/A')}"):
                    with st.form(f"edit_scope_{scope['id']}"):
                        new_name = st.text_input("Nombre", value=scope.get('scope_name', ''), key=f"name_s_{scope['id']}")
                        cols = st.columns(2)
                        with cols[0]: save_clicked = st.form_submit_button("Guardar", type="primary", key=f"save_s_{scope['id']}")
                        with cols[1]: delete_clicked = st.form_submit_button("Eliminar", key=f"del_s_{scope['id']}")
                        if save_clicked:
                            if update_entry('validity_scopes', scope['id'], {'scope_name': new_name}): st.success("Actualizado."); st.rerun()
                        if delete_clicked:
                            st.warning("¡Irreversible!")
                            confirm_key = f"del_confirm_s_{scope['id']}"
                            if confirm_key not in st.session_state: st.session_state[confirm_key] = False
                            st.session_state[confirm_key] = st.checkbox("Confirmar eliminación.", key=f"cb_{confirm_key}", value=st.session_state[confirm_key])
                            if st.session_state[confirm_key]:
                                if delete_entry('validity_scopes', scope['id']): st.success("Eliminado."); st.session_state[confirm_key] = False; st.rerun()
        else: st.info("No hay alcances para editar/eliminar.")

    # --- RESTRICCIONES ---
    with tab_restriction:
        st.subheader("Administrar Restricciones")
        restrictions_data = get_restrictions()
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### Crear Nueva Restricción")
            with st.form("restriction_form_create", clear_on_submit=True):
                desc = st.text_area("Descripción (Ej: No válido feriados)")
                submitted = st.form_submit_button("Crear", type="primary")
                if submitted and desc:
                    if create_restriction(desc): st.rerun()
                elif submitted: st.warning("La descripción es obligatoria.")
        with col2:
            st.markdown("#### Lista Completa")
            if restrictions_data: st.dataframe(pd.DataFrame(restrictions_data).rename(columns={'restriction_description': 'Descripción'}), use_container_width=True, hide_index=True)
            else: st.info("No hay restricciones registradas.")
        st.divider()
        st.markdown("#### Editar / Eliminar Restricciones")
        if restrictions_data:
             for restriction in restrictions_data:
                 desc_short = restriction.get('restriction_description','')[:50]
                 # --- ¡CORRECCIÓN AQUÍ! --- Remove key= argument from expander ---
                 with st.expander(f"ID {restriction['id']} - {desc_short}..."):
                    with st.form(f"edit_restriction_{restriction['id']}"):
                        new_desc = st.text_area("Descripción", value=restriction.get('restriction_description',''), key=f"desc_r_{restriction['id']}")
                        cols = st.columns(2)
                        with cols[0]: save_clicked = st.form_submit_button("Guardar", type="primary", key=f"save_r_{restriction['id']}")
                        with cols[1]: delete_clicked = st.form_submit_button("Eliminar", key=f"del_r_{restriction['id']}")
                        if save_clicked:
                            if update_entry('restrictions', restriction['id'], {'restriction_description': new_desc}): st.success("Actualizado."); st.rerun()
                        if delete_clicked:
                            st.warning("¡Irreversible!")
                            confirm_key = f"del_confirm_r_{restriction['id']}"
                            if confirm_key not in st.session_state: st.session_state[confirm_key] = False
                            st.session_state[confirm_key] = st.checkbox("Confirmar eliminación.", key=f"cb_{confirm_key}", value=st.session_state[confirm_key])
                            if st.session_state[confirm_key]:
                                if delete_entry('restrictions', restriction['id']): st.success("Eliminado."); st.session_state[confirm_key] = False; st.rerun()
        else: st.info("No hay restricciones para editar/eliminar.")

# --- AGREGAR AL FINAL DE db_service.py ---

def get_batch_details_for_reprint(batch_id: str):
    """
    Obtiene todos los datos necesarios para regenerar las imágenes QR de un lote existente.
    Trae cupones, scopes y restrictions.
    """
    token = st.session_state.get('token')
    # Consulta compleja para traer el cupón con sus relaciones
    select_query = (
        "id,consecutive,expiration_date,branch_permissions,"
        "coupon_scopes(validity_scopes(scope_name)),"
        "coupon_restrictions(restrictions(restriction_description))"
    )
    url = f"{POSTGREST_ENDPOINT}/coupons?batch_id=eq.{batch_id}&select={select_query}&order=consecutive.asc"
    
    try:
        response = requests.get(url, headers=get_headers(token))
        response.raise_for_status()
        data = response.json()
        return data
    except Exception as e:
        st.error(f"Error al obtener detalles del lote para reimpresión: {e}")
        return []

def delete_batch(batch_id: str):
    """
    Elimina un lote completo.
    NOTA: Supabase debe tener 'ON DELETE CASCADE' configurado en las FK.
    Si no, habría que borrar tablas hijas manualmente primero.
    Intentamos borrar el Batch padre.
    """
    token = st.session_state.get('token')
    if not token: return False
    
    # 1. Borrar el Recibo asociado (Opcional, si no hay cascada)
    delete_entry('batch_receipts', batch_id, 'batch_id')
    
    # 2. Borrar el Lote (Esto debería borrar los cupones en cascada)
    url = f"{POSTGREST_ENDPOINT}/batches?id=eq.{batch_id}"
    try:
        response = requests.delete(url, headers=get_headers(token))
        response.raise_for_status()
        return response.status_code == 204
    except Exception as e:
        st.error(f"Error al eliminar el lote: {e}")
        return False
