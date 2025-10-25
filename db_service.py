# db_service.py (VERSIÓN COMPLETA FINAL)
import requests
import streamlit as st
import pandas as pd
import json
import uuid
import auth
from db_config import POSTGREST_ENDPOINT, get_headers
from datetime import datetime, timedelta, date


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
        try: error_msg = err.response.json().get('message', str(err))
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
        # Some APIs might return 200 OK with details, but 204 is common for DELETE
        return response.status_code == 204
    except requests.exceptions.HTTPError as err:
        try: error_msg = err.response.json().get('message', str(err))
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
    asociado_comprador: str,
    batch_name: str,
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
    """Genera lote, cupones, relaciones M:M y RECIBO."""
    token = st.session_state.get('token')
    if not token:
        st.error("Se requiere autenticación para crear el lote.")
        return None

    try:
        # 1. Preparar datos básicos
        branches = get_branches()
        branch_options = {b['name']: b['id'] for b in branches}
        allowed_branch_ids = [str(branch_options[name]) for name in branch_names if name in branch_options] # Ensure IDs are strings if needed by DB
        start_consecutive = get_next_consecutive()
        end_consecutive = start_consecutive + count - 1
        batch_uuid = str(uuid.uuid4())
        expiration_date = (datetime.now() + timedelta(days=months_valid * 30)).strftime("%Y-%m-%d") # Approx 30 days/month
        current_timestamp_iso = datetime.now().isoformat() # Use ISO format with timezone if possible

        # 2. Calcular valores
        total_ref_crc = round(value_crc * count, 2)
        total_ref_usd = round(value_usd * count, 2)
        disc_per_coupon_crc = calculate_discount_per_coupon(value_crc, promo_data)
        disc_per_coupon_usd = calculate_discount_per_coupon(value_usd, promo_data)
        total_discount_crc = round(disc_per_coupon_crc * count, 2)
        total_discount_usd = round(disc_per_coupon_usd * count, 2)
        total_sale_crc = round(total_ref_crc - total_discount_crc, 2)
        total_sale_usd = round(total_ref_usd - total_discount_usd, 2)
        sale_basis_crc = round(value_crc - disc_per_coupon_crc, 2) # Sale value per coupon
        sale_basis_usd = round(value_usd - disc_per_coupon_usd, 2) # Sale value per coupon

        # 3. Generar Batch Name
        base_name_part = f"{promo_data.get('type_name', 'Lote')}"
        if asociado_comprador:
            base_name = f"{asociado_comprador.strip()}_{base_name_part}"
        else:
            base_name = base_name_part
        final_batch_name = batch_name.strip() if batch_name else f"{base_name}_{datetime.now().strftime('%Y%m%d%H%M')}_{batch_uuid[:4]}"

        # 4. Insertar Lote (Batches)
        batch_payload = {
            'id': batch_uuid,
            'batch_name': final_batch_name,
            'json_qrs': {'count': count, 'promo_description': promo_data.get('description', '')},
            'consecutive_start': start_consecutive,
            'consecutive_end': end_consecutive,
            'branch_ids': allowed_branch_ids if allowed_branch_ids else None, # Use None if empty list causes issues
            'expiration_date': expiration_date,
            'type_id': type_id,
            'created_by_user_id': user_id,
            'sale_value_basis_crc': sale_basis_crc,
            'sale_value_basis_usd': sale_basis_usd,
            'total_ref_value_crc': total_ref_crc,
            'total_ref_value_usd': total_ref_usd,
            'total_sale_value_crc': total_sale_crc,
            'total_sale_value_usd': total_sale_usd,
            'creation_date': current_timestamp_iso # Explicit creation date for batch
        }
        created_batch_result = create_entry('batches', batch_payload, return_representation=True)
        if not created_batch_result:
            raise Exception("Fallo al crear el registro del lote (batches).")
        # Ensure we get the dict, even if API returns a list
        created_batch_data = created_batch_result[0] if isinstance(created_batch_result, list) else created_batch_result

        # 5. Preparar e Insertar Cupones y Relaciones M:M
        coupon_entries = []
        coupon_scopes_entries = []
        coupon_restrictions_entries = []
        for i in range(count):
            coupon_uuid = str(uuid.uuid4())
            consecutive = start_consecutive + i
            coupon_entries.append({
                'id': coupon_uuid, 'batch_id': batch_uuid, 'consecutive': consecutive,
                'promo_type_id': promo_data.get('id'), # FK to promos table
                'branch_permissions': allowed_branch_ids if allowed_branch_ids else None, # Array of branch IDs
                'base_value_colones': value_crc, 'base_value_dolares': value_usd,
                'expiration_date': expiration_date, 'creation_date': current_timestamp_iso
            })
            # Prepare M:M entries
            for scope_id in scope_ids: coupon_scopes_entries.append({'coupon_id': coupon_uuid, 'scope_id': scope_id})
            for restriction_id in restriction_ids: coupon_restrictions_entries.append({'coupon_id': coupon_uuid, 'restriction_id': restriction_id})

        # Bulk insert coupons
        coupon_url = f"{POSTGREST_ENDPOINT}/coupons"
        headers = get_headers(token) # Reuse headers
        coupon_response = requests.post(coupon_url, headers=headers, data=json.dumps(coupon_entries))
        coupon_response.raise_for_status()

        # Bulk insert M:M relations if any
        if coupon_scopes_entries:
            scope_url = f"{POSTGREST_ENDPOINT}/coupon_scopes"
            scope_response = requests.post(scope_url, headers=headers, data=json.dumps(coupon_scopes_entries))
            scope_response.raise_for_status()
        if coupon_restrictions_entries:
            restriction_url = f"{POSTGREST_ENDPOINT}/coupon_restrictions"
            restriction_response = requests.post(restriction_url, headers=headers, data=json.dumps(coupon_restrictions_entries))
            restriction_response.raise_for_status()

        # 6. Insertar Recibo
        receipt_payload = {
            'batch_id': batch_uuid,
            'batch_name': final_batch_name,
            'coupon_count': count,
            'consecutive_start': start_consecutive,
            'consecutive_end': end_consecutive,
            'total_ref_value_crc': total_ref_crc,
            'total_ref_value_usd': total_ref_usd,
            'total_sale_value_crc': total_sale_crc,
            'total_sale_value_usd': total_sale_usd
            # 'created_at' is handled by DB default
        }
        # Get the created receipt data back
        created_receipt_result = create_entry('batch_receipts', receipt_payload, return_representation=True)
        if not created_receipt_result:
            st.warning("El lote y los cupones se crearon, pero hubo un error al guardar el registro del recibo.")
            receipt_data_for_return = receipt_payload # Return payload as fallback
        else:
             # Ensure we get the dict
            receipt_data_for_return = created_receipt_result[0] if isinstance(created_receipt_result, list) else created_receipt_result

        # Return all relevant data
        return {'batch_data': created_batch_data, 'coupon_entries': coupon_entries, 'receipt_data': receipt_data_for_return}

    except requests.exceptions.HTTPError as err:
        try: error_msg = err.response.json().get('message', str(err.response.text))
        except: error_msg = str(err)
        st.error(f"Error HTTP al generar lote: {error_msg}")
        return None
    except Exception as e:
        import traceback
        st.error(f"Error inesperado en la creación del lote: {e}\n{traceback.format_exc()}") # More detail for debugging
        return None


# =================================================================
# 3. FUNCIONES DE REPORTES
# =================================================================

def get_activity_report(filters: str):
    """Obtiene el reporte detallado de cupones individuales."""
    token = st.session_state.get('token')
    select_params = (
        "id,consecutive,is_redeemed,redemption_date,invoice_number,creation_date,expiration_date,"
        "base_value_colones,base_value_dolares,"
        "batch:batch_id(id,batch_name,sale_value_basis_crc,sale_value_basis_usd,type:types(type_name),creator:created_by_user_id(username))," # Fetch required batch fields
        "branch:redemption_branch_id(name),"
        "user:redeemed_by_user_id(username)"
    ).replace(' ', '')
    url = f"{POSTGREST_ENDPOINT}/coupons?select={select_params}"
    all_params = [f for f in [filters, "order=creation_date.desc"] if f]
    url_final = url + ("&" + "&".join(all_params) if all_params else "")

    try:
        response = requests.get(url_final, headers=get_headers(token))
        response.raise_for_status()
        data = response.json()
        if not data: return pd.DataFrame()

        df = pd.DataFrame(data)

        # Robust aplanamiento using .get() to avoid errors if nested data is missing
        df['Sucursal Canje'] = df['branch'].apply(lambda x: x.get('name') if isinstance(x, dict) else 'N/A')
        df['Canjeado Por'] = df['user'].apply(lambda x: x.get('username') if isinstance(x, dict) else 'N/A')
        df['Tipo/Campaña'] = df['batch'].apply(lambda x: x.get('type', {}).get('type_name') if isinstance(x, dict) else 'N/A')
        df['Lote'] = df['batch'].apply(lambda x: x.get('batch_name') if isinstance(x, dict) else 'N/A')
        df['Creador Lote'] = df['batch'].apply(lambda x: x.get('creator', {}).get('username') if isinstance(x, dict) else 'N/A')
        df['Valor Pagado Cupón CRC'] = df['batch'].apply(lambda x: pd.to_numeric(x.get('sale_value_basis_crc'), errors='coerce') if isinstance(x, dict) else 0.0).fillna(0.0)
        df['Valor Pagado Cupón USD'] = df['batch'].apply(lambda x: pd.to_numeric(x.get('sale_value_basis_usd'), errors='coerce') if isinstance(x, dict) else 0.0).fillna(0.0)
        df['is_redeemed'] = df['is_redeemed'].astype(bool)

        # Format dates nicely
        for col in ['creation_date', 'expiration_date', 'redemption_date']:
             if col in df.columns:
                 df[col] = pd.to_datetime(df[col], errors='coerce').dt.strftime('%Y-%m-%d %H:%M') # Removed seconds

        # Define final column order and select existing columns
        column_order = [
            'id', 'consecutive', 'is_redeemed', 'creation_date', 'expiration_date',
            'base_value_colones', 'base_value_dolares',
            'Valor Pagado Cupón CRC', 'Valor Pagado Cupón USD',
            'Tipo/Campaña', 'Lote', 'Creador Lote',
            'redemption_date', 'invoice_number', 'Sucursal Canje', 'Canjeado Por'
        ]
        final_columns = [c for c in column_order if c in df.columns]
        return df[final_columns]

    except requests.exceptions.HTTPError as e:
        try: error_msg = e.response.json().get('message', str(e.response.text))
        except: error_msg = str(e)
        st.error(f"Error HTTP cargando reporte cupones: {error_msg}")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Error inesperado cargando reporte cupones: {e}")
        return pd.DataFrame()


def get_batch_report(filters: str = None):
    """Obtiene el reporte resumen de lotes."""
    token = st.session_state.get('token')
    # Include 'id' for linking to receipt later
    select_params = (
        "id,batch_name,creation_date,expiration_date,"
        "consecutive_start,consecutive_end,"
        "total_ref_value_crc,total_ref_value_usd,"
        "total_sale_value_crc,total_sale_value_usd,"
        "creator:created_by_user_id(username),"
        "coupons(count)" # Efficient count via relationship
    ).replace(' ', '')
    url_batches = f"{POSTGREST_ENDPOINT}/batches?select={select_params}&order=creation_date.desc"
    # URL to get redeemed counts efficiently (aggregate)
    url_redeemed_agg = f"{POSTGREST_ENDPOINT}/coupons?select=batch_id&is_redeemed=eq.true" # Fetch all redeemed batch_ids

    try:
        # Get Batch Data
        res_b = requests.get(url_batches, headers=get_headers(token))
        res_b.raise_for_status()
        batches_data = res_b.json()
        if not batches_data: return pd.DataFrame()
        df_b = pd.DataFrame(batches_data)

        # Get Redeemed Data and Count
        res_r = requests.get(url_redeemed_agg, headers=get_headers(token))
        res_r.raise_for_status()
        redeemed_data = res_r.json()
        redeemed_counts = pd.DataFrame(redeemed_data)['batch_id'].value_counts().to_dict() if redeemed_data else {}


        # Process DataFrame
        df_b['Creador'] = df_b['creator'].apply(lambda x: x.get('username') if isinstance(x, dict) else 'N/A')
        # Use the count from relationship if available, else calculate
        df_b['Creados'] = df_b['coupons'].apply(lambda x: x[0]['count'] if isinstance(x, list) and x and 'count' in x[0] else (df_b['consecutive_end'] - df_b['consecutive_start'] + 1))
        df_b['Canjeados'] = df_b['id'].map(redeemed_counts).fillna(0).astype(int)
        today = date.today()
        df_b['exp_date'] = pd.to_datetime(df_b['expiration_date'], errors='coerce').dt.date
        df_b['Vencido?'] = df_b['exp_date'] < today
        df_b['Creado'] = pd.to_datetime(df_b['creation_date'], errors='coerce').dt.strftime('%Y-%m-%d') # Just date
        df_b['Vence'] = pd.to_datetime(df_b['expiration_date'], errors='coerce').dt.strftime('%Y-%m-%d') # Just date

        # Define columns for the final report, including the batch 'id'
        report_columns = {
            'id': 'ID Lote', # Include ID for linking
            'batch_name': 'Nombre Lote', 'Creados': 'Creados', 'Canjeados': 'Canjeados',
            'Vencido?': 'Vencido?', 'consecutive_start': 'Inicio', 'consecutive_end': 'Fin',
            'total_ref_value_crc': 'Ref CRC', 'total_ref_value_usd': 'Ref USD',
            'total_sale_value_crc': 'Venta CRC', 'total_sale_value_usd': 'Venta USD',
            'Creador': 'Creador', 'Creado': 'Creado', 'Vence': 'Vence'
        }
        df_report = df_b[list(report_columns.keys())].rename(columns=report_columns)

        return df_report

    except requests.exceptions.HTTPError as e:
        try: error_msg = e.response.json().get('message', str(e.response.text))
        except: error_msg = str(e)
        st.error(f"Error HTTP cargando reporte lotes: {error_msg}")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Error inesperado cargando reporte lotes: {e}")
        return pd.DataFrame()


def get_receipt_data(receipt_id: int):
    """Obtiene los datos guardados de un recibo por su ID (PK)."""
    token = st.session_state.get('token')
    url = f"{POSTGREST_ENDPOINT}/batch_receipts?id=eq.{receipt_id}&select=*"
    try:
        response = requests.get(url, headers=get_headers(token))
        response.raise_for_status()
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
        response = requests.get(url, headers=get_headers(token))
        response.raise_for_status()
        data = response.json()
        if not data: return pd.DataFrame()

        df = pd.DataFrame(data)
        # Format date and rename for display
        df['created_at'] = pd.to_datetime(df['created_at']).dt.strftime('%Y-%m-%d %H:%M')
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
            with st.form("branch_form", clear_on_submit=True):
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
                with st.expander(f"ID {branch['id']} - {branch['name']}"):
                    # Use unique keys combining prefix and ID for forms inside loops
                    form_key_edit = f"edit_branch_{branch['id']}"
                    with st.form(form_key_edit):
                        new_name = st.text_input("Nombre", value=branch['name'], key=f"name_b_{branch['id']}")
                        new_address = st.text_area("Dirección", value=branch.get('address', ''), key=f"addr_b_{branch['id']}")
                        cols = st.columns(2)
                        with cols[0]: save_clicked = st.form_submit_button("Guardar Cambios", type="primary")
                        with cols[1]: delete_clicked = st.form_submit_button("Eliminar Sucursal")

                        if save_clicked:
                            if update_entry('branches', branch['id'], {'name': new_name, 'address': new_address}):
                                st.success("Actualizado con éxito.")
                                st.rerun() # Rerun to reflect changes
                            # Error message is handled within update_entry

                        if delete_clicked:
                            # Add a confirmation checkbox directly inside the form for deletion
                            st.warning("¡Esta acción es irreversible!")
                            confirm_delete = st.checkbox("Sí, deseo eliminar esta sucursal.", key=f"del_confirm_b_{branch['id']}")
                            if confirm_delete:
                                if delete_entry('branches', branch['id']):
                                    st.success("Sucursal eliminada.")
                                    st.rerun()
                                # Error handled in delete_entry
                            else:
                                st.info("Marque la casilla para confirmar la eliminación.")
        else: st.info("No hay sucursales para editar/eliminar.")

    # --- TIPOS/CAMPAÑAS ---
    with tab_type:
        st.subheader("Administrar Tipos/Campañas de Cupón")
        types_data = get_types()
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### Crear Nuevo Tipo/Campaña")
            with st.form("type_form", clear_on_submit=True):
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
                with st.expander(f"ID {type_item['id']} - {type_item['type_name']}"):
                    with st.form(f"edit_type_{type_item['id']}"):
                        new_name = st.text_input("Nombre", value=type_item['type_name'], key=f"name_t_{type_item['id']}")
                        cols = st.columns(2)
                        with cols[0]: save_clicked = st.form_submit_button("Guardar", type="primary")
                        with cols[1]: delete_clicked = st.form_submit_button("Eliminar")
                        if save_clicked:
                            if update_entry('types', type_item['id'], {'type_name': new_name}): st.success("Actualizado."); st.rerun()
                        if delete_clicked:
                            st.warning("¡Irreversible!")
                            confirm = st.checkbox("Confirmar eliminación.", key=f"del_confirm_t_{type_item['id']}")
                            if confirm:
                                if delete_entry('types', type_item['id']): st.success("Eliminado."); st.rerun()
        else: st.info("No hay tipos/campañas para editar/eliminar.")

    # --- PROMOCIONES ---
    with tab_promo:
        st.subheader("Administrar Promociones/Descuentos")
        promos_data = get_promos()
        with st.form("promo_form", clear_on_submit=True):
             st.markdown("#### Crear Nueva Promoción")
             col1, col2 = st.columns([2,1]) # Wider first column
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
                types = ["Porcentaje", "Valor Fijo", "Producto"]
                idx = 0
                if promo.get('is_cash_value'): idx = 1
                elif promo.get('is_product'): idx = 2
                with st.expander(f"ID {promo['id']} - {promo['type_name']}"):
                    with st.form(f"edit_promo_{promo['id']}"):
                        col_e1, col_e2 = st.columns([2,1])
                        with col_e1:
                            e_name = st.text_input("Nombre", value=promo['type_name'], key=f"pn_{promo['id']}")
                            e_desc = st.text_area("Descripción", value=promo.get('description',''), key=f"pd_{promo['id']}")
                        with col_e2:
                            e_value = st.number_input("Valor", value=float(promo.get('value', 0.0)), min_value=0.0, format="%.2f", key=f"pv_{promo['id']}")
                            e_type = st.radio("Tipo", types, index=idx, key=f"pt_{promo['id']}", horizontal=True)
                        is_p, is_c, is_pr = (e_type == "Porcentaje", e_type == "Valor Fijo", e_type == "Producto")
                        col_p1, col_p2 = st.columns(2)
                        with col_p1: save_button = st.form_submit_button("Guardar", type="primary")
                        with col_p2: delete_button = st.form_submit_button("Eliminar")
                        if save_button:
                            payload = {'type_name': e_name, 'is_percentage': is_p, 'is_cash_value': is_c, 'is_product': is_pr, 'value': e_value, 'description': e_desc}
                            if update_entry('promos', promo['id'], payload): st.success("Actualizado."); st.rerun()
                        if delete_button:
                            st.warning("¡Irreversible!")
                            confirm = st.checkbox("Confirmar eliminación.", key=f"del_confirm_p_{promo['id']}")
                            if confirm:
                                if delete_entry('promos', promo['id']): st.success("Eliminado."); st.rerun()
        else: st.info("No hay promociones para editar/eliminar.")

     # --- VALIDEZ ---
    with tab_validity:
        st.subheader("Administrar Alcances de Validez")
        scopes_data = get_validity_scopes()
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### Crear Nuevo Alcance")
            with st.form("scope_form", clear_on_submit=True):
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
                 with st.expander(f"ID {scope['id']} - {scope['scope_name']}"):
                    with st.form(f"edit_scope_{scope['id']}"):
                        new_name = st.text_input("Nombre", value=scope['scope_name'], key=f"name_s_{scope['id']}")
                        cols = st.columns(2)
                        with cols[0]: save_clicked = st.form_submit_button("Guardar", type="primary")
                        with cols[1]: delete_clicked = st.form_submit_button("Eliminar")
                        if save_clicked:
                            if update_entry('validity_scopes', scope['id'], {'scope_name': new_name}): st.success("Actualizado."); st.rerun()
                        if delete_clicked:
                            st.warning("¡Irreversible!")
                            confirm = st.checkbox("Confirmar eliminación.", key=f"del_confirm_s_{scope['id']}")
                            if confirm:
                                if delete_entry('validity_scopes', scope['id']): st.success("Eliminado."); st.rerun()
        else: st.info("No hay alcances para editar/eliminar.")

    # --- RESTRICCIONES ---
    with tab_restriction:
        st.subheader("Administrar Restricciones")
        restrictions_data = get_restrictions()
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### Crear Nueva Restricción")
            with st.form("restriction_form", clear_on_submit=True):
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
                 with st.expander(f"ID {restriction['id']}"):
                    with st.form(f"edit_restriction_{restriction['id']}"):
                        new_desc = st.text_area("Descripción", value=restriction.get('restriction_description',''), key=f"desc_r_{restriction['id']}")
                        cols = st.columns(2)
                        with cols[0]: save_clicked = st.form_submit_button("Guardar", type="primary")
                        with cols[1]: delete_clicked = st.form_submit_button("Eliminar")
                        if save_clicked:
                            if update_entry('restrictions', restriction['id'], {'restriction_description': new_desc}): st.success("Actualizado."); st.rerun()
                        if delete_clicked:
                            st.warning("¡Irreversible!")
                            confirm = st.checkbox("Confirmar eliminación.", key=f"del_confirm_r_{restriction['id']}")
                            if confirm:
                                if delete_entry('restrictions', restriction['id']): st.success("Eliminado."); st.rerun()
        else: st.info("No hay restricciones para editar/eliminar.")
