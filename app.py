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

# Funciones de interacción con la API REST de Supabase
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

def insertar_registro(nombre_tabla, datos):
    url_endpoint = f"{SUPABASE_URL}/rest/v1/{nombre_tabla}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }
    try:
        response = requests.post(url_endpoint, headers=headers, json=datos, timeout=10)
        if response.status_code in [200, 201]:
            return True, "OK"
        else:
            return False, response.text
    except Exception as e:
        return False, str(e)

# Evaluación de Semáforo para Módulo 1
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

# Menú Lateral de Navegación
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

# ==========================================
# MÓDULO 1: LISTA MAESTRA & SEMÁFORO
# ==========================================
if modulo == "1. Lista Maestra & Acreditación":
    st.header("📋 Dashboard de Control y Acreditaciones Mineras")
    
    equipos = consultar_tabla("equipos")
    
    if equipos:
        df = pd.DataFrame(equipos)
        
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
        
        nombres_amigables = {
            "fecha_venc_soat": "SOAT",
            "fecha_venc_poliza": "Póliza",
            "fecha_retorqueo_ruedas": "Retorqueo Ruedas",
            "fecha_venc_citv": "Revisión Técnica (CITV)",
            "fecha_venc_gps": "GPS",
            "fecha_venc_tarjeta_mercancias": "Tarjeta Mercancías",
            "fecha_venc_cert_operatividad": "Certif. Operatividad",
            "fecha_venc_cert_inspección": "Certif. Inspección"
        }

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

        st.subheader("🚨 Resumen Rápido de Estado por Documento / Permiso")
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
        st.subheader("🔍 Filtro de Flota por Permiso")
        
        doc_seleccionado = st.selectbox(
            "Selecciona un Permiso para inspeccionar el semáforo detallado de la flota:",
            options=["TODOS"] + [nombres_amigables.get(c, c) for c in cols_monitoreadas if c in df.columns]
        )

        columnas_base = [col for col in ["placa", "codigo", "marca", "modelo", "comentario", "fotocheck"] if col in df.columns]
        
        if doc_seleccionado == "TODOS":
            cols_mostrar = columnas_base + [f"estado_{c}" for c in cols_monitoreadas if f"estado_{c}" in df.columns]
        else:
            clave_col = [k for k, v in nombres_amigables.items() if v == doc_seleccionado][0]
            cols_mostrar = columnas_base + [clave_col, f"estado_{clave_col}"]

        st.dataframe(df[cols_mostrar], use_container_width=True)

    else:
        st.info("No hay datos registrados en la flota aún.")

# ==========================================
# MÓDULO 2: REGISTRO DIARIO DE PARTES Y TAREO
# ==========================================
elif modulo == "2. Registro Diario de Partes y Tareo":
    st.header("📝 Registro Diario de Partes de Trabajo y Tareo")
    
    equipos = consultar_tabla("equipos")
    
    if not equipos:
        st.warning("⚠️ No se encontraron equipos registrados en la tabla 'equipos'. Debe registrar primero la flota.")
    else:
        df_equipos = pd.DataFrame(equipos)
        
        # Determinar la columna de código en la tabla equipos
        col_codigo = "codigo" if "codigo" in df_equipos.columns else ("codigo_equipo" if "codigo_equipo" in df_equipos.columns else "placa")
        
        # Extraer lista limpia y única de códigos de equipos válidos
        lista_codigos = sorted(list(set(df_equipos[col_codigo].dropna().astype(str))))
        
        st.subheader("📋 Formulario de Ingreso de Parte Diario")
        
        with st.form("form_parte_diario", clear_on_submit=True):
            st.markdown("##### 📍 Identificación del Equipo y Datos Operativos")
            col_1, col_2, col_3 = st.columns(3)
            
            with col_1:
                codigo_sel = st.selectbox("Código del Equipo (Único en Flota) *", lista_codigos)
                fecha_parte = st.date_input("Fecha del Parte *", datetime.now().date())
            with col_2:
                turno = st.selectbox("Turno *", ["Día", "Noche"])
                frente_asignado = st.text_input("Frente Asignado")
            with col_3:
                actividad = st.text_input("Actividad Realizada")
                combustible = st.number_input("Combustible Abastecido (Galones)", min_value=0.0, step=0.5)

            st.divider()
            
            st.markdown("##### ⏱️ Lectura de Horómetros y Kilometraje")
            col_h1, col_h2 = st.columns(2)
            
            with col_h1:
                st.caption(" Horómetro (Horas)")
                horo_init = st.number_input("Horómetro Inicial", min_value=0.0, step=0.1)
                horo_fin = st.number_input("Horómetro Final", min_value=0.0, step=0.1)
                horas_trab = max(0.0, horo_fin - horo_init)
                st.info(f"**Horas Trabajadas:** `{horas_trab:.1f} hrs`")

            with col_h2:
                st.caption(" 🛣️ Odómetro (Kilómetros)")
                km_init = st.number_input("Kilómetro Inicial", min_value=0.0, step=1.0)
                km_fin = st.number_input("Kilómetro Final", min_value=0.0, step=1.0)
                km_rec = max(0.0, km_fin - km_init)
                st.info(f"**Kilómetros Recorridos:** `{km_rec:.1f} km`")

            st.divider()
            observaciones = st.text_area("Observaciones / Novedades del Turno")
            
            guardar = st.form_submit_button("💾 Guardar Parte Diario", use_container_width=True)
            
            if guardar:
                if horo_fin < horo_init:
                    st.error("❌ El Horómetro Final no puede ser menor al Horómetro Inicial.")
                elif km_fin < km_init:
                    st.error("❌ El Kilómetro Final no puede ser menor al Kilómetro Inicial.")
                else:
                    nuevo_parte = {
                        "fecha": str(fecha_parte),
                        "codigo_equipo": codigo_sel,
                        "turno": turno,
                        "horometro_inicial": horo_init,
                        "horometro_final": horo_fin,
                        "horas_trabajadas": horas_trab,
                        "kilometro_inicial": km_init,
                        "kilometro_final": km_fin,
                        "kilometros_recorridos": km_rec,
                        "frente_asignado": frente_asignado,
                        "actividad": actividad,
                        "combustible_galones": combustible,
                        "observaciones": observaciones
                    }
                    
                    exito, msg = insertar_registro("partes_diarios", nuevo_parte)
                    if exito:
                        st.success(f"✅ Parte diario registrado con éxito para el equipo `{codigo_sel}`.")
                    else:
                        st.error(f"❌ Error al guardar en Supabase: {msg}")

        st.divider()
        st.subheader("📊 Historial de Partes Diarios Registrados")
        partes_registrados = consultar_tabla("partes_diarios")
        if partes_registrados:
            st.dataframe(pd.DataFrame(partes_registrados), use_container_width=True)
        else:
            st.info("Aún no se han registrado partes diarios en la base de datos.")
