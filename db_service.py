# db_service.py (VERSIÓN CORREGIDA - REPORTES + Lotes)
import requests
import streamlit as st
import pandas as pd
import json
import uuid
import auth
from db_config import POSTGREST_ENDPOINT, get_headers
from datetime import datetime, timedelta, date # Importar date


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

    discount_value = promo_data.get('value', 0.0) # Usar .get para evitar error si no existe

    # Convertir discount_value a float por seguridad
    try:
        discount_value = float(discount_value)
    except (ValueError, TypeError):
        discount_value = 0.0

    if promo_data.get('is_percentage'):
        discount = base_value * (discount_value / 100.0)
    elif promo_data.get('is_cash_value'):
        discount = discount_value
    else: # is_product o no definido
        discount = 0.0

    sale_value = base_value - discount
    return round(max(0.0, sale_value), 2) # Aseguramos 2 decimales y no negativo

# --- FUNCIÓN CENTRAL DE CREACIÓN DE LOTE ---
def create_coupon_batch(
    count: int,
    batch_name: str, # <-- NUEVO PARÁMETRO
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

        # --- USAR BATCH NAME PERSONALIZADO O AUTOGENERADO ---
        final_batch_name = batch_name if batch_name else f"{promo_data.get('type_name', 'Lote')}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{batch_uuid[:4]}"

        batch_payload = {
            'id': batch_uuid,
            'batch_name': final_batch_name, # <-- NOMBRE USADO AQUÍ
            'json_qrs': {'count': count, 'promo_description': promo_data.get('description', '')},
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
            'total_sale_value_usd': total_sale_value_usd,

            # Añadir fecha de creación explícita al lote
            'creation_date': datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f%z") # Asegura formato ISO 8601
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
                'promo_type_id': promo_data.get('id'),
                'branch_permissions': allowed_branch_ids,
                'base_value_colones': value_crc,
                'base_value_dolares': value_usd,
                'expiration_date': expiration_date,
                'creation_date': datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f%z") # Asegura formato ISO 8601
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
# 3. FUNCIONES DE REPORTES
# =================================================================

def get_activity_report(filters: str):
    """Obtiene el reporte de actividad de cupones individuales con joins."""
    token = st.session_state.get('token')

    # SELECT expandido para traer toda la info del cupón y su lote
    select_params = (
        "id,consecutive,is_redeemed,redemption_date,invoice_number,creation_date,expiration_date,"
        "base_value_colones,base_value_dolares,"
        "batch:batch_id(*,type:types(type_name),creator:created_by_user_id(username))," # Trae todo de batches, tipo y creador
        "branch:redemption_branch_id(name),"
        "user:redeemed_by_user_id(username)"
    )

    select_params = select_params.replace(' ', '')

    url = f"{POSTGREST_ENDPOINT}/coupons?select={select_params}"

    all_params = []
    if filters:
        all_params.append(filters)

    all_params.append("order=creation_date.desc") # Ordenar por fecha de creación del cupón

    url_final = url + "&" + "&".join(all_params)

    try:
        response = requests.get(url_final, headers=get_headers(token))
        response.raise_for_status()
        data = response.json()

        if data:
            df = pd.DataFrame(data)

            # Aplanamiento de datos
            df['Sucursal Canje'] = df['branch'].apply(lambda x: x['name'] if isinstance(x, dict) else 'N/A')
            df['Canjeado Por'] = df['user'].apply(lambda x: x['username'] if isinstance(x, dict) else 'N/A')
            df['Tipo/Campaña'] = df['batch'].apply(lambda x: x.get('type', {}).get('type_name') if isinstance(x, dict) else 'N/A')
            df['Lote (Batch Name)'] = df['batch'].apply(lambda x: x.get('batch_name') if isinstance(x, dict) else 'N/A')
            df['Creador Lote'] = df['batch'].apply(lambda x: x.get('creator', {}).get('username') if isinstance(x, dict) else 'N/A')
            df['Venta Lote Base (CRC)'] = df['batch'].apply(lambda x: x.get('sale_value_basis_crc') if isinstance(x, dict) else 0.0) # Valor venta individual
            df['Venta Lote Base (USD)'] = df['batch'].apply(lambda x: x.get('sale_value_basis_usd') if isinstance(x, dict) else 0.0) # Valor venta individual

            df['is_redeemed'] = df['is_redeemed'].astype(bool)

            # Convertir fechas a formato legible si es necesario (opcional)
            for col in ['creation_date', 'expiration_date', 'redemption_date']:
                 if col in df.columns:
                     df[col] = pd.to_datetime(df[col]).dt.strftime('%Y-%m-%d %H:%M:%S')


            # Reordenar columnas para el reporte de cupones
            column_order = [
                'id', 'consecutive', 'is_redeemed', 'creation_date', 'expiration_date',
                'base_value_colones', 'base_value_dolares',
                'Venta Lote Base (CRC)', 'Venta Lote Base (USD)', # Precio venta individual
                'Tipo/Campaña', 'Lote (Batch Name)', 'Creador Lote',
                'redemption_date', 'invoice_number', 'Sucursal Canje', 'Canjeado Por'
            ]

            final_columns = [col for col in column_order if col in df.columns]
            return df[final_columns]

        return pd.DataFrame()

    except requests.exceptions.HTTPError as e:
        try:
            error_msg = e.response.json().get('message', str(e))
        except:
            error_msg = str(e)
        st.error(f"Error al cargar el reporte de cupones (HTTP): {error_msg}")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Error inesperado al cargar el reporte de cupones: {e}")
        return pd.DataFrame()


# --- ¡NUEVA FUNCIÓN PARA REPORTE DE LOTES! ---
def get_batch_report(filters: str = None):
    """Obtiene el reporte resumen de lotes."""
    token = st.session_state.get('token')

    # 1. Obtener datos de batches con JOINs
    select_params = (
        "id,batch_name,creation_date,expiration_date,"
        "consecutive_start,consecutive_end,"
        "total_ref_value_crc,total_ref_value_usd,"
        "total_sale_value_crc,total_sale_value_usd,"
        "creator:created_by_user_id(username),"
        "coupons(count)" # Contar todos los cupones por lote
    )
    select_params = select_params.replace(' ', '')
    url_batches = f"{POSTGREST_ENDPOINT}/batches?select={select_params}&order=creation_date.desc"

    # 2. Obtener conteo de cupones canjeados por lote
    # Usamos una función RPC o una vista agregada sería más eficiente, pero
    # por simplicidad, podemos obtener todos los canjeados y agrupar en pandas.
    url_redeemed = f"{POSTGREST_ENDPOINT}/coupons?select=batch_id&is_redeemed=eq.true"

    try:
        # Obtener datos de Lotes
        response_batches = requests.get(url_batches, headers=get_headers(token))
        response_batches.raise_for_status()
        batches_data = response_batches.json()

        if not batches_data:
            return pd.DataFrame() # No hay lotes

        df_batches = pd.DataFrame(batches_data)

        # Obtener datos de Canjeados
        response_redeemed = requests.get(url_redeemed, headers=get_headers(token))
        response_redeemed.raise_for_status()
        redeemed_data = response_redeemed.json()

        # Contar canjeados por batch_id
        redeemed_counts = {}
        if redeemed_data:
            df_redeemed = pd.DataFrame(redeemed_data)
            redeemed_counts = df_redeemed.groupby('batch_id').size().to_dict()

        # Aplanar y añadir datos calculados
        df_batches['Creador Lote'] = df_batches['creator'].apply(lambda x: x['username'] if isinstance(x, dict) else 'N/A')
        # Contar cupones creados (más fiable que usar start/end si hay gaps)
        df_batches['Cupones Creados'] = df_batches['coupons'].apply(lambda x: x[0]['count'] if isinstance(x, list) and len(x)>0 else 0)
        df_batches['Cupones Canjeados'] = df_batches['id'].map(redeemed_counts).fillna(0).astype(int)

        # Calcular si está vencido
        today = date.today() # Usar date para comparar solo la fecha
        # Convertir expiration_date a objeto date
        df_batches['expiration_date_obj'] = pd.to_datetime(df_batches['expiration_date']).dt.date
        df_batches['Vencido?'] = df_batches['expiration_date_obj'] < today

        # Formatear fechas para mostrar
        df_batches['Fecha Creación'] = pd.to_datetime(df_batches['creation_date']).dt.strftime('%Y-%m-%d')
        df_batches['Fecha Vencimiento'] = pd.to_datetime(df_batches['expiration_date']).dt.strftime('%Y-%m-%d')


        # Seleccionar y renombrar columnas finales
        report_columns = {
            'batch_name': 'Nombre Lote',
            'Cupones Creados': 'Creados',
            'Cupones Canjeados': 'Canjeados',
            'Vencido?': 'Vencido?',
            'consecutive_start': 'Consec. Inicial',
            'consecutive_end': 'Consec. Final',
            'total_ref_value_crc': 'Ref. Total (CRC)',
            'total_ref_value_usd': 'Ref. Total (USD)',
            'total_sale_value_crc': 'Venta Total (CRC)',
            'total_sale_value_usd': 'Venta Total (USD)',
            'Creador Lote': 'Creador',
            'Fecha Creación': 'Creado',
            'Fecha Vencimiento': 'Vence'
        }

        df_report = df_batches[list(report_columns.keys())].rename(columns=report_columns)

        return df_report

    except requests.exceptions.HTTPError as e:
        try:
            error_msg = e.response.json().get('message', str(e))
        except:
            error_msg = str(e)
        st.error(f"Error al cargar el reporte de lotes (HTTP): {error_msg}")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Error inesperado al cargar el reporte de lotes: {e}")
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

    tab_branch, tab_type, tab_promo, tab_validity, tab_restriction = st.tabs([
        "Sucursales",
        "Tipos/Campañas",
        "Promociones/Descuentos",
        "Validez de Cupón",
        "Restricciones"
    ])

    # --- SUCURSALES ---
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
                    if create_branch(branch_name, branch_address): st.rerun()
                elif submitted: st.warning("El nombre es obligatorio.")
        with col2:
            st.markdown("#### Lista Completa")
            if branches_data: st.dataframe(pd.DataFrame(branches_data), use_container_width=True)
            else: st.info("No hay sucursales.")
        st.markdown("--- \n #### Editar / Eliminar Sucursales")
        if branches_data:
            for branch in branches_data:
                with st.expander(f"ID {branch['id']} - {branch['name']}"):
                    with st.form(f"edit_branch_{branch['id']}"):
                        new_name = st.text_input("Nombre", value=branch['name'], key=f"name_{branch['id']}")
                        new_address = st.text_area("Dirección", value=branch.get('address', ''), key=f"address_{branch['id']}")
                        col_b1, col_b2 = st.columns(2)
                        with col_b1: save_button = st.form_submit_button("Guardar", type="primary")
                        with col_b2: delete_button = st.form_submit_button("Eliminar", type="secondary")
                        if save_button and update_entry('branches', branch['id'], {'name': new_name, 'address': new_address}): st.success("Actualizado."); st.rerun()
                        if delete_button:
                            confirm_delete = st.checkbox("Confirmar", key=f"cbd_{branch['id']}")
                            if confirm_delete and delete_entry('branches', branch['id']): st.success("Eliminado."); st.rerun()
                            elif confirm_delete: st.error("No se pudo eliminar.")
        else: st.info("Nada para editar.")

    # --- TIPOS/CAMPAÑAS ---
    with tab_type:
        st.subheader("Administrar Tipos/Campañas de Cupón")
        types_data = get_types()
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### Crear Nuevo Tipo/Campaña")
            with st.form("type_form"):
                type_name = st.text_input("Nombre (Ej: Marketing)")
                submitted = st.form_submit_button("Crear", type="primary")
                if submitted and type_name:
                    if create_type(type_name): st.rerun()
                elif submitted: st.warning("El nombre es obligatorio.")
        with col2:
            st.markdown("#### Lista Completa")
            if types_data: st.dataframe(pd.DataFrame(types_data).rename(columns={'type_name': 'Nombre'}), use_container_width=True)
            else: st.info("No hay tipos.")
        st.markdown("--- \n #### Editar / Eliminar Tipos/Campañas")
        if types_data:
            for type_item in types_data:
                with st.expander(f"ID {type_item['id']} - {type_item['type_name']}"):
                     with st.form(f"edit_type_{type_item['id']}"):
                        new_name = st.text_input("Nombre", value=type_item['type_name'], key=f"name_t{type_item['id']}")
                        col_i1, col_i2 = st.columns(2)
                        with col_i1: save_button = st.form_submit_button("Guardar", type="primary")
                        with col_i2: delete_button = st.form_submit_button("Eliminar", type="secondary")
                        if save_button and update_entry('types', type_item['id'], {'type_name': new_name}): st.success("Actualizado."); st.rerun()
                        if delete_button:
                            confirm_delete = st.checkbox("Confirmar", key=f"cdt_{type_item['id']}")
                            if confirm_delete and delete_entry('types', type_item['id']): st.success("Eliminado."); st.rerun()
                            elif confirm_delete: st.error("No se pudo eliminar.")
        else: st.info("Nada para editar.")

    # --- PROMOCIONES/DESCUENTOS ---
    with tab_promo:
        st.subheader("Administrar Promociones/Descuentos")
        promos_data = get_promos()
        with st.form("promo_form"):
             st.markdown("#### Crear Nueva Promoción/Descuento")
             col1, col2, col3 = st.columns(3)
             with col1: promo_name = st.text_input("Nombre (Ej: 20% Bebidas)")
             with col2: promo_value = st.number_input("Valor (20 para 20%, 5000 para ₡5000)", min_value=0.0, format="%.2f")
             with col3: value_type = st.radio("Tipo Valor", ["Porcentaje", "Valor Fijo", "Producto"])
             promo_description = st.text_area("Descripción Detallada (para canje)")
             submitted = st.form_submit_button("Crear", type="primary")
             if submitted and promo_name and promo_description:
                 is_p, is_c, is_pr = (value_type == "Porcentaje", value_type == "Valor Fijo", value_type == "Producto")
                 if create_promo(promo_name, is_p, is_c, is_pr, promo_value, promo_description): st.rerun()
             elif submitted: st.warning("Nombre y descripción son obligatorios.")
        st.markdown("--- \n #### Promociones Existentes")
        if promos_data: st.dataframe(pd.DataFrame(promos_data), use_container_width=True)
        else: st.info("No hay promociones.")
        st.markdown("--- \n #### Editar / Eliminar Promociones")
        if promos_data:
            for promo in promos_data:
                types = ["Porcentaje", "Valor Fijo", "Producto"]
                idx = 0
                if promo.get('is_cash_value'): idx = 1
                elif promo.get('is_product'): idx = 2
                with st.expander(f"ID {promo['id']} - {promo['type_name']}"):
                    with st.form(f"edit_promo_{promo['id']}"):
                        col_e1, col_e2 = st.columns(2)
                        with col_e1:
                            e_name = st.text_input("Nombre", value=promo['type_name'], key=f"pn_{promo['id']}")
                            e_desc = st.text_area("Descripción", value=promo.get('description',''), key=f"pd_{promo['id']}")
                        with col_e2:
                            e_value = st.number_input("Valor", value=float(promo.get('value', 0.0)), min_value=0.0, format="%.2f", key=f"pv_{promo['id']}")
                            e_type = st.radio("Tipo Valor", types, index=idx, key=f"pt_{promo['id']}")
                        is_p, is_c, is_pr = (e_type == "Porcentaje", e_type == "Valor Fijo", e_type == "Producto")
                        col_p1, col_p2 = st.columns(2)
                        with col_p1: save_button = st.form_submit_button("Guardar", type="primary")
                        with col_p2: delete_button = st.form_submit_button("Eliminar", type="secondary")
                        if save_button:
                            payload = {'type_name': e_name, 'is_percentage': is_p, 'is_cash_value': is_c, 'is_product': is_pr, 'value': e_value, 'description': e_desc}
                            if update_entry('promos', promo['id'], payload): st.success("Actualizado."); st.rerun()
                        if delete_button:
                            confirm_delete = st.checkbox("Confirmar", key=f"cdp_{promo['id']}")
                            if confirm_delete and delete_entry('promos', promo['id']): st.success("Eliminado."); st.rerun()
                            elif confirm_delete: st.error("No se pudo eliminar.")
        else: st.info("Nada para editar.")

    # --- VALIDEZ ---
    with tab_validity:
        st.subheader("Administrar Alcances de Validez")
        scopes_data = get_validity_scopes()
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### Crear Nuevo Alcance")
            with st.form("scope_form"):
                scope_name = st.text_input("Nombre (Ej: Solo Comida)")
                submitted = st.form_submit_button("Crear", type="primary")
                if submitted and scope_name:
                    if create_validity_scope(scope_name): st.rerun()
                elif submitted: st.warning("El nombre es obligatorio.")
        with col2:
            st.markdown("#### Lista Completa")
            if scopes_data: st.dataframe(pd.DataFrame(scopes_data).rename(columns={'scope_name': 'Nombre'}), use_container_width=True)
            else: st.info("No hay alcances.")
        st.markdown("--- \n #### Editar / Eliminar Alcances")
        if scopes_data:
            for scope in scopes_data:
                 with st.expander(f"ID {scope['id']} - {scope['scope_name']}"):
                    with st.form(f"edit_scope_{scope['id']}"):
                        new_name = st.text_input("Nombre", value=scope['scope_name'], key=f"name_s{scope['id']}")
                        col_s1, col_s2 = st.columns(2)
                        with col_s1: save_button = st.form_submit_button("Guardar", type="primary")
                        with col_s2: delete_button = st.form_submit_button("Eliminar", type="secondary")
                        if save_button and update_entry('validity_scopes', scope['id'], {'scope_name': new_name}): st.success("Actualizado."); st.rerun()
                        if delete_button:
                            confirm_delete = st.checkbox("Confirmar", key=f"cds_{scope['id']}")
                            if confirm_delete and delete_entry('validity_scopes', scope['id']): st.success("Eliminado."); st.rerun()
                            elif confirm_delete: st.error("No se pudo eliminar.")
        else: st.info("Nada para editar.")

    # --- RESTRICCIONES ---
    with tab_restriction:
        st.subheader("Administrar Restricciones")
        restrictions_data = get_restrictions()
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### Crear Nueva Restricción")
            with st.form("restriction_form"):
                desc = st.text_area("Descripción (Ej: No Feriados)")
                submitted = st.form_submit_button("Crear", type="primary")
                if submitted and desc:
                    if create_restriction(desc): st.rerun()
                elif submitted: st.warning("La descripción es obligatoria.")
        with col2:
            st.markdown("#### Lista Completa")
            if restrictions_data: st.dataframe(pd.DataFrame(restrictions_data).rename(columns={'restriction_description': 'Descripción'}), use_container_width=True)
            else: st.info("No hay restricciones.")
        st.markdown("--- \n #### Editar / Eliminar Restricciones")
        if restrictions_data:
             for restriction in restrictions_data:
                 with st.expander(f"ID {restriction['id']}"):
                    with st.form(f"edit_restriction_{restriction['id']}"):
                        new_desc = st.text_area("Descripción", value=restriction.get('restriction_description',''), key=f"desc_r{restriction['id']}")
                        col_r1, col_r2 = st.columns(2)
                        with col_r1: save_button = st.form_submit_button("Guardar", type="primary")
                        with col_r2: delete_button = st.form_submit_button("Eliminar", type="secondary")
                        if save_button and update_entry('restrictions', restriction['id'], {'restriction_description': new_desc}): st.success("Actualizado."); st.rerun()
                        if delete_button:
                            confirm_delete = st.checkbox("Confirmar", key=f"cdr_{restriction['id']}")
                            if confirm_delete and delete_entry('restrictions', restriction['id']): st.success("Eliminado."); st.rerun()
                            elif confirm_delete: st.error("No se pudo eliminar.")
        else: st.info("Nada para editar.")
