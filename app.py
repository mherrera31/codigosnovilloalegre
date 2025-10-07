# app.py
import streamlit as st
import qrcode
from PIL import Image, ImageDraw, ImageFont
import uuid
import os
import sqlite3
from datetime import datetime, timedelta
import pandas as pd
from pyzbar.pyzbar import decode  # Para leer los QR desde una imagen

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

st.title("🎁 Sistema de QR para Descuentos y Regalos")

# Simulación de Login con Roles en la barra lateral
st.sidebar.header("👤 Simulación de Login")
conn = get_db_connection()
users = conn.execute("SELECT * FROM users").fetchall()
user_map = {f"{user['username']} ({user['role']})": user for user in users}
selected_user_str = st.sidebar.selectbox("Seleccionar Usuario", list(user_map.keys()))
CURRENT_USER = user_map[selected_user_str]
st.sidebar.info(f"Logueado como: **{CURRENT_USER['username']}**\n\nRol: **{CURRENT_USER['role']}**")
conn.close()

# --- MÓDULO 1: CREACIÓN DE QR (Roles: Admin, Creator) ---
if CURRENT_USER['role'] in ['Admin', 'Creator']:
    st.header(" Módulo 1: Creación de Códigos QR")
    
    with st.form("qr_creator_form"):
        st.subheader("Configuración del QR")
        
        col1, col2 = st.columns(2)
        with col1:
            description = st.text_input("Descripción (ej: 20% de Descuento en Bebidas)", "Café Americano GRATIS")
            value = st.text_input("Valor (ej: 20%, 5.00, etc.)", "3.50")
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
        batch_id = f"batch_{uuid.uuid4().hex[:6]}"
        st.success(f"Generando {count} QR(s) en el lote '{batch_id}'...")
        
        branch_map = {branch['name']: branch['id'] for branch in branches}
        selected_branch_ids = [branch_map[name] for name in allowed_branches]

        progress_bar = st.progress(0)
        for i in range(count):
            unique_id = str(uuid.uuid4())
            expiration_date = datetime.now() + timedelta(days=valid_days)
            
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO qr_codes (uuid, description, value, category, expiration_date, batch_id, created_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (unique_id, description, value, category, expiration_date.date(), batch_id, CURRENT_USER['id'])
            )
            qr_id = cursor.lastrowid

            if selected_branch_ids:
                for branch_id in selected_branch_ids:
                    cursor.execute("INSERT INTO qr_branch_permissions (qr_id, branch_id) VALUES (?, ?)", (qr_id, branch_id))
            
            conn.commit()
            conn.close()
            
            # Generar imagen
            output_path = os.path.join('generated_qrs', f"{unique_id}.png")
            create_qr_card(unique_id, output_path, description, expiration_date.strftime("%Y-%m-%d"))

            with st.expander(f"✅ QR Generado: {unique_id[:8]}..."):
                st.image(output_path)
                with open(output_path, "rb") as file:
                    st.download_button(
                        label="Descargar Tarjeta",
                        data=file,
                        file_name=f"tarjeta_{unique_id[:8]}.png",
                        mime="image/png"
                    )
            progress_bar.progress((i + 1) / count)
        st.balloons()


# --- MÓDULO 2: SCAN Y CANJE (Rol: Cashier) ---
if CURRENT_USER['role'] == 'Cashier':
    st.header(" Módulo 2: Canje de QR (Cajero)")

    uploaded_file = st.file_uploader(
        "Sube una imagen del código QR para escanearlo", type=["png", "jpg", "jpeg"]
    )
    
    if uploaded_file is not None:
        image = Image.open(uploaded_file)
        st.image(image, caption='QR Escaneado', width=250)
        
        decoded_objects = decode(image)
        if not decoded_objects:
            st.error("No se pudo decodificar ningún QR en la imagen.")
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
                    st.error(f"❌ **CANJEADO**: Este QR ya fue canjeado el {qr_info['redemption_date']}.")
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
                    st.error(f"❌ **SUCURSAL INCORRECTA**: Este QR no es válido en esta sucursal.")
                    error = True

                if not error:
                    st.success("✅ **CÓDIGO VÁLIDO PARA CANJE**")
                    st.json({
                        "Descripción": qr_info['description'],
                        "Valor": qr_info['value'],
                        "Categoría": qr_info['category'],
                        "Vence": qr_info['expiration_date']
                    })

                    with st.form("redeem_form"):
                        invoice_number = st.text_input("Número de Factura del Cliente")
                        # st.file_uploader("Foto de la factura (funcionalidad futura)")
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


# --- MÓDULO 3: REPORTES (Rol: Admin) ---
if CURRENT_USER['role'] == 'Admin':
    st.header(" Módulo 3: Reportes de Actividad")
    
    st.sidebar.header("Filtros de Reporte")
    conn = get_db_connection()
    branches = conn.execute("SELECT name FROM branches").fetchall()
    
    selected_status = st.sidebar.selectbox("Estado", ["Todos", "Canjeados", "No Canjeados"])
    
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
        
    start_date = st.sidebar.date_input("Fecha de creación (desde)", value=None)
    end_date = st.sidebar.date_input("Fecha de creación (hasta)", value=None)

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
    total_qrs = len(df)
    redeemed_qrs = df['is_redeemed'].sum()
    not_redeemed_qrs = total_qrs - redeemed_qrs

    col1, col2, col3 = st.columns(3)
    col1.metric("Total de QRs en Filtro", f"{total_qrs} 🎟️")
    col2.metric("Total Canjeados", f"{redeemed_qrs} ✅")
    col3.metric("Pendientes de Canje", f"{not_redeemed_qrs} ⏳")
