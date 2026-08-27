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

# Obtener credenciales desde los Secrets
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
except Exception:
    st.error("⚠️ Faltan los Secrets (SUPABASE_URL o SUPABASE_KEY) en Streamlit Cloud.")
    st.stop()

# Función para consultar datos vía API REST directa
def consultar_tabla(nombre_tabla):
    endpoint = f"{SUPABASE_URL}/rest/v1/{nombre_tabla}?select=*"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    response = requests.get(endpoint, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        st.error(f"Error {response.status_code}: {response.text}")
        return []

# Menú Navegación
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
        st.success(f"✅ Se cargaron {len(df_equipos)} equipos en la base de datos.")
        st.dataframe(df_equipos, use_container_width=True)
    else:
        st.info("No hay equipos registrados o la tabla está vacía en Supabase.")
