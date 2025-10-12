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

if app_mode == "🛠️ Creador de QRs":
    st.header("Módulo de Creación de Tarjetas QR")
    
    with st.form("qr_creator_form"):
        st.subheader("Configuración de la Tarjeta")
        col1, col2 = st.columns(2)
        with col1:
            description = st.text_input("Descripción (ej: 20% Descuento Bebidas)", "Corte de Carne de Regalo")
            value = st.text_input("Valor de referencia (ej: 20%, 5.00)", "25.00")
            category = st.selectbox("Categoría", ["Cortes", "Bebidas", "Postres", "Todo"])
        with col2:
            valid_days = st.number_input("Días de vigencia", min_value=1, max_value=365, value=30)
            conn = get_db_connection()
            branches = conn.execute("SELECT * FROM branches").fetchall()
            conn.close()
            allowed_branches = st.multiselect("Sucursales permitidas (dejar en blanco para todas)", options=[branch['name'] for branch in branches])
            count = st.number_input("Cantidad de tarjetas a generar (lote)", min_value=1, max_value=100, value=1)
        submitted = st.form_submit_button("🚀 Generar Tarjetas", type="primary")

    if submitted:
        batch_id = f"batch_{uuid.uuid4().hex[:6]}"
        st.success(f"Generando {count} tarjeta(s) en el lote '{batch_id}'...")
        
        generated_image_paths = [] # Lista para guardar las rutas de las imágenes
        progress_bar = st.progress(0)

        for i in range(count):
            unique_id = str(uuid.uuid4())
            expiration_date = datetime.now() + timedelta(days=valid_days)
            
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO qr_codes (uuid, description, value, category, expiration_date, batch_id, created_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (unique_id, description, value, category, expiration_date.date(), batch_id, 1) # Creado por user 1 (admin) de ejemplo
            )
            qr_id = cursor.lastrowid
            # Aquí iría la lógica para insertar las sucursales permitidas si es necesario
            conn.commit()
            conn.close()
            
            output_path = os.path.join('generated_qrs', f"{unique_id}.png")
            create_qr_card(unique_id, output_path, description, expiration_date.strftime("%Y-%m-%d"))
            generated_image_paths.append(output_path)

            # Mostrar la tarjeta individual con su botón de descarga
            with st.expander(f"✅ Tarjeta generada: {unique_id[:8]}..."):
                st.image(output_path)
                with open(output_path, "rb") as file:
                    st.download_button(label="Descargar esta imagen", data=file, file_name=f"tarjeta_{unique_id[:8]}.png", mime="image/png")
            
            progress_bar.progress((i + 1) / count)
        
        st.balloons()

        # --- SECCIÓN DE GENERACIÓN DE PDF ---
        st.subheader("⬇️ Descargar Lote Completo")
        st.info("Todas las tarjetas generadas se han compilado en un solo archivo PDF para facilitar la impresión.")

        pdf_path = generate_pdf_from_images(generated_image_paths, f"lote_tarjetas_{batch_id}.pdf")

        with open(pdf_path, "rb") as pdf_file:
            st.download_button(
                label="Descargar PDF con todas las tarjetas",
                data=pdf_file,
                file_name=os.path.basename(pdf_path),
                mime="application/pdf"
            )


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
