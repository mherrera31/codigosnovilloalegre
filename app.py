import streamlit as st
import auth 
import db_service
import user_service
# Importamos las utilidades de QR/PDF que vamos a necesitar luego (y que estaban en el app.py original)
import qrcode 
from PIL import Image, ImageDraw, ImageFont 
import uuid
import os
from datetime import datetime, timedelta
import pandas as pd
from pyzbar.pyzbar import decode
from fpdf import FPDF 
from db_config import get_supabase_client # Para futuras operaciones directas si son necesarias

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Sistema de QR Novillo Alegre", layout="wide")

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

