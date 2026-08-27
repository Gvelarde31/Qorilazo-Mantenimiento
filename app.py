import streamlit as st
import requests
import pandas as pd

# Configuración de la página
st.set_page_config(
    page_title="Qorilazo - Gestión de Mantenimiento",
    page_icon="🚜",
    layout="wide"
)

st.title("🚜 QORILAZO - Control y Predicción de Mantenimiento")
st.caption("Corredor Minero Apurímac - Cusco")

# Lectura y sanitización estricta de Secrets
try:
    # .strip() quita espacios e invisibles; .rstrip('/') quita barras finales duplicadas
    SUPABASE_URL = st.secrets["SUPABASE_URL"].strip().rstrip('/')
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"].strip()
except Exception:
    st.error("⚠️ Faltan los Secrets (SUPABASE_URL o SUPABASE_KEY) en Streamlit Cloud.")
    st.stop()

# Función con manejo de errores y rutas garantizadas
def consultar_tabla(nombre_tabla):
    # Construcción limpia de la URL de Supabase PostgREST
    url_endpoint = f"{SUPABASE_URL}/rest/v1/{nombre_tabla}"
    
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    params = {
        "select": "*"
    }
    
    try:
        response = requests.get(url_endpoint, headers=headers, params=params, timeout=10)
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            st.error(f"❌ Error 404: La tabla '{nombre_tabla}' no fue encontrada o la URL es incorrecta.")
            st.info(f"📍 Ruta intentada: `{url_endpoint}`")
            return []
        else:
            st.error(f"❌ Error HTTP {response.status_code}: {response.text}")
            return []
            
    except Exception as e:
        st.error(f"⚠️ Error al conectar con el servidor: {e}")
        return []

# Menú de Navegación Lateral
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

# Módulo 1: Lista Maestra
if modulo == "1. Lista Maestra & Acreditación":
    st.header("📋 Lista Maestra de Equipos y Acreditación Minera")
    
    equipos = consultar_tabla("equipos")
    
    if equipos:
        df_equipos = pd.DataFrame(equipos)
        st.success(f"✅ Conexión exitosa. Se cargaron {len(df_equipos)} registros de la flota.")
        st.dataframe(df_equipos, use_container_width=True)
    else:
        st.info("No hay equipos registrados o la tabla está vacía.")
