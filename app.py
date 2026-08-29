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

# Función de evaluación del Semáforo según las reglas
def evaluar_fecha(fecha_str):
    if not fecha_str or pd.isna(fecha_str) or str(fecha_str).strip() == "":
        return "⚪ Sin fecha", "GRIS", None
    try:
        fecha_venc = datetime.strptime(str(fecha_str)[:10], "%Y-%m-%d").date()
        hoy = datetime.now().date()
        dias = (fecha_venc - hoy).days
        
        if dias <= 15:
            if dias <= 0:
                return f"🔴 Vencido ({abs(dias)}d)", "ROJO", dias
            else:
                return f"🔴 Crítico ({dias}d)", "ROJO", dias
        elif 16 <= dias <= 31:
            return f"🟡 Alerta ({dias}d)", "AMARILLO", dias
        else:
            return f"🟢 Vigente ({dias}d)", "VERDE", dias
    except Exception:
        return "⚪ Formato inválido", "GRIS", None

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

# Módulo 1: Lista Maestra & Dashboard de Alertas
if modulo == "1. Lista Maestra & Acreditación":
    st.header("📋 Dashboard de Control y Acreditaciones Mineras")
    
    equipos = consultar_tabla("equipos")
    
    if equipos:
        df = pd.DataFrame(equipos)
        
        # Lista exacta de columnas a monitorear
        cols_monitoreadas = [
            "fecha_venc_soat",
            "fecha_venc_poliza",
            "fecha_retorqueo_ruedas",
            "fecha_venc_citv",
            "fecha_venc_gps",
            "fecha_venc_tarjeta_mercancias",
            "fecha_venc_cert_operatividad",
            "fecha_venc_cert_inspección"
        ]
        
        # Mapeo para nombres más limpios en la interfaz
        nombres_amigables = {
            "fecha_venc_soat": "SOAT",
            "fecha_venc_poliza": "Póliza",
            "fecha_retorqueo_ruedas": "Retorqueo Ruedas",
            "fecha_venc_citv": "CITV",
            "fecha_venc_gps": "GPS",
            "fecha_venc_tarjeta_mercancias": "Tarjeta Mercancías",
            "fecha_venc_cert_operatividad": "Certif. Operatividad",
            "fecha_venc_cert_inspección": "Certif. Inspección"
        }

        # Procesar datos de semáforo
        resumen_alertas = []
        for col in cols_monitoreadas:
            if col in df.columns:
                resultados = df[col].apply(evaluar_fecha)
                df[f"estado_{col}"] = [r[0] for r in resultados]
                colores = [r[1] for r in resultados]
                
                rojos = colores.count("ROJO")
                amarillos = colores.count("AMARILLO")
                verdes = colores.count("VERDE")
                
                resumen_alertas.append({
                    "Clave": col,
                    "Documento / Permiso": nombres_amigables.get(col, col),
                    "🔴 Crítico (≤15d)": rojos,
                    "🟡 Alerta (16-31d)": amarillos,
                    "🟢 Vigente (≥32d)": verdes
                })

        df_resumen = pd.DataFrame(resumen_alertas)

        # --- SECCIÓN 1: DASHBOARD RESUMEN DE ALERTAS ---
        st.subheader("🚨 Resumen Rápido de Estado por Documento / Permiso")
        
        # Mostrar métricas en formato de tarjetas compactas
        cols_grid = st.columns(4)
        for idx, row in df_resumen.iterrows():
            col_target = cols_grid[idx % 4]
            with col_target:
                alerta_texto = ""
                if row["🔴 Crítico (≤15d)"] > 0:
                    alerta_texto += f"🔴 {row['🔴 Crítico (≤15d)']} "
                if row["🟡 Alerta (16-31d)"] > 0:
                    alerta_texto += f"🟡 {row['🟡 Alerta (16-31d)']}"
                if not alerta_texto:
                    alerta_texto = "🟢 0 Alertas"
                    
                st.metric(
                    label=f"📌 {row['Documento / Permiso']}",
                    value=alerta_texto,
                    delta=f"Total Evaluados: {len(df)}",
                    delta_color="off"
                )

        st.divider()

        # --- SECCIÓN 2: VISTA DETALLADA Y FILTROS ---
        st.subheader("🔍 Filtro de Flota por Permiso")
        
        doc_seleccionado = st.selectbox(
            "Selecciona un Permiso para inspeccionar el semáforo detallado de la flota:",
            options=["TODOS"] + [nombres_amigables.get(c, c) for c in cols_monitoreadas if c in df.columns]
        )

        # Formatear la vista final de la tabla
        columnas_base = [col for col in ["placa", "codigo", "marca", "modelo", "comentario", "fotocheck"] if col in df.columns]
        
        if doc_seleccionado == "TODOS":
            cols_mostrar = columnas_base + [f"estado_{c}" for c in cols_monitoreadas if f"estado_{c}" in df.columns]
        else:
            # Obtener nombre original de columna
            clave_col = [k for k, v in nombres_amigables.items() if v == doc_seleccionado][0]
            cols_mostrar = columnas_base + [clave_col, f"estado_{clave_col}"]

        st.dataframe(df[cols_mostrar], use_container_width=True)

    else:
        st.info("No hay datos registrados aún. Importa tu flota en Supabase para visualizar el dashboard.")
