# app.py (VERSIÓN CORREGIDA - Tabs de Reportes y Enlace Escáner)
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
# from pyzbar.pyzbar import decode # Ya no se usa en este archivo
# from fpdf import FPDF # Ya no se usa para generar PDF de lote
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
CARD_WIDTH_PX = 1063
CARD_HEIGHT_PX = 591
CARD_WIDTH_MM = 90
CARD_HEIGHT_MM = 50
QR_SIZE_PX = 250
BORDER_PX = 50


# ----------------------------------------
# FUNCIONES AUXILIARES (QR y Plantilla JPG)
# ----------------------------------------

def create_qr_card(data_to_encode: str, output_path: str, description: str, expiration: str, consecutive: str):
    """
    Genera una imagen de tarjeta (9cm ANCHO x 5cm ALTO @ 300DPI) con el QR y el consecutivo.
    Usa la plantilla PNG subida si existe.
    """
    template_path = st.session_state.get(TEMPLATE_PATH_KEY)
    if template_path and os.path.exists(template_path):
        try:
            card_img = Image.open(template_path).convert('RGB')
            if card_img.size != (CARD_WIDTH_PX, CARD_HEIGHT_PX):
                st.warning(f"Plantilla redimensionada a {CARD_WIDTH_PX}x{CARD_HEIGHT_PX}px.")
                card_img = card_img.resize((CARD_WIDTH_PX, CARD_HEIGHT_PX))
        except Exception as e:
            st.error(f"Error al cargar plantilla: {e}. Usando fondo blanco.")
            card_img = Image.new('RGB', (CARD_WIDTH_PX, CARD_HEIGHT_PX), (255, 255, 255))
    else:
        card_img = Image.new('RGB', (CARD_WIDTH_PX, CARD_HEIGHT_PX), (255, 255, 255))

    draw = ImageDraw.Draw(card_img)

    # Dibujar banda roja y título si no hay plantilla
    if not template_path:
        draw.rectangle([0, 0, CARD_WIDTH_PX, 80], fill=(191, 2, 2))
        try:
            title_font = ImageFont.truetype("arialbd.ttf", size=32)
            draw.text((30, 25), "TARJETA DE REGALO NOVILLO ALEGRE", fill=(255,255,255), font=title_font)
        except IOError: pass # Ignorar si la fuente no está

    # Cargar fuentes principales
    try:
        main_font = ImageFont.truetype("arial.ttf", size=30)
        consecutive_font = ImageFont.truetype("arialbd.ttf", size=40)
    except IOError:
        main_font = consecutive_font = ImageFont.load_default()

    # Generar QR
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=8, border=2)
    qr.add_data(data_to_encode)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert('RGB')

    # Posiciones
    QR_POSITION_X = CARD_WIDTH_PX - QR_SIZE_PX - BORDER_PX
    QR_POSITION_Y = 100

    if template_path:
        # Posiciones asumidas para la plantilla
        PROMO_DESCRIPTION_POSITION = (BORDER_PX, 400)
        EXPIRATION_POSITION = (BORDER_PX, 440)
        CONSECUTIVE_POSITION = (BORDER_PX, 480)
    else:
        # Posiciones estándar sobre fondo blanco
        PROMO_DESCRIPTION_POSITION = (BORDER_PX, 150)
        EXPIRATION_POSITION = (BORDER_PX, 250)
        CONSECUTIVE_POSITION = (BORDER_PX, 480)

    # Dibujar textos
    draw.text(PROMO_DESCRIPTION_POSITION, description, fill=(0,0,0), font=main_font)
    draw.text(EXPIRATION_POSITION, f"Válido hasta: {expiration}", fill=(100, 100, 100), font=main_font)
    draw.text(CONSECUTIVE_POSITION, f"CONSECUTIVO: {consecutive}", fill=(0, 0, 0), font=consecutive_font)

    # Pegar QR
    qr_scaled = qr_img.resize((QR_SIZE_PX, QR_SIZE_PX))
    card_img.paste(qr_scaled, (QR_POSITION_X, QR_POSITION_Y))

    # Guardar como JPG
    card_img.save(output_path, "JPEG", quality=95)
    return output_path


def generate_design_template(output_filename):
    """Genera una plantilla de GUÍA en formato JPG (9x5 cm horizontal)."""
    img = Image.new('RGB', (CARD_WIDTH_PX, CARD_HEIGHT_PX), (230, 230, 230))
    draw = ImageDraw.Draw(img)
    try:
        title_font = ImageFont.truetype("arialbd.ttf", size=40)
        main_font = ImageFont.truetype("arial.ttf", size=24)
    except IOError: title_font = main_font = ImageFont.load_default()

    draw.text((BORDER_PX, BORDER_PX), "GUÍA DE DISEÑO HORIZONTAL (1063x591 px)", fill=(0,0,0), font=title_font)
    QR_POS_X = CARD_WIDTH_PX - QR_SIZE_PX - BORDER_PX
    QR_POS_Y = 100
    draw.rectangle([QR_POS_X, QR_POS_Y, QR_POS_X + QR_SIZE_PX, QR_POS_Y + QR_SIZE_PX], outline=(255, 0, 0), width=3)
    draw.text((QR_POS_X + 10, QR_POS_Y + 10), "ESPACIO PARA QR (250x250 px)", fill=(255,0,0), font=main_font)
    TEXT_POS_X = BORDER_PX; TEXT_POS_Y = 400
    draw.rectangle([TEXT_POS_X, TEXT_POS_Y, CARD_WIDTH_PX - BORDER_PX, CARD_HEIGHT_PX - BORDER_PX], outline=(0, 0, 255), width=3)
    draw.text((TEXT_POS_X + 10, TEXT_POS_Y + 10), "ESPACIO RECOMENDADO PARA TEXTOS", fill=(0,0,255), font=main_font)
    draw.text((TEXT_POS_X + 10, TEXT_POS_Y + 40), "(Descripción, Validez, Consecutivo)", fill=(0,0,255), font=main_font)
    img.save(output_filename, "JPEG", quality=95)


# ----------------------------------------
# LÓGICA DE INICIALIZACIÓN Y CONTROL DE ACCESO
# ----------------------------------------
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'user_role' not in st.session_state: st.session_state['user_role'] = None
if 'branch_id' not in st.session_state: st.session_state['branch_id'] = None

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
st.image(LOGO_URL, width=300)
st.title("QR-Creator")
user = auth.get_current_user()
user_role = auth.get_user_role()

with st.sidebar:
    st.sidebar.header("Menú de Navegación")
    if user_role:
        st.success(f"**Usuario:** {st.session_state.get('username', user.get('email', 'N/A'))}")
        st.success(f"**Rol:** {user_role}")
        menu_options = ["🏠 Dashboard"]
        if user_role == 'Admin': menu_options.extend(["🔑 Gestión de Usuarios", "⚙️ Configuración", "📊 Reportes"])
        if user_role in ['Admin', 'Creator']: menu_options.append("🛠️ Creador de QRs")
        if user_role in ['Admin', 'Cashier']: menu_options.append("📲 Escáner (Cajero)") # Mantener opción
        app_mode = st.sidebar.radio("Seleccione el módulo", menu_options)
        st.markdown("---")
        if st.button("Cerrar Sesión", key="logout_btn"): auth.sign_out()
    else:
        st.error("Error al cargar rol. Favor reintentar.")
        auth.sign_out()
        st.stop()

# ----------------------------------------
# RENDERIZACIÓN DE MÓDULOS
# ----------------------------------------

if app_mode == "🏠 Dashboard":
    st.header("Bienvenido al Sistema Novillo Alegre")
    st.info(f"Su rol actual es **{user_role}**. Use el menú de la izquierda para navegar.")

elif app_mode == "🔑 Gestión de Usuarios":
    user_service.render_user_management()

elif app_mode == "⚙️ Configuración":
    db_service.render_config_management()

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

    tab_creator, tab_template = st.tabs(["Generador de Lote", "Gestión de Plantilla"])

    with tab_creator:
        st.header("Módulo de Creación de Tarjetas QR")
        with st.form("qr_creator_form"):
            st.subheader("Configuración de la Tarjeta")
            input_batch_name = st.text_input("**Nombre Personalizado del Lote** (Opcional)")
            col1, col2 = st.columns(2)
            with col1:
                selected_promo_name = st.selectbox("Promoción/Diseño (Descuento Venta)", options=list(promo_options.keys()))
                selected_promo = promo_options.get(selected_promo_name, {})
                st.caption(f"Desc. Canje: {selected_promo.get('description', 'N/A')}")
                value_crc = st.number_input("Valor Base Cupón (CRC)", value=float(selected_promo.get('value', 0.0)), min_value=0.0, format="%.2f")
                value_usd = st.number_input("Valor Base Cupón (USD)", value=round(float(selected_promo.get('value', 0.0)) / 590, 2), min_value=0.0, format="%.2f")
                sale_value_crc = db_service.calculate_sale_value(value_crc, selected_promo)
                sale_value_usd = db_service.calculate_sale_value(value_usd, selected_promo)
                st.markdown(f"**Valor Venta (CRC):** ₡{sale_value_crc:,.2f}")
                st.markdown(f"**Valor Venta (USD):** ${sale_value_usd:,.2f}")
            with col2:
                valid_months = st.selectbox("Meses Vigencia", options=[3, 6, 9, 12], index=0)
                selected_type_name = st.selectbox("Tipo/Campaña", options=list(type_options.keys()))
                allowed_branches = st.multiselect("Sucursales Permitidas", options=branch_options)
                selected_scope_names = st.multiselect("Validez Cupón", options=list(scope_options.keys()))
                selected_restriction_names = st.multiselect("Restricciones", options=list(restriction_options.keys()))
                count = st.number_input("Cantidad", min_value=1, max_value=1000, value=1)
            submitted = st.form_submit_button("🚀 Generar Tarjetas", type="primary")

        if submitted:
            type_id = type_options.get(selected_type_name)
            user_id = st.session_state.get('user_id')
            selected_scope_ids = [scope_options[name] for name in selected_scope_names]
            selected_restriction_ids = [restriction_options[name] for name in selected_restriction_names]

            if not selected_promo or not type_id or not user_id:
                st.error("Faltan datos (Promoción, Tipo o Usuario).")
            else:
                st.info(f"Generando {count} tarjeta(s)...")
                coupon_entries = db_service.create_coupon_batch(
                    count=count, batch_name=input_batch_name, promo_data=selected_promo,
                    value_crc=value_crc, value_usd=value_usd, type_id=type_id,
                    months_valid=valid_months, branch_names=allowed_branches,
                    scope_ids=selected_scope_ids, restriction_ids=selected_restriction_ids,
                    user_id=user_id
                )
                if coupon_entries:
                    st.balloons()
                    generated_image_paths = []
                    for entry in coupon_entries:
                        output_path = os.path.join(GENERATED_QRS_DIR, f"{entry['consecutive']:04d}.jpg")
                        create_qr_card(entry['id'], output_path, selected_promo['description'], entry['expiration_date'], f"{entry['consecutive']:04d}")
                        generated_image_paths.append(output_path)

                    st.subheader("⬇️ Descargar Lote Completo (ZIP)")
                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                        for file_path in generated_image_paths:
                            zip_file.write(file_path, os.path.basename(file_path))
                    zip_buffer.seek(0)
                    zip_filename = f"lote_{coupon_entries[0]['batch_id']}.zip"
                    st.download_button(label=f"Descargar Lote ({count} tarjetas)", data=zip_buffer, file_name=zip_filename, mime="application/zip", key="zip_dl")

    with tab_template:
        st.header("Gestión de Plantilla para Arte y Diseño")
        st.subheader("1. Guía de Espacios (JPG)")
        st.markdown("Guía horizontal (9x5 cm) para ubicar QR y textos.")
        BLANK_JPG_PATH = os.path.join(TEMPLATE_DIR, "plantilla_guia.jpg")
        if st.button("Descargar Guía JPG", key="dl_guide"):
            generate_design_template(BLANK_JPG_PATH)
            with open(BLANK_JPG_PATH, "rb") as f:
                st.download_button(label="Descargar Guía (JPG)", data=f, file_name=os.path.basename(BLANK_JPG_PATH), mime="image/jpeg")
        st.markdown("---")
        st.subheader("2. Subir Plantilla de Arte (PNG)")
        uploaded_file = st.file_uploader("Suba PNG (1063x591px, Horizontal) como fondo", type="png", key="up_tmpl")
        if uploaded_file:
            template_filename = "plantilla_arte_activa.png"
            save_path = os.path.join(TEMPLATE_DIR, template_filename)
            with open(save_path, "wb") as f: f.write(uploaded_file.getbuffer())
            st.session_state[TEMPLATE_PATH_KEY] = save_path
            st.success(f"Plantilla cargada: {uploaded_file.name}")
        if st.session_state.get(TEMPLATE_PATH_KEY): st.info(f"🎨 Plantilla Actual: {os.path.basename(st.session_state[TEMPLATE_PATH_KEY])}")
        else: st.warning("No hay plantilla cargada. Se usará fondo blanco.")

# --- MÓDULO ESCÁNER (ENLACE) ---
elif app_mode == "📲 Escáner (Cajero)":
    st.header("Abrir Aplicación de Escáner")
    st.markdown("Presione el botón para abrir la aplicación web de escaneo de cupones.")
    SCANNER_URL = "https://scannernovillo.netlify.app/"
    st.link_button("Abrir Escáner", url=SCANNER_URL, type="primary")

# --- MÓDULO REPORTES (CON TABS) ---
elif app_mode == "📊 Reportes":
    if user_role != 'Admin':
        st.error("Acceso denegado.")
        st.stop()

    st.header("Módulo de Reportes")

    tab_cupones, tab_lotes = st.tabs(["Reporte de Cupones Emitidos", "Reporte de Lotes"])

    with tab_cupones:
        st.subheader("Reporte Detallado de Cupones Emitidos")
        st.sidebar.header("Filtros Reporte Cupones") # Mover filtros a sidebar

        # Filtros existentes para cupones (Fecha)
        col1_date, col2_date = st.sidebar.columns(2)
        with col1_date:
            start_date_coupon = st.date_input("Creación Cupón (desde)", value=None, key="coupon_start")
        with col2_date:
            end_date_coupon = st.date_input("Creación Cupón (hasta)", value=None, key="coupon_end")

        # Construir filtros para la función get_activity_report
        coupon_filters = []
        if start_date_coupon: coupon_filters.append(f"creation_date=gte.{start_date_coupon}")
        if end_date_coupon: coupon_filters.append(f"creation_date=lte.{end_date_coupon}")
        coupon_filter_string = "&".join(coupon_filters)

        # Obtener y mostrar datos de cupones
        df_coupons = db_service.get_activity_report(coupon_filter_string)
        if not df_coupons.empty:
            st.dataframe(df_coupons, use_container_width=True)
            # Métricas (opcional aquí, ya que es detalle)
            total_qrs = len(df_coupons)
            redeemed_qrs = df_coupons['is_redeemed'].sum()
            st.metric("Total Cupones en Filtro", f"{total_qrs} 🎟️")
            st.metric("Total Canjeados", f"{redeemed_qrs} ✅")

        else:
            st.info("No hay cupones que coincidan con los filtros o no se pudieron cargar.")


    with tab_lotes:
        st.subheader("Reporte Resumen de Lotes Creados")
        # Aquí podrías añadir filtros específicos para lotes si es necesario
        # Por ahora, muestra todos los lotes

        df_batches = db_service.get_batch_report() # Llamar a la nueva función
        if not df_batches.empty:
            st.dataframe(df_batches, use_container_width=True)
            # Métricas globales de lotes
            total_lotes = len(df_batches)
            total_cupones_creados = df_batches['Creados'].sum()
            total_cupones_canjeados = df_batches['Canjeados'].sum()
            st.metric("Total Lotes Creados", f"{total_lotes}")
            st.metric("Total Cupones Creados (Todos los Lotes)", f"{total_cupones_creados}")
            st.metric("Total Cupones Canjeados (Todos los Lotes)", f"{total_cupones_canjeados}")
        else:
            st.info("No hay lotes creados o no se pudieron cargar.")
