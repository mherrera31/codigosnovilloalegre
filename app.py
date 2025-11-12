# app.py (VERSIÓN CORREGIDA - Vista Previa con Botón)
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
# --- INICIO CAMBIO: Nuevos imports para Supabase ---
from supabase import create_client, Client
from db_config import SUPABASE_URL # Importar la URL base
# --- FIN CAMBIO ---

# --- CONFIGURACIÓN Y CONSTANTES ---
st.set_page_config(page_title="Sistema QR Novillo Alegre", layout="wide")
LOGO_URL = "https://placehold.co/300x100/1E3260/FFFFFF/png?text=Novillo+Alegre+QR"
TEMPLATE_DIR = 'design_templates'; os.makedirs(TEMPLATE_DIR, exist_ok=True)
GENERATED_QRS_DIR = 'generated_qrs'; os.makedirs(GENERATED_QRS_DIR, exist_ok=True)

# --- TAMAÑO 8.5cm x 5cm ---
CARD_WIDTH_PX = 1004 
CARD_HEIGHT_PX = 591
CARD_WIDTH_MM = 85
CARD_HEIGHT_MM = 50
# --- FIN TAMAÑO ---

QR_SIZE_PX = 250; BORDER_PX = 50

# --- INICIO CAMBIO: Inicializar Supabase Client para Storage ---
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
# --- FIN CAMBIO ---


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
# --- INICIO CAMBIO: Nuevo estado para la vista previa ---
if 'show_preview' not in st.session_state: st.session_state['show_preview'] = False
# --- FIN CAMBIO ---

# --- CAMBIO: Obtener lista de plantillas desde Supabase Storage ---
@st.cache_data(ttl=60) # Cache por 60 segundos
def get_template_list():
    try:
        files = supabase_client.storage.from_(BUCKET_NAME).list()
        # Filtrar solo PNGs y quitar la extensión
        return sorted([
            f['name'].replace('.png', '') 
            for f in files 
            if f['name'].endswith('.png')
        ])
    except Exception as e:
        st.error(f"Error al listar plantillas del bucket: {e}")
        return []

# --- FUNCIONES AUXILIARES ---
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
    Genera JPG de tarjeta 8.5x5cm con QR.
    """
    card_img = None
    try:
        if template_name:
            # Descargar los bytes del archivo desde el bucket
            file_bytes = supabase_client.storage.from_(BUCKET_NAME).download(f"{template_name}.png")
            # Abrir los bytes en memoria
            card_img = Image.open(io.BytesIO(file_bytes)).convert('RGB')
            if card_img.size != (CARD_WIDTH_PX, CARD_HEIGHT_PX):
                card_img = card_img.resize((CARD_WIDTH_PX, CARD_HEIGHT_PX))
    except Exception as e:
        st.error(f"Error al cargar plantilla '{template_name}': {e}. Usando fondo blanco.")
        card_img = None 

    # Si no hay plantilla (o falla), crea fondo blanco
    if card_img is None: 
        card_img = Image.new('RGB', (CARD_WIDTH_PX, CARD_HEIGHT_PX), (255, 255, 255))

    draw = ImageDraw.Draw(card_img)
    
    # Cargar 4 fuentes locales (DejaVuSans) con encoding="utf-8"
    try:
        desc_font = ImageFont.truetype("DejaVuSans.ttf", size=36, encoding="utf-8") 
        exp_font = ImageFont.truetype("DejaVuSans.ttf", size=30, encoding="utf-8")  
        consecutive_font = ImageFont.truetype("DejaVuSans-Bold.ttf", size=65, encoding="utf-8") 
        sucursal_font = ImageFont.truetype("DejaVuSans.ttf", size=28, encoding="utf-8") 
    except IOError:
        st.error("Error: No se encontraron los archivos de fuente (DejaVuSans.ttf o DejaVuSans-Bold.ttf). Asegúrate de que estén en la misma carpeta que app.py.")
        desc_font = exp_font = consecutive_font = sucursal_font = ImageFont.load_default()

    # Generar QR
    qr = qrcode.QRCode(1, qrcode.constants.ERROR_CORRECT_M, 8, 2); qr.add_data(data_to_encode); qr.make(fit=True); qr_img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
    
    # Lógica de Posiciones y Text Wrap
    
    # 1. Textos
    exp_text = f"Válido hasta: {expiration}"
    cons_text = f"{consecutive}" 

    # Texto de Sucursales
    if not branch_names: 
        sucursales_text = "Válido en todas las sucursales"
    else:
        sucursales_text = "Sucursales: " + ", ".join(branch_names)

    # 2. Posición QR
    QR_X = CARD_WIDTH_PX - QR_SIZE_PX - BORDER_PX
    QR_Y = BORDER_PX + 50 
    QR_POS = (int(QR_X), int(QR_Y))

    # 3. Calcular anchos
    exp_width = exp_font.getlength(exp_text)
    cons_width = consecutive_font.getlength(cons_text)
    sucursales_width = sucursal_font.getlength(sucursales_text)

    # 4. Posición Consecutivo
    CONS_X_CENTERED_ON_QR = (QR_X + (QR_SIZE_PX / 2)) - (cons_width / 2)
    CONS_Y = QR_Y + QR_SIZE_PX + 20 
    CONS_POS = (int(CONS_X_CENTERED_ON_QR), int(CONS_Y))

    # 5. Posición Sucursales
    cons_bbox = consecutive_font.getbbox(cons_text)
    cons_height = cons_bbox[3] - cons_bbox[1]
    SUC_X_CENTERED_ON_QR = (QR_X + (QR_SIZE_PX / 2)) - (sucursales_width / 2)
    SUC_Y = CONS_Y + cons_height + 15 
    SUC_POS = (int(SUC_X_CENTERED_ON_QR), int(SUC_Y))

    # 6. Posición Fecha
    exp_bbox = exp_font.getbbox(exp_text)
    exp_height = exp_bbox[3] - exp_bbox[1]
    EXP_X_CENTERED_ON_CARD = (CARD_WIDTH_PX / 2) - (exp_width / 2)
    EXP_Y_BOTTOM = CARD_HEIGHT_PX - BORDER_PX - exp_height
    EXP_POS = (int(EXP_X_CENTERED_ON_CARD), int(EXP_Y_BOTTOM))

    # 7. Lógica de Text Wrap para Validez/Restricciones
    WRAP_CHARS = 55 
    GAP_BETWEEN_BLOCKS = 20 
    
    validez_text = "Validez: " + ". ".join(scopes_text_list) if scopes_text_list else ""
    restric_text = "Restricciones: " + ". ".join(restrictions_text_list) if restrictions_text_list else ""

    wrapped_validez = textwrap.wrap(validez_text, width=WRAP_CHARS)
    wrapped_restric = textwrap.wrap(restric_text, width=WRAP_CHARS)
    
    desc_bbox = desc_font.getbbox("A")
    line_height = (desc_bbox[3] - desc_bbox[1]) + 5 
    
    total_text_height = 0
    if wrapped_validez:
        total_text_height += (len(wrapped_validez) * line_height)
    if wrapped_restric:
        total_text_height += (len(wrapped_restric) * line_height)
    if wrapped_validez and wrapped_restric:
        total_text_height += GAP_BETWEEN_BLOCKS 
    
    current_y = EXP_Y_BOTTOM - 15 - total_text_height 

    for line in wrapped_validez:
        line_width = desc_font.getlength(line)
        LINE_X_CENTERED = (CARD_WIDTH_PX / 2) - (line_width / 2)
        draw.text((int(LINE_X_CENTERED), int(current_y)), line, fill=(0,0,0), font=desc_font)
        current_y += line_height
    
    if wrapped_validez and wrapped_restric:
        current_y += GAP_BETWEEN_BLOCKS

    for line in wrapped_restric:
        line_width = desc_font.getlength(line)
        LINE_X_CENTERED = (CARD_WIDTH_PX / 2) - (line_width / 2)
        draw.text((int(LINE_X_CENTERED), int(current_y)), line, fill=(0,0,0), font=desc_font)
        current_y += line_height
    
    # Dibujar Textos (Consecutivo, Sucursales y Fecha)
    draw.text(CONS_POS, cons_text, fill=(0,0,0), font=consecutive_font)
    draw.text(SUC_POS, sucursales_text, fill=(80,80,80), font=sucursal_font) 
    draw.text(EXP_POS, exp_text, fill=(100,100,100), font=exp_font)
    
    # Pegar QR
    qr_scaled = qr_img.resize((QR_SIZE_PX, QR_SIZE_PX))
    card_img.paste(qr_scaled, QR_POS)

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

# --- BARRA LATERAL Y NAVEGÁCIÓ ---
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
            
            # Selector de Plantilla (usa Supabase)
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

            # Inputs
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
                selected_restriction_names = st.multiselect("Restricciones (Aparecerá en la tarjeta)", options=restriction_list, default=default_restrictions, key=f"{form_key}_restrictions")

                default_count = None if st.session_state.get('clear_form_inputs') else st.session_state.get(f'{form_key}_count')
                count = st.number_input("Cantidad (*Obligatorio*)", min_value=1, max_value=1000, value=default_count, placeholder="1", key=f'{form_key}_count')

            # --- Live Calculation Display (Inside Form, Before Submit) ---
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

                # (cálculos... sin cambios)
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
            
            # --- INICIO CAMBIO: Vista Previa con Botón ---
            st.divider()
            st.subheader("Vista Previa")
            
            # 1. El Botón
            if st.button("Ver Vista Previa", key=f"{form_key}_preview_btn"):
                st.session_state['show_preview'] = True
            
            # 2. El Contenedor de la Vista Previa
            if st.session_state.get('show_preview', False):
                with st.container(border=True): 
                    try:
                        # Leer valores en vivo del st.session_state
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
                        
                        create_qr_card(
                            "PREVIEW-ID-12345678",
                            template_name_for_preview, 
                            preview_path,
                            live_scopes,
                            live_restric,
                            live_branch_list,
                            (datetime.now() + timedelta(days=live_months * 30)).strftime("%Y-%m-%d"),
                            "0000"
                        )
                        st.image(preview_path, caption="Vista previa generada con datos de ejemplo.")
                        
                        # 3. Botón para ocultar
                        if st.button("Ocultar Vista Previa", key=f"{form_key}_hide_preview"):
                            st.session_state['show_preview'] = False
                            st.rerun() 
                    
                    except Exception as e:
                        st.error(f"No se pudo generar la vista previa: {e}")
            else:
                st.caption("Presione 'Ver Vista Previa' para previsualizar la tarjeta con los datos actuales.")
            # --- FIN CAMBIO: Vista Previa con Botón ---

            st.divider()

            # --- Submit Button ---
            submitted = st.form_submit_button("✔️ Generar Lote")

            if submitted:
                # Ocultar la vista previa al generar
                st.session_state['show_preview'] = False
                
                # --- VALIDACIÓN FINAL ---
                error = False
                # Re-fetch final values from state at submission time
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

                        for entry in coupons:
                            path = os.path.join(GENERATED_QRS_DIR, f"{entry['consecutive']:04d}.jpg")
                            
                            create_qr_card(
                                entry['id'], 
                                template_name_for_submit, 
                                path, 
                                scopes_text_list, 
                                restrictions_text_list, 
                                branch_names_for_card, 
                                entry['expiration_date'], 
                                f"{entry['consecutive']:04d}"
                            )

                            generated_paths.append(path)
                        zip_buffer = io.BytesIO()
                        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                            for p in generated_paths: zf.write(p, os.path.basename(p))
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
                st.session_state['show_preview'] = False # <-- CAMBIO: Ocultar preview
                st.rerun()

        if 'clear_form_inputs' in st.session_state:
             st.session_state['clear_form_inputs'] = False


    # --- INICIO CAMBIO: Pestaña de Gestión de Plantilla (Rehecha para Supabase) ---
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
                    
                    # Verificar si ya existe en Supabase
                    existing_templates = get_template_list()
                    if template_name in existing_templates:
                        st.error(f"Ya existe una plantilla con el nombre '{template_name}'. Use otro nombre.")
                    else:
                        try:
                            # Validar dimensiones
                            img = Image.open(up_file)
                            if img.size != (CARD_WIDTH_PX, CARD_HEIGHT_PX):
                                st.error(f"Error: La imagen debe ser de {CARD_WIDTH_PX}x{CARD_HEIGHT_PX} píxeles. La subida es de {img.size[0]}x{img.size[1]}px.")
                            else:
                                # Subir a Supabase Storage
                                file_bytes = up_file.getbuffer()
                                supabase_client.storage.from_(BUCKET_NAME).upload(
                                    file_path=save_name,
                                    file=file_bytes,
                                    file_options={"content-type": "image/png"}
                                )
                                st.success(f"Plantilla '{template_name}' guardada en el bucket.")
                                st.cache_data.clear() # Limpiar el cache de get_template_list
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
                    
                    # Obtener URL pública para st.image
                    try:
                        public_url = supabase_client.storage.from_(BUCKET_NAME).get_public_url(f"{t_name}.png")
                        st.image(public_url, width=400, caption=f"Vista previa de {t_name}")
                    except Exception as e:
                        st.error(f"No se pudo cargar la imagen: {e}")
                    
                    if st.button("Eliminar Plantilla", key=f"delete_{t_name}", type="primary"):
                        try:
                            # Borrar de Supabase
                            supabase_client.storage.from_(BUCKET_NAME).remove([f"{t_name}.png"])
                            st.success(f"Plantilla '{t_name}' eliminada del bucket.")
                            st.cache_data.clear()
                            st.rerun()
                        except Exception as e:
                            st.error(f"No se pudo eliminar: {e}")
        
        st.divider()
        st.subheader("3. Guía de Diseño (JPG)")
        st.markdown(f"Guía horizontal ({CARD_WIDTH_PX}x{CARD_HEIGHT_PX} px).")
        # La guía se sigue generando localmente solo para la descarga
        BLANK_JPG_GUIDE = os.path.join(TEMPLATE_DIR, "plantilla_guia.jpg")
        if st.button("Generar/Descargar Guía JPG", key="dl_guide"):
            generate_design_template(BLANK_JPG_GUIDE);
            with open(BLANK_JPG_GUIDE, "rb") as f: 
                st.download_button("Descargar Guía (JPG)", f, os.path.basename(BLANK_JPG_GUIDE), "image/jpeg", key="dl_guide_btn")
    # --- FIN CAMBIO: Pestaña de Gestión de Plantilla ---


# --- MÓDULO REPORTES ---
elif app_mode == "📊 Reportes":
    if user_role != 'Admin': st.error("Acceso denegado."); st.stop()
    st.header("Reportes")
    tab_cupones, tab_lotes, tab_recibos = st.tabs(["Cupones Emitidos", "Lotes", "Recibos de Lote"])

    # --- Tab Cupones ---
    with tab_cupones:
        st.subheader("Detalle de Cupones Emitidos")
        st.sidebar.header("Filtros Reporte Cupones")
        col1_date, col2_date = st.sidebar.columns(2)
        with col1_date: start_date_coupon = st.date_input("Creación Desde", value=None, key="c_start")
        with col2_date: end_date_coupon = st.date_input("Creación Hasta", value=None, key="c_end")
        coupon_filters = []
        if start_date_coupon: coupon_filters.append(f"creation_date=gte.{start_date_coupon}")
        if end_date_coupon: coupon_filters.append(f"creation_date=lte.{end_date_coupon}")
        coupon_filter_string = "&".join(coupon_filters)
        df_coupons = db_service.get_activity_report(coupon_filter_string)
        if not df_coupons.empty:
            st.dataframe(df_coupons, use_container_width=True, hide_index=True)
            total_qrs = len(df_coupons); redeemed_qrs = df_coupons['is_redeemed'].sum()
            c1, c2 = st.columns(2); c1.metric("Total", f"{total_qrs} 🎟️"); c2.metric("Canjeados", f"{redeemed_qrs} ✅")
        else: st.info("No hay cupones con esos filtros.")

    # --- Tab Lotes ---
    with tab_lotes:
        st.subheader("Resumen de Lotes Creados")
        df_batches = db_service.get_batch_report()
        if not df_batches.empty:
            df_display_batches = df_batches.copy()
            num_cols_crc = ['Ref CRC', 'Venta CRC']; num_cols_usd = ['Ref USD', 'Venta USD']
            for col in num_cols_crc: df_display_batches[col] = pd.to_numeric(df_display_batches[col], errors='coerce').fillna(0).apply(lambda x: f"₡ {x:,.2f}")
            for col in num_cols_usd: df_display_batches[col] = pd.to_numeric(df_display_batches[col], errors='coerce').fillna(0).apply(lambda x: f"$ {x:,.2f}")
            df_display_batches['Creados'] = pd.to_numeric(df_display_batches['Creados'], errors='coerce').fillna(0).astype(int)
            df_display_batches['Canjeados'] = pd.to_numeric(df_display_batches['Canjeados'], errors='coerce').fillna(0).astype(int)
            st.dataframe(df_display_batches.drop(columns=['ID Lote'], errors='ignore'), use_container_width=True, hide_index=True)
            total_lotes = len(df_batches); total_creados = pd.to_numeric(df_batches['Creados'], errors='coerce').sum(); total_canjeados = pd.to_numeric(df_batches['Canjeados'], errors='coerce').sum()
            c1,c2,c3 = st.columns(3); c1.metric("Lotes", f"{total_lotes}"); c2.metric("Total Creados", f"{int(total_creados)}"); c3.metric("Total Canjeados", f"{int(total_canjeados)}")
        else: st.info("No hay lotes creados.")

    # --- Tab Recibos ---
    with tab_recibos:
        st.subheader("Visualizar / Reimprimir Recibos de Lote")
        df_receipts_list = db_service.get_all_receipts()
        if not df_receipts_list.empty:
            receipt_options_dict = {f"{row['Recibo ID']} - {row['Nombre Lote']} ({row['Fecha Generado']})": row['Recibo ID'] for _, row in df_receipts_list.iterrows()}
            receipt_display_list = ["-- Seleccione un Recibo --"] + list(receipt_options_dict.keys())
            selected_receipt_display = st.selectbox("Seleccione el recibo:", options=receipt_display_list, index=0, key="receipt_selector")
            if selected_receipt_display != "-- Seleccione un Recibo --":
                selected_receipt_id = receipt_options_dict[selected_receipt_display]
                st.session_state['selected_receipt_id'] = selected_receipt_id
                if st.session_state['selected_receipt_id']:
                    receipt_data = db_service.get_receipt_data(st.session_state['selected_receipt_id'])
                    if receipt_data:
                        st.divider(); st.subheader(f"Detalles del Recibo #{st.session_state['selected_receipt_id']}")
                        st.code(format_receipt(receipt_data), language=None)
                        st.caption("Copie o imprima (Ctrl+P / Cmd+P).")
                    else: st.error(f"No se cargaron detalles del recibo ID: {st.session_state['selected_receipt_id']}")
            else: st.session_state['selected_receipt_id'] = None; st.info("Seleccione un recibo.")
        else: st.warning("No hay recibos guardados.")
