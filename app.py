import streamlit as st
import requests
import pandas as pd
from datetime import datetime

# Configuración de la página
st.set_page_config(
    page_title="Qorilazo - Gestión de Mantenimiento",
    page_icon="🚜",
    layout="wide"
)

st.title("🚜 QORILAZO - Control y Predicción de Mantenimiento")
st.caption("Corredor Minero Apurímac - Cusco")

# Lectura segura de Secrets
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"].strip().rstrip('/')
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"].strip()
except Exception:
    st.error("⚠️ Faltan los Secrets de Supabase en Streamlit Cloud.")
    st.stop()

# Función para consultar datos
def consultar_tabla(nombre_tabla):
    url_endpoint = f"{SUPABASE_URL}/rest/v1/{nombre_tabla}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    params = {"select": "*"}
    try:
        response = requests.get(url_endpoint, headers=headers, params=params, timeout=10)
        return response.json() if response.status_code == 200 else []
    except Exception:
        return []

# Menú Lateral
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

# Módulo 1: Lista Maestra & Semáforo
if modulo == "1. Lista Maestra & Acreditación":
    st.header("📋 Lista Maestra de Equipos y Semáforo de Acreditaciones")
    
    equipos = consultar_tabla("equipos")
    
    if equipos:
        df = pd.DataFrame(equipos)
        
        # Métrica / KPIs Rápidos
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Flota Registrada", len(df))
        col2.metric("Equipos Operativos", len(df[df['estado'] == 'OPERATIVO']) if 'estado' in df.columns else len(df))
        col3.metric("Ubicación Principal", "Corredor Minero")
        
        st.divider()
        st.subheader("📌 Estado de la Flota")
        
        # Mostrar tabla interactiva
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No hay datos registrados aún. Asegúrate de importar tu CSV en Supabase.")
