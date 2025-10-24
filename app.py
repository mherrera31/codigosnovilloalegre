# app.py (VERSIÓN FINAL - Descarga JPG Individual)
import streamlit as st
import auth 
import db_service
import user_service
import requests 

# --- Imports para la funcionalidad de QR/PDF ---
import qrcode 
from PIL import Image, ImageDraw, ImageFont 
import uuid
import os
from datetime import datetime, timedelta
import pandas as pd
from pyzbar.pyzbar import decode
from fpdf import FPDF 
from db_config import get_headers 

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Sistema de QR Novillo Alegre", layout="wide")

LOGO_URL = "https://placehold.co/300x100/1E3260/FFFFFF/png?text=Novillo+Alegre+QR"

# --- CONFIGURACIÓN DE RUTAS ---
TEMPLATE_DIR = 'design_templates'
os.makedirs(TEMPLATE_DIR, exist_ok=True)
TEMPLATE_PATH_KEY = 'current_template_path'

# Inicializa la ruta de la plantilla si no existe
if TEMPLATE_PATH_KEY not in st.session_state:
    st.session_state[TEMPLATE_PATH_KEY] = None

# --- DIMENSIONES Y CONSTANTES CLAVE ---
# Dimensiones de la tarjeta: 9 cm de ANCHO x 5 cm de ALTO
# A 300 DPI:
# 9 cm * (300 px / 2.54 cm) = 1062.99 px -> ~1063 px
# 5 cm * (300 px / 2.54 cm) = 590.55 px -> ~591 px

CARD_WIDTH_PX = 1063  # Ancho en píxeles (HORIZONTAL)
CARD_HEIGHT_PX = 591  # Alto en píxeles (VERTICAL)

# Dimensiones en MM para PDF
CARD_WIDTH_MM = 90
CARD_HEIGHT_MM = 50

QR_SIZE_PX = 250 # Tamaño del QR en píxeles
BORDER_PX = 50   # Margen de seguridad


# ----------------------------------------
# FUNCIONES AUXILIARES (QR y PDF) - CORRECCIÓN DE POSICIONAMIENTO Y ORIENTACIÓN
# ----------------------------------------

def create_qr_card(data_to_encode: str, output_path: str, description: str, expiration: str, consecutive: str):
    """
    Genera una imagen de tarjeta (9cm ANCHO x 5cm ALTO @ 300DPI) con el QR y el consecutivo.
    AJUSTE CRÍTICO: Se corrigieron las coordenadas para asegurar la visibilidad del QR
    y la orientación horizontal de la tarjeta.
    """
    if not os.path.exists('generated_qrs'):
        os.makedirs('generated_qrs')
        
    # Usar las dimensiones fijas para la tarjeta horizontal
    card_img = Image.new('RGB', (CARD_WIDTH_PX, CARD_HEIGHT_PX), (255, 255, 255))
    draw = ImageDraw.Draw(card_img) 
    
    # 1. DIBUJO DE ENCABEZADO
    # Banda roja superior
    draw.rectangle([0, 0, CARD_WIDTH_PX, 80], fill=(191, 2, 2)) # Ancho completo, 80px de alto
    
    try:
        title_font = ImageFont.truetype("arialbd.ttf", size=32)
        main_font = ImageFont.truetype("arial.ttf", size=30)
        consecutive_font = ImageFont.truetype("arialbd.ttf", size=40)
    except IOError:
        # Fallback si las fuentes no se encuentran
        default_font = ImageFont.load_default()
        title_font = default_font 
        main_font = default_font
        consecutive_font = default_font
        
    draw.text((30, 25), "TARJETA DE REGALO NOVILLO ALEGRE", fill=(255,255,255), font=title_font)

    # 2. GENERACIÓN DEL QR
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=8, border=2)
    qr.add_data(data_to_encode)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
    
    # 3. POSICIONES Y DIBUJO DE CONTENIDO
    # El QR debe estar en la esquina superior derecha (con un margen)
    # Posición X: Ancho de la tarjeta - Tamaño del QR - Margen
    # Posición Y: Margen superior (para no chocar con la banda roja)
    
    # ¡¡CORRECCIÓN CLAVE!!
    QR_POSITION_X = CARD_WIDTH_PX - QR_SIZE_PX - BORDER_PX # (1063 - 250 - 50 = 763)
    QR_POSITION_Y = 100 # (Debajo de la banda roja de 80px)

    # Posiciones de texto para que no se superpongan
    PROMO_DESCRIPTION_POSITION = (BORDER_PX, 150) # (50, 150)
    EXPIRATION_POSITION = (BORDER_PX, 250) # (50, 250)
    CONSECUTIVE_POSITION = (BORDER_PX, 480) # (50, 480) - Cerca del fondo

    # Dibujar Promoción
    draw.text(PROMO_DESCRIPTION_POSITION, description, fill=(0,0,0), font=main_font)
    
    # Dibujar Válido hasta
    draw.text(EXPIRATION_POSITION, f"Válido hasta: {expiration}", fill=(100, 100, 100), font=main_font)

    # Dibujar Consecutivo
    draw.text(CONSECUTIVE_POSITION, f"CONSECUTIVO: {consecutive}", fill=(0, 0, 0), font=consecutive_font)

    # 4. PEGAR EL QR ESCALADO Y POSICIONADO CORRECTAMENTE
    # ¡¡ESTA ES LA LÍNEA QUE DIBUJA EL QR!!
    qr_scaled = qr_img.resize((QR_SIZE_PX, QR_SIZE_PX))
    card_img.paste(qr_scaled, (QR_POSITION_X, QR_POSITION_Y))
    
    # CAMBIO: Guardar como JPG de alta calidad
    card_img.save(output_path, "JPEG", quality=95)
    return output_path
    
# =========================================================================
# FUNCIÓN DE PDF ELIMINADA (generate_pdf_from_images ya no se necesita)
# =========================================================================

def generate_design_template(output_filename):
    """Genera una plantilla de PDF con espacio blanco para el arte, QR y consecutivo (9x5 cm horizontal)."""
    # ¡¡CORRECCIÓN CLAVE!! Orientación 'L' para Landscape (horizontal)
    pdf = FPDF(orientation='L', unit='mm', format=(CARD_WIDTH_MM, CARD_HEIGHT_MM))
    pdf.add_page()
    
    pdf.set_font("Arial", "B", 8)
    pdf.cell(CARD_WIDTH_MM, 5, "PLANTILLA DE DISEÑO HORIZONTAL (9x5 CM)", 0, 1, 'C')
    
    # Coordenadas en MM para el espacio del QR
    QR_POS_X_MM = 60 
    QR_POS_Y_MM = 15 
    QR_DIM_MM = 25 
    
    pdf.set_fill_color(255, 255, 255)
    pdf.rect(QR_POS_X_MM, QR_POS_Y_MM, QR_DIM_MM, QR_DIM_MM, 'F') 
    
    pdf.set_text_color(150, 150, 150)
    pdf.set_font("Arial", "", 6)
    pdf.set_xy(QR_POS_X_MM, QR_POS_Y_MM + 1)
    pdf.multi_cell(QR_DIM_MM, 2.5, "ESPACIO QR\n2.5x2.5 cm", 0, 'C')
    
    # Indicador de espacio para el consecutivo
    CONSECUTIVE_POS_X_MM = 5
    CONSECUTIVE_POS_Y_MM = 40
    pdf.set_xy(CONSECUTIVE_POS_X_MM, CONSECUTIVE_POS_Y_MM)
    pdf.multi_cell(QR_POS_X_MM - CONSECUTIVE_POS_X_MM - 5, 3, "ESPACIO PARA DESCRIPCIÓN Y CONSECUTIVO", 0, 'L')


    pdf.output(output_filename)


# ----------------------------------------
# LÓGICA DE INICIALIZACIÓN Y CONTROL DE ACCESO
# ----------------------------------------

# Inicializa el estado de la sesión
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'user_role' not in st.session_state:
    st.session_state['user_role'] = None
if 'branch_id' not in st.session_state:
    st.session_state['branch_id'] = None

# ----------------------------------------
# LOGIN GATE
# ----------------------------------------

if not auth.is_authenticated():
    st.image(LOGO_URL, width=300) 
    st.title("QR-CReator (Inicie Sesion)")
    auth.login_ui()
    st.stop()
    
# ----------------------------------------
# BARRA LATERAL (SIDEBAR) Y NAVEGACIÓN
# ----------------------------------------

# Mostrar Logo en la página principal y título
st.image(LOGO_URL, width=300) 
st.title("QR-Creator")

# Información del usuario en la barra lateral
user = auth.get_current_user()
user_role = auth.get_user_role()

with st.sidebar:
    st.sidebar.header("Menú de Navegación")
    
    if user_role:
        st.success(f"**Usuario:** {st.session_state.get('username', user.get('email', 'N/A'))}")
        st.success(f"**Rol:** {user_role}")
        
        menu_options = ["🏠 Dashboard"]
        
        if user_role == 'Admin':
            menu_options.extend(["🔑 Gestión de Usuarios (Admin)", "⚙️ Configuración (Admin)", "📊 Reportes (Admin)"])
        
        if user_role in ['Admin', 'Creator']:
            menu_options.append("🛠️ Creador de QRs")
        
        if user_role in ['Admin', 'Cashier']:
            menu_options.append("📲 Escáner (Cajero)")
            
        app_mode = st.sidebar.radio("Seleccione el módulo", menu_options)

        st.markdown("---")
        if st.button("Cerrar Sesión", key="logout_btn"):
            auth.sign_out()
    else:
        st.error("Error al cargar rol. Favor reintentar.")
        auth.sign_out()
        st.stop()


# ----------------------------------------
# RENDERIZACIÓN DE MÓDULOS
# ----------------------------------------

if app_mode == "🏠 Dashboard":
    st.header("Bienvenido al Sistema Novillo Alegre")
    st.info(f"Su rol actual es **{user_role}**. Utilice el menú de la izquierda para navegar.")

elif app_mode == "🔑 Gestión de Usuarios (Admin)":
    user_service.render_user_management() 

elif app_mode == "⚙️ Configuración (Admin)":
    db_service.render_config_management()
    
# --- MÓDULO CREADOR DE QRS (MIGRADO A SUPABASE) ---

elif app_mode == "🛠️ Creador de QRs":
    
    promos = db_service.get_promos()
    branches = db_service.get_branches()
    types = db_service.get_types() 
    scopes = db_service.get_validity_scopes() 
    restrictions = db_service.get_restrictions() 

    promo_options = {p['type_name']: p for p in promos}
    branch_options = [b['name'] for b in branches]
    type_options = {t['type_name']: t['id'] for t in types} 
    scope_options = {s['scope_name']: s['id'] for s in scopes} 
    restriction_options = {r['restriction_description']: r['id'] for r in restrictions} 

    
    # --- Interfaz de Pestañas ---
    tab_creator, tab_template = st.tabs(["Generador de Lote", "Gestión de Plantilla"])
    
    with tab_creator:
        st.header("Módulo de Creación de Tarjetas QR")
        
        with st.form("qr_creator_form"):
            st.subheader("Configuración de la Tarjeta")
            
            col1, col2 = st.columns(2)
            with col1:
                selected_promo_name = st.selectbox("Seleccionar Promoción/Diseño (Determina el Descuento)", options=list(promo_options.keys()))
                selected_promo = promo_options.get(selected_promo_name)
                
                st.caption(f"Descripción para el canje: {selected_promo.get('description', 'N/A')}")
                
                # Input de Valor Base
                value_crc = st.number_input("Valor Base del Cupón (Colones)", value=selected_promo.get('value', 0.0), min_value=0.0, format="%.2f")
                value_usd = st.number_input("Valor Base del Cupón (Dólares)", value=round(selected_promo.get('value', 0.0) / 590, 2), min_value=0.0, format="%.2f")

                # Cálculo y Muestra del Valor de Venta (Feedback)
                if selected_promo:
                    sale_value_crc = db_service.calculate_sale_value(value_crc, selected_promo)
                    sale_value_usd = db_service.calculate_sale_value(value_usd, selected_promo)
                    
                    st.markdown(f"**Valor de Venta (CRC):** ₡{sale_value_crc:,.2f}")
                    st.markdown(f"**Valor de Venta (USD):** ${sale_value_usd:,.2f}")

            with col2:
                # Dropdown de meses de vigencia
                valid_months = st.selectbox("Meses de vigencia", options=[3, 6, 9, 12], index=0)
                
                # Selector de Tipo/Campaña
                selected_type_name = st.selectbox("Tipo/Campaña (Define el Uso)", options=list(type_options.keys()))
                
                # Selectores de Validez y Restricciones
                allowed_branches = st.multiselect("Sucursales permitidas (dejar vacío para todas)", options=branch_options)
                selected_scope_names = st.multiselect("Validez de Cupón (Alcances permitidos)", options=list(scope_options.keys()))
                selected_restriction_names = st.multiselect("Restricciones Aplicadas", options=list(restriction_options.keys()))

                count = st.number_input("Cantidad de tarjetas a generar (lote)", min_value=1, max_value=100, value=1)
                
            submitted = st.form_submit_button("🚀 Generar Tarjetas", type="primary")

        if submitted:
            type_id = type_options.get(selected_type_name) 
            user_id = st.session_state.get('user_id')
            
            # Obtener IDs de las selecciones
            selected_scope_ids = [scope_options[name] for name in selected_scope_names]
            selected_restriction_ids = [restriction_options[name] for name in selected_restriction_names]
            
            if not selected_promo or not type_id or not user_id:
                st.error("Faltan datos de configuración (Promoción o Tipo/Campaña).")
            else:
                st.success(f"Generando {count} tarjeta(s)...")
                
                coupon_entries = db_service.create_coupon_batch(
                    count=count,
                    promo_data=selected_promo, 
                    value_crc=value_crc,
                    value_usd=value_usd,
                    type_id=type_id,
                    months_valid=valid_months, 
                    branch_names=allowed_branches,
                    scope_ids=selected_scope_ids, 
                    restriction_ids=selected_restriction_ids, 
                    user_id=user_id
                )
                
                if coupon_entries:
                    st.balloons()
                    generated_image_paths = []
                    
                    # Loop 1: Generar todas las imágenes JPG
                    for entry in coupon_entries:
                        unique_id = entry['id']
                        consecutive = str(entry['consecutive']).zfill(4) 
                        expiration = entry['expiration_date']
                        
                        # ¡¡CAMBIO CLAVE A JPG!!
                        output_path = os.path.join('generated_qrs', f"{unique_id}.jpg")
                        
                        # LLAMADA A LA FUNCIÓN CORREGIDA create_qr_card
                        create_qr_card(unique_id, output_path, selected_promo['description'], expiration, consecutive)
                        # Guardar el path Y el consecutivo para el botón de descarga
                        generated_image_paths.append((output_path, consecutive))
                        
                    
                    # =======================================================
                    # ¡¡CAMBIO CLAVE: Sección de Descarga JPG!!
                    # =======================================================
                    st.subheader("⬇️ Descargar Tarjetas Individuales (JPG)")
                    st.info(f"Se generaron {len(generated_image_paths)} tarjetas.")

                    # Usar columnas para mostrar los botones de descarga
                    cols = st.columns(3) 
                    
                    for idx, (path, consecutive) in enumerate(generated_image_paths):
                        with open(path, "rb") as file:
                            # Colocar cada botón en una columna (ciclo 0, 1, 2, 0, 1, 2...)
                            cols[idx % 3].download_button(
                                label=f"Descargar Consecutivo {consecutive}",
                                data=file,
                                file_name=os.path.basename(path),
                                mime="image/jpeg", # Mime-type para JPG
                                key=f"jpg_dl_{consecutive}" # Clave única
                            )
                    
                    # =======================================================
                    # SECCIÓN DE PDF ELIMINADA
                    # =======================================================


    # ----------------------------------------
    # GESTIÓN Y DESCARGA DE PLANTILLAS DE DISEÑO (Actualizada para orientación horizontal)
    # ----------------------------------------
    with tab_template:
        st.header("Gestión de Plantilla para Arte y Diseño")
        
        # 1. DESCARGA DE LA GUÍA DE ESPACIOS
        st.subheader("1. Guía de Espacios (Para el Diseñador)")
        st.markdown("Use esta guía para crear su arte y dejar el espacio libre para el QR y el consecutivo. **Orientación Horizontal (9x5 cm).**")
        
        BLANK_PDF_PATH = os.path.join(TEMPLATE_DIR, "plantilla_guia_horizontal_9x5.pdf")
        if st.button("Descargar Guía PDF (9x5 cm)", key="download_guide"):
            generate_design_template(BLANK_PDF_PATH)
            with open(BLANK_PDF_PATH, "rb") as pdf_file:
                st.download_button(
                    label="Descargar Guía de Diseño (PDF)",
                    data=pdf_file,
                    file_name=BLANK_PDF_PATH,
                    mime="application/pdf"
                )
    
        st.markdown("---")
        
        # 2. CARGA DE LA PLANTILLA DE ARTE (PDF)
        st.subheader("2. Subir Plantilla de Arte (PDF Terminado)")
        
        uploaded_file = st.file_uploader(
            "Suba el PDF de Diseño (Arte Terminado, 9x5cm, Horizontal) para usar como fondo", 
            type="pdf", 
            key="template_uploader"
        )
        
        if uploaded_file is not None:
            template_filename = "plantilla_arte_activa.pdf"
            save_path = os.path.join(TEMPLATE_DIR, template_filename)
            
            with open(save_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            st.session_state[TEMPLATE_PATH_KEY] = save_path
            st.success(f"Plantilla de Arte cargada exitosamente: {uploaded_file.name}")
            
        if st.session_state[TEMPLATE_PATH_KEY]:
            st.info(f"🎨 **Plantilla Actual:** {os.path.basename(st.session_state[TEMPLATE_PATH_KEY])} (Lista para usar en el Generador de Lote).")
        else:
            st.warning("No hay ninguna plantilla de diseño cargada actualmente. Se usará fondo blanco.")



elif app_mode == "📲 Escáner (Cajero)":
    # Usar el módulo de HTML/PWA
    st.warning("Módulo de escáner migrado a PWA. Presione el botón para abrir la aplicación de canje móvil.")
    
    st.info("Debe configurar la URL del escáner PWA en la sección de código.")
    
    # URL de ejemplo (DEBE SER CAMBIADA POR TU URL ALOJADA)
    PWA_BASE_URL = "https://tudominio.com/scanner.html" 
    st.link_button("Abrir Escáner de Canje", url=PWA_BASE_URL, type="primary")


elif app_mode == "📊 Reportes (Admin)":
    
    if user_role != 'Admin':
        st.error("Acceso denegado. Solo administradores pueden ver reportes.")
        st.stop()
        
    st.header("Módulo de Reportes de Actividad")
    
    st.sidebar.header("Filtros de Reporte")
    
    # --- OBTENER DATOS DE SUPABASE ---
    branches = db_service.get_branches()
    branch_names = [b['name'] for b in branches]
    
    selected_status = st.sidebar.selectbox("Estado", ["Todos", "Canjeados", "No Canjeados"])
    start_date = st.sidebar.date_input("Fecha de creación (desde)", value=None)
    end_date = st.sidebar.date_input("Fecha de creación (hasta)", value=None)

    # Lógica para construir el filtro de PostgREST
    filters = []
    if selected_status == "Canjeados":
        filters.append("is_redeemed=eq.true")
    elif selected_status == "No Canjeados":
        filters.append("is_redeemed=eq.false")
        
    if start_date:
        filters.append(f"creation_date=gte.{start_date}")
    if end_date:
        filters.append(f"creation_date=lte.{end_date}")
    
    df = pd.DataFrame() 
    
    filter_string = "&".join(filters)
    
    # LLAMADA MIGRADA A SUPABASE
    report_data = db_service.get_activity_report(filter_string)
    
    # Reasignar 'df' solo si los datos son válidos
    df = pd.DataFrame() 
    
    # Si report_data es un DataFrame válido (no None y no está vacío), lo asignamos a df.
    if isinstance(report_data, pd.DataFrame) and not report_data.empty:
        df = report_data
    
    st.subheader("Datos Completos")
    st.dataframe(df, width='stretch')

    # Métricas
    if not df.empty:
        # Aseguramos que la columna sea numérica si no lo es (para el .sum())
        df['is_redeemed'] = pd.to_numeric(df['is_redeemed'], errors='coerce').fillna(0)
        
        total_qrs = len(df)
        redeemed_qrs = df['is_redeemed'].sum()
        not_redeemed_qrs = total_qrs - redeemed_qrs
    else:
        total_qrs = redeemed_qrs = not_redeemed_qrs = 0

    col1, col2, col3 = st.columns(3)
    col1.metric("Total de QRs en Filtro", f"{total_qrs} 🎟️")
    col2.metric("Total Canjeados", f"{redeemed_qrs} ✅")
    col3.metric("Pendientes de Canje", f"{not_redeemed_qrs} ⏳")
