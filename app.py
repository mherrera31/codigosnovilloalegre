# app.py (INICIO CORREGIDO Y LISTO PARA EJECUTARSE)
import streamlit as st
import auth 
import db_service
import user_service
import requests # Necesario para db_service y auth

# --- Imports para la funcionalidad de QR/PDF (del app.py original) ---
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

# --- FIN DE LAS FUNCIONES QR/PDF ---

# Inicializa el estado de la sesión
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'user_role' not in st.session_state:
    st.session_state['user_role'] = None
if 'branch_id' not in st.session_state:
    st.session_state['branch_id'] = None
# Agregamos la inicialización del cliente Supabase para cachearlo
get_supabase_client()


# ----------------------------------------
# LÓGICA DE CONTROL DE ACCESO (LOGIN GATE)
# ----------------------------------------

if not auth.is_authenticated():
    # PÁGINA DE LOGIN
    st.image("https://novilloalegre.com.pa/wp-content/uploads/2020/07/logo-novillo-alegre-panama-restaurante-parrillada-argentina.png", width=300)
    st.title("Sistema de QRs de Regalo - Acceso Restringido")
    auth.login_ui()
    st.stop()
    
# ----------------------------------------
# BARRA LATERAL (SIDEBAR) Y NAVEGACIÓN
# ----------------------------------------

# Mostrar Logo en la página principal y título
st.image("https://novilloalegre.com.pa/wp-content/uploads/2020/07/logo-novillo-alegre-panama-restaurante-parrillada-argentina.png", width=300)
st.title("Sistema de QRs de Regalo")

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
    
# --- MÓDULOS PENDIENTES DE REFACTORIZAR (Por ahora, son el código original) ---

# Nota: El código restante (Creador, Escáner, Reportes) DEBE ser refactorizado
# para usar las funciones de Supabase de db_service en lugar de sqlite3.

elif app_mode == "🛠️ Creador de QRs":
    # Lógica del creador de QRs pendiente de migrar a Supabase
    st.warning("Módulo pendiente de migración a Supabase.")
    # Colocar aquí el código del creador de QRs del app.py original (con adaptación de DB)

elif app_mode == "📲 Escáner (Cajero)":
    # Lógica del escáner pendiente de migrar a Supabase
    st.warning("Módulo pendiente de migración a Supabase.")
    # Colocar aquí el código del escáner de app.py original (con adaptación de DB)

elif app_mode == "📊 Reportes (Admin)":
    # Lógica de reportes pendiente de migrar a Supabase
    st.warning("Módulo pendiente de migración a Supabase.")
    # Colocar aquí el código de reportes de app.py original (con adaptación de DB)

# ----------------------------------------
# FUNCIONES AUXILIARES (QR y PDF)
# ----------------------------------------

def create_qr_card(data_to_encode: str, output_path: str, description: str, expiration: str):
    """Genera una imagen de tarjeta con el QR, optimizada para tamaño de presentación."""
    
    # Asegúrate de que la carpeta de salida exista
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
        
    # Pegar QR
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

