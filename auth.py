# auth.py
from db_config import get_supabase_client
import streamlit as st

supabase = get_supabase_client()

def sign_in(email, password):
    """
    Intenta iniciar sesión y, si es exitoso, obtiene el perfil (rol y sucursal) del usuario.
    """
    try:
        # 1. Autenticación con Supabase Auth
        response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password,
        })
        
        if response.user and response.session:
            user_id = response.user.id
            
            # 2. Consultar el perfil del usuario (rol y sucursal)
            # Hacemos un JOIN implícito para obtener el role_name
            profile_response = supabase.from_('profiles').select('*, roles(role_name)').eq('id', user_id).execute()
            
            if profile_response.data and profile_response.data[0]:
                profile = profile_response.data[0]
                
                # 3. Guardar el estado completo en la sesión de Streamlit
                st.session_state['logged_in'] = True
                st.session_state['user'] = response.user
                st.session_state['user_id'] = user_id
                st.session_state['user_role'] = profile['roles']['role_name']
                st.session_state['branch_id'] = profile['branch_id']
                st.session_state['username'] = profile['username']
                
                st.success(f"Bienvenido, {profile['username']} ({profile['roles']['role_name']}).")
                st.rerun() 
            else:
                st.error("Su cuenta no tiene un perfil asignado. Contacte al administrador.")
                supabase.auth.sign_out() # Forzar logout si existe en Auth pero no en profiles
        else:
            st.error("Credenciales inválidas.")
            
    except Exception as e:
        # Los errores de Supabase suelen ser descriptivos
        st.error("Credenciales inválidas o error de conexión.")
        print(f"Error de Supabase: {e}")

def sign_out():
    """Cierra la sesión y limpia el estado de Streamlit."""
    try:
        supabase.auth.sign_out()
        st.session_state.clear()
        st.session_state['logged_in'] = False # Asegurar que el flag de sesión quede en False
        st.rerun()
    except Exception as e:
        st.error("Error al cerrar sesión.")
        print(f"Error de Supabase: {e}")

def get_current_user():
    """Retorna el objeto de usuario de la sesión."""
    return st.session_state.get('user', None)

def is_authenticated():
    """Verifica si hay un usuario autenticado."""
    return st.session_state.get('logged_in', False)

def get_user_role():
    """Retorna el rol del usuario actual."""
    return st.session_state.get('user_role', None)

def login_ui():
    """Muestra el formulario de login en la barra lateral de Streamlit."""
    with st.sidebar:
        st.subheader("Acceso al Sistema")
        email = st.text_input("Correo Electrónico")
        password = st.text_input("Contraseña", type="password")
        
        if st.button("Iniciar Sesión", type="primary"):
            if email and password:
                sign_in(email, password)
            else:
                st.warning("Ingrese correo y contraseña.")
