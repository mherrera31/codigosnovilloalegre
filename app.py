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
        st.success(f"**Usuario:** {st.session_state.get('username', user.email)}")
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
    # Lógica del creador de QRs pendiente de migrar a Supabase
    st.warning("Módulo pendiente de migración de SQLite a Supabase.")
    st.info("Para que este módulo funcione, debe: 1. Crear la tabla BATCHES. 2. Migrar la lógica de creación de códigos del app.py original para usar db_service.py.")


elif app_mode == "📲 Escáner (Cajero)":
    # Lógica del escáner pendiente de migrar a Supabase
    st.warning("Módulo pendiente de migración de SQLite a Supabase.")
    st.info("Para que este módulo funcione, debe: 1. Migrar la lógica de validación y canje del app.py original para usar db_service.py.")


elif app_mode == "📊 Reportes (Admin)":
    # Lógica de reportes pendiente de migrar a Supabase
    st.warning("Módulo pendiente de migración de SQLite a Supabase.")
    st.info("Para que este módulo funcione, debe: 1. Migrar la lógica de consultas de reportes del app.py original para usar db_service.py.")
