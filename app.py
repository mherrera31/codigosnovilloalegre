# app.py (VERSIÓN COMPLETA FINAL - Mandatory, Live Calc, Allowed Branches Report)
import streamlit as st
import auth
import db_service
import user_service # Import user_service here
import requests
import qrcode
from PIL import Image, ImageDraw, ImageFont
import uuid
import os
from datetime import datetime, timedelta
import pandas as pd
import zipfile
import io

# --- CONFIGURACIÓN Y CONSTANTES ---
st.set_page_config(page_title="Sistema QR Novillo Alegre", layout="wide")
LOGO_URL = "https://placehold.co/300x100/1E3260/FFFFFF/png?text=Novillo+Alegre+QR"
TEMPLATE_DIR = 'design_templates'; os.makedirs(TEMPLATE_DIR, exist_ok=True)
GENERATED_QRS_DIR = 'generated_qrs'; os.makedirs(GENERATED_QRS_DIR, exist_ok=True)
TEMPLATE_PATH_KEY = 'current_template_path'
CARD_WIDTH_PX = 1063; CARD_HEIGHT_PX = 591
CARD_WIDTH_MM = 90; CARD_HEIGHT_MM = 50
QR_SIZE_PX = 250; BORDER_PX = 50

# --- Inicialización de Estado ---
# Essential state variables
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'user_role' not in st.session_state: st.session_state['user_role'] = None
if 'username' not in st.session_state: st.session_state['username'] = None
if 'user_id' not in st.session_state: st.session_state['user_id'] = None
if 'branch_id' not in st.session_state: st.session_state['branch_id'] = None
if TEMPLATE_PATH_KEY not in st.session_state: st.session_state[TEMPLATE_PATH_KEY] = None
# State for receipt and download display
if 'last_receipt_data' not in st.session_state: st.session_state['last_receipt_data'] = None
if 'show_receipt' not in st.session_state: st.session_state['show_receipt'] = False
if 'last_zip_buffer' not in st.session_state: st.session_state['last_zip_buffer'] = None
if 'last_zip_filename' not in st.session_state: st.session_state['last_zip_filename'] = None
# State for selected receipt in reports
if 'selected_receipt_id' not in st.session_state: st.session_state['selected_receipt_id'] = None
# State for form key to allow programmatic reset
if 'form_key_counter' not in st.session_state: st.session_state['form_key_counter'] = 0


# --- FUNCIONES AUXILIARES ---
def create_qr_card(data_to_encode: str, output_path: str, description: str, expiration: str, consecutive: str):
    """Genera JPG de tarjeta 9x5cm con QR, usando plantilla PNG si existe."""
    template_path = st.session_state.get(TEMPLATE_PATH_KEY)
    card_img = None
    try:
        if template_path and os.path.exists(template_path):
            card_img = Image.open(template_path).convert('RGB')
            if card_img.size != (CARD_WIDTH_PX, CARD_HEIGHT_PX):
                card_img = card_img.resize((CARD_WIDTH_PX, CARD_HEIGHT_PX))
    except Exception as e:
        st.error(f"Err Plantilla: {e}. Fondo blanco.")

    if card_img is None:
        card_img = Image.new('RGB', (CARD_WIDTH_PX, CARD_HEIGHT_PX), (255, 255, 255))

    draw = ImageDraw.Draw(card_img)
    has_template = template_path and os.path.exists(template_path) and card_img.size == (CARD_WIDTH_PX, CARD_HEIGHT_PX)
    if not has_template:
        draw.rectangle([0, 0, CARD_WIDTH_PX, 80], fill=(191, 2, 2))
        try:
            title_font = ImageFont.truetype("arialbd.ttf", size=32)
            draw.text((30, 25), "TARJETA DE REGALO NOVILLO ALEGRE", fill=(255,255,255), font=title_font)
        except IOError: pass
    try:
        main_font = ImageFont.truetype("arial.ttf", size=30)
        consecutive_font = ImageFont.truetype("arialbd.ttf", size=40)
    except IOError:
        main_font = consecutive_font = ImageFont.load_default()

    qr = qrcode.QRCode(1, qrcode.constants.ERROR_CORRECT_M, 8, 2); qr.add_data(data_to_encode); qr.make(fit=True); qr_img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
    QR_X = CARD_WIDTH_PX - QR_SIZE_PX - BORDER_PX; QR_Y = 100
    if has_template: PROMO_POS = (BORDER_PX, 400); EXP_POS = (BORDER_PX, 440); CONS_POS = (BORDER_PX, 480)
    else: PROMO_POS = (BORDER_PX, 150); EXP_POS = (BORDER_PX, 250); CONS_POS = (BORDER_PX, 480)
    draw.text(PROMO_POS, description, fill=(0,0,0), font=main_font); draw.text(EXP_POS, f"Válido hasta: {expiration}", fill=(100,100,100), font=main_font); draw.text(CONS_POS, f"CONSECUTIVO: {consecutive}", fill=(0,0,0), font=consecutive_font)
    qr_scaled = qr_img.resize((QR_SIZE_PX, QR_SIZE_PX)); card_img.paste(qr_scaled, (QR_X, QR_Y))
    card_img.save(output_path, "JPEG", quality=95); return output_path

def generate_design_template(output_filename):
    """Genera guía JPG 9x5cm."""
    img = Image.new('RGB', (CARD_WIDTH_PX, CARD_HEIGHT_PX), (230, 230, 230)); draw = ImageDraw.Draw(img)
    try: title_font = ImageFont.truetype("arialbd.ttf", size=40); main_font = ImageFont.truetype("arial.ttf", size=24)
    except IOError: title_font = main_font = ImageFont.load_default()
    draw.text((BORDER_PX, BORDER_PX), "GUÍA HORIZONTAL (1063x591 px)", fill=(0,0,0), font=title_font)
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
if 'user_role' not in st.session_state: st.session_state['user_role'] = None
if 'username' not in st.session_state: st.session_state['username'] = 'N/A' # Default username
if 'user_id' not in st.session_state: st.session_state['user_id'] = None
if 'branch_id' not in st.session_state: st.session_state['branch_id'] = None
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
        # Use index=0 to default to Dashboard if the previous selection is no longer valid
        current_selection_index = 0
        if 'app_mode_select' in st.session_state and st.session_state['app_mode_select'] in menu_options:
            current_selection_index = menu_options.index(st.session_state['app_mode_select'])

        app_mode = st.sidebar.radio(
            "Módulo",
            menu_options,
            key="app_mode_select",
            index=current_selection_index
        )
        st.markdown("---");
        if st.button("Cerrar Sesión", key="logout_btn"): auth.sign_out()
    else: st.error("Error rol."); auth.sign_out(); st.stop()

# ----------------------------------------
# RENDERIZACIÓN DE MÓDULOS
# ----------------------------------------

if app_mode == "🏠 Dashboard": st.header("Bienvenido al Sistema")
elif app_mode == "🔑 Gestión de Usuarios":
    # Ensure user_service is imported before calling its function
    user_service.render_user_management() # Call the user management render function
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
    promo_options = {p['type_name']: p for p in promos if p.get('type_name')} # Ensure name exists
    branch_options = [b['name'] for b in branches if b.get('name')]
    type_options = {t['type_name']: t['id'] for t in types if t.get('type_name')}
    scope_options = {s['scope_name']: s['id'] for s in scopes if s.get('scope_name')}
    restriction_options = {r['restriction_description']: r['id'] for r in restrictions if r.get('restriction_description')}

    tab_creator, tab_template = st.tabs(["Generador de Lote", "Gestión de Plantilla"])

    with tab_creator:
        st.header("Creación de Tarjetas QR")

        # --- Form Handling ---
        if 'form_key_counter' not in st.session_state: st.session_state['form_key_counter'] = 0
        form_key = f"qr_creator_form_{st.session_state['form_key_counter']}"

        # --- Live Calculation Display Area (Outside Form) ---
        # Get current values from state (widgets update state via key)
        live_promo_name = st.session_state.get(f"{form_key}_promo", "-- Seleccione Promoción --")
        live_promo_data = promo_options.get(live_promo_name, {})
        live_vcrc = st.session_state.get(f"{form_key}_vcrc") # Can be None
        live_vusd = st.session_state.get(f"{form_key}_vusd") # Can be None
        live_count = st.session_state.get(f'{form_key}_count') # Can be None

        st.subheader("Cálculo Estimado")
        calc_placeholder = st.empty() # Placeholder to show calculation or prompt

        # Perform calculation only if all required inputs are valid numbers > 0
        if (live_promo_name != "-- Seleccione Promoción --" and
                isinstance(live_vcrc, (int, float)) and live_vcrc >= 0 and
                isinstance(live_vusd, (int, float)) and live_vusd >= 0 and
                isinstance(live_count, int) and live_count > 0):
            disc_crc = db_service.calculate_discount_per_coupon(live_vcrc, live_promo_data)
            disc_usd = db_service.calculate_discount_per_coupon(live_vusd, live_promo_data)
            total_sale_crc = round((live_vcrc * live_count) - (disc_crc * live_count), 2)
            total_sale_usd = round((live_vusd * live_count) - (disc_usd * live_count), 2)

            with calc_placeholder.container():
                calc_col1, calc_col2 = st.columns(2)
                with calc_col1:
                    st.metric(label="Descuento x Cupón (CRC)", value=f"₡ {disc_crc:,.2f}")
                    st.metric(label="Valor Total Pagado (CRC)", value=f"₡ {total_sale_crc:,.2f}")
                with calc_col2:
                    st.metric(label="Descuento x Cupón (USD)", value=f"$ {disc_usd:,.2f}")
                    st.metric(label="Valor Total Pagado (USD)", value=f"$ {total_sale_usd:,.2f}")
        else:
             with calc_placeholder.container():
                st.caption("ℹ️ Llene todos los campos marcados con (*) para ver el cálculo estimado.")
        st.divider()


        # --- Form Definition ---
        # clear_on_submit=False allows retaining values on validation error
        with st.form(form_key, clear_on_submit=False):
            st.subheader("Configuración del Lote")
            promo_list = ["-- Seleccione Promoción --"] + sorted(list(promo_options.keys())) # Sort options
            type_list = ["-- Seleccione Tipo --"] + sorted(list(type_options.keys()))
            scope_list = sorted(list(scope_options.keys()))
            restriction_list = sorted(list(restriction_options.keys()))

            # Removed optional batch name input
            # Use state key for persistence on error
            input_asociado = st.text_input("**Asociado o Comprador (*Obligatorio*)**", key=f"{form_key}_asoc")

            col1, col2 = st.columns(2)
            with col1:
                selected_promo_name = st.selectbox("Promoción/Diseño (*Obligatorio*)", options=promo_list, index=0, key=f"{form_key}_promo")
                st.caption(f"Descripción (Canje): {promo_options.get(selected_promo_name, {}).get('description', 'N/A')}")
                # Use state key for persistence on error
                value_crc = st.number_input("Valor Base CRC (*Obligatorio*)", min_value=0.0, format="%.2f", value=st.session_state.get(f"{form_key}_vcrc"), placeholder="0.00", key=f"{form_key}_vcrc")
                value_usd = st.number_input("Valor Base USD (*Obligatorio*)", min_value=0.0, format="%.2f", value=st.session_state.get(f"{form_key}_vusd"), placeholder="0.00", key=f"{form_key}_vusd")

            with col2:
                valid_months = st.selectbox("Meses Vigencia (*Obligatorio*)", options=[3, 6, 9, 12], index=0, key=f"{form_key}_months")
                selected_type_name = st.selectbox("Tipo/Campaña (*Obligatorio*)", options=type_list, index=0, key=f"{form_key}_type")
                # Add checkbox for "All Branches"
                all_branches_selected = st.checkbox("Permitir en Todas las Sucursales", key=f"{form_key}_all_branches", value=False) # Default to specific selection
                allowed_branches = st.multiselect(
                    "Sucursales Permitidas (Obligatorio si 'Todas' no está marcado)",
                    options=branch_options,
                    key=f"{form_key}_branches",
                    disabled=all_branches_selected # Disable if "All" is checked
                 )
                # Make Scope and Restriction mandatory
                selected_scope_names = st.multiselect("Validez Cupón (*Obligatorio*)", options=scope_list, key=f"{form_key}_scopes")
                selected_restriction_names = st.multiselect("Restricciones (*Obligatorio*)", options=restriction_list, key=f"{form_key}_restrictions")
                count = st.number_input("Cantidad (*Obligatorio*)", min_value=1, max_value=1000, value=st.session_state.get(f'{form_key}_count'), placeholder="1", key=f'{form_key}_count')

            submitted = st.form_submit_button("✔️ Generar Lote")

            if submitted:
                # --- VALIDACIÓN FINAL (Todos los campos requeridos) ---
                error = False
                # Re-fetch values using keys from CURRENT state inside submission block
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


                if not asoc_val: st.error("❌ 'Asociado' es obligatorio."); error = True
                if not promo_val or promo_val == "-- Seleccione Promoción --": st.error("❌ Seleccione Promoción."); error = True
                if vcrc_val is None or vcrc_val < 0: st.error("❌ Ingrese Valor Base CRC válido (puede ser 0.00)."); error = True
                if vusd_val is None or vusd_val < 0: st.error("❌ Ingrese Valor Base USD válido (puede ser 0.00)."); error = True
                if not type_val or type_val == "-- Seleccione Tipo --": st.error("❌ Seleccione Tipo/Campaña."); error = True
                if count_val is None or count_val <= 0: st.error("❌ Ingrese Cantidad > 0."); error = True
                if months_val is None: st.error("❌ Seleccione Meses de Vigencia."); error=True
                # Mandatory validation for branches OR "all" checkbox
                if not all_branches_val and not branches_val: st.error("❌ Seleccione al menos una Sucursal Permitida o marque 'Todas'."); error = True
                if not scopes_val: st.error("❌ Seleccione al menos una opción de Validez Cupón."); error = True
                if not restrictions_val: st.error("❌ Seleccione al menos una Restricción."); error = True


                if not error:
                    # Proceed with generation
                    type_id = type_options.get(type_val)
                    user_id = st.session_state.get('user_id')
                    scope_ids = [scope_options[n] for n in scopes_val]
                    restriction_ids = [restriction_options[n] for n in restrictions_val]
                    # Use branches_val ONLY if all_branches_val is False
                    branch_names_to_send = branches_val if not all_branches_val else []
                    selected_promo_data = promo_options.get(promo_val, {})

                    st.info(f"⚙️ Generando {count_val} tarjeta(s)... Por favor espere.")

                    result = db_service.create_coupon_batch(
                        count=count_val, asociado_comprador=asoc_val, # Pass asociado
                        promo_data=selected_promo_data, value_crc=vcrc_val, value_usd=vusd_val,
                        type_id=type_id, months_valid=months_val, branch_names=branch_names_to_send, # Send specific or empty list
                        scope_ids=scope_ids, restriction_ids=restriction_ids, user_id=user_id
                    )

                    if result and result.get('coupon_entries'):
                        st.success("✅ ¡Lote y recibo generados!")
                        st.balloons()
                        generated_paths = []; coupons = result['coupon_entries']
                        for entry in coupons:
                            path = os.path.join(GENERATED_QRS_DIR, f"{entry['consecutive']:04d}.jpg")
                            create_qr_card(entry['id'], path, selected_promo_data.get('description','N/A'), entry['expiration_date'], f"{entry['consecutive']:04d}")
                            generated_paths.append(path)
                        zip_buffer = io.BytesIO()
                        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                            for p in generated_paths: zf.write(p, os.path.basename(p))
                        zip_buffer.seek(0)
                        zip_filename = f"lote_{coupons[0]['batch_id']}.zip"
                        # Save state for display outside form
                        st.session_state['last_receipt_data'] = result.get('receipt_data')
                        st.session_state['show_receipt'] = True
                        st.session_state['last_zip_buffer'] = zip_buffer
                        st.session_state['last_zip_filename'] = zip_filename
                        # Reset calculation state
                        st.session_state[f'{form_key}_promo'] = "-- Seleccione Promoción --"
                        st.session_state[f'{form_key}_vcrc'] = None; st.session_state[f'{form_key}_vusd'] = None
                        st.session_state[f'{form_key}_count'] = None; st.session_state[f'{form_key}_asoc'] = ""
                        st.session_state[f'{form_key}_scopes'] = []; st.session_state[f'{form_key}_restrictions'] = []
                        st.session_state[f'{form_key}_branches'] = []; st.session_state[f'{form_key}_all_branches'] = False
                        # Increment form key counter to force form reset on rerun
                        st.session_state['form_key_counter'] += 1
                        st.rerun() # Rerun to display receipt and clear form
                    else:
                        st.error("🚨 Error al generar el lote. Revise los mensajes."); st.session_state['show_receipt'] = False

        # --- Display Receipt and Download (Outside Form) ---
        if st.session_state.get('show_receipt') and st.session_state.get('last_receipt_data'):
            st.divider()
            st.subheader("🧾 Recibo Generado")
            receipt_text = format_receipt(st.session_state['last_receipt_data'])
            st.code(receipt_text, language=None)
            st.caption("Puede copiar este texto o usar Ctrl+P / Cmd+P para imprimir.")
            st.subheader("⬇️ Descargar Tarjetas (ZIP)")
            if st.session_state.get('last_zip_buffer') and st.session_state.get('last_zip_filename'):
                st.download_button(
                    label="Descargar Lote Completo", data=st.session_state['last_zip_buffer'],
                    file_name=st.session_state['last_zip_filename'], mime="application/zip", key="zip_dl_final")
            else: st.warning("Archivo ZIP no encontrado.")
            if st.button("✨ Listo (Ocultar Recibo)"):
                st.session_state['show_receipt'] = False; st.session_state['last_receipt_data'] = None
                st.session_state['last_zip_buffer'] = None; st.session_state['last_zip_filename'] = None
                st.session_state['form_key_counter'] += 1 # Increment key again helps ensure reset
                st.rerun()

    # --- Gestión de Plantilla ---
    with tab_template:
        st.header("Gestión de Plantilla"); st.subheader("1. Guía (JPG)"); st.markdown("Guía horizontal (9x5 cm).")
        BLANK_JPG = os.path.join(TEMPLATE_DIR, "plantilla_guia.jpg")
        if st.button("Generar/Descargar Guía JPG", key="dl_guide"):
            generate_design_template(BLANK_JPG);
            with open(BLANK_JPG, "rb") as f: st.download_button("Descargar Guía (JPG)", f, os.path.basename(BLANK_JPG), "image/jpeg", key="dl_guide_btn")
        st.markdown("---"); st.subheader("2. Subir Plantilla (PNG)")
        up_file = st.file_uploader("Suba PNG (1063x591px, Horizontal)", type="png", key="up_tmpl")
        if up_file:
            save_path = os.path.join(TEMPLATE_DIR, "plantilla_arte_activa.png")
            try:
                with open(save_path, "wb") as f: f.write(up_file.getbuffer())
                st.session_state[TEMPLATE_PATH_KEY] = save_path; st.success(f"Plantilla cargada: {up_file.name}")
            except Exception as e: st.error(f"Error al guardar: {e}")
        current_template = st.session_state.get(TEMPLATE_PATH_KEY)
        if current_template and os.path.exists(current_template): st.info(f"🎨 Plantilla Actual: {os.path.basename(current_template)}")
        else: st.warning("No hay plantilla. Se usará fondo blanco.")


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
            # Display DataFrame, ensuring 'Sucursales Permitidas' is shown
            st.dataframe(df_coupons, use_container_width=True, hide_index=True)
            total_qrs = len(df_coupons); redeemed_qrs = df_coupons['is_redeemed'].sum()
            c1, c2 = st.columns(2); c1.metric("Total", f"{total_qrs} 🎟️"); c2.metric("Canjeados", f"{redeemed_qrs} ✅")
        else: st.info("No hay cupones con esos filtros.")

    # --- Tab Lotes ---
    with tab_lotes:
        st.subheader("Resumen de Lotes Creados")
        df_batches = db_service.get_batch_report()
        if not df_batches.empty:
            # Format numeric columns before display
            num_cols_crc = ['Ref CRC', 'Venta CRC']
            num_cols_usd = ['Ref USD', 'Venta USD']
            # Create a copy to avoid modifying the original DataFrame used elsewhere
            df_display_batches = df_batches.copy()
            for col in num_cols_crc: df_display_batches[col] = pd.to_numeric(df_display_batches[col], errors='coerce').fillna(0).apply(lambda x: f"₡ {x:,.2f}")
            for col in num_cols_usd: df_display_batches[col] = pd.to_numeric(df_display_batches[col], errors='coerce').fillna(0).apply(lambda x: f"$ {x:,.2f}")

            # Display formatted dataframe
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
                st.session_state['selected_receipt_id'] = selected_receipt_id # Store selection
                if st.session_state['selected_receipt_id']:
                    receipt_data = db_service.get_receipt_data(st.session_state['selected_receipt_id'])
                    if receipt_data:
                        st.divider(); st.subheader(f"Detalles del Recibo #{st.session_state['selected_receipt_id']}")
                        st.code(format_receipt(receipt_data), language=None)
                        st.caption("Copie o imprima (Ctrl+P / Cmd+P).")
                    else: st.error(f"No se cargaron detalles del recibo ID: {st.session_state['selected_receipt_id']}")
            else: st.session_state['selected_receipt_id'] = None; st.info("Seleccione un recibo.")
        else: st.warning("No hay recibos guardados.")

# --- Módulo Gestión de Usuarios (placeholder for edit/delete) ---
# This part needs the user_service.py update for edit/delete functionality
elif app_mode == "🔑 Gestión de Usuarios":
     if user_role != 'Admin':
         st.error("Acceso denegado.")
         st.stop()
     # Call the render function from user_service which should now include edit/delete
     user_service.render_user_management()
