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
from fpdf import FPDF # Importamos la librería para PDF

# --- CONFIGURACIÓN DE LA PÁGINA Y LA BASE DE DATOS ---
st.set_page_config(page_title="Sistema de QR Novillo Alegre", layout="wide")

DB_NAME = 'qrsystem.db'

def init_db():
    """Inicializa la base de datos y las tablas si no existen."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Tabla de Sucursales
    cursor.execute('CREATE TABLE IF NOT EXISTS branches (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE)')
    
    # Tabla de Usuarios (para simular roles)
    cursor.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE, role TEXT, branch_id INTEGER)')

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
    cursor.execute('CREATE TABLE IF NOT EXISTS qr_branch_permissions (qr_id INTEGER, branch_id INTEGER, PRIMARY KEY (qr_id, branch_id))')

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

init_db()

def get_db_connection():
    """Obtiene una conexión a la base de datos."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

# --- FUNCIONES AUXILIARES ---

def create_qr_card(data_to_encode: str, output_path: str, description: str, expiration: str):
    """Genera una imagen de tarjeta con el QR, optimizada para tamaño de presentación."""
    if not os.path.exists('generated_qrs'):
        os.makedirs('generated_qrs')
        
    # Dimensiones con una relación de aspecto de tarjeta de presentación (aprox 1.75)
    card_width, card_height = 875, 500 
    bg_color, text_color = (255, 255, 255), (0, 0, 0)
    accent_color = (191, 2, 2) # Rojo Novillo Alegre

    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=8, border=2)
    qr.add_data(data_to_encode)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
    
    card_img = Image.new('RGB', (card_width, card_height), bg_color)
    draw = ImageDraw.Draw(card_img)

    # Aquí puedes agregar el logo de Novillo Alegre
    # try:
    #     logo = Image.open("logo_novillo.png")
    #     card_img.paste(logo, (50, 30), logo)
    # except FileNotFoundError:
    draw.rectangle([0, 0, card_width, 80], fill=accent_color)
    try:
        title_font = ImageFont.truetype("arialbd.ttf", size=32)
        main_font = ImageFont.truetype("arial.ttf", size=30)
    except IOError:
        title_font = main_font = ImageFont.load_default()
    draw.text((30, 25), "TARJETA DE REGALO NOVILLO ALEGRE", fill=(255,255,255), font=title_font)
        
    # Pegar QR
    card_img.paste(qr_img, (card_width - 300, 120))
    
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
        pdf.image(image_path, x=0, y=0, w=CARD_WIDTH_MM) # w ajusta la imagen al ancho de la tarjeta
        
    pdf.output(output_filename)
    return output_filename

# --- INTERFAZ DE STREAMLIT ---

st.image("https://novilloalegre.com.pa/wp-content/uploads/2020/07/logo-novillo-alegre-panama-restaurante-parrillada-argentina.png", width=300)
st.title("Sistema de QRs de Regalo")

# --- MENÚ DE NAVEGACIÓN ---
st.sidebar.title("Menú de Navegación")
app_mode = st.sidebar.radio(
    "Seleccione el módulo",
    ["🛠️ Creador de QRs", "📲 Escáner (Cajero)", "📊 Reportes (Admin)"]
)

# --- MÓDULO 1: CREACIÓN DE QR ---
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
            allowed_branches = st.multilet("Sucursales permitidas (dejar en blanco para todas)", options=[branch['name'] for branch in branches])
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

# --- MÓDULO 2: SCAN Y CANJE (Cajero) ---
elif app_mode == "📲 Escáner (Cajero)":
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
    
# --- MÓDULO 3: REPORTES (Admin) ---
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
