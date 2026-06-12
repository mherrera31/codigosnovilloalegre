# app.py (VERSIÓN CON EDITOR VISUAL Y FECHAS EXACTAS)
import streamlit as st
import auth
import db_service
import user_service 
import requests
import qrcode
from PIL import Image, ImageDraw, ImageFont
import uuid
import os
import json
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

# --- TAMAÑO 8.5cm x 5cm ---
CARD_WIDTH_PX = 1004 
CARD_HEIGHT_PX = 591
CARD_WIDTH_MM = 85
CARD_HEIGHT_MM = 50
# --- FIN TAMAÑO ---

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

# --- FUNCIONES AUXILIARES ---
def load_template_config(template_name):
    """Descarga las coordenadas JSON desde Supabase."""
    if not template_name or template_name == "Fondo Blanco":
        return None
    try:
        file_bytes = supabase_client.storage.from_(BUCKET_NAME).download(f"{template_name}.json")
        return json.loads(file_bytes.decode('utf-8'))
    except Exception:
        return None 

def create_qr_card(
    data_to_encode: str, 
    template_name: str, 
    output_path: str, 
    scopes_text_list: list, 
    restrictions_text_list: list, 
    branch_names: list, 
    consecutive: str,
    layout_config: dict = None
):
    """Genera JPG de tarjeta con posiciones dinámicas."""
    
    # POSICIONES POR DEFECTO
    if not layout_config:
        layout_config = {
            'qr_x': CARD_WIDTH_PX - QR_SIZE_PX - BORDER_PX, 'qr_y': BORDER_PX + 30, 'qr_size': QR_SIZE_PX,
            'cons_x': CARD_WIDTH_PX - QR_SIZE_PX - BORDER_PX + 80, 'cons_y': BORDER_PX + 30 + QR_SIZE_PX + 10,
            'suc_x': CARD_WIDTH_PX - QR_SIZE_PX - BORDER_PX + 20, 'suc_y': BORDER_PX + 30 + QR_SIZE_PX + 70,
            'val_x': 50, 'val_y': 350
        }

    card_img = None
    try:
        if template_name and template_name != "Fondo Blanco":
            file_bytes = supabase_client.storage.from_(BUCKET_NAME).download(f"{template_name}.png")
            card_img = Image.open(io.BytesIO(file_bytes)).convert('RGB')
            if card_img.size != (CARD_WIDTH_PX, CARD_HEIGHT_PX):
                card_img = card_img.resize((CARD_WIDTH_PX, CARD_HEIGHT_PX))
    except Exception as e:
        card_img = None 

    if card_img is None: 
        card_img = Image.new('RGB', (CARD_WIDTH_PX, CARD_HEIGHT_PX), (255, 255, 255))

    draw = ImageDraw.Draw(card_img)
    
    # --- FUENTES ---
    try:
        validez_font = ImageFont.truetype("DejaVuSans-Bold.ttf", size=30) 
        sucursal_font = ImageFont.truetype("DejaVuSans-Bold.ttf", size=24) 
        consecutive_font = ImageFont.truetype("DejaVuSans-Bold.ttf", size=55) 
        footer_font = ImageFont.truetype("DejaVuSans-Bold.ttf", size=24)  
        web_font = ImageFont.truetype("DejaVuSans-Bold.ttf", size=24)
    except IOError:
        validez_font = footer_font = consecutive_font = sucursal_font = web_font = ImageFont.load_default()

    # Generar QR
    qr = qrcode.QRCode(1, qrcode.constants.ERROR_CORRECT_M, 8, 2); qr.add_data(data_to_encode); qr.make(fit=True); 
    qr_img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
    
    # --- TEXTOS ---
    validez_text = "Validez: " + ". ".join(scopes_text_list) if scopes_text_list else ""
    terms_text = "Ver Términos y Condiciones en"
    web_text = "www.restauranteelnovilloalegre.com"
    cons_text = f"{consecutive}"
    branch_names_list = branch_names if branch_names else ["Válido en todas", "las sucursales"]

    # --- DIBUJO BASADO EN COORDENADAS DINÁMICAS ---
    
    # 1. QR
    qr_scaled = qr_img.resize((int(layout_config['qr_size']), int(layout_config['qr_size'])))
    card_img.paste(qr_scaled, (int(layout_config['qr_x']), int(layout_config['qr_y'])))
    
    # 2. Consecutivo
    draw.text((int(layout_config['cons_x']), int(layout_config['cons_y'])), cons_text, fill=(0,0,0), font=consecutive_font)
    
    # 3. Sucursales
    current_suc_y = int(layout_config['suc_y'])
    for line in branch_names_list:
        draw.text((int(layout_config['suc_x']), current_suc_y), line, fill=(0,0,0), font=sucursal_font)
        current_suc_y += 26 

    # 4. Validez
    validez_lines = textwrap.wrap(validez_text, width=35)
    bbox_val = validez_font.getbbox("A") if hasattr(validez_font, 'getbbox') else (0,0,0,30)
    h_val_line = (bbox_val[3] - bbox_val[1]) + 10
    current_y_val = int(layout_config['val_y'])
    for line in validez_lines:
        draw.text((int(layout_config['val_x']), current_y_val), line, fill=(0,0,0), font=validez_font)
        current_y_val += h_val_line

    # 5. Footer Web (Fijo abajo al centro)
    bbox_web = web_font.getbbox(web_text) if hasattr(web_font, 'getbbox') else (0,0,0,24)
    h_web = bbox_web[3] - bbox_web[1]
    bbox_terms = footer_font.getbbox(terms_text) if hasattr(footer_font, 'getbbox') else (0,0,0,24)
    h_terms = bbox_terms[3] - bbox_terms[1]
    Y_WEB = CARD_HEIGHT_PX - BORDER_PX - h_web
    Y_TERMS = Y_WEB - h_terms - 8 
    CARD_CENTER_X = CARD_WIDTH_PX / 2
    draw.text((int(CARD_CENTER_X - (footer_font.getlength(terms_text) / 2)), int(Y_TERMS)), terms_text, fill=(0,0,0), font=footer_font)
    draw.text((int(CARD_CENTER_X - (web_font.getlength(web_text) / 2)), int(Y_WEB)), web_text, fill=(0,0,0), font=web_font)

    card_img.save(output_path, "JPEG", quality=95)
    return output_path

def generate_design_template(output_filename):
    """Genera guía JPG 8.5x5cm."""
    img = Image.new('RGB', (CARD_WIDTH_PX, CARD_HEIGHT_PX), (230, 230, 230)); draw = ImageDraw.Draw(img)
    try:
        title_font = ImageFont.truetype("DejaVuSans-Bold.ttf", size=40)
        main_font = ImageFont.truetype("DejaVuSans.ttf", size=24)
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
        if user_role == 'Admin': 
            menu_options.extend(["🔑 Gestión de Usuarios", "⚙️ Configuración", "📊 Reportes", "📦 Gestión de Lotes"])
        
        if user_role in ['Admin', 'Creator']: 
            menu_options.append("🛠️ Creador QR")
        
        if user_role in ['Admin', 'Cashier']: 
            menu_options.append("📲 Escáner")

        if user_role == 'Contabilidad':
            menu_options.append("📊 Reportes")
        
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

        if 'form_key_counter' not in st.session_state: st.session_state['form_key_counter'] = 0
        form_key = f"qr_creator_form_{st.session_state['form_key_counter']}"
        
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

            submitted = st.form_submit_button("✔️ Generar Lote")

            if submitted:
                st.session_state['show_preview'] = False
                
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
                                    
                                    layout_cfg = load_template_config(template_name_for_submit)
                                    create_qr_card(
                                        entry['id'], 
                                        template_name_for_submit, 
                                        path, 
                                        scopes_text_list, 
                                        restrictions_text_list, 
                                        branch_names_for_card, 
                                        f"{entry['consecutive']:04d}",
                                        layout_cfg
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

                    template_name_for_preview = None
                    if live_template_name_str != "Fondo Blanco":
                        template_name_for_preview = live_template_name_str 
                    
                    live_branch_list = []
                    if not live_all_branches:
                        live_branch_list = live_branches

                    preview_path = os.path.join(GENERATED_QRS_DIR, "preview.jpg")
                    
                    layout_cfg_preview = load_template_config(template_name_for_preview)
                    create_qr_card(
                        "PREVIEW-ID-12345678",
                        template_name_for_preview, 
                        preview_path,
                        live_scopes,
                        [], 
                        live_branch_list,
                        "0000",
                        layout_cfg_preview
                    )
                    st.image(preview_path, caption="Vista previa generada con los datos actuales del formulario.", width=700)
                    
                    if st.button("Ocultar Vista Previa", key=f"{form_key}_hide_preview"):
                        st.session_state['show_preview'] = False
                        st.rerun() 
                
                except Exception as e:
                    st.error(f"No se pudo generar la vista previa: {e}")
        else:
            st.caption("Presione 'Ver/Actualizar Vista Previa' para previsualizar la tarjeta con los datos del formulario.")

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
        
        # --- NUEVO EDITOR VISUAL ---
        st.subheader("🛠️ Editor Visual de Plantilla")
        templates_for_editor = get_template_list()
        
        if templates_for_editor:
            editor_template = st.selectbox("Seleccione plantilla a editar", templates_for_editor)
            
            # Cargar config actual o por defecto
            current_cfg = load_template_config(editor_template)
            if not current_cfg:
                current_cfg = {
                    'qr_x': 680, 'qr_y': 80, 'qr_size': 250,
                    'cons_x': 760, 'cons_y': 340,
                    'suc_x': 700, 'suc_y': 400,
                    'val_x': 50, 'val_y': 350
                }

            col_editor1, col_editor2 = st.columns([1, 1.5])
            
            with col_editor1:
                st.markdown("**Controles de Posición**")
                new_cfg = {}
                new_cfg['qr_size'] = st.slider("Tamaño del QR", 100, 400, int(current_cfg['qr_size']))
                new_cfg['qr_x'] = st.slider("Posición QR (Izquierda/Derecha)", 0, CARD_WIDTH_PX, int(current_cfg['qr_x']))
                new_cfg['qr_y'] = st.slider("Posición QR (Arriba/Abajo)", 0, CARD_HEIGHT_PX, int(current_cfg['qr_y']))
                st.divider()
                new_cfg['cons_x'] = st.slider("Posición Consecutivo (Izquierda/Derecha)", 0, CARD_WIDTH_PX, int(current_cfg['cons_x']))
                new_cfg['cons_y'] = st.slider("Posición Consecutivo (Arriba/Abajo)", 0, CARD_HEIGHT_PX, int(current_cfg['cons_y']))
                st.divider()
                new_cfg['val_x'] = st.slider("Posición Texto Validez (X)", 0, CARD_WIDTH_PX, int(current_cfg['val_x']))
                new_cfg['val_y'] = st.slider("Posición Texto Validez (Y)", 0, CARD_HEIGHT_PX, int(current_cfg['val_y']))
                st.divider()
                new_cfg['suc_x'] = st.slider("Posición Sucursales (X)", 0, CARD_WIDTH_PX, int(current_cfg['suc_x']))
                new_cfg['suc_y'] = st.slider("Posición Sucursales (Y)", 0, CARD_HEIGHT_PX, int(current_cfg['suc_y']))

                if st.button("💾 Guardar Configuración", type="primary"):
                    json_data = json.dumps(new_cfg).encode('utf-8')
                    try:
                        supabase_client.storage.from_(BUCKET_NAME).upload(
                            path=f"{editor_template}.json", 
                            file=json_data, 
                            file_options={"content-type": "application/json", "upsert": "true"}
                        )
                        st.success("¡Configuración guardada exitosamente!")
                    except Exception as e:
                        st.error(f"Error guardando configuración: {e}")

            with col_editor2:
                st.markdown("**Vista Previa en Vivo**")
                preview_editor_path = os.path.join(GENERATED_QRS_DIR, "editor_preview.jpg")
                create_qr_card(
                    "PREVIEW-123", editor_template, preview_editor_path, 
                    ["Solo Cena", "Válido Lunes a Jueves"], [], 
                    ["Multiplaza", "Escazú"], "0001", new_cfg
                )
                st.image(preview_editor_path, use_column_width=True)
            
            st.divider()
        else:
            st.info("Suba al menos una plantilla para usar el editor visual.")

        
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
                                file_bytes = up_file.getvalue() 
                                supabase_client.storage.from_(BUCKET_NAME).upload(
                                    path=save_name, 
                                    file=file_bytes, 
                                    file_options={"content-type": "image/png"}
                                )
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
                            
                            # Borrar el JSON si existe
                            try:
                                supabase_client.storage.from_(BUCKET_NAME).remove([f"{t_name}.json"])
                            except:
                                pass
                                
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


# --- MÓDULO GESTIÓN DE LOTES (Nuevo) ---
elif app_mode == "📦 Gestión de Lotes":
    if user_role != 'Admin': st.error("Acceso denegado."); st.stop()
    st.header("Gestión Administrativa de Lotes")
    st.markdown("Desde aquí puede **volver a descargar los QRs** de un lote existente o **eliminarlo** permanentemente.")

    df_batches = db_service.get_batch_report()
    
    if not df_batches.empty:
        st.dataframe(df_batches, use_container_width=True, hide_index=True)
        st.divider()

        batch_options = {f"{row['Nombre Lote']} (Creado: {row['Creado']})": row['ID Lote'] for _, row in df_batches.iterrows()}
        selected_batch_name = st.selectbox("Seleccione un Lote para gestionar:", ["-- Seleccione --"] + list(batch_options.keys()))

        if selected_batch_name != "-- Seleccione --":
            selected_batch_id = batch_options[selected_batch_name]
            st.info(f"Lote seleccionado ID: {selected_batch_id}")

            col_actions1, col_actions2 = st.columns(2)

            with col_actions1:
                st.subheader("📥 Re-descargar QRs")
                st.markdown("Genere nuevamente el archivo ZIP con los códigos QR originales.")
                
                template_list_regen = ["Fondo Blanco"] + get_template_list()
                selected_template_regen = st.selectbox("Plantilla para reimpresión:", template_list_regen, key="regen_template")

                if st.button("Generar ZIP de Reimpresión", type="primary"):
                    with st.spinner("Recuperando datos y generando imágenes..."):
                        coupons_data = db_service.get_batch_details_for_reprint(selected_batch_id)
                        
                        if coupons_data:
                            zip_buffer_regen = io.BytesIO()
                            template_name_regen = None if selected_template_regen == "Fondo Blanco" else selected_template_regen

                            with zipfile.ZipFile(zip_buffer_regen, 'w', zipfile.ZIP_DEFLATED) as zf:
                                for coupon in coupons_data:
                                    scopes_list = [s['validity_scopes']['scope_name'] for s in coupon.get('coupon_scopes', []) if s.get('validity_scopes')]
                                    restric_list = [r['restrictions']['restriction_description'] for r in coupon.get('coupon_restrictions', []) if r.get('restrictions')]
                                    
                                    branch_ids = coupon.get('branch_permissions')
                                    branch_names_regen = []
                                    if branch_ids:
                                        all_branches = db_service.get_branches()
                                        b_map = {str(b['id']): b['name'] for b in all_branches}
                                        branch_names_regen = [b_map.get(str(bid), "Sucursal") for bid in branch_ids]

                                    fname = f"{coupon['consecutive']:04d}.jpg"
                                    path = os.path.join(GENERATED_QRS_DIR, fname)

                                    layout_cfg_regen = load_template_config(template_name_regen)
                                    create_qr_card(
                                        coupon['id'],
                                        template_name_regen,
                                        path,
                                        scopes_list,
                                        restric_list,
                                        branch_names_regen,
                                        f"{coupon['consecutive']:04d}",
                                        layout_cfg_regen
                                    )
                                    zf.write(path, fname)
                            
                            zip_buffer_regen.seek(0)
                            st.success("✅ Archivo generado exitosamente.")
                            st.download_button(
                                label="⬇️ Descargar ZIP Ahora",
                                data=zip_buffer_regen,
                                file_name=f"REIMPRESION_Lote_{selected_batch_id[:4]}.zip",
                                mime="application/zip"
                            )
                        else:
                            st.error("No se encontraron cupones para este lote.")

            with col_actions2:
                st.subheader("🗑️ Eliminar Lote")
                st.warning("⚠️ ESTA ACCIÓN ES IRREVERSIBLE. Borrará el lote, todos sus cupones y el historial de canjes.")
                
                confirm_del_batch = st.checkbox("Estoy seguro de que quiero eliminar este lote.", key="confirm_del_batch")
                
                if st.button("Eliminar Lote Definitivamente", type="secondary", disabled=not confirm_del_batch):
                    with st.spinner("Eliminando registros..."):
                        if db_service.delete_batch(selected_batch_id):
                            st.success("Lote eliminado correctamente.")
                            st.rerun()
                        else:
                            st.error("Hubo un error al eliminar el lote.")

    else:
        st.info("No hay lotes registrados para gestionar.")


# --- MÓDULO REPORTES ---
elif app_mode == "📊 Reportes":
    if user_role not in ['Admin', 'Contabilidad']: st.error("Acceso denegado."); st.stop()
    st.header("Reportes")
    tab_cupones, tab_lotes, tab_recibos = st.tabs(["Cupones Emitidos", "Lotes", "Recibos de Lote"])

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
            from datetime import datetime

            df_coupons['temp_fecha_venc'] = pd.to_datetime(df_coupons['Fecha de Vencimiento'], errors='coerce')
            
            total_qrs = len(df_coupons)
            redeemed_qrs = df_coupons['Canjeado'].sum()
            sin_canjear_qrs = total_qrs - redeemed_qrs
            
            vencidos_qrs = len(df_coupons[
                (df_coupons['Canjeado'] == False) & 
                (df_coupons['temp_fecha_venc'] < datetime.now())
            ])

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total", f"{total_qrs} 🎟️")
            c2.metric("Canjeados", f"{redeemed_qrs} ✅")
            c3.metric("Sin Canjear", f"{sin_canjear_qrs} ⏳")
            c4.metric("Vencidos", f"{vencidos_qrs} ⚠️")
            st.divider()
            
            def obtener_estado(row):
                if row['Canjeado']: return "Canjeado"
                elif row['temp_fecha_venc'] < datetime.now(): return "Vencido"
                else: return "Activo"

            df_coupons['Estado'] = df_coupons.apply(obtener_estado, axis=1)
            df_coupons['Canjeado'] = df_coupons['Canjeado'].apply(lambda x: "SÍ ✅" if x else "NO")

            cols_to_exclude = ['Estado', 'Canjeado', 'temp_fecha_venc', 'id'] 
            cols = ['Estado', 'Canjeado'] + [c for c in df_coupons.columns if c not in cols_to_exclude]
            df_final_view = df_coupons[cols].copy()

            def colorear_filas(row):
                if row['Estado'] == 'Vencido':
                    return ['background-color: #ffd700; color: black'] * len(row)
                elif row['Estado'] == 'Canjeado':
                    return ['background-color: #32CD32; color: black; font-weight: bold'] * len(row)
                else:
                    return [''] * len(row)

            st.dataframe(df_final_view.style.apply(colorear_filas, axis=1), hide_index=True)

        else:
            st.info("No hay cupones con esos filtros.")

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
