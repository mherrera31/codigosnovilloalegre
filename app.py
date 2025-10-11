# app.py
import streamlit as st
import auth 
import db_service
import user_service
# Importa tus utilidades de QR/PDF aquí si es necesario
# import qr_utils 

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Sistema de QR Novillo Alegre", layout="wide")

# Inicializa el estado de la sesión si no existe
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'user_role' not in st.session_state:
    st.session_state['user_role'] = None
if 'branch_id' not in st.session_state:
    st.session_state['branch_id'] = None

# ----------------------------------------
# LÓGICA DE CONTROL DE ACCESO (LOGIN GATE)
# ----------------------------------------

if not auth.is_authenticated():
    # PÁGINA DE LOGIN
    st.image("https://novilloalegre.com.pa/wp-content/uploads/2020/07/logo-novillo-alegre-panama-restaurante-parrillada-argentina.png", width=300)
    st.title("Sistema de QRs de Regalo - Acceso Restringido")
    auth.login_ui()
    st.stop() # Detener el resto de la ejecución
    
# ----------------------------------------
# BARRA LATERAL (SIDEBAR) Y NAVEGACIÓN
# ----------------------------------------

# Mostrar Logo en la página principal y título
st.image("https://novilloalegre.com.pa/wp-content/uploads/2020/07/logo-novillo-alegre-panama-restaurante-parrillada-argentina.png", width=300)
st.title("Sistema de QRs de Regalo")

# Información del usuario en la barra lateral
user = auth.get_current_user()
user_role = st.session_state.get('user_role')

with st.sidebar:
    st.sidebar.header("Menú de Navegación")
    
    if user_role:
        st.success(f"**Usuario:** {user.email}")
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
        # Esto no debería pasar si el login fue exitoso, pero es un fallback
        st.error("Error: Rol de usuario no definido. Cerrando sesión.")
        auth.sign_out()
        st.stop()
        

# ----------------------------------------
# RENDERIZACIÓN DE MÓDULOS
# ----------------------------------------

if app_mode == "🏠 Dashboard":
    st.header("Bienvenido al Sistema Novillo Alegre")
    st.info(f"Su rol actual ({user_role}) le da acceso a las siguientes secciones.")

# Lógica para los módulos de contenido (PENDIENTES DE CREAR EN ARCHIVOS SEPARADOS)
# Por ahora, mantendremos la estructura if/elif para el código existente en app.py,
# pero en una estructura final, cada uno de estos bloques llamaría a una función
# como 'creator_module.render()'

elif app_mode == "🔑 Gestión de Usuarios (Admin)":
    # Aquí iría el código del módulo de gestión de usuarios (o la llamada a una función/archivo)
    user_service.render_user_management() # Función a crear
    # st.header("Módulo de Gestión de Usuarios") 

elif app_mode == "⚙️ Configuración (Admin)":
    # Aquí iría el código del módulo de configuración (o la llamada a una función/archivo)
    db_service.render_config_management() # Función a crear
    # st.header("Módulo de Configuración")
    
elif app_mode == "🛠️ Creador de QRs":
    st.header("Módulo de Creación de Tarjetas QR")
    # ... (código existente del Creador de QRs de app.py)

elif app_mode == "📲 Escáner (Cajero)":
    st.header("Módulo de Cajero: Escanear QR")
    # ... (código existente del Escáner de app.py)

elif app_mode == "📊 Reportes (Admin)":
    st.header("Módulo de Reportes de Actividad")
    # ... (código existente de Reportes de app.py)
