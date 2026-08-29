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

# Función para evaluar el estado del documento (Semáforo)
def calcular_estado_semaforo(fecha_str):
    if not fecha_str or pd.isna(fecha_str):
        return "⚪ Sin fecha"
    try:
        fecha_venc = datetime.strptime(str(fecha_str), "%Y-%m-%d").date()
        hoy = datetime.now().date()
        dias = (fecha_venc - hoy).days
        
        if dias <= 0:
            return f"🔴 Vencido ({abs(dias)}d)"
        elif dias <= 15:
            return f"🟡 Por vencer ({dias}d)"
        else:
            return f"🟢 Vigente ({dias}d)"
    except Exception:
        return "⚪ Formato inválido"

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
        
        # Columnas de fechas de acreditación a evaluar
        columnas_fechas = [col for col in df.columns if col.startswith("fecha_venc_")]
        
        # Generar columnas de semáforo dinámicas
        for col in columnas_fechas:
            nombre_semaforo = col.replace("fecha_venc_", "estado_")
            df[nombre_semaforo] = df[col].apply(calcular_estado_semaforo)
            
        # Conteo de alertas globales
        todos_estados = df[[c for c in df.columns if c.startswith("estado_")]].values.flatten()
        vencidos = sum(1 for e in todos_estados if "🔴" in str(e))
        por_vencer = sum(1 for e in todos_estados if "🟡" in str(e))
        vigentes = sum(1 for e in todos_estados if "🟢" in str(e))
        
        # Métricas KPI
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        kpi1.metric("Total Flota", len(df))
        kpi2.metric("Documentos Vigentes", vigentes)
        kpi3.metric("Por Vencer (≤15 días)", por_vencer)
        kpi4.metric("Documentos Vencidos", vencidos)
        
        st.divider()
        st.subheader("📌 Monitoreo de Acreditaciones Mineras")
        
        # Mostrar tabla organizada
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No hay datos registrados aún. Asegúrate de importar tu CSV en Supabase.")
