# app.py
import streamlit as st
import qrcode
from PIL import Image, ImageDraw, ImageFont
import uuid
import os
import sqlite3
from datetime import datetime, timedelta
import pandas as pd
from pyzbar.pyzbar import decode

# --- CONFIGURACIÓN DE LA PÁGINA Y LA BASE DE DATOS ---
st.set_page_config(page_title="Sistema de QR Dinámicos", layout="wide")

DB_NAME = 'qrsystem.db'

def init_db():
    """Inicializa la base de datos y las tablas si no existen."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Tabla de Sucursales
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS branches (
        id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE
    )''')
    
    # Tabla de Usuarios (para simular roles)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE, role TEXT, branch_id INTEGER
    )''')

    # Tabla principal de Códigos QR
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS qr_codes (
        id INTEGER PRIMARY KEY, uuid TEXT NOT NULL UNIQUE, description TEXT, value TEXT,
        category TEXT, expiration_date DATE, batch_id TEXT, created_by INTEGER,
        creation_date DATETIME DEFAULT CURRENT_TIMESTAMP, is_redeemed BOOLEAN DEFAULT 0,
        redeemed_by INTEGER, redemption_date DATETIME, redemption_branch_id INTEGER,
        invoice_number TEXT
    )''')

    # Tabla para permisos de sucursal por QR
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS qr_branch_permissions (
        qr_id INTEGER, branch_id INTEGER,
        PRIMARY KEY (qr_id, branch_id)
    )''')

    # Insertar datos de ejemplo si las tablas están vacías
    cursor.execute("SELECT COUNT(*) FROM branches")
    if cursor.fetchone()[0] == 0:
        cursor.executemany("INSERT INTO branches (id, name) VALUES (?, ?)", 
                           [(1, 'Sucursal Central'), (2, 'Sucursal Norte'), (3, 'Sucursal Sur')])
    
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        cursor.executemany("INSERT INTO users (id, username, role, branch_id) VALUES (?, ?, ?, ?)",
                           [(1, 'admin', 'Admin', None),
                            (2, 'creador_central', 'Creator', 1),
                            (3, 'cajero_norte', 'Cashier', 2)])
    
    conn.commit()
    conn.close()

# Llama a la inicialización al inicio de la app
init_db()

def get_db_connection():
    """Obtiene una conexión a la base de datos."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

# --- FUNCIONES AUXILIARES ---

def create_qr_card(data_to_encode: str, output_path: str, description: str, expiration: str):
    """Genera una imagen de tarjeta de regalo con el QR."""
    if not os.path.exists('generated_qrs'):
        os.makedirs('generated_qrs')
        
    card_width, card_height = 800, 500
    bg_color, text_color = (255, 255, 255), (0, 0, 0)
    accent_color = (22, 82, 127)

    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=8, border=2)
    qr.add_data(data_to_encode)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert('RGB')

    card_img = Image.new('RGB', (card_width, card_height), bg_color)
    draw = ImageDraw.Draw(card_img)

    draw.rectangle([0, 0, card_width, 100], fill=accent_color)
    try:
        title_font = ImageFont.truetype("arial.ttf", size=40)
        main_font = ImageFont.truetype("arial.ttf", size=28)
        small_font = ImageFont.truetype("arial.ttf", size=20)
    except IOError:
        title_font = main_font = small_font = ImageFont.load_default()

    draw.text((30, 25), "Tarjeta de Regalo / Descuento", fill=bg_color, font=title_font)
    card_img.paste(qr_img, (550, 140))
    
    draw.text((40, 150), description, fill=text_color, font=main_font)
    draw.text((40, 250), f"Válido hasta: {expiration}", fill=(100, 100, 100), font=small_font)
    draw.text((40, 290), "Presenta este QR en caja.", fill=(100, 100, 100), font=small_font)

    card_img.save(output_path)
    return output_path

# --- INTERFAZ DE STREAMLIT ---

st.title("🎁 Sistema de QR para Descuentos")

# --- MENÚ DE NAVEGACIÓN ---
st.sidebar.title("Menú de Navegación")
app_mode = st.sidebar.radio(
    "Seleccione el módulo",
    ["📲 Escáner (Cajero)", "🛠️ Creador de QRs", "📊 Reportes (Admin)"]
)

# --- MÓDULO 2: SCAN Y CANJE (Rol: Cashier) ---
if app_mode == "📲 Escáner (Cajero)":
    st.header(" Módulo de Cajero: Escanear QR")

    # Simulación de selección de cajero y sucursal
    st.info("Simulación: El cajero y la sucursal se seleccionarían en un login real.")
    CURRENT_USER = {"id": 3, "branch_id": 2} # Cajero Norte de ejemplo

    uploaded_file = st.file_uploader(
        "Presiona para activar la cámara o subir una foto del QR", type=["png", "jpg", "jpeg"]
    )
    
    if uploaded_file is not None:
        image = Image.open(uploaded_file)
        
        decoded_objects = decode(image)
        if not decoded_objects:
            st.error("No se pudo leer ningún código QR en la imagen. Intenta de nuevo.")
        else:
            qr_uuid = decoded_objects[0].data.decode('utf-8')
            st.info(f"UUID decodificado: `{qr_uuid}`")

            conn = get_db_connection()
            qr_info = conn.execute("SELECT * FROM qr_codes WHERE uuid = ?", (qr_uuid,)).fetchone()
            
            if not qr_info:
                st.error("Código QR no encontrado en la base de datos. ¡No es válido!")
            else:
                # Validaciones
                error = False
                if qr_info['is_redeemed']:
                    st.error(f"❌ **CANJEADO**: Este QR ya fue usado el {qr_info['redemption_date']}.")
                    error = True
                
                expiration_date = datetime.strptime(qr_info['expiration_date'], '%Y-%m-%d').date()
                if expiration_date < datetime.now().date():
                    st.error(f"❌ **EXPIRADO**: Este QR venció el {qr_info['expiration_date']}.")
                    error = True

                # Validar sucursal
                user_branch_id = CURRENT_USER['branch_id']
                permissions = conn.execute(
                    "SELECT branch_id FROM qr_branch_permissions WHERE qr_id = ?", (qr_info['id'],)
                ).fetchall()
                allowed_branch_ids = [p['branch_id'] for p in permissions]
                
                if allowed_branch_ids and user_branch_id not in allowed_branch_ids:
                    st.error(f"❌ **SUCURSAL INCORRECTA**: Este QR no es válido en esta tienda.")
                    error = True

                if not error:
                    st.success("✅ **CÓDIGO VÁLIDO PARA CANJEAR**")
                    
                    # --- AQUÍ EL CAJERO SABE QUÉ HACER ---
                    st.subheader("Instrucción para el Cajero:")
                    st.markdown(f"## **Aplicar:** {qr_info['description']}")
                    st.markdown(f"**Valor de referencia:** {qr_info['value']}")
                    
                    with st.form("redeem_form"):
                        invoice_number = st.text_input("Ingresar Número de Factura del Cliente")
                        redeem_button = st.form_submit_button("Confirmar Canje", type="primary")

                        if redeem_button and invoice_number:
                            conn.execute(
                                """UPDATE qr_codes SET is_redeemed = 1, redeemed_by = ?, 
                                   redemption_branch_id = ?, invoice_number = ?, redemption_date = ?
                                   WHERE uuid = ?""",
                                (CURRENT_USER['id'], user_branch_id, invoice_number, datetime.now(), qr_uuid)
                            )
                            conn.commit()
                            st.success("¡Canje registrado exitosamente!")
                            st.balloons()
                        elif redeem_button and not invoice_number:
                            st.warning("El número de factura es obligatorio.")
            conn.close()

# --- MÓDULO 1: CREACIÓN DE QR (Roles: Admin, Creator) ---
if app_mode == "🛠️ Creador de QRs":
    st.header("Módulo de Creación de Códigos QR")
    
    with st.form("qr_creator_form"):
        st.subheader("Configuración del QR")
        
        col1, col2 = st.columns(2)
        with col1:
            description = st.text_input("Descripción (ej: 20% Descuento Bebidas)", "Café Americano GRATIS")
            value = st.text_input("Valor de referencia (ej: 20%, 5.00)", "3.50")
            category = st.selectbox("Categoría", ["bebidas", "comida", "postre", "todo"])
        with col2:
            valid_days = st.number_input("Días de vigencia", min_value=1, max_value=365, value=30)
            conn = get_db_connection()
            branches = conn.execute("SELECT * FROM branches").fetchall()
            conn.close()
            allowed_branches = st.multiselect(
                "Sucursales permitidas (dejar en blanco para todas)",
                options=[branch['name'] for branch in branches],
            )
            count = st.number_input("Cantidad de QRs a generar (lote)", min_value=1, max_value=100, value=1)

        submitted = st.form_submit_button("🚀 Generar QR(s)", type="primary")

    if submitted:
        # Lógica de creación de QR...
        # (El resto del código de creación es el mismo)
        pass # Se omite por brevedad, es el mismo código de la versión anterior.


# --- MÓDULO 3: REPORTES (Rol: Admin) ---
if app_mode == "📊 Reportes (Admin)":
    st.header("Módulo de Reportes de Actividad")
    
    st.sidebar.header("Filtros de Reporte")
    conn = get_db_connection()
    
    query = "SELECT * FROM qr_codes" # Simplificado para el ejemplo
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    st.dataframe(df)
    # (El resto del código de reportes es el mismo)
    pass
