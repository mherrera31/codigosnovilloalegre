# app.py (VERSIÓN CORREGIDA - Límite 1000)
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

# --- ¡NUEVOS IMPORTS PARA ZIP! ---
import zipfile
import io

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Sistema de QR Novillo Alegre", layout="wide")

LOGO_URL = "https://placehold.co/300x100/1E3260/FFFFFF/png?text=Novillo+Alegre+QR"

# --- CONFIGURACIÓN DE RUTAS ---
TEMPLATE_DIR = 'design_templates'
os.makedirs(TEMPLATE_DIR, exist_ok=True)
GENERATED_QRS_DIR = 'generated_qrs'
os.makedirs(GENERATED_QRS_DIR, exist_ok=True)

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
    ¡¡MODIFICADO!!: Ahora usa la plantilla PNG subida si existe.
    """

    # ¡¡CAMBIO CLAVE!!: Cargar la plantilla PNG si existe, si no, crear fondo blanco.
    template_path = st.session_state.get(TEMPLATE_PATH_KEY)
    if template_path and os.path.exists(template_path):
        try:
            card_img = Image.open(template_path).convert('RGB')
            # Asegurarse de que la plantilla tenga el tamaño correcto
            if card_img.size != (CARD_WIDTH_PX, CARD_HEIGHT_PX):
                st.warning(f"La plantilla {os.path.basename(template_path)} no tiene el tamaño correcto (1063x591px). Se redimensionará, pero podría verse distorsionada.")
                card_img = card_img.resize((CARD_WIDTH_PX, CARD_HEIGHT_PX))
        except Exception as e:
            st.error(f"Error al cargar la plantilla: {e}. Se usará fondo blanco.")
            card_img = Image.new('RGB', (CARD_WIDTH_PX, CARD_HEIGHT_PX), (255, 255, 255))
    else:
        # Usar fondo blanco por defecto si no hay plantilla
        card_img = Image.new('RGB', (CARD_WIDTH_PX, CARD_HEIGHT_PX), (255, 255, 255))

    draw = ImageDraw.Draw(card_img)

    # 1. DIBUJO DE ENCABEZADO
    # Si no se usa plantilla, dibujar la banda roja.
    if not template_path:
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

    # Si no se usa plantilla, dibujar el título.
    if not template_path:
        draw.text((30, 25), "TARJETA DE REGALO NOVILLO ALEGRE", fill=(255,255,255), font=title_font)

    # 2. GENERACIÓN DEL QR
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=8, border=2)
    qr.add_data(data_to_encode)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert('RGB')

    # 3. POSICIONES Y DIBUJO DE CONTENIDO
    # Posición del QR (Esquina superior derecha)
    QR_POSITION_X = CARD_WIDTH_PX - QR_SIZE_PX - BORDER_PX # (1063 - 250 - 50 = 763)
    QR_POSITION_Y = 100 # (Debajo de la banda roja de 80px)

    # Posiciones de texto (Ajustadas para plantilla o fondo blanco)
    # Si hay plantilla, asumimos que el diseñador dejó espacio para esto.
    # Si no hay plantilla, las posiciones son fijas.

    if template_path:
        # Posiciones asumidas para la plantilla (esquina inferior izquierda)
        PROMO_DESCRIPTION_POSITION = (BORDER_PX, 400)
        EXPIRATION_POSITION = (BORDER_PX, 440)
        CONSECUTIVE_POSITION = (BORDER_PX, 480)
    else:
        # Posiciones estándar sobre fondo blanco
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
    qr_scaled = qr_img.resize((QR_SIZE_PX, QR_SIZE_PX))
    card_img.paste(qr_scaled, (QR_POSITION_X, QR_POSITION_Y))

    # CAMBIO: Guardar como JPG de alta calidad
    card_img.save(output_path, "JPEG", quality=95)
    return output_path

# =========================================================================
# FUNCIÓN DE GUÍA (AHORA GENERA JPG)
# =========================================================================

def generate_design_template(output_filename):
    """
    Genera una plantilla de GUÍA en formato JPG (9x5 cm horizontal).
    """
    # Crear imagen base
    img = Image.new('RGB', (CARD_WIDTH_PX, CARD_HEIGHT_PX), (230, 230, 230)) # Fondo gris claro
    draw = ImageDraw.Draw(img)

    try:
        title_font = ImageFont.truetype("arialbd.ttf", size=40)
        main_font = ImageFont.truetype("arial.ttf", size=24)
    except IOError:
        title_font = main_font = ImageFont.load_default()

    # Título de la guía
    draw.text((BORDER_PX, BORDER_PX), "GUÍA DE DISEÑO HORIZONTAL (1063x591 px)", fill=(0,0,0), font=title_font)

    # --- Definir zonas ---
    # Zona del QR (Esquina superior derecha)
    QR_POS_X = CARD_WIDTH_PX - QR_SIZE_PX - BORDER_PX
    QR_POS_Y = 100
    draw.rectangle(
        [QR_POS_X, QR_POS_Y, QR_POS_X + QR_SIZE_PX, QR_POS_Y + QR_SIZE_PX],
        outline=(255, 0, 0), width=3
    )
    draw.text((QR_POS_X + 10, QR_POS_Y + 10), "ESPACIO PARA QR (250x250 px)", fill=(255,0,0), font=main_font)

    # Zona de Textos (Esquina inferior izquierda)
    TEXT_POS_X = BORDER_PX
    TEXT_POS_Y = 400
    draw.rectangle(
        [TEXT_POS_X, TEXT_POS_Y, CARD_WIDTH_PX - BORDER_PX, CARD_HEIGHT_PX - BORDER_PX],
        outline=(0, 0, 255), width=3
    )
    draw.text((TEXT_POS_X + 10, TEXT_POS_Y + 10), "ESPACIO RECOMENDADO PARA TEXTOS", fill=(0,0,255), font=main_font)
    draw.text((TEXT_POS_X + 10, TEXT_POS_Y + 40), "(Descripción, Validez, Consecutivo)", fill=(0,0,255), font=main_font)

    # Guardar como JPG
    img.save(output_filename, "JPEG", quality=95)


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

                # =======================================================
                # ¡¡CAMBIO CLAVE: max_value a 1000!!
                count = st.number_input("Cantidad de tarjetas a generar (lote)", min_value=1, max_value=1000, value=1)
                # =======================================================

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
                st.info(f"Generando {count} tarjeta(s)...")

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
                        output_path = os.path.join(GENERATED_QRS_DIR, f"{consecutive}.jpg")

                        # LLAMADA A LA FUNCIÓN CORREGIDA create_qr_card
                        create_qr_card(unique_id, output_path, selected_promo['description'], expiration, consecutive)
                        # Guardar el path para el ZIP
                        generated_image_paths.append(output_path)


                    # =======================================================
                    # ¡¡CAMBIO CLAVE: Sección de Descarga ZIP!!
                    # =======================================================
                    st.subheader("⬇️ Descargar Lote Completo (ZIP)")

                    # Crear un buffer de bytes en memoria para el ZIP
                    zip_buffer = io.BytesIO()

                    # Crear el archivo ZIP y añadir todas las imágenes generadas
                    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                        for file_path in generated_image_paths:
                            # Añadir el archivo al ZIP usando solo el nombre del archivo (ej: "0234.jpg")
                            zip_file.write(file_path, os.path.basename(file_path))

                    # Preparar el buffer para la descarga
                    zip_buffer.seek(0)

                    # Nombre del archivo ZIP
                    zip_filename = f"lote_tarjetas_{coupon_entries[0]['batch_id']}.zip"

                    st.download_button(
                        label=f"Descargar Lote Completo ({count} tarjetas)",
                        data=zip_buffer,
                        file_name=zip_filename,
                        mime="application/zip",
                        key="zip_download_btn" # Clave única
                    )


    # ----------------------------------------
    # GESTIÓN Y DESCARGA DE PLANTILLAS DE DISEÑO (Actualizada para JPG y PNG)
    # ----------------------------------------
    with tab_template:
        st.header("Gestión de Plantilla para Arte y Diseño")

        # 1. DESCARGA DE LA GUÍA DE ESPACIOS
        st.subheader("1. Guía de Espacios (Para el Diseñador)")
        st.markdown("Use esta guía para crear su arte y dejar el espacio libre para el QR y el consecutivo. **Orientación Horizontal (9x5 cm).**")

        # ¡¡CAMBIO A JPG!!
        BLANK_JPG_PATH = os.path.join(TEMPLATE_DIR, "plantilla_guia_horizontal_9x5.jpg")
        if st.button("Descargar Guía JPG (9x5 cm)", key="download_guide"):
            generate_design_template(BLANK_JPG_PATH)
            with open(BLANK_JPG_PATH, "rb") as file:
                st.download_button(
                    label="Descargar Guía de Diseño (JPG)",
                    data=file,
                    file_name=os.path.basename(BLANK_JPG_PATH),
                    mime="image/jpeg" # ¡¡CAMBIO DE MIME-TYPE!!
                )

        st.markdown("---")

        # 2. CARGA DE LA PLANTILLA DE ARTE (PNG)
        st.subheader("2. Subir Plantilla de Arte (PNG Terminado)")

        # ¡¡CAMBIO A PNG!!
        uploaded_file = st.file_uploader(
            "Suba el PNG de Diseño (Arte Terminado, 1063x591px, Horizontal) para usar como fondo",
            type="png",
            key="template_uploader"
        )

        if uploaded_file is not None:
            # ¡¡CAMBIO A PNG!!
            template_filename = "plantilla_arte_activa.png"
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
    # ¡¡NUEVO!! Cargar datos para los nuevos filtros
    types = db_service.get_types()
    type_options = {t['type_name']: t['id'] for t in types}
    all_types = {"Todos": None}
    all_types.update(type_options)

    branches = db_service.get_branches()
    branch_options = {b['name']: b['id'] for b in branches}
    all_branches = {"Todas": None}
    all_branches.update(branch_options)

    # --- NUEVOS FILTROS ---
    selected_type_name = st.sidebar.selectbox("Filtrar por Tipo/Campaña", options=list(all_types.keys()))
    selected_type_id = all_types.get(selected_type_name)

    selected_branch_name = st.sidebar.selectbox("Filtrar por Sucursal de Canje", options=list(all_branches.keys()))
    selected_branch_id = all_branches.get(selected_branch_name)

    selected_status = st.sidebar.selectbox("Filtrar por Estado", ["Todos", "Canjeados", "No Canjeados"])

    col1_date, col2_date = st.sidebar.columns(2)
    with col1_date:
        start_date = st.date_input("Fecha de creación (desde)", value=None)
    with col2_date:
        end_date = st.date_input("Fecha de creación (hasta)", value=None)

    # Lógica para construir el filtro de PostgREST
    filters = []

    # ¡¡NUEVO!! Aplicar filtros
    if selected_type_id:
        # Necesitamos filtrar por el type_id dentro de la tabla batches, a la que se une desde coupons
        # La sintaxis correcta es: nombre_relacion_en_select.columna_en_tabla_relacionada=eq.valor
        filters.append(f"batch.type_id=eq.{selected_type_id}")

    if selected_branch_id:
        filters.append(f"redemption_branch_id=eq.{selected_branch_id}")

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
    # Mostrar el dataframe con todas las nuevas columnas
    st.dataframe(df, use_container_width=True)

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
