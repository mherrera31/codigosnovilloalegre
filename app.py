# app.py (VERSIÓN CONSOLIDADA Y CORREGIDA PARA EL DESPLIEGUE)
import streamlit as st
import auth 
import db_service
import user_service
import requests # Cliente HTTP para interactuar con la API de Supabase

# --- Imports para la funcionalidad de QR/PDF ---
import qrcode 
from PIL import Image, ImageDraw, ImageFont 
import uuid
import os
from datetime import datetime, timedelta
import pandas as pd
from pyzbar.pyzbar import decode
from fpdf import FPDF 
from db_config import get_headers # Solo necesitamos get_headers de db_config

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Sistema de QR Novillo Alegre", layout="wide")

LOGO_URL = "https://placehold.co/300x100/1E3260/FFFFFF/png?text=Novillo+Alegre+QR"

# ----------------------------------------
# FUNCIONES AUXILIARES (QR y PDF)
# NOTA: Estas funciones fueron consolidadas aquí. En un paso posterior, deben ir a qr_utils.py
# ----------------------------------------

# --- CONFIGURACIÓN DE RUTAS ---
TEMPLATE_DIR = 'design_templates'
os.makedirs(TEMPLATE_DIR, exist_ok=True)
TEMPLATE_PATH_KEY = 'current_template_path'

# Inicializa la ruta de la plantilla si no existe
if TEMPLATE_PATH_KEY not in st.session_state:
    st.session_state[TEMPLATE_PATH_KEY] = None


def create_qr_card(data_to_encode: str, output_path: str, description: str, expiration: str):
    """Genera una imagen de tarjeta con el QR, optimizada para tamaño de presentación."""
    
    if not os.path.exists('generated_qrs'):
        os.makedirs('generated_qrs')
        
    card_width, card_height = 875, 500 
    bg_color, text_color = (255, 255, 255), (0, 0, 0)
    accent_color = (191, 2, 2) 

    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=8, border=2)
    qr.add_data(data_to_encode)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
    
    card_img = Image.new('RGB', (card_width, card_height), bg_color)
    draw = ImageDraw.Draw(card_img)

    draw.rectangle([0, 0, card_width, 80], fill=accent_color)
    try:
        title_font = ImageFont.truetype("arialbd.ttf", size=32)
        main_font = ImageFont.truetype("arial.ttf", size=30)
    except IOError:
        title_font = main_font = ImageFont.load_default()
        
    draw.text((30, 25), "TARJETA DE REGALO NOVILLO ALEGRE", fill=(255,255,255), font=title_font)
        
    qr_scaled = qr_img.resize((card_height - 100, card_height - 100))
    card_img.paste(qr_scaled, (card_width - qr_scaled.width - 50, 100))
    
    draw.text((50, 150), description, fill=text_color, font=main_font)
    draw.text((50, 220), f"Válido hasta: {expiration}", fill=(100, 100, 100), font=main_font)

    card_img.save(output_path)
    return output_path

def generate_pdf_from_images(image_paths, output_filename):
    """Crea un PDF a partir de una lista de imágenes, cada una en una página tamaño tarjeta."""
    CARD_WIDTH_MM = 85.6
    CARD_HEIGHT_MM = 53.98
    pdf = FPDF(orientation='L', unit='mm', format=(CARD_WIDTH_MM, CARD_HEIGHT_MM))
    
    for image_path in image_paths:
        pdf.add_page()
        pdf.image(image_path, x=0, y=0, w=CARD_WIDTH_MM, h=CARD_HEIGHT_MM) 
        
    pdf.output(output_filename)
    return output_filename

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
    # PÁGINA DE LOGIN
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
        # CORRECCIÓN AQUÍ: Usamos user.get('email') en lugar de user.email
        st.success(f"**Usuario:** {st.session_state.get('username', user.get('email', 'N/A'))}")
        st.success(f"**Rol:** {user_role}")
        
        # Opciones de menú basadas en el rol
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
    
# --- MÓDULOS PENDIENTES DE REFACTORIZAR (Módulos de Negocio Central) ---

elif app_mode == "🛠️ Creador de QRs":
    
    # Obtener datos maestros (Solo se ejecuta si el usuario es Admin/Creator)
    promos = db_service.get_promos()
    branches = db_service.get_branches()
    issuers = db_service.get_issuers()

    promo_options = {p['type_name']: p for p in promos}
    branch_options = [b['name'] for b in branches]
    issuer_options = {i['issuer_name']: i['id'] for i in issuers}
    
    # --- Interfaz de Pestañas ---
    tab_creator, tab_template = st.tabs(["Generador de Lote", "Gestión de Plantilla"])
    
    with tab_creator:
        st.header("Módulo de Creación de Tarjetas QR")
        
        with st.form("qr_creator_form"):
            st.subheader("Configuración de la Tarjeta")
            
            col1, col2 = st.columns(2)
            with col1:
                selected_promo_name = st.selectbox("Seleccionar Promoción/Diseño", options=list(promo_options.keys()))
                selected_promo = promo_options.get(selected_promo_name)
                
                # Campos de valor pre-llenados (requiere que la tabla 'promos' tenga estos campos)
                st.caption(f"Descripción: {selected_promo['description']}")
                value_crc = st.number_input("Valor de Referencia (Colones)", value=selected_promo['value'], min_value=0.0, format="%.2f")
                value_usd = st.number_input("Valor de Referencia (Dólares)", value=round(selected_promo['value'] / 590, 2), min_value=0.0, format="%.2f") # Tasa de cambio simulada
            
            with col2:
                valid_days = st.number_input("Días de vigencia", min_value=1, max_value=365, value=30)
                allowed_branches = st.multiselect("Sucursales permitidas (dejar vacío para todas)", options=branch_options)
                selected_issuer_name = st.selectbox("Emisor/Campaña", options=list(issuer_options.keys()))
                count = st.number_input("Cantidad de tarjetas a generar (lote)", min_value=1, max_value=100, value=1)
                
            submitted = st.form_submit_button("🚀 Generar Tarjetas", type="primary")

        if submitted:
            issuer_id = issuer_options.get(selected_issuer_name)
            user_id = st.session_state.get('user_id')
            
            if not selected_promo or not issuer_id or not user_id:
                st.error("Faltan datos de configuración (Promoción o Emisor).")
            else:
                st.success(f"Generando {count} tarjeta(s)...")
                
                # LLAMADA A LA FUNCIÓN MIGRADA DE SUPABASE
                coupon_entries = db_service.create_coupon_batch(
                    count=count,
                    description=selected_promo['description'],
                    promo_id=selected_promo['id'],
                    value_crc=value_crc,
                    value_usd=value_usd,
                    issuer_id=issuer_id,
                    valid_days=valid_days,
                    branch_names=allowed_branches, # Se convierte a IDs dentro del servicio
                    user_id=user_id,
                    batch_name_prefix=selected_promo_name
                )
                
                if coupon_entries:
                    st.balloons()
                    generated_image_paths = []
                    
                    # Generar imágenes y preparar el PDF
                    for entry in coupon_entries:
                        unique_id = entry['id']
                        consecutive = str(entry['consecutive']).zfill(4) # Formato 0001
                        expiration = entry['expiration_date']
                        
                        output_path = os.path.join('generated_qrs', f"{unique_id}.png")
                        
                        # Usar la función de creación de tarjeta (que será modificada en Tarea D)
                        create_qr_card(unique_id, output_path, selected_promo['description'], expiration, consecutive)
                        generated_image_paths.append(output_path)
                        
                        # ... (Mostrar tarjetas individuales con botón de descarga si es necesario)
                        
                    # Sección de Descarga de Lote PDF
                    st.subheader("⬇️ Descargar Lote Completo")
                    pdf_path = generate_pdf_from_images(generated_image_paths, f"lote_tarjetas_{coupon_entries[0]['batch_id']}.pdf")

                    with open(pdf_path, "rb") as pdf_file:
                        st.download_button(
                            label="Descargar PDF con todas las tarjetas",
                            data=pdf_file,
                            file_name=os.path.basename(pdf_path),
                            mime="application/pdf"
                        )

    # ----------------------------------------
    # GESTIÓN Y DESCARGA DE PLANTILLAS DE DISEÑO
    # ----------------------------------------
    with tab_template:
        st.header("Gestión de Plantilla para Arte y Diseño")
        
        # 1. DESCARGA DE LA GUÍA DE ESPACIOS
        st.subheader("1. Guía de Espacios (Para el Diseñador)")
        st.markdown("Use esta guía para crear su arte y dejar el espacio libre para el QR y el consecutivo.")
        
        BLANK_PDF_PATH = os.path.join(TEMPLATE_DIR, "plantilla_guia_9x5.pdf")
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
            "Suba el PDF de Diseño (Arte Terminado, 9x5cm) para usar como fondo", 
            type="pdf", 
            key="template_uploader"
        )
        
        if uploaded_file is not None:
            # Guardar el archivo subido de forma persistente
            template_filename = "plantilla_arte_activa.pdf"
            save_path = os.path.join(TEMPLATE_DIR, template_filename)
            
            with open(save_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            st.session_state[TEMPLATE_PATH_KEY] = save_path
            st.success(f"Plantilla de Arte cargada exitosamente: {uploaded_file.name}")
            
        # Mostrar el estado actual de la plantilla
        if st.session_state[TEMPLATE_PATH_KEY]:
            st.info(f"🎨 **Plantilla Actual:** {os.path.basename(st.session_state[TEMPLATE_PATH_KEY])} (Lista para usar en el Generador de Lote).")
        else:
            st.warning("No hay ninguna plantilla de diseño cargada actualmente. Se usará fondo blanco.")



elif app_mode == "📲 Escáner (Cajero)":
    # Lógica del escáner pendiente de migrar a Supabase
    st.warning("Módulo pendiente de migración de SQLite a Supabase.")
    st.info("Para que este módulo funcione, debe: 1. Migrar la lógica de validación y canje del app.py original para usar db_service.py.")


elif app_mode == "📊 Reportes (Admin)":
    st.header("Módulo de Reportes de Actividad")
    
    st.sidebar.header("Filtros de Reporte")
    conn = get_db_connection()
    branches = conn.execute("SELECT name FROM branches").fetchall()
    
    selected_status = st.sidebar.selectbox("Estado", ["Todos", "Canjeados", "No Canjeados"])
    start_date = st.sidebar.date_input("Fecha de creación (desde)", value=None)
    end_date = st.sidebar.date_input("Fecha de creación (hasta)", value=None)

    query = """
        SELECT qr.uuid, qr.description, qr.is_redeemed, 
               b.name as redemption_branch, qr.redemption_date, qr.invoice_number,
               uc.username as creator, qr.creation_date
        FROM qr_codes qr
        LEFT JOIN users uc ON qr.created_by = uc.id
        LEFT JOIN branches b ON qr.redemption_branch_id = b.id
        WHERE 1=1
    """
    params = []
    
    if selected_status == "Canjeados":
        query += " AND qr.is_redeemed = 1"
    elif selected_status == "No Canjeados":
        query += " AND qr.is_redeemed = 0"
        
    if start_date:
        query += " AND date(qr.creation_date) >= ?"
        params.append(start_date)
    if end_date:
        query += " AND date(qr.creation_date) <= ?"
        params.append(end_date)
    
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    
    st.subheader("Datos Completos")
    st.dataframe(df)

    # Métricas
    if not df.empty:
        total_qrs = len(df)
        redeemed_qrs = df['is_redeemed'].sum()
        not_redeemed_qrs = total_qrs - redeemed_qrs
    else:
        total_qrs = redeemed_qrs = not_redeemed_qrs = 0

    col1, col2, col3 = st.columns(3)
    col1.metric("Total de QRs en Filtro", f"{total_qrs} 🎟️")
    col2.metric("Total Canjeados", f"{redeemed_qrs} ✅")
    col3.metric("Pendientes de Canje", f"{not_redeemed_qrs} ⏳")
