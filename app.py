import streamlit as st
from supabase import create_client

# Configuración de la página
st.set_page_config(
    page_title="Qorilazo - Gestión de Mantenimiento",
    page_icon="🚜",
    layout="wide"
)

# Título Principal
st.title("🚜 QORILAZO - Control y Predicción de Mantenimiento")
st.caption("Corredor Minero Apurímac - Cusco")

# Conexión a Supabase mediante Secrets
@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

try:
    supabase = init_connection()
    st.sidebar.success("✅ Conectado a Supabase")
except Exception as e:
    st.sidebar.error("⚠️ Error de conexión a la Base de Datos")

# Menú Navegación Lateral
modulo = st.sidebar.radio(
    "Navegación / Módulos:",
    [
        "1. Lista Maestra & Acreditación",
        "2. Registro Diario de Partes y Tareo",
        "3. Programación Semanal PM",
        "4. Historial de Mantenimientos",
        "5. Catálogo de Repuestos"
    ]
)

# Módulo 1: Lista Maestra de Equipos
if modulo == "1. Lista Maestra & Acreditación":
    st.header("📋 Lista Maestra de Equipos y Acreditación Minera")
    
    # Obtener datos de la tabla equipos
    res = supabase.table("equipos").select("*").execute()
    equipos = res.data
    
    if equipos:
        st.dataframe(equipos, use_container_width=True)
    else:
        st.info("No hay equipos registrados aún en la base de datos.")
