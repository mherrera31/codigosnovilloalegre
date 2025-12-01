# app.py (CÓDIGO COMPLETO Y VERIFICADO - Centrado Absoluto y Sin Faltantes)
import streamlit as st
import auth
import db_service
import user_service 
import requests
import qrcode
from PIL import Image, ImageDraw, ImageFont
import uuid
import os
from datetime import datetime, timedelta
import pandas as pd
import zipfile
import io
import textwrap 
from supabase import create_client, Client
from db_config import SUPABASE_URL 

# --- CONFIGURACIÓN Y CONSTANTES ---
st.set_page_config(page_title="Sistema QR Novillo Alegre", layout="wide")
LOGO_URL = "https://placehold.co/300x100/1E3260/FFFFFF/png?text=Novillo+Alegre+QR"
TEMPLATE_DIR = 'design_templates'; os.makedirs(TEMPLATE_DIR, exist_ok=True)
GENERATED_QRS_DIR = 'generated_qrs'; os.makedirs(GENERATED_QRS_DIR, exist_ok=True)

# --- TAMAÑO DE TARJETA (8.5cm x 5cm) ---
CARD_WIDTH_PX = 1004 
CARD_HEIGHT_PX = 591
CARD_WIDTH_MM = 85
CARD_HEIGHT_MM = 50

QR_SIZE_PX = 250; BORDER_PX = 50

# --- INICIALIZAR SUPABASE CLIENT PARA STORAGE ---
try:
    SUPABASE_SERVICE_KEY = st.secrets["SUPABASE_SERVICE_KEY"]
    supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    BUCKET_NAME = "plantillas"
except KeyError:
    st.error("Error: Secreto 'SUPABASE_SERVICE_KEY' no encontrado. Por favor configúralo en Streamlit Cloud.")
    st.stop()
except Exception as e:
    st.error(f"Error al inicializar Supabase: {e}")
    st.stop()


# --- Inicialización de Estado ---
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'user_role' not in st.session_state: st.session_state['user_role'] = None
if 'username' not in st.session_state: st.session_state['username'] = 'N/A' 
if 'user_id' not in st.session_state: st.session_state['user_id'] = None
if 'branch_id' not in st.session_state: st.session_state['branch_id'] = None
if 'last_receipt_data' not in st.session_state: st.session_state['last_receipt_data'] = None
if 'show_receipt' not in st.session_state: st.session_state['show_receipt'] = False
if 'last_zip_buffer' not in st.session_state: st.session_state['last_zip_buffer'] = None
if 'last_zip_filename' not in st.session_state: st.session_state['last_zip_filename'] = None
if 'selected_receipt_id' not in st.session_state: st.session_state['selected_receipt_id'] = None
if 'form_key_counter' not in st.session_state: st.session_state['form_key_counter'] = 0
if 'clear_form_inputs' not in st.session_state: st.session_state['clear_form_inputs'] = False
if 'show_preview' not in st.session_state: st.session_state['show_preview'] = False

# --- Obtener lista de plantillas desde Supabase Storage ---
@st.cache_data(ttl=60) 
def get_template_list():
    try:
        files = supabase_client.storage.from_(BUCKET_NAME).list()
        return sorted([
            f['name'].replace('.png', '') 
            for f in files 
            if f['name'].endswith('.png')
        ])
    except Exception as e:
        st.error(f"Error al listar plantillas del bucket: {e}")
        return []

# --- FUNCIONES AUXILIARES DE DIBUJO ---
def create_qr_card(
    data_to_encode: str, 
    template_name: str, 
    output_path: str, 
    scopes_text_list: list, 
    restrictions_text_list: list, 
    branch_names: list, 
    expiration: str, 
    consecutive: str
):
    """
    Genera JPG de tarjeta.
    CAMBIOS: Validez centrada en el medio de la tarjeta (como el footer).
    """
    card_img = None
    try:
        if template_name:
            file_bytes = supabase_client.storage.from_(BUCKET_NAME).download(f"{template_name}.png")
            card_img = Image.open(io.BytesIO(file_bytes)).convert('RGB')
            if card_img.size != (CARD_WIDTH_PX, CARD_HEIGHT_PX):
                card_img = card_img.resize((CARD_WIDTH_PX, CARD_HEIGHT_PX))
    except Exception as e:
        st.error(f"Error al cargar plantilla '{template_name}': {e}. Usando fondo blanco.")
        card_img = None 

    if card_img is None: 
        card_img = Image.new('RGB', (CARD_WIDTH_PX, CARD_HEIGHT_PX), (255, 255, 255))

    draw = ImageDraw.Draw(card_img)
    
    # --- FUENTES ---
    try:
        validez_font = ImageFont.truetype("DejaVuSans-Bold.ttf", size=22, encoding="utf-8") 
        sucursal_font = ImageFont.truetype("DejaVuSans-Bold.ttf", size=19, encoding="utf-8") 
        consecutive_font = ImageFont.truetype("DejaVuSans-Bold.ttf", size=55, encoding="utf-8") 
        footer_font = ImageFont.truetype("DejaVuSans-Bold.ttf", size=24, encoding="utf-8")  
        web_font = ImageFont.truetype("DejaVuSans-Bold.ttf", size=24, encoding="utf-8")
    except IOError:
        st.error("Error: No se encontraron los archivos de fuente (DejaVuSans). Usando default.")
        validez_font = footer_font = consecutive_font = sucursal_font = web_font = ImageFont.load_default()

    # Generar QR
    qr = qrcode.QRCode(1, qrcode.constants.ERROR_CORRECT_M, 8, 2); qr.add_data(data_to_encode); qr.make(fit=True); qr_img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
    
    # --- TEXTOS ---
    validez_text = "Validez: " + ". ".join(scopes_text_list) if scopes_text_list else ""
    date_text = f"Válido hasta: {expiration}"
    terms_text = "Ver Términos y Condiciones en"
    web_text = "www.restauranteelnovilloalegre.com"
    cons_text = f"{consecutive}"
    
    if not branch_names: 
        # Si la lista está vacía, significa "Todas"
        sucursales_text = "Válido en todas las sucursales"
        branch_names_list = ["Válido en todas", "las sucursales"]
    else:
        branch_names_list = branch_names

    # --- POSICIONAMIENTO (LAYOUT) ---
    
    # 1. QR (Derecha, Arriba)
    QR_X = CARD_WIDTH_PX - QR_SIZE_PX - BORDER_PX
    QR_Y = BORDER_PX + 30
    QR_POS = (int(QR_X), int(QR_Y))

    # 2. Consecutivo (Centrado debajo del QR)
    cons_width = consecutive_font.getlength(cons_text)
    # Centrado relativo al QR
    CONS_X = QR_X + (QR_SIZE_PX / 2) - (cons_width / 2)
    CONS_Y = QR_Y + QR_SIZE_PX + 10
    
    # 3. Sucursales (Lista vertical debajo del Consecutivo)
    cons_bbox = consecutive_font.getbbox(cons_text)
    cons_height = cons_bbox[3] - cons_bbox[1]
    current_suc_y = CONS_Y + cons_height + 40 
    
    # Dibujar Columna Derecha (QR, Consecutivo, Sucursales)
    qr_scaled = qr_img.resize((QR_SIZE_PX, QR_SIZE_PX))
    card_img.paste(qr_scaled, QR_POS)
    draw.text((int(CONS_X), int(CONS_Y)), cons_text, fill=(0,0,0), font=consecutive_font)
    
    for line in branch_names_list:
        w = sucursal_font.getlength(line)
        x = QR_X + (QR_SIZE_PX / 2) - (w / 2)
        draw.text((int(x), int(current_suc_y)), line, fill=(0,0,0), font=sucursal_font)
        current_suc_y += 22 # Salto de línea

    # --- FOOTER (Abajo al centro de TODA la tarjeta) ---
    # Orden: Web -> Terms -> Fecha
    
    bbox_web = web_font.getbbox(web_text); h_web = bbox_web[3] - bbox_web[1]
    bbox_terms = footer_font.getbbox(terms_text); h_terms = bbox_terms[3] - bbox_terms[1]
    bbox_date = footer_font.getbbox(date_text); h_date = bbox_date[3] - bbox_date[1]
    
    # Posiciones Y
    Y_WEB = CARD_HEIGHT_PX - BORDER_PX - h_web
    Y_TERMS = Y_WEB - h_terms - 8 
    Y_DATE = Y_TERMS - h_date - 8
    
    # Centrar X (CARD_WIDTH_PX / 2)
    CARD_CENTER_X = CARD_WIDTH_PX / 2
    
    X_WEB = CARD_CENTER_X - (web_font.getlength(web_text) / 2)
    X_TERMS = CARD_CENTER_X - (footer_font.getlength(terms_text) / 2)
    X_DATE = CARD_CENTER_X - (footer_font.getlength(date_text) / 2)
    
    draw.text((int(X_DATE), int(Y_DATE)), date_text, fill=(0,0,0), font=footer_font)
    draw.text((int(X_TERMS), int(Y_TERMS)), terms_text, fill=(0,0,0), font=footer_font)
    draw.text((int(X_WEB), int(Y_WEB)), web_text, fill=(0,0,0), font=web_font)

    # --- VALIDEZ (Centrado en TODA la tarjeta, Arriba de Fecha) ---
    
    # Envolver texto para evitar colisión con la derecha
    # Con fuente tamaño 22, ~40 caracteres es un buen límite antes de chocar con sucursales
    validez_lines = textwrap.wrap(validez_text, width=40)
    
    bbox_val = validez_font.getbbox("A")
    h_val_line = (bbox_val[3] - bbox_val[1]) + 10
    total_h_val = len(validez_lines) * h_val_line
    
    # Posicionar justo ARRIBA de la Fecha
    Y_START_VAL = Y_DATE - total_h_val - 20 
    
    current_y_val = Y_START_VAL
    for line in validez_lines:
        w = validez_font.getlength(line)
        # Centrado en el medio de la tarjeta
        x = CARD_CENTER_X - (w / 2)
        draw.text((int(x), int(current_y_val)), line, fill=(0,0,0), font=validez_font)
        current_y_val += h_val_line

    card_img.save(output_path, "JPEG", quality=95); return output_path

def generate_design_template(output_filename):
    """Genera guía JPG 8.5x5cm."""
    img = Image.new('RGB', (CARD_WIDTH_PX, CARD_HEIGHT_PX), (230, 230, 230)); draw = ImageDraw.Draw(img)
    try:
        title_font = ImageFont.truetype("DejaVuSans-Bold.ttf", size=40, encoding="utf-8")
        main_font = ImageFont.truetype("DejaVuSans.ttf", size=24, encoding="utf-8")
    except IOError:
        title_font = main_font = ImageFont.load_default()
    draw.text((BORDER_PX, BORDER_PX), f"GUÍA HORIZONTAL ({CARD_WIDTH_PX}x{CARD_HEIGHT_PX} px)", fill=(0,0,0), font=title_font)
    QR_X = CARD_WIDTH_PX - QR_SIZE_PX - BORDER_PX; QR_Y = 100; draw.rectangle([QR_X, QR_Y, QR_X + QR_SIZE_PX, QR_Y + QR_SIZE_PX], outline=(255,0,0), width=3); draw.text((QR_X + 10, QR_Y + 10), "ESPACIO QR (250x250)", fill=(255,0,0), font=main_font)
    TXT_X = BORDER_PX; TXT_Y = 400; draw.rectangle([TXT_X, TXT_Y, CARD_WIDTH_PX - BORDER_PX, CARD_HEIGHT_PX - BORDER_PX], outline=(0,0,255), width=3); draw.text((TXT_X + 10, TXT_Y + 10), "ESPACIO TEXTOS", fill=(0,0,255), font=main_font); draw.text((TXT_X + 10, TXT_Y + 40), "(Desc, Validez, Consec.)", fill=(0,0,255), font=main_font)
    img.save(output_filename, "JPEG", quality=95)

def format_receipt(receipt_data):
    """Formatea los datos del recibo para mostrar en st.code."""
    if not receipt_data: return "Error: No se encontraron datos de recibo."
    created_at_str = 'N/A'; created_at_val = receipt_data.get('created_at')
    if created_at_val:
        try: dt_obj = pd.to_datetime(created_at_val); created_at_str = dt_obj.strftime('%Y-%m-%d %H:%M:%S')
        except Exception: created_at_str = str(created_at_val)
    def safe_float(val, default=0.0):
        try: return float(val) if val is not None else default
        except (ValueError, TypeError): return default

    return f"""
    -----------------------------------------
            RECIBO DE GENERACIÓN DE LOTE
    -----------------------------------------
    Recibo ID:         {receipt_data.get('id', 'N/A')}
    Nombre Lote:       {receipt_data.get('batch_name', 'N/A')}
    Cantidad Creada:   {receipt_data.get('coupon_count', 'N/A')}
    Consecutivo Inicial: {receipt_data.get('consecutive_start', 0):04d}
    Consecutivo Final:   {receipt_data.get('consecutive_end', 0):04d}
    -----------------------------------------
    Valor Base Total (CRC): ₡ {safe_float(receipt_data.get('total_ref_value_crc')):,.2f}
    Valor Base Total (USD): $ {safe_float(receipt_data.get('total_ref_value_usd')):,.2f}
    -----------------------------------------
    VALOR TOTAL PAGADO (CRC): ₡ {safe_float(receipt_data.get('total_sale_value_crc')):,.2f}
    VALOR TOTAL PAGADO (USD): $ {safe_float(receipt_data.get('total_sale_value_usd')):,.2f}
    -----------------------------------------
    Fecha Generación: {created_at_str}
    -----------------------------------------
    """

# --- LÓGICA DE INICIALIZACIÓN Y LOGIN ---
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
# ... (rest of state initialization)
if not auth.is_authenticated():
    st.image(LOGO_URL, width=300); st.title("QR-Creator"); auth.login_ui(); st.stop()

# --- BARRA LATERAL Y NAVEGACIÓN ---
st.image(LOGO_URL, width=300); st.title("QR-Creator")
user = auth.get_current_user(); user_role = auth.get_user_role()
with st.sidebar:
    st.sidebar.header("Menú");
    if user_role:
        st.success(f"**Usuario:** {st.session_state.get('username', 'N/A')}\n**Rol:** {user_role}")
        menu_options = ["🏠 Dashboard"]
        if user_role == 'Admin': menu_options.extend(["🔑 Gestión de Usuarios", "⚙️ Configuración", "📊 Reportes"])
        if user_role in ['Admin', 'Creator']: menu_options.append("🛠️ Creador QR")
        if user_role in ['Admin', 'Cashier']: menu_options.append("📲 Escáner")
        current_selection_index = 0
        if 'app_mode_select' in st.session_state and st.session_state['app_mode_select'] in menu_options:
            current_selection_index = menu_options.index(st.session_state['app_mode_select'])
        app_mode = st.sidebar.radio("Módulo", menu_options, key="app_mode_select", index=current_selection_index)
        st.markdown("---");
        if st.button("Cerrar Sesión", key="logout_btn"): auth.sign_out()
    else: st.error("Error rol."); auth.sign_out(); st.stop()

# ----------------------------------------
# RENDERIZACIÓN DE MÓDULOS
# ----------------------------------------

if app_mode == "🏠 Dashboard": st.header("Bienvenido al Sistema")
elif app_mode == "🔑 Gestión de Usuarios": user_service.render_user_management()
elif app_mode == "⚙️ Configuración": db_service.render_config_management()
elif app_mode == "📲 Escáner":
    st.header("Abrir Aplicación de Escáner")
    st.markdown("Presione el botón para abrir la aplicación web de escaneo.")
    SCANNER_URL = "https://scannernovillo.netlify.app/"
    st.link_button("Abrir Escáner", url=SCANNER_URL, type="primary")

# --- MÓDULO CREADOR QR ---
elif app_mode == "🛠️ Creador QR":
    # Load master data
    promos = db_service.get_promos(); branches = db_service.get_branches()
    types = db_service.get_types(); scopes = db_service.get_validity_scopes()
    restrictions = db_service.get_restrictions()
    promo_options = {p['type_name']: p for p in promos if p.get('type_name')}
    branch_options = sorted([b['name'] for b in branches if b.get('name')])
    type_options = {t['type_name']: t['id'] for t in types if t.get('type_name')}
    scope_options = {s['scope_name']: s['id'] for s in scopes if s.get('scope_name')}
    restriction_options = {r['restriction_description']: r['id'] for r in restrictions if r.get('restriction_description')}

    tab_creator, tab_template = st.tabs(["Generador de Lote", "Gestión de Plantilla"])

    with tab_creator:
        st.header("Creación de Tarjetas QR")

        # --- Form Handling ---
        if 'form_key_counter' not in st.session_state: st.session_state['form_key_counter'] = 0
        form_key = f"qr_creator_form_{st.session_state['form_key_counter']}"
        
        # --- Form Definition ---
        with st.form(form_key, clear_on_submit=False):
            st.subheader("Configuración del Lote")
            promo_list = ["-- Seleccione Promoción --"] + sorted(list(promo_options.keys()))
            type_list = ["-- Seleccione Tipo --"] + sorted(list(type_options.keys()))
            scope_list = sorted(list(scope_options.keys()))
            restriction_list = sorted(list(restriction_options.keys()))
            
            template_list = ["Fondo Blanco"] + get_template_list() 
            default_template_index = 0
            current_template_sel = st.session_state.get(f"{form_key}_template")
            if not st.session_state.get('clear_form_inputs') and current_template_sel in template_list:
                default_template_index = template_list.index(current_template_sel)
            
            selected_template_name = st.selectbox(
                "1. Seleccione Plantilla", 
                options=template_list, 
                index=default_template_index,
                key=f"{form_key}_template"
            )
            st.markdown("---")

            default_asoc = "" if st.session_state.get('clear_form_inputs') else st.session_state.get(f"{form_key}_asoc", "")
            input_asociado = st.text_input("**2. Asociado o Comprador (*Obligatorio*)**", value=default_asoc, key=f"{form_key}_asoc")

            col1, col2 = st.columns(2)
            with col1:
                st.markdown("#### 3. Detalles de Promoción y Valor")
                promo_index = 0
                current_promo_sel = st.session_state.get(f"{form_key}_promo")
                if not st.session_state.get('clear_form_inputs') and current_promo_sel in promo_list: promo_index = promo_list.index(current_promo_sel)
                selected_promo_name = st.selectbox("Promoción/Diseño (*Obligatorio*)", options=promo_list, index=promo_index, key=f"{form_key}_promo")
                st.caption(f"Descrip. de Promoción (Solo referencia): {promo_options.get(selected_promo_name, {}).get('description', 'N/A')}")

                default_vcrc = None if st.session_state.get('clear_form_inputs') else st.session_state.get(f"{form_key}_vcrc")
                default_vusd = None if st.session_state.get('clear_form_inputs') else st.session_state.get(f"{form_key}_vusd")
                value_crc = st.number_input("Valor Base CRC (*Obligatorio*)", min_value=0.0, format="%.2f", value=default_vcrc, placeholder="0.00", key=f"{form_key}_vcrc")
                value_usd = st.number_input("Valor Base USD (*Obligatorio*)", min_value=0.0, format="%.2f", value=default_vusd, placeholder="0.00", key=f"{form_key}_vusd")

            with col2:
                st.markdown("#### 4. Reglas y Límite")
                months_index = 0; default_months = 3 if st.session_state.get('clear_form_inputs') else st.session_state.get(f"{form_key}_months", 3)
                if default_months in [3, 6, 9, 12]: months_index = [3, 6, 9, 12].index(default_months)
                valid_months = st.selectbox("Meses Vigencia (*Obligatorio*)", options=[3, 6, 9, 12], index=months_index, key=f"{form_key}_months")

                type_index = 0; current_type_sel = st.session_state.get(f"{form_key}_type")
                if not st.session_state.get('clear_form_inputs') and current_type_sel in type_list: type_index = type_list.index(current_type_sel)
                selected_type_name = st.selectbox("Tipo/Campaña (*Obligatorio*)", options=type_list, index=type_index, key=f"{form_key}_type")

                default_all_branches = False if st.session_state.get('clear_form_inputs') else st.session_state.get(f"{form_key}_all_branches", False)
                all_branches_selected = st.checkbox("Permitir en Todas las Sucursales", value=default_all_branches, key=f"{form_key}_all_branches")

                default_branches_raw = [] if st.session_state.get('clear_form_inputs') else st.session_state.get(f"{form_key}_branches", [])
                default_branches = [b for b in default_branches_raw if b in branch_options] 
                allowed_branches = st.multiselect(
                    "Sucursales Permitidas (Aparecerá en la tarjeta)", 
                    options=branch_options, default=default_branches, key=f"{form_key}_branches", disabled=all_branches_selected
                 )

                default_scopes_raw = [] if st.session_state.get('clear_form_inputs') else st.session_state.get(f"{form_key}_scopes", [])
                default_scopes = [s for s in default_scopes_raw if s in scope_list] 
                selected_scope_names = st.multiselect("Validez Cupón (Aparecerá en la tarjeta)", options=scope_list, default=default_scopes, key=f"{form_key}_scopes")

                default_restrictions_raw = [] if st.session_state.get('clear_form_inputs') else st.session_state.get(f"{form_key}_restrictions", [])
                default_restrictions = [r for r in default_restrictions_raw if r in restriction_list] 
                selected_restriction_names = st.multiselect("Restricciones (NO se imprimirá en tarjeta, solo sistema)", options=restriction_list, default=default_restrictions, key=f"{form_key}_restrictions")

                default_count = None if st.session_state.get('clear_form_inputs') else st.session_state.get(f'{form_key}_count')
                count = st.number_input("Cantidad (*Obligatorio*)", min_value=1, max_value=1000, value=default_count, placeholder="1", key=f'{form_key}_count')

            # --- Live Calculation Display ---
            st.divider()
            st.subheader("Cálculo Estimado")
            
            live_promo_name_calc = st.session_state[f"{form_key}_promo"]
            live_promo_data_calc = promo_options.get(live_promo_name_calc, {})
            live_vcrc_calc = st.session_state[f"{form_key}_vcrc"]
            live_vusd_calc = st.session_state[f"{form_key}_vusd"]
            live_count_calc = st.session_state[f"{form_key}_count"]

            if (live_promo_name_calc and live_promo_name_calc != "-- Seleccione Promoción --" and
                    isinstance(live_vcrc_calc, (int, float)) and live_vcrc_calc >= 0 and
                    isinstance(live_vusd_calc, (int, float)) and live_vusd_calc >= 0 and
                    isinstance(live_count_calc, int) and live_count_calc > 0):

                disc_crc_calc = db_service.calculate_discount_per_coupon(live_vcrc_calc, live_promo_data_calc)
                disc_usd_calc = db_service.calculate_discount_per_coupon(live_vusd_calc, live_promo_data_calc)
                sale_crc_individual = round(live_vcrc_calc - disc_crc_calc, 2)
                sale_usd_individual = round(live_vusd_calc - disc_usd_calc, 2)
                base_total_crc_calc = round(live_vcrc_calc * live_count_calc, 2)
                base_total_usd_calc = round(live_vusd_calc * live_count_calc, 2)
                total_discount_crc_calc = round(disc_crc_calc * live_count_calc, 2)
                total_discount_usd_calc = round(disc_usd_calc * live_count_calc, 2)
                total_sale_crc_calc = round(base_total_crc_calc - total_discount_crc_calc, 2)
                total_sale_usd_calc = round(base_total_usd_calc - total_discount_usd_calc, 2)

                st.markdown("**Costo Individual**")
                calc_col1_ind, calc_col2_ind = st.columns(2)
                with calc_col1_ind:
                    st.metric(label="Valor Base (CRC)", value=f"₡ {live_vcrc_calc:,.2f}")
                    st.metric(label="Descuento (CRC)", value=f"₡ {disc_crc_calc:,.2f}")
                    st.metric(label="Total Pagado (CRC)", value=f"₡ {sale_crc_individual:,.2f}")
                with calc_col2_ind:
                    st.metric(label="Valor Base (USD)", value=f"$ {live_vusd_calc:,.2f}")
                    st.metric(label="Descuento (USD)", value=f"$ {disc_usd_calc:,.2f}")
                    st.metric(label="Total Pagado (USD)", value=f"$ {sale_usd_individual:,.2f}")

                st.markdown(f"**Costo Lote ({live_count_calc} cupones)**")
                calc_col1_tot, calc_col2_tot = st.columns(2)
                with calc_col1_tot:
                    st.metric(label="Valor Base Total (CRC)", value=f"₡ {base_total_crc_calc:,.2f}")
                    st.metric(label="Descuento Total (CRC)", value=f"₡ {total_discount_crc_calc:,.2f}")
                    st.metric(label="Valor Total Pagado (CRC)", value=f"₡ {total_sale_crc_calc:,.2f}")
                with calc_col2_tot:
                    st.metric(label="Valor Base Total (USD)", value=f"$ {base_total_usd_calc:,.2f}")
                    st.metric(label="Descuento Total (USD)", value=f"$ {total_discount_usd_calc:,.2f}")
                    st.metric(label="Valor Total Pagado (USD)", value=f"$ {total_sale_usd_calc:,.2f}")
            else:
                 st.caption("ℹ️ Llene todos los campos (*) para ver el cálculo.")

            st.divider()

            # --- Submit Button ---
            submitted = st.form_submit_button("✔️ Generar Lote")

            if submitted:
                st.session_state['show_preview'] = False
                
                # --- VALIDACIÓN FINAL ---
                error = False
                asoc_val = st.session_state[f"{form_key}_asoc"]
                promo_val = st.session_state[f"{form_key}_promo"]
                vcrc_val = st.session_state[f"{form_key}_vcrc"]
                vusd_val = st.session_state[f"{form_key}_vusd"]
                type_val = st.session_state[f"{form_key}_type"]
                count_val = st.session_state[f'{form_key}_count']
                months_val = st.session_state[f"{form_key}_months"]
                scopes_val = st.session_state[f"{form_key}_scopes"]
                restrictions_val = st.session_state[f"{form_key}_restrictions"]
                all_branches_val = st.session_state[f"{form_key}_all_branches"]
                branches_val = st.session_state[f"{form_key}_branches"]
                template_name_val = st.session_state[f"{form_key}_template"] 

                # Perform checks
                if not asoc_val: st.error("❌ 'Asociado' obligatorio."); error = True
                if not promo_val or promo_val == "-- Seleccione Promoción --": st.error("❌ Seleccione Promoción."); error = True
                if vcrc_val is None or vcrc_val < 0: st.error("❌ Valor Base CRC >= 0.00."); error = True
                if vusd_val is None or vusd_val < 0: st.error("❌ Valor Base USD >= 0.00."); error = True
                if not type_val or type_val == "-- Seleccione Tipo --": st.error("❌ Seleccione Tipo."); error = True
                if count_val is None or count_val <= 0: st.error("❌ Cantidad > 0."); error = True
                if months_val is None: st.error("❌ Seleccione Meses."); error=True
                if not all_branches_val and not branches_val: 
                    st.error("❌ Seleccione Sucursales o marque 'Todas'."); error = True
                
                if not error:
                    type_id = type_options.get(type_val)
                    user_id = st.session_state.get('user_id')
                    scope_ids = [scope_options[n] for n in scopes_val]
                    restriction_ids = [restriction_options[n] for n in restrictions_val]
                    
                    branch_names_for_db = [] 
                    branch_names_for_card = [] 
                    if not all_branches_val:
                        branch_names_for_db = branches_val 
                        branch_names_for_card = branches_val 
                    
                    template_name_for_submit = None
                    if template_name_val != "Fondo Blanco":
                        template_name_for_submit = template_name_val

                    selected_promo_data = promo_options.get(promo_val, {})

                    st.info(f"⚙️ Generando {count_val} tarjeta(s)... Por favor espere.")
                    result = db_service.create_coupon_batch(
                        count=count_val, asociado_comprador=asoc_val,
                        promo_data=selected_promo_data, value_crc=vcrc_val, value_usd=vusd_val,
                        type_id=type_id, months_valid=months_val, 
                        branch_names=branch_names_for_db, 
                        scope_ids=scope_ids, restriction_ids=restriction_ids, user_id=user_id
                    )
                    if result and result.get('coupon_entries'):
                        st.success("✅ ¡Lote y recibo generados!")
                        st.balloons()
                        generated_paths = []; coupons = result['coupon_entries']

                        scopes_text_list = st.session_state[f"{form_key}_scopes"]
                        restrictions_text_list = st.session_state[f"{form_key}_restrictions"]

                        with st.spinner("Creando archivos ZIP..."):
                            zip_buffer = io.BytesIO()
                            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                                for entry in coupons:
                                    path = os.path.join(GENERATED_QRS_DIR, f"{entry['consecutive']:04d}.jpg")
                                    
                                    try:
                                        # Formatear la fecha de la DB (YYYY-MM-DD) a DD-MM-YYYY
                                        date_obj = datetime.strptime(entry['expiration_date'][:10], "%Y-%m-%d")
                                        formatted_date = date_obj.strftime("%d-%m-%Y")
                                    except Exception:
                                        formatted_date = entry['expiration_date']

                                    create_qr_card(
                                        entry['id'], 
                                        template_name_for_submit, 
                                        path, 
                                        scopes_text_list, 
                                        restrictions_text_list, 
                                        branch_names_for_card, 
                                        formatted_date, 
                                        f"{entry['consecutive']:04d}"
                                    )
                                    zf.write(path, os.path.basename(path))
                                    generated_paths.append(path) 
                            
                            zip_buffer.seek(0)
                        
                        zip_filename = f"lote_{coupons[0]['batch_id']}.zip"
                        
                        st.session_state['last_receipt_data'] = result.get('receipt_data')
                        st.session_state['show_receipt'] = True
                        st.session_state['last_zip_buffer'] = zip_buffer
                        st.session_state['last_zip_filename'] = zip_filename
                        
                        st.session_state['clear_form_inputs'] = True
                        st.session_state['form_key_counter'] += 1 
                        st.rerun() 
                    else:
                        st.error("🚨 Error al generar el lote. Campos NO borrados. Revise mensajes.")
                        st.session_state['show_receipt'] = False
                        st.session_state['clear_form_inputs'] = False 
                else:
                    st.session_state['clear_form_inputs'] = False
        
        # --- FIN DEL st.form ---
        
        # --- Vista Previa (FUERA del form) ---
        st.divider()
        st.subheader("Vista Previa")
        
        if st.button("Ver/Actualizar Vista Previa", key=f"{form_key}_preview_btn"):
            st.session_state['show_preview'] = True
        
        if st.session_state.get('show_preview', False):
            with st.container(border=True): 
                try:
                    live_template_name_str = st.session_state.get(f"{form_key}_template", "Fondo Blanco")
                    live_scopes = st.session_state.get(f"{form_key}_scopes", [])
                    live_restric = st.session_state.get(f"{form_key}_restrictions", [])
                    live_branches = st.session_state.get(f"{form_key}_branches", [])
                    live_all_branches = st.session_state.get(f"{form_key}_all_branches", False)
                    live_months = st.session_state.get(f"{form_key}_months", 3)

                    template_name_for_preview = None
                    if live_template_name_str != "Fondo Blanco":
                        template_name_for_preview = live_template_name_str 
                    
                    live_branch_list = []
                    if not live_all_branches:
                        live_branch_list = live_branches

                    preview_path = os.path.join(GENERATED_QRS_DIR, "preview.jpg")
                    
                    preview_date = (datetime.now() + timedelta(days=live_months * 30)).strftime("%d-%m-%Y")

                    create_qr_card(
                        "PREVIEW-ID-12345678",
                        template_name_for_preview, 
                        preview_path,
                        live_scopes,
                        [], # Empty restrictions
                        live_branch_list,
                        preview_date, # <-- Fecha formateada
                        "0000"
                    )
                    st.image(preview_path, caption="Vista previa generada con los datos actuales del formulario.", width=700)
                    
                    if st.button("Ocultar Vista Previa", key=f"{form_key}_hide_preview"):
                        st.session_state['show_preview'] = False
                        st.rerun() 
                
                except Exception as e:
                    st.error(f"No se pudo generar la vista previa: {e}")
        else:
            st.caption("Presione 'Ver/Actualizar Vista Previa' para previsualizar la tarjeta con los datos del formulario.")


        # --- Display Receipt and Download (Outside Form) ---
        if st.session_state.get('show_receipt') and st.session_state.get('last_receipt_data'):
            st.divider()
            st.subheader("🧾 Recibo Generado")
            receipt_text = format_receipt(st.session_state['last_receipt_data'])
            st.code(receipt_text, language=None)
            st.subheader("⬇️ Descargar Tarjetas (ZIP)")
            if st.session_state.get('last_zip_buffer') and st.session_state.get('last_zip_filename'):
                st.download_button(
                    label="Descargar Lote Completo", data=st.session_state['last_zip_buffer'],
                    file_name=st.session_state['last_zip_filename'], mime="application/zip", key="zip_dl_final")
            else: st.warning("Archivo ZIP no encontrado.")
            if st.button("✨ Listo (Ocultar Recibo)"):
                st.session_state['show_receipt'] = False; st.session_state['last_receipt_data'] = None
                st.session_state['last_zip_buffer'] = None; st.session_state['last_zip_filename'] = None
                st.session_state['clear_form_inputs'] = True 
                st.session_state['form_key_counter'] += 1
                st.session_state['show_preview'] = False 
                st.rerun()

        if 'clear_form_inputs' in st.session_state:
             st.session_state['clear_form_inputs'] = False


    # --- Pestaña de Gestión de Plantilla ---
    with tab_template:
        st.header("Gestión de Plantillas de Diseño (en Supabase)")
        
        st.subheader("1. Subir Nueva Plantilla")
        with st.form("template_form", clear_on_submit=True):
            template_name = st.text_input("Nombre de la Plantilla (ej: Navidad2025, DiaPadre)")
            up_file = st.file_uploader(f"Suba PNG ({CARD_WIDTH_PX}x{CARD_HEIGHT_PX}px, Horizontal)", type="png")
            submitted = st.form_submit_button("Guardar Plantilla en Supabase")
            
            if submitted:
                if not template_name:
                    st.error("Debe ingresar un nombre para la plantilla.")
                elif not up_file:
                    st.error("Debe seleccionar un archivo PNG.")
                else:
                    save_name = f"{template_name}.png"
                    
                    existing_templates = get_template_list()
                    if template_name in existing_templates:
                        st.error(f"Ya existe una plantilla con el nombre '{template_name}'. Use otro nombre.")
                    else:
                        try:
                            img = Image.open(up_file)
                            if img.size != (CARD_WIDTH_PX, CARD_HEIGHT_PX):
                                st.error(f"Error: La imagen debe ser de {CARD_WIDTH_PX}x{CARD_HEIGHT_PX} píxeles. La subida es de {img.size[0]}x{img.size[1]}px.")
                            else:
                                # --- INICIO CORRECCIÓN: .getvalue() en lugar de .getbuffer() ---
                                file_bytes = up_file.getvalue() 
                                supabase_client.storage.from_(BUCKET_NAME).upload(
                                    path=save_name, 
                                    file=file_bytes, # <-- Ahora son bytes
                                    file_options={"content-type": "image/png"}
                                )
                                # --- FIN CORRECCIÓN ---
                                st.success(f"Plantilla '{template_name}' guardada en el bucket.")
                                st.cache_data.clear() 
                                st.rerun()
                        except Exception as e:
                            st.error(f"Error al guardar en Supabase: {e}")

        st.divider()
        st.subheader("2. Plantillas Guardadas en el Bucket")
        
        templates = get_template_list()
        if not templates:
            st.info("No hay plantillas guardadas en el bucket 'plantillas'.")
        else:
            for t_name in templates:
                with st.container(border=True):
                    st.markdown(f"**Nombre:** `{t_name}`")
                    
                    try:
                        public_url = supabase_client.storage.from_(BUCKET_NAME).get_public_url(f"{t_name}.png")
                        st.image(public_url, width=400, caption=f"Vista previa de {t_name}")
                    except Exception as e:
                        st.error(f"No se pudo cargar la imagen: {e}")
                    
                    if st.button("Eliminar Plantilla", key=f"delete_{t_name}", type="primary"):
                        try:
                            supabase_client.storage.from_(BUCKET_NAME).remove([f"{t_name}.png"])
                            st.success(f"Plantilla '{t_name}' eliminada del bucket.")
                            st.cache_data.clear()
                            st.rerun()
                        except Exception as e:
                            st.error(f"No se pudo eliminar: {e}")
        
        st.divider()
        st.subheader("3. Guía de Diseño (JPG)")
        st.markdown(f"Guía horizontal ({CARD_WIDTH_PX}x{CARD_HEIGHT_PX} px).")
        BLANK_JPG_GUIDE = os.path.join(TEMPLATE_DIR, "plantilla_guia.jpg")
        if st.button("Generar/Descargar Guía JPG", key="dl_guide"):
            generate_design_template(BLANK_JPG_GUIDE);
            with open(BLANK_JPG_GUIDE, "rb") as f: 
                st.download_button("Descargar Guía (JPG)", f, os.path.basename(BLANK_JPG_GUIDE), "image/jpeg", key="dl_guide_btn")
