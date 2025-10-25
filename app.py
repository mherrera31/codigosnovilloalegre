# app.py (VERSIÓN COMPLETA FINAL - Con Tab Recibos)
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
if TEMPLATE_PATH_KEY not in st.session_state: st.session_state[TEMPLATE_PATH_KEY] = None
if 'last_receipt_data' not in st.session_state: st.session_state['last_receipt_data'] = None
if 'show_receipt' not in st.session_state: st.session_state['show_receipt'] = False
if 'last_zip_buffer' not in st.session_state: st.session_state['last_zip_buffer'] = None
if 'last_zip_filename' not in st.session_state: st.session_state['last_zip_filename'] = None
if 'selected_receipt_id' not in st.session_state: st.session_state['selected_receipt_id'] = None


# --- FUNCIONES AUXILIARES ---
def create_qr_card(data_to_encode: str, output_path: str, description: str, expiration: str, consecutive: str):
    """Genera JPG de tarjeta 9x5cm con QR, usando plantilla PNG si existe."""
    template_path = st.session_state.get(TEMPLATE_PATH_KEY)
    card_img = None # Initialize to None
    try:
        if template_path and os.path.exists(template_path):
            card_img = Image.open(template_path).convert('RGB')
            if card_img.size != (CARD_WIDTH_PX, CARD_HEIGHT_PX):
                # st.warning(f"Plantilla redimensionada a {CARD_WIDTH_PX}x{CARD_HEIGHT_PX}px.") # Reduce warnings
                card_img = card_img.resize((CARD_WIDTH_PX, CARD_HEIGHT_PX))
    except Exception as e:
        st.error(f"Error al cargar plantilla: {e}. Usando fondo blanco.")
        # Fallback even if loading fails
    
    if card_img is None: # Create new image if template failed or doesn't exist
        card_img = Image.new('RGB', (CARD_WIDTH_PX, CARD_HEIGHT_PX), (255, 255, 255))

    draw = ImageDraw.Draw(card_img)
    # Dibujar elementos base si no hay plantilla efectiva
    has_template = template_path and os.path.exists(template_path) and card_img.size == (CARD_WIDTH_PX, CARD_HEIGHT_PX) # Check again after potential resize/error
    if not has_template:
        draw.rectangle([0, 0, CARD_WIDTH_PX, 80], fill=(191, 2, 2))
        try:
            title_font = ImageFont.truetype("arialbd.ttf", size=32)
            draw.text((30, 25), "TARJETA DE REGALO NOVILLO ALEGRE", fill=(255,255,255), font=title_font)
        except IOError: pass # Ignorar si la fuente no está

    # Cargar fuentes principales
    try:
        main_font = ImageFont.truetype("arial.ttf", size=30)
        consecutive_font = ImageFont.truetype("arialbd.ttf", size=40)
    except IOError:
        main_font = consecutive_font = ImageFont.load_default()

    # Generar QR
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=8, border=2)
    qr.add_data(data_to_encode); qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
    QR_POS_X = CARD_WIDTH_PX - QR_SIZE_PX - BORDER_PX; QR_POS_Y = 100

    # Posiciones de texto
    if has_template: # Posiciones asumidas para la plantilla
        PROMO_POS = (BORDER_PX, 400); EXP_POS = (BORDER_PX, 440); CONS_POS = (BORDER_PX, 480)
    else: # Posiciones estándar sobre fondo blanco
        PROMO_POS = (BORDER_PX, 150); EXP_POS = (BORDER_PX, 250); CONS_POS = (BORDER_PX, 480)

    # Dibujar textos
    draw.text(PROMO_POS, description, fill=(0,0,0), font=main_font)
    draw.text(EXP_POS, f"Válido hasta: {expiration}", fill=(100, 100, 100), font=main_font)
    draw.text(CONS_POS, f"CONSECUTIVO: {consecutive}", fill=(0, 0, 0), font=consecutive_font)

    # Pegar QR
    qr_scaled = qr_img.resize((QR_SIZE_PX, QR_SIZE_PX))
    card_img.paste(qr_scaled, (QR_POS_X, QR_POS_Y))

    # Guardar como JPG
    card_img.save(output_path, "JPEG", quality=95)
    return output_path

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
    # Safely get values using .get() with defaults
    created_at_str = 'N/A'
    created_at_val = receipt_data.get('created_at')
    if created_at_val:
        try:
             # Try parsing with timezone first, then without if it fails
             dt_obj = pd.to_datetime(created_at_val)
             created_at_str = dt_obj.strftime('%Y-%m-%d %H:%M:%S')
        except Exception:
             created_at_str = str(created_at_val) # Fallback to string representation

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
    Valor Base Total (CRC): ₡ {float(receipt_data.get('total_ref_value_crc', 0.0)):,.2f}
    Valor Base Total (USD): $ {float(receipt_data.get('total_ref_value_usd', 0.0)):,.2f}
    -----------------------------------------
    VALOR TOTAL PAGADO (CRC): ₡ {float(receipt_data.get('total_sale_value_crc', 0.0)):,.2f}
    VALOR TOTAL PAGADO (USD): $ {float(receipt_data.get('total_sale_value_usd', 0.0)):,.2f}
    -----------------------------------------
    Fecha Generación: {created_at_str}
    -----------------------------------------
    """

# --- LÓGICA DE INICIALIZACIÓN Y LOGIN ---
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'user_role' not in st.session_state: st.session_state['user_role'] = None
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
        # Consistent naming for sidebar options
        if user_role == 'Admin': menu_options.extend(["🔑 Gestión de Usuarios", "⚙️ Configuración", "📊 Reportes"])
        if user_role in ['Admin', 'Creator']: menu_options.append("🛠️ Creador QR")
        if user_role in ['Admin', 'Cashier']: menu_options.append("📲 Escáner")
        app_mode = st.sidebar.radio("Módulo", menu_options, key="app_mode_select")
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
    st.markdown("Presione el botón para abrir la aplicación web de escaneo de cupones.")
    SCANNER_URL = "https://scannernovillo.netlify.app/" # Make sure this is correct
    st.link_button("Abrir Escáner", url=SCANNER_URL, type="primary")

# --- MÓDULO CREADOR QR ---
elif app_mode == "🛠️ Creador QR":
    # Load master data
    promos = db_service.get_promos(); branches = db_service.get_branches()
    types = db_service.get_types(); scopes = db_service.get_validity_scopes()
    restrictions = db_service.get_restrictions()
    promo_options = {p['type_name']: p for p in promos}
    branch_options = [b['name'] for b in branches]
    type_options = {t['type_name']: t['id'] for t in types}
    scope_options = {s['scope_name']: s['id'] for s in scopes}
    restriction_options = {r['restriction_description']: r['id'] for r in restrictions}

    tab_creator, tab_template = st.tabs(["Generador de Lote", "Gestión de Plantilla"])

    with tab_creator:
        st.header("Creación de Tarjetas QR")

        # --- Form Handling ---
        # Initialize form state if not present (helps with clearing)
        if 'form_key_counter' not in st.session_state: st.session_state['form_key_counter'] = 0
        form_key = f"qr_creator_form_{st.session_state['form_key_counter']}"

        with st.form(form_key, clear_on_submit=False): # Control clearing manually via rerun
            st.subheader("Configuración del Lote")
            promo_list = ["-- Seleccione Promoción --"] + list(promo_options.keys())
            type_list = ["-- Seleccione Tipo --"] + list(type_options.keys())

            # Inputs
            input_asociado = st.text_input("**Asociado o Comprador** (Obligatorio)", key=f"{form_key}_asoc")
            input_batch_name = st.text_input("Nombre Personalizado Lote (Opcional)", key=f"{form_key}_bname")

            col1, col2 = st.columns(2)
            with col1:
                selected_promo_name = st.selectbox("Promoción/Diseño*", options=promo_list, index=0, key=f"{form_key}_promo")
                selected_promo = promo_options.get(selected_promo_name, {})
                st.caption(f"Descripción (Canje): {selected_promo.get('description', 'N/A')}")
                value_crc = st.number_input("Valor Base CRC*", min_value=0.0, format="%.2f", value=None, placeholder="0.00", key=f"{form_key}_vcrc")
                value_usd = st.number_input("Valor Base USD*", min_value=0.0, format="%.2f", value=None, placeholder="0.00", key=f"{form_key}_vusd")

                # Calculation Display
                count_val = st.session_state.get(f'{form_key}_count', 0) if st.session_state.get(f'{form_key}_count') is not None else 0
                if selected_promo_name != "-- Seleccione Promoción --" and value_crc is not None and value_usd is not None and count_val > 0:
                    disc_crc = db_service.calculate_discount_per_coupon(value_crc, selected_promo)
                    disc_usd = db_service.calculate_discount_per_coupon(value_usd, selected_promo)
                    total_sale_crc = round((value_crc * count_val) - (disc_crc * count_val), 2)
                    total_sale_usd = round((value_usd * count_val) - (disc_usd * count_val), 2)
                    st.markdown(f"**Desc. x Cupón (CRC):** ₡`{disc_crc:,.2f}` | **Total Pagado:** ₡`{total_sale_crc:,.2f}`")
                    st.markdown(f"**Desc. x Cupón (USD):** $`{disc_usd:,.2f}` | **Total Pagado:** $`{total_sale_usd:,.2f}`")
                else: st.caption("Llene campos (*) para ver cálculo.")

            with col2:
                valid_months = st.selectbox("Meses Vigencia*", options=[3, 6, 9, 12], index=0, key=f"{form_key}_months")
                selected_type_name = st.selectbox("Tipo/Campaña*", options=type_list, index=0, key=f"{form_key}_type")
                allowed_branches = st.multiselect("Sucursales Permitidas", options=branch_options, key=f"{form_key}_branches")
                selected_scope_names = st.multiselect("Validez Cupón", options=list(scope_options.keys()), key=f"{form_key}_scopes")
                selected_restriction_names = st.multiselect("Restricciones", options=list(restriction_options.keys()), key=f"{form_key}_restrictions")
                count = st.number_input("Cantidad*", min_value=1, max_value=1000, value=None, placeholder="1", key=f'{form_key}_count')

            submitted = st.form_submit_button("✔️ Generar Lote")

            if submitted:
                # Validation logic remains the same
                error = False
                if not input_asociado: st.error("❌ 'Asociado' es obligatorio."); error = True
                if selected_promo_name == "-- Seleccione Promoción --": st.error("❌ Seleccione Promoción."); error = True
                # Check for None explicitly because 0 is a valid value
                if value_crc is None or value_crc < 0: st.error("❌ Ingrese Valor Base CRC válido."); error = True
                if value_usd is None or value_usd < 0: st.error("❌ Ingrese Valor Base USD válido."); error = True
                if selected_type_name == "-- Seleccione Tipo --": st.error("❌ Seleccione Tipo/Campaña."); error = True
                if count is None or count <= 0: st.error("❌ Ingrese Cantidad > 0."); error = True

                if not error:
                    # Proceed with generation
                    type_id = type_options.get(selected_type_name)
                    user_id = st.session_state.get('user_id')
                    scope_ids = [scope_options[n] for n in selected_scope_names]
                    restriction_ids = [restriction_options[n] for n in selected_restriction_names]
                    st.info(f"⚙️ Generando {count} tarjeta(s)... Por favor espere.")

                    result = db_service.create_coupon_batch(
                        count=count, asociado_comprador=input_asociado, batch_name=input_batch_name,
                        promo_data=selected_promo, value_crc=value_crc, value_usd=value_usd,
                        type_id=type_id, months_valid=valid_months, branch_names=allowed_branches,
                        scope_ids=scope_ids, restriction_ids=restriction_ids, user_id=user_id
                    )

                    if result and result.get('coupon_entries'):
                        st.success("✅ ¡Lote y recibo generados!")
                        st.balloons()
                        generated_paths = []
                        coupons = result['coupon_entries']
                        # Generate JPGs
                        for entry in coupons:
                            path = os.path.join(GENERATED_QRS_DIR, f"{entry['consecutive']:04d}.jpg")
                            create_qr_card(entry['id'], path, selected_promo.get('description','N/A'), entry['expiration_date'], f"{entry['consecutive']:04d}")
                            generated_paths.append(path)
                        # Create ZIP
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
                        # Increment counter to force form reset on next interaction
                        st.session_state['form_key_counter'] += 1
                        st.rerun() # Rerun to display receipt and clear form visually
                    else:
                        st.error("🚨 Error al generar el lote. Revise los mensajes.")
                        st.session_state['show_receipt'] = False # Ensure old receipt isn't shown

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
            # Button to clear state and effectively start over
            if st.button("✨ Listo (Ocultar Recibo)"):
                st.session_state['show_receipt'] = False
                st.session_state['last_receipt_data'] = None
                st.session_state['last_zip_buffer'] = None
                st.session_state['last_zip_filename'] = None
                # Incrementing counter helps ensure form truly resets if rerun isn't enough
                st.session_state['form_key_counter'] += 1
                st.rerun()

    # --- Gestión de Plantilla ---
    with tab_template:
        st.header("Gestión de Plantilla"); st.subheader("1. Guía (JPG)"); st.markdown("Guía horizontal (9x5 cm).")
        BLANK_JPG = os.path.join(TEMPLATE_DIR, "plantilla_guia.jpg")
        # Generate guide on demand before download
        if st.button("Generar/Descargar Guía JPG", key="dl_guide"):
            generate_design_template(BLANK_JPG);
            with open(BLANK_JPG, "rb") as f:
                st.download_button("Descargar Guía (JPG)", f, os.path.basename(BLANK_JPG), "image/jpeg", key="dl_guide_btn")
        st.markdown("---"); st.subheader("2. Subir Plantilla (PNG)")
        up_file = st.file_uploader("Suba PNG (1063x591px, Horizontal)", type="png", key="up_tmpl")
        if up_file:
            save_path = os.path.join(TEMPLATE_DIR, "plantilla_arte_activa.png")
            try:
                with open(save_path, "wb") as f: f.write(up_file.getbuffer())
                st.session_state[TEMPLATE_PATH_KEY] = save_path; st.success(f"Plantilla cargada: {up_file.name}")
            except Exception as e:
                st.error(f"Error al guardar plantilla: {e}")
        # Display current template info
        current_template = st.session_state.get(TEMPLATE_PATH_KEY)
        if current_template and os.path.exists(current_template): st.info(f"🎨 Plantilla Actual: {os.path.basename(current_template)}")
        else: st.warning("No hay plantilla cargada. Se usará fondo blanco.")


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
        df_batches = db_service.get_batch_report() # Includes 'ID Lote' now
        if not df_batches.empty:
            # Display simple dataframe for now, reimprimir can be added based on this
            st.dataframe(df_batches.drop(columns=['ID Lote'], errors='ignore'), use_container_width=True, hide_index=True) # Hide internal ID
            total_lotes = len(df_batches); total_creados = df_batches['Creados'].sum(); total_canjeados = df_batches['Canjeados'].sum()
            c1,c2,c3 = st.columns(3); c1.metric("Lotes", f"{total_lotes}"); c2.metric("Creados", f"{total_creados}"); c3.metric("Canjeados", f"{total_canjeados}")
        else: st.info("No hay lotes creados.")

    # --- Tab Recibos ---
    with tab_recibos:
        st.subheader("Visualizar / Reimprimir Recibos de Lote")
        df_receipts_list = db_service.get_all_receipts()

        if not df_receipts_list.empty:
            # Create display options: "ID - Nombre (Fecha)"
            receipt_options_dict = {
                f"{row['Recibo ID']} - {row['Nombre Lote']} ({row['Fecha Generado']})": row['Recibo ID']
                for _, row in df_receipts_list.iterrows()
            }
            receipt_display_list = ["-- Seleccione un Recibo --"] + list(receipt_options_dict.keys())

            selected_receipt_display = st.selectbox(
                "Seleccione el recibo:",
                options=receipt_display_list, index=0, key="receipt_selector"
            )

            if selected_receipt_display != "-- Seleccione un Recibo --":
                selected_receipt_id = receipt_options_dict[selected_receipt_display]
                # Store selected ID in session state to persist selection
                st.session_state['selected_receipt_id'] = selected_receipt_id

                # Fetch and display the selected receipt data using the ID from state
                if st.session_state['selected_receipt_id']:
                    receipt_data = db_service.get_receipt_data(st.session_state['selected_receipt_id'])
                    if receipt_data:
                        st.divider()
                        st.subheader(f"Detalles del Recibo #{st.session_state['selected_receipt_id']}")
                        receipt_text = format_receipt(receipt_data)
                        st.code(receipt_text, language=None)
                        st.caption("Puede copiar este texto o usar Ctrl+P / Cmd+P para imprimir.")
                    else:
                        st.error(f"No se pudieron cargar detalles del recibo ID: {st.session_state['selected_receipt_id']}")
            else:
                 # Clear selection if default is chosen
                 st.session_state['selected_receipt_id'] = None
                 st.info("Seleccione un recibo de la lista para ver sus detalles.")
        else:
            st.warning("No se han encontrado recibos guardados.")
