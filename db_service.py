# db_service.py
from db_config import supabase
import streamlit as st
import pandas as pd

# --- Funciones de Lectura General ---

def get_data_table(table_name: str):
    """Obtiene todos los datos de una tabla específica."""
    try:
        response = supabase.from_(table_name).select('*').execute()
        return response.data
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

# --- Funciones de Creación (Administración de Metadata) ---

def create_branch(name: str, address: str):
    """Inserta una nueva sucursal."""
    try:
        data, count = supabase.from_('branches').insert({'name': name, 'address': address}).execute()
        if count:
            st.success(f"Sucursal '{name}' creada con éxito.")
            return True
        return False
    except Exception as e:
        st.error(f"Error al crear sucursal: {e}")
        return False

def create_issuer(name: str):
    """Inserta un nuevo emisor."""
    try:
        data, count = supabase.from_('issuers').insert({'issuer_name': name}).execute()
        if count:
            st.success(f"Emisor '{name}' creado con éxito.")
            return True
        return False
    except Exception as e:
        st.error(f"Error al crear emisor: {e}")
        return False

def create_promo(type_name: str, is_percentage: bool, is_cash_value: bool, is_product: bool, value: float, description: str):
    """Inserta un nuevo tipo de promoción."""
    try:
        data, count = supabase.from_('promos').insert({
            'type_name': type_name, 
            'is_percentage': is_percentage, 
            'is_cash_value': is_cash_value, 
            'is_product': is_product, 
            'value': value, 
            'description': description
        }).execute()
        if count:
            st.success(f"Promoción '{type_name}' creada con éxito.")
            return True
        return False
    except Exception as e:
        st.error(f"Error al crear promoción: {e}")
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
            st.markdown("#### Sucursales Existentes")
            branches_data = get_branches()
            if branches_data:
                df_branches = pd.DataFrame(branches_data)
                st.dataframe(df_branches, use_container_width=True)
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
