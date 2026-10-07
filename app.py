import streamlit as st
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, time
import io
import unicodedata
import re

# Configuración de la página
st.set_page_config(
    page_title="Qorilazo - Sistema de Mantenimiento",
    page_icon="🚜",
    layout="wide"
)

st.title("🚜 QORILAZO - Control y Mantenimiento de Flota")
st.caption("Corredor Minero Apurímac - Cusco")

# Lectura segura de Secrets de Supabase
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"].strip().rstrip('/')
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"].strip()
except Exception:
    st.error("⚠️ Faltan los Secrets de Supabase en Streamlit Cloud.")
    st.stop()

# Funciones REST Supabase
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
        return response.json() if response.status_code in [200, 201] else []
    except Exception:
        return []

def insertar_o_actualizar(nombre_tabla, datos):
    url_endpoint = f"{SUPABASE_URL}/rest/v1/{nombre_tabla}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }
    try:
        response = requests.post(url_endpoint, headers=headers, json=datos, timeout=10)
        return response.status_code in [200, 201, 204], response.text
    except Exception as e:
        return False, str(e)

def insertar_registro(nombre_tabla, datos):
    url_endpoint = f"{SUPABASE_URL}/rest/v1/{nombre_tabla}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }
    try:
        response = requests.post(url_endpoint, headers=headers, json=datos, timeout=10)
        return response.status_code in [200, 201], response.json() if response.status_code in [200, 201] else response.text
    except Exception as e:
        return False, str(e)

def eliminar_registro(nombre_tabla, columna_id, valor_id):
    url_endpoint = f"{SUPABASE_URL}/rest/v1/{nombre_tabla}?{columna_id}=eq.{valor_id}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    try:
        response = requests.delete(url_endpoint, headers=headers, timeout=10)
        return response.status_code in [200, 204]
    except Exception:
        return False

def actualizar_estado_equipo(placa, nuevo_estado):
    url_endpoint = f"{SUPABASE_URL}/rest/v1/lista_maestra?placa=eq.{placa}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }
    datos = {"estado_operativo": nuevo_estado}
    try:
        response = requests.patch(url_endpoint, headers=headers, json=datos, timeout=10)
        return response.status_code in [200, 204]
    except Exception:
        return False

def generar_excel_bytes(dataframe, nombre_hoja="Datos"):
    buffer = io.BytesIO()
    try:
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            dataframe.to_excel(writer, sheet_name=nombre_hoja, index=False)
        return buffer.getvalue()
    except Exception:
        return dataframe.to_csv(index=False, sep=";").encode('utf-8-sig')

def normalizar_texto(texto):
    if not texto or pd.isna(texto):
        return ""
    texto_str = str(texto)
    return ''.join(
        c for c in unicodedata.normalize('NFD', texto_str)
        if unicodedata.category(c) != 'Mn'
    ).upper().strip()

def aplicar_busqueda_libre(df, columnas, query_texto):
    if not query_texto:
        return df
    q_norm = normalizar_texto(query_texto)
    if not q_norm:
        return df

    mask = pd.Series(False, index=df.index)
    es_palabra_corta = len(q_norm) <= 2
    pattern = r'\b' + re.escape(q_norm) + r'\b' if es_palabra_corta else q_norm

    for col in columnas:
        if col in df.columns:
            serie_norm = df[col].apply(normalizar_texto)
            if es_palabra_corta:
                mask |= serie_norm.str.contains(pattern, regex=True, na=False)
            else:
                mask |= serie_norm.str.contains(pattern, regex=False, na=False)
                
    return df[mask]

def calcular_dias_vencimiento(fecha_str):
    if not fecha_str or pd.isna(fecha_str) or str(fecha_str).strip() == "":
        return None, "SIN FECHA"
    try:
        fecha_venc = datetime.strptime(str(fecha_str)[:10], "%Y-%m-%d").date()
        hoy = datetime.now().date()
        dias = (fecha_venc - hoy).days
        
        if dias <= 15:
            estado = "CRÍTICO"
        elif 16 <= dias <= 31:
            estado = "ALERTA"
        else:
            estado = "VIGENTE"
            
        return dias, estado
    except Exception:
        return None, "FORMATO INVÁLIDO"

def parse_fecha(fecha_val):
    if not fecha_val or pd.isna(fecha_val) or str(fecha_val).strip() == "":
        return datetime.now().date()
    try:
        return datetime.strptime(str(fecha_val)[:10], "%Y-%m-%d").date()
    except Exception:
        return datetime.now().date()

def parse_hora(hora_str, default_time):
    if not hora_str or pd.isna(hora_str) or str(hora_str).strip() == "":
        return default_time
    try:
        if "T" in str(hora_str):
            t_part = str(hora_str).split("T")[1][:8]
            return datetime.strptime(t_part, "%H:%M:%S").time()
        else:
            return datetime.strptime(str(hora_str)[:8], "%H:%M:%S").time()
    except Exception:
        return default_time

def obtener_rango_sabado_viernes(fecha_ref):
    dias_desde_sabado = (fecha_ref.weekday() - 5) % 7
    sabado = fecha_ref - timedelta(days=dias_desde_sabado)
    viernes = sabado + timedelta(days=6)
    return sabado, viernes

def obtener_valor_umbral(tipo_flota):
    tf_norm = normalizar_texto(tipo_flota)
    if "CAMIONETA" in tf_norm:
        return 1500.0
    elif any(k in tf_norm for k in ["CISTERNA DE COMBUSTIBLE", "VAN", "COASTER"]):
        return 1000.0
    elif any(k in tf_norm for k in ["CISTERNA", "AGUA", "GRUA", "MINICARGADOR", "VOLQUETE", "RETROEXCAVADORA", "RODILLO", "MOTONIVELADORA"]):
        return 65.0
    else:
        return 250.0

# Menú Lateral
modulo = st.sidebar.radio(
    "Navegación / Módulos:",
    [
        "1. Lista Maestra (Alta y Baja)",
        "2. Estatus Equipo (Acreditaciones)",
        "3. Reporte Diario (Hoja RD)",
        "4. Programa Mantenimiento (Control Semanal)",
        "5. Vale de Combustible & Z-Score",
        "6. Registro Cisterna (En desarrollo)",
        "7. Valorización & Catálogo de Insumos"
    ]
)

# ==========================================
# MÓDULO 1: LISTA MAESTRA DE FLOTA
# ==========================================
if modulo == "1. Lista Maestra (Alta y Baja)":
    st.header("📋 Lista Maestra de Flota (`lista_maestra`)")
    st.caption("Administración de datos maestros, altas, retiros y filtros universales por cualquier columna.")

    equipos = consultar_tabla("lista_maestra")
    df_equipos = pd.DataFrame(equipos) if equipos else pd.DataFrame()

    tab_activos, tab_agregar, tab_retirar, tab_inactivos = st.tabs([
        "📋 Flota Activa & Filtros Universales", 
        "➕ Agregar Equipo", 
        "❌ Quitar Equipo",
        "📁 Equipos Retirados"
    ])

    with tab_activos:
        if not df_equipos.empty and "estado_operativo" in df_equipos.columns:
            df_activos = df_equipos[df_equipos["estado_operativo"] == "OPERATIVO"].copy()
            
            cols_deseadas = [
                "codigo_interno", "placa", "tipo_flota", "frecuencia_mantenimiento", "anio",
                "marca", "modelo", "capacidad", "razon_social", "ruc", "contacto",
                "propietario", "comunidad", "potencia_kw", "potencia_hp", "potencia_cv",
                "fecha_ingreso_proyecto", "frente_asignado"
            ]
            cols_disponibles = [c for c in cols_deseadas if c in df_activos.columns]
            
            st.subheader("🔍 Panel de Filtros Multivariable y Búsqueda Libre")
            
            f_col1, f_col2, f_col3 = st.columns([1.5, 1.5, 2])
            
            with f_col1:
                columna_filtro = st.selectbox(
                    "1. Seleccione Columna para Filtrar:",
                    options=["NINGUNO"] + cols_disponibles
                )
                
            with f_col2:
                if columna_filtro != "NINGUNO":
                    opciones_valores = ["TODOS"] + sorted(list(df_activos[columna_filtro].dropna().astype(str).unique()))
                    valor_filtro = st.selectbox(f"2. Filtrar por {columna_filtro}:", opciones_valores)
                else:
                    valor_filtro = "TODOS"
                    st.selectbox("2. Valor de Filtro:", ["TODOS"], disabled=True)
                    
            with f_col3:
                busqueda_texto = st.text_input("🔎 3. Búsqueda Libre (Placa, Código, Marca, Modelo, etc.):").strip()

            df_filtrado = df_activos.copy()
            
            if columna_filtro != "NINGUNO" and valor_filtro != "TODOS":
                df_filtrado = df_filtrado[df_filtrado[columna_filtro].astype(str) == valor_filtro]
                
            if busqueda_texto:
                df_filtrado = aplicar_busqueda_libre(df_filtrado, cols_disponibles, busqueda_texto)

            st.divider()
            
            m1, m2 = st.columns([1, 3])
            with m1:
                st.metric("Equipos Encontrados", f"{len(df_filtrado)} de {len(df_activos)}")
            
            st.dataframe(df_filtrado[cols_disponibles], use_container_width=True)
            
            st.download_button(
                label="📥 Descargar Resultado Filtrado en Excel (.xlsx)",
                data=generar_excel_bytes(df_filtrado[cols_disponibles], "Flota_Filtrada"),
                file_name=f"Lista_Maestra_Filtrada_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        else:
            st.info("No hay equipos activos registrados en la base de datos.")

    with tab_agregar:
        st.subheader("➕ Agregar Nuevo Equipo a la Lista Maestra")
        with st.form("form_alta_equipo", clear_on_submit=True):
            st.markdown("##### 📍 Datos de Identificación y Operación")
            c1, c2, c3 = st.columns(3)
            with c1:
                placa = st.text_input("Placa del Vehículo / Serie *").upper().strip()
                codigo_interno = st.text_input("Código Interno *").upper().strip()
                tipo_flota = st.selectbox("Tipo de Flota / Categoría *", [
                    "Camioneta", "Volquete", "Cisterna de Agua", "Cisterna de Combustible",
                    "Motoniveladora", "Rodillo Compactador", "Retroexcavadora", 
                    "Excavadora", "Cargador Frontal", "Tractor de Oruga", "Coaster", "Van", "Otro"
                ])
            with c2:
                frecuencia_pm = st.number_input("Frecuencia PM (Horas / KM) *", min_value=100, step=50, value=250)
                frente_asignado = st.text_input("Frente Asignado *", value="Frente Principal")
                fecha_ingreso = st.date_input("Fecha de Ingreso al Proyecto *", datetime.now().date())
            with c3:
                marca = st.text_input("Marca")
                modelo = st.text_input("Modelo")
                anio = st.number_input("Año de Fabricación", min_value=1990, max_value=2030, value=2024, step=1)

            st.divider()
            st.markdown("##### ⚙️ Capacidades y Potencia")
            c4, c5, c6 = st.columns(3)
            with c4:
                capacidad = st.text_input("Capacidad (ej. 15 m3 / 5000 gln)")
                potencia_kw = st.number_input("Potencia (kW)", min_value=0.0, step=1.0, value=0.0)
            with c5:
                potencia_hp = st.number_input("Potencia (HP)", min_value=0.0, step=1.0, value=0.0)
            with c6:
                potencia_cv = st.number_input("Potencia (CV)", min_value=0.0, step=1.0, value=0.0)

            st.divider()
            st.markdown("##### 🏢 Datos Institucionales y Propietario")
            c7, c8, c9 = st.columns(3)
            with c7:
                propietario = st.text_input("Propietario")
                razon_social = st.text_input("Razón Social")
            with c8:
                ruc = st.text_input("RUC")
                contacto = st.text_input("Contacto / Teléfono")
            with c9:
                comunidad = st.text_input("Comunidad")

            st.divider()
            guardar_btn = st.form_submit_button("💾 Guardar y Dar de Alta Equipo", use_container_width=True)

            if guardar_btn:
                if not placa or not codigo_interno:
                    st.error("❌ La Placa y el Código Interno son obligatorios.")
                else:
                    nuevo_registro = {
                        "placa": placa,
                        "codigo_interno": codigo_interno,
                        "tipo_flota": tipo_flota,
                        "frecuencia_mantenimiento": frecuencia_pm,
                        "frente_asignado": frente_asignado,
                        "fecha_ingreso_proyecto": str(fecha_ingreso),
                        "marca": marca if marca else None,
                        "modelo": modelo if modelo else None,
                        "anio": int(anio) if anio else None,
                        "capacidad": capacidad if capacidad else None,
                        "potencia_kw": potencia_kw,
                        "potencia_hp": potencia_hp,
                        "potencia_cv": potencia_cv,
                        "propietario": propietario if propietario else None,
                        "razon_social": razon_social if razon_social else None,
                        "ruc": ruc if ruc else None,
                        "contacto": contacto if contacto else None,
                        "comunidad": comunidad if comunidad else None,
                        "estado_operativo": "OPERATIVO"
                    }

                    exito, res = insertar_registro("lista_maestra", nuevo_registro)
                    if exito:
                        st.success(f"✅ Equipo Placa `{placa}` registrado exitosamente.")
                        st.rerun()
                    else:
                        st.error(f"❌ Error al guardar en Supabase: {res}")

    with tab_retirar:
        st.subheader("❌ Retirar Equipo de la Flota Activa")
        st.caption("Esta acción pasará el equipo a estado 'RETIRADO' sin eliminar sus registros históricos.")

        if not df_equipos.empty and "estado_operativo" in df_equipos.columns:
            df_retirar = df_equipos[df_equipos["estado_operativo"] == "OPERATIVO"]
            if not df_retirar.empty:
                opciones_retirado = [
                    f"{r['placa']} - {r['codigo_interno']} ({r['tipo_flota']})"
                    for _, r in df_retirar.iterrows()
                ]
                equipo_sel = st.selectbox("Seleccione el equipo a retirar de la obra:", opciones_retirado)
                
                if st.button("⚠️ Confirmar Retiro de Equipo", use_container_width=True):
                    placa_target = equipo_sel.split(" - ")[0].strip()
                    if actualizar_estado_equipo(placa_target, "RETIRADO"):
                        st.success(f"✅ El equipo `{placa_target}` ha sido retirado correctamente.")
                        st.rerun()
                    else:
                        st.error("❌ No se pudo actualizar el estado del equipo en Supabase.")
            else:
                st.info("No hay equipos activos disponibles para retirar.")
        else:
            st.info("No hay registros en la base de datos.")

    with tab_inactivos:
        st.subheader("📁 Historial de Equipos Retirados / Inactivos")
        if not df_equipos.empty and "estado_operativo" in df_equipos.columns:
            df_inactivos = df_equipos[df_equipos["estado_operativo"] == "RETIRADO"].copy()
            if not df_inactivos.empty:
                cols_mostrar_in = ["codigo_interno", "placa", "tipo_flota", "marca", "frente_asignado", "propietario"]
                cols_existentes_in = [c for c in cols_mostrar_in if c in df_inactivos.columns]
                st.dataframe(df_inactivos[cols_existentes_in], use_container_width=True)

                st.divider()
                st.markdown("##### 🔄 Reincorporar Equipo a la Flota Activa")
                equipo_reinc = st.selectbox("Seleccione equipo a reactivar:", df_inactivos["placa"].tolist())
                if st.button("🟢 Reincorporar Equipo", use_container_width=True):
                    if actualizar_estado_equipo(equipo_reinc, "OPERATIVO"):
                        st.success(f"✅ El equipo `{equipo_reinc}` ha sido reincorporado a la flota activa.")
                        st.rerun()
                    else:
                        st.error("❌ No se pudo reactivar el equipo.")
            else:
                st.info("No hay equipos en el historial de retirados.")

# ==========================================
# MÓDULO 2: ESTATUS EQUIPO (ACREDITACIONES)
# ==========================================
elif modulo == "2. Estatus Equipo (Acreditaciones)":
    st.header("🛡 Estatus del Equipo & Control de Acreditaciones (`estatus_equipo`)")
    st.caption("Sincronización en tiempo real con la Lista Maestra, días faltantes y semáforos de vencimiento.")

    equipos = consultar_tabla("lista_maestra")
    estatus = consultar_tabla("estatus_equipo")

    df_equipos = pd.DataFrame(equipos) if equipos else pd.DataFrame()
    df_estatus = pd.DataFrame(estatus) if estatus else pd.DataFrame()

    tab_estatus_lista, tab_actualizar = st.tabs([
        "📋 Estatus de Documentación & Filtros",
        "✏️ Actualizar Permisos de Equipo"
    ])

    with tab_estatus_lista:
        if not df_equipos.empty and "estado_operativo" in df_equipos.columns:
            df_activos = df_equipos[df_equipos["estado_operativo"] == "OPERATIVO"].copy()
            
            if not df_estatus.empty:
                df_merged = df_activos.merge(df_estatus, on="placa", how="left")
            else:
                df_merged = df_activos.copy()
                for col in ["fotocheck", "soat", "poliza", "retorqueo", "citv", "gps", "tarjeta_mercancias", "certificado_operatividad", "certificado_inspeccion", "comentario"]:
                    df_merged[col] = None

            documentos = [
                ("soat", "dias_faltante_soat", "estado_soat", "SOAT"),
                ("poliza", "dias_faltante_poliza", "estado_poliza", "Póliza"),
                ("retorqueo", "dias_faltante_retorqueo", "estado_retorqueo", "Retorqueo"),
                ("citv", "dias_faltante_citv", "estado_citv", "CITV"),
                ("gps", "dias_faltante_gps", "estado_gps", "GPS"),
                ("tarjeta_mercancias", "dias_faltante_tarjeta_mercancias", "estado_tarjeta_mercancias", "Tarjeta Mercancías"),
                ("certificado_operatividad", "dias_faltante_certificado_operatividad", "estado_certificado_operatividad", "Cert. Operatividad"),
                ("certificado_inspeccion", "dias_faltante_certificado_inspeccion", "estado_certificado_inspeccion", "Cert. Inspección")
            ]

            resumen_documentos = []

            for col_fecha, col_dias, col_estado, nom_doc in documentos:
                if col_fecha in df_merged.columns:
                    calc_res = df_merged[col_fecha].apply(calcular_dias_vencimiento)
                    df_merged[col_dias] = [r[0] for r in calc_res]
                    df_merged[col_estado] = [r[1] for r in calc_res]
                    
                    c_crit = sum(1 for r in calc_res if r[1] == "CRÍTICO")
                    c_aler = sum(1 for r in calc_res if r[1] == "ALERTA")
                    c_vige = sum(1 for r in calc_res if r[1] == "VIGENTE")
                    c_sinf = sum(1 for r in calc_res if r[1] == "SIN FECHA")
                    
                    resumen_documentos.append({
                        "Documento / Permiso": nom_doc,
                        "🔴 CRÍTICO (≤15d)": c_crit,
                        "🟡 ALERTA (16-31d)": c_aler,
                        "🟢 VIGENTE (≥32d)": c_vige,
                        "⚪ SIN FECHA": c_sinf
                    })

            st.subheader("🚨 Resumen Semafórico por Documento y Permiso")
            df_resumen_doc = pd.DataFrame(resumen_documentos)
            st.dataframe(df_resumen_doc, use_container_width=True)
            st.divider()

            st.subheader("🔍 Filtro Específico por Permiso y Estado de Vencimiento")

            cols_export_estatus = [
                "tipo_flota", "codigo_interno", "placa", "frente_asignado", "fotocheck",
                "soat", "dias_faltante_soat", "estado_soat",
                "poliza", "dias_faltante_poliza", "estado_poliza",
                "retorqueo", "dias_faltante_retorqueo", "estado_retorqueo",
                "citv", "dias_faltante_citv", "estado_citv",
                "gps", "dias_faltante_gps", "estado_gps",
                "tarjeta_mercancias", "dias_faltante_tarjeta_mercancias", "estado_tarjeta_mercancias",
                "certificado_operatividad", "dias_faltante_certificado_operatividad", "estado_certificado_operatividad",
                "certificado_inspeccion", "dias_faltante_certificado_inspeccion", "estado_certificado_inspeccion",
                "comentario"
            ]
            
            cols_disp_estatus = [c for c in cols_export_estatus if c in df_merged.columns]

            c_e1, c_e2, c_e3 = st.columns([1.5, 1.5, 2])
            with c_e1:
                permiso_sel = st.selectbox(
                    "1. Seleccione Permiso a Inspeccionar:",
                    options=["TODOS LOS PERMISOS"] + [nom for _, _, _, nom in documentos]
                )
            with c_e2:
                estado_sel = st.selectbox(
                    "2. Filtrar Estado:",
                    options=["TODOS", "CRÍTICO", "ALERTA", "VIGENTE", "SIN FECHA"]
                )
            with c_e3:
                txt_est = st.text_input("🔎 3. Búsqueda Libre (Placa, Código, Fotocheck 'SI' / 'NO'):").strip()

            df_est_filtrado = df_merged.copy()

            if permiso_sel != "TODOS LOS PERMISOS":
                col_estado_target = [col_est for _, _, col_est, nom in documentos if nom == permiso_sel][0]
                if estado_sel != "TODOS":
                    df_est_filtrado = df_est_filtrado[df_est_filtrado[col_estado_target] == estado_sel]
            elif estado_sel != "TODOS":
                cols_estados = [col_est for _, _, col_est, _ in documentos if col_est in df_est_filtrado.columns]
                mask_cualquiera = pd.Series(False, index=df_est_filtrado.index)
                for ce in cols_estados:
                    mask_cualquiera |= (df_est_filtrado[ce] == estado_sel)
                df_est_filtrado = df_est_filtrado[mask_cualquiera]

            if txt_est:
                df_est_filtrado = aplicar_busqueda_libre(df_est_filtrado, cols_disp_estatus, txt_est)

            st.metric("Equipos Encontrados", f"{len(df_est_filtrado)} de {len(df_activos)}")

            st.dataframe(df_est_filtrado[cols_disp_estatus], use_container_width=True)

            st.download_button(
                label="📥 Descargar Reporte de Estatus Filtrado en Excel (.xlsx)",
                data=generar_excel_bytes(df_est_filtrado[cols_disp_estatus], "Estatus_Equipos_Filtrado"),
                file_name=f"Estatus_Equipos_Filtrado_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        else:
            st.info("No hay equipos activos registrados en la base de datos.")

    with tab_actualizar:
        st.subheader("✏️ Actualizar Fechas de Vencimiento de Permisos")
        if not df_equipos.empty:
            df_activos = df_equipos[df_equipos["estado_operativo"] == "OPERATIVO"]
            opciones_eq = [f"{r['placa']} - {r['codigo_interno']} ({r['tipo_flota']})" for _, r in df_activos.iterrows()]
            
            eq_sel_est = st.selectbox("Seleccione el equipo a actualizar:", opciones_eq)
            placa_sel_est = eq_sel_est.split(" - ")[0].strip()

            datos_previos = {}
            if not df_estatus.empty:
                match_e = df_estatus[df_estatus["placa"] == placa_sel_est]
                if not match_e.empty:
                    datos_previos = match_e.iloc[0].to_dict()

            with st.form("form_permisos_equipo", clear_on_submit=True):
                st.markdown(f"##### 🛡️ Permisos para el Equipo Placa: `{placa_sel_est}`")
                
                ce1, ce2, ce3 = st.columns(3)
                with ce1:
                    fotocheck = st.selectbox("Fotocheck", ["SI", "NO"], index=0 if datos_previos.get("fotocheck") != "NO" else 1)
                    soat = st.date_input("Vencimiento SOAT", value=parse_fecha(datos_previos.get("soat")))
                    poliza = st.date_input("Vencimiento Póliza Vehicular", value=parse_fecha(datos_previos.get("poliza")))
                with ce2:
                    retorqueo = st.date_input("Vencimiento Retorqueo", value=parse_fecha(datos_previos.get("retorqueo")))
                    citv = st.date_input("Vencimiento CITV / Rev. Técnica", value=parse_fecha(datos_previos.get("citv")))
                    gps = st.date_input("Vencimiento GPS", value=parse_fecha(datos_previos.get("gps")))
                with ce3:
                    tarjeta = st.date_input("Vencimiento Tarjeta Mercancías", value=parse_fecha(datos_previos.get("tarjeta_mercancias")))
                    operatividad = st.date_input("Certificado Operatividad", value=parse_fecha(datos_previos.get("certificado_operatividad")))
                    inspeccion = st.date_input("Certificado Inspección", value=parse_fecha(datos_previos.get("certificado_inspeccion")))

                comentario = st.text_input("Comentario / Observaciones", value=datos_previos.get("comentario", "") if datos_previos.get("comentario") else "")

                st.divider()
                guardar_est_btn = st.form_submit_button("💾 Guardar Estatus de Permisos", use_container_width=True)

                if guardar_est_btn:
                    reg_estatus = {
                        "placa": placa_sel_est,
                        "fotocheck": fotocheck,
                        "soat": str(soat),
                        "poliza": str(poliza),
                        "retorqueo": str(retorqueo),
                        "citv": str(citv),
                        "gps": str(gps),
                        "tarjeta_mercancias": str(tarjeta),
                        "certificado_operatividad": str(operatividad),
                        "certificado_inspeccion": str(inspeccion),
                        "comentario": comentario
                    }

                    exito_e, res_e = insertar_o_actualizar("estatus_equipo", reg_estatus)
                    if exito_e:
                        st.success(f"✅ Permisos actualizados para la Placa `{placa_sel_est}`.")
                        st.rerun()
                    else:
                        st.error(f"❌ Error al guardar en Supabase: {res_e}")

# ==========================================
# MÓDULO 3: REPORTE DIARIO (HOJA RD / REGISTRO)
# ==========================================
elif modulo == "3. Reporte Diario (Hoja RD)":
    st.header("📝 Módulo 3: Reporte Diario & Tareo de Trabajos (`reporte_diario`)")
    st.caption("Ficha interactiva equivalente a 'REGISTRO' conectada al Catálogo Maestro de Insumos.")

    equipos = consultar_tabla("lista_maestra")
    reportes = consultar_tabla("reporte_diario")
    insumos_cat = consultar_tabla("lista_insumos")

    df_equipos = pd.DataFrame(equipos) if equipos else pd.DataFrame()
    df_reportes = pd.DataFrame(reportes) if reportes else pd.DataFrame()
    df_ins_cat = pd.DataFrame(insumos_cat) if insumos_cat else pd.DataFrame()

    tab_registro_rd, tab_consulta_rd = st.tabs([
        "✍️ Ficha de Registro Diario (Buscardatos/Guardardatos)",
        "📊 Consolidado Reporte Diario & Filtros de Fecha"
    ])

    with tab_registro_rd:
        st.subheader("📋 Ficha de Campo Individual (Búsqueda y Edición Automática)")
        if df_equipos.empty:
            st.warning("⚠️ Debe registrar equipos en la Lista Maestra antes de ingresar partes diarios.")
        else:
            df_activos = df_equipos[df_equipos["estado_operativo"] == "OPERATIVO"]
            opciones_placa = [f"{r['placa']} - {r['codigo_interno']} ({r['tipo_flota']})" for _, r in df_activos.iterrows()]

            st.markdown("##### 🔎 1. Selección de Fecha y Equipo")
            col_b1, col_b2 = st.columns(2)
            with col_b1:
                fecha_sel = st.date_input("FECHA del Reporte *", datetime.now().date())
            with col_b2:
                eq_sel_rd = st.selectbox("CÓDIGO / PLACA EQUIPO *", opciones_placa)
                placa_sel_rd = eq_sel_rd.split(" - ")[0].strip()

            reg_existente = {}
            if not df_reportes.empty:
                df_reportes["fecha_reporte_dt"] = pd.to_datetime(df_reportes["fecha_reporte"], errors="coerce").dt.date
                match_rd = df_reportes[
                    (df_reportes["fecha_reporte_dt"] == fecha_sel) & 
                    (df_reportes["placa"] == placa_sel_rd)
                ]
                if not match_rd.empty:
                    reg_existente = match_rd.iloc[0].to_dict()
                    st.info("ℹ️ **Registro Encontrado:** Se cargaron los datos guardados anteriormente para este día y equipo. Puede editarlos directamente.")
                else:
                    st.success("✨ **Registro Nuevo:** No existen datos previos para este día. Complete la ficha para guardar un nuevo reporte.")

            info_eq = df_activos[df_activos["placa"] == placa_sel_rd].iloc[0].to_dict()
            cod_int_rd = info_eq.get("codigo_interno", "")
            tipo_flota_rd = info_eq.get("tipo_flota", "")
            frente_default = reg_existente.get("frente_asignado", info_eq.get("frente_asignado", "Frente Principal"))

            opciones_ins_cat = ["NINGUNO"]
            dict_precios_cat = {}
            if not df_ins_cat.empty:
                opciones_ins_cat += sorted(list(df_ins_cat["detalle_insumo"].dropna().astype(str).unique()))
                for _, r_cat in df_ins_cat.iterrows():
                    dict_precios_cat[r_cat["detalle_insumo"]] = float(r_cat.get("precio_insumo", 0.0) or 0.0)

            insumo_prev = reg_existente.get("detalle_insumo", "NINGUNO")
            idx_ins_cat = opciones_ins_cat.index(insumo_prev) if insumo_prev in opciones_ins_cat else 0

            with st.form("form_registro_diario_vba", clear_on_submit=False):
                st.markdown("##### 🚜 2. Información Operativa y de Máquina")
                r1, r2, r3 = st.columns(3)
                with r1:
                    st.text_input("Código Interno", value=cod_int_rd, disabled=True)
                    st.text_input("Equipo / Flota", value=tipo_flota_rd, disabled=True)
                    n_ot = st.text_input("ORDEN DE TRABAJO (N° OT)", value=reg_existente.get("numero_ot", ""))
                with r2:
                    frente_rd = st.text_input("FRENTE TRABAJO", value=frente_default)
                    
                    cod_estado_prev = str(reg_existente.get("codigo", "1")).strip()
                    idx_cod = 0 if cod_estado_prev in ["1", "1.0"] else 1
                    cod_estado_sel = st.selectbox("CÓDIGO DE ESTADO *", ["1 - Operativo", "2 - Inoperativo"], index=idx_cod)
                    cod_estado_val = "1" if "1" in cod_estado_sel else "2"
                    estado_auto = "Operativo" if cod_estado_val == "1" else "Inoperativo"
                    
                    st.info(f"📌 **Estado Reflejado:** `{estado_auto}`")
                    tec_resp = st.text_input("Técnico / Operador Responsable", value=reg_existente.get("tecnico_responsable", ""))
                with r3:
                    hr_val = st.number_input("Horómetro (HR)", min_value=0.0, step=0.1, value=float(reg_existente.get("hr", 0.0)))
                    km_val = st.number_input("Kilometraje (KM)", min_value=0.0, step=0.1, value=float(reg_existente.get("km", 0.0)))

                st.divider()
                st.markdown("##### ⏱️ 3. Horarios y Mantenimiento")
                r4, r5, r6 = st.columns(3)
                with r4:
                    t_inc = parse_hora(reg_existente.get("hora_inicio"), time(6, 0))
                    t_fn = parse_hora(reg_existente.get("hora_fin"), time(17, 0))
                    h_inicio = st.time_input("Hora Inicio", value=t_inc)
                    h_fin = st.time_input("Hora Final", value=t_fn)
                    
                    dt_start = datetime.combine(fecha_sel, h_inicio)
                    dt_end = datetime.combine(fecha_sel, h_fin)
                    diff_seconds = (dt_end - dt_start).total_seconds()
                    horas_mc_calc = round(max(0.0, diff_seconds / 3600.0), 2)
                    st.info(f"⏱️ **Horas MC Calculadas:** `{horas_mc_calc} h`")

                with r5:
                    list_tipo_manto = ["Preventivo", "Correctivo", "Implementacion"]
                    t_manto_prev = reg_existente.get("tipo_mantenimiento", "Preventivo")
                    idx_tm = list_tipo_manto.index(t_manto_prev) if t_manto_prev in list_tipo_manto else 0
                    tipo_manto = st.selectbox("TIPO MANTENIMIENTO *", list_tipo_manto, index=idx_tm)
                    
                    desc_trabajo = st.text_input("DESCRIPCIÓN DE TRABAJOS EJECUTADOS", value=reg_existente.get("descripcion_trabajo", ""))

                with r6:
                    hb_prev = int(float(reg_existente.get("hb", 10))) if reg_existente.get("hb") else 10
                    idx_hb = 0 if hb_prev == 10 else 1
                    hb_sel = st.selectbox("HORAS BASE (HB) *", [10, 5], index=idx_hb)
                    
                    dm_num = round(max(0.0, (hb_sel - horas_mc_calc) / hb_sel), 2) if hb_sel > 0 else 1.0
                    st.metric("Disponibilidad Mecánica (DM)", f"{int(dm_num * 100)}%")

                st.divider()
                st.markdown("##### 🛠️ 4. Trabajos Ejecutados e Insumos")
                r7, r8 = st.columns(2)
                with r7:
                    actividad_rd = st.text_area("ACTIVIDAD / DETALLE DE TRABAJO", value=reg_existente.get("actividad", ""))
                    backlog_rd = st.text_input("BACKLOG / OBSERVACIONES", value=reg_existente.get("backlog", ""))
                with r8:
                    insumo_seleccionado = st.selectbox("SELECCIONAR INSUMO DE ALMACÉN (MÓDULO 7)", opciones_ins_cat, index=idx_ins_cat)
                    
                    if insumo_seleccionado != "NINGUNO" and insumo_seleccionado in dict_precios_cat:
                        precio_auto = dict_precios_cat[insumo_seleccionado]
                        st.caption(f"📦 **Precio automático del modulo 7:** S/. {precio_auto:.2f}")
                    else:
                        precio_auto = float(reg_existente.get("precio_insumo", 0.0) or 0.0)

                    c_p1, c_p2 = st.columns(2)
                    with c_p1:
                        precio_mo = st.number_input("Costo Mano de Obra / HH (S/.)", min_value=0.0, step=10.0, value=float(reg_existente.get("precio", 0.0)))
                    with c_p2:
                        precio_insumo = st.number_input("Precio Insumo / Repuesto (S/.) *", min_value=0.0, step=1.0, value=precio_auto)

                st.divider()
                
                guardar_rd_btn = st.form_submit_button("💾 Guardar Parte Diario en Supabase", use_container_width=True)

                if guardar_rd_btn:
                    str_h_inicio = f"{fecha_sel}T{h_inicio.strftime('%H:%M:%S')}"
                    str_h_fin = f"{fecha_sel}T{h_fin.strftime('%H:%M:%S')}"

                    nuevo_rd = {
                        "fecha_reporte": str(fecha_sel),
                        "placa": placa_sel_rd,
                        "frente_asignado": frente_rd,
                        "numero_ot": n_ot if n_ot else "",
                        "codigo": cod_estado_val,          # "1" o "2"
                        "estado": estado_auto,             # "Operativo" u "Inoperativo"
                        "hr": hr_val,
                        "km": km_val,
                        "tecnico_responsable": tec_resp,
                        "descripcion_trabajo": desc_trabajo,
                        "backlog": backlog_rd,
                        "hora_inicio": str_h_inicio,
                        "hora_fin": str_h_fin,
                        "tipo_mantenimiento": tipo_manto,
                        "actividad": actividad_rd,
                        "horas_mc": horas_mc_calc,
                        "hb": hb_sel,
                        "dm": dm_num,
                        "precio": precio_mo,               # Columna 'precio' (Mano de Obra)
                        "detalle_insumo": insumo_seleccionado if insumo_seleccionado != "NINGUNO" else "",
                        "precio_insumo": precio_insumo    # Columna 'precio_insumo'
                    }

                    if "id" in reg_existente:
                        nuevo_rd["id"] = reg_existente["id"]

                    exito_rd, res_rd = insertar_o_actualizar("reporte_diario", nuevo_rd)
                    if exito_rd:
                        st.success(f"✅ Se guardaron los datos para la fecha `{fecha_sel}` y la Placa `{placa_sel_rd}` exitosamente.")
                        st.rerun()
                    else:
                        st.error(f"❌ Error al guardar datos en Supabase: {res_rd}")

    with tab_consulta_rd:
        st.subheader("🔍 Consulta Consolidada del Reporte Diario (`RD`)")
        st.caption("Filtre por Ciclo Semanal (Sábado a Viernes), Rango de Fechas Personalizado y/o Placa específica.")

        if df_reportes.empty:
            st.info("No hay partes diarios registrados en la base de datos.")
        else:
            if not df_equipos.empty:
                df_rd_full = df_reportes.merge(
                    df_equipos[["placa", "codigo_interno", "tipo_flota"]],
                    on="placa", how="left"
                )
            else:
                df_rd_full = df_reportes.copy()
                df_rd_full["codigo_interno"] = ""
                df_rd_full["tipo_flota"] = ""

            df_rd_full["fecha_reporte_dt"] = pd.to_datetime(df_rd_full["fecha_reporte"], errors="coerce").dt.date

            st.markdown("##### 📅 1. Selección de Modo de Filtro de Fechas")
            modo_fecha = st.radio(
                "Modo de Filtro de Fecha:",
                ["Semana Operativa (Sábado a Viernes)", "Rango de Fechas Personalizado (ej. 24 Ene a 24 Feb)", "Todos los Registros"],
                horizontal=True
            )

            hoy = datetime.now().date()
            if modo_fecha == "Semana Operativa (Sábado a Viernes)":
                sab_default, vie_default = obtener_rango_sabado_viernes(hoy)
                c_f1, c_f2 = st.columns(2)
                with c_f1:
                    fecha_inicio_filtro = st.date_input("Sábado de Inicio de Semana:", value=sab_default)
                with c_f2:
                    fecha_fin_filtro = st.date_input("Viernes de Cierre de Semana:", value=vie_default)
            elif modo_fecha == "Rango de Fechas Personalizado (ej. 24 Ene a 24 Feb)":
                c_f1, c_f2 = st.columns(2)
                with c_f1:
                    fecha_inicio_filtro = st.date_input("Fecha Inicio Corte:", value=hoy - timedelta(days=30))
                with c_f2:
                    fecha_fin_filtro = st.date_input("Fecha Fin Corte:", value=hoy)
            else:
                fecha_inicio_filtro = None
                fecha_fin_filtro = None

            st.markdown("##### 🚜 2. Filtro por Equipo / Placa Específica")
            placas_disponibles_rd = ["TODOS LOS EQUIPOS"] + sorted(list(df_rd_full["placa"].dropna().astype(str).unique()))
            placa_filtro_rd = st.selectbox("Seleccione Placa Específica:", placas_disponibles_rd)

            df_rd_filtrado = df_rd_full.copy()

            if fecha_inicio_filtro and fecha_fin_filtro:
                df_rd_filtrado = df_rd_filtrado[
                    (df_rd_filtrado["fecha_reporte_dt"] >= fecha_inicio_filtro) &
                    (df_rd_filtrado["fecha_reporte_dt"] <= fecha_fin_filtro)
                ]

            if placa_filtro_rd != "TODOS LOS EQUIPOS":
                df_rd_filtrado = df_rd_filtrado[df_rd_filtrado["placa"] == placa_filtro_rd]

            if "dm" in df_rd_filtrado.columns:
                df_rd_filtrado["dm_pct"] = (pd.to_numeric(df_rd_filtrado["dm"], errors="coerce") * 100).round(0).astype(str) + "%"
            else:
                df_rd_filtrado["dm_pct"] = "100%"

            st.divider()
            
            cols_export_rd = [
                "numero_ot", "codigo", "fecha_reporte", "codigo_interno", "placa", "tipo_flota",
                "frente_asignado", "estado", "hr", "km", "tecnico_responsable",
                "descripcion_trabajo", "backlog", "hora_inicio", "hora_fin",
                "tipo_mantenimiento", "actividad", "hb", "horas_mc", "dm_pct",
                "precio", "detalle_insumo", "precio_insumo"
            ]

            cols_disp_rd = [c for c in cols_export_rd if c in df_rd_filtrado.columns]

            st.metric("Registros de Trabajo Encontrados", len(df_rd_filtrado))
            st.dataframe(df_rd_filtrado[cols_disp_rd], use_container_width=True)

            st.download_button(
                label="📥 Descargar Reporte Diario Consolidado (Formato RD) en Excel (.xlsx)",
                data=generar_excel_bytes(df_rd_filtrado[cols_disp_rd], "RD_Reporte_Diario"),
                file_name=f"Reporte_Diario_EMQ_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

# ==========================================
# MÓDULO 4: PROGRAMA MANTENIMIENTO (CONTROL SEMANAL)
# ==========================================
elif modulo == "4. Programa Mantenimiento (Control Semanal)":
    st.header("📅 Módulo 4: Programa de Mantenimiento Preventivo (`programa_mantenimiento`)")
    st.caption("Planificación semanal, cálculo de horas faltantes, promedios de avance y semáforo de estado de máquinas.")

    equipos = consultar_tabla("lista_maestra")
    programas = consultar_tabla("programa_mantenimiento")

    df_equipos = pd.DataFrame(equipos) if equipos else pd.DataFrame()
    df_programas = pd.DataFrame(programas) if programas else pd.DataFrame()

    tab_control_pm, tab_editar_pm = st.tabs([
        "📊 Reporte de Control Semanal & Semáforo",
        "✏️ Actualizar Horómetros / Fechas de PM"
    ])

    if not df_equipos.empty and "estado_operativo" in df_equipos.columns:
        df_activos_pm = df_equipos[df_equipos["estado_operativo"] == "OPERATIVO"].copy()

        if not df_programas.empty:
            df_pm_full = df_activos_pm.merge(df_programas, on="placa", how="left")
        else:
            df_pm_full = df_activos_pm.copy()
            for c_pm in ["semana_anterior", "ultimo_pm", "fecha_manual", "horometro_actual", "horometro_mnto", "estado_actual", "fecha_actual"]:
                df_pm_full[c_pm] = None

        df_pm_full["semana_anterior"] = pd.to_numeric(df_pm_full["semana_anterior"], errors="coerce").fillna(0.0)
        df_pm_full["ultimo_pm"] = pd.to_numeric(df_pm_full["ultimo_pm"], errors="coerce").fillna(0.0)
        df_pm_full["horometro_actual"] = pd.to_numeric(df_pm_full["horometro_actual"], errors="coerce").fillna(0.0)
        df_pm_full["frecuencia_mantenimiento"] = pd.to_numeric(df_pm_full["frecuencia_mantenimiento"], errors="coerce").fillna(250.0)

        df_pm_full["promedio"] = ((df_pm_full["horometro_actual"] - df_pm_full["semana_anterior"]) / 7.0).round(2)
        df_pm_full["horometro_mnto"] = (df_pm_full["ultimo_pm"] + df_pm_full["frecuencia_mantenimiento"]).round(2)
        df_pm_full["horometro_faltante"] = (df_pm_full["horometro_mnto"] - df_pm_full["horometro_actual"]).round(2)

        def calc_dias_faltante(row):
            prom = row["promedio"]
            h_falt = row["horometro_faltante"]
            if pd.notna(prom) and prom > 0 and pd.notna(h_falt):
                return round(h_falt / prom, 1)
            return None

        df_pm_full["dias_faltante"] = df_pm_full.apply(calc_dias_faltante, axis=1)

        hoy_date = datetime.now().date()
        df_pm_full["fecha_actual"] = str(hoy_date)

        def calc_fecha_aprox(row):
            d_falt = row["dias_faltante"]
            if pd.notna(d_falt) and d_falt is not None:
                try:
                    return str(hoy_date + timedelta(days=float(d_falt)))
                except Exception:
                    return ""
            return ""

        df_pm_full["fecha_aprox"] = df_pm_full.apply(calc_fecha_aprox, axis=1)

        def calc_estado_semaforo(row):
            h_act = row["horometro_actual"]
            h_mnto = row["horometro_mnto"]
            tf = row.get("tipo_flota", "")
            umbral_val = obtener_valor_umbral(tf)

            if h_act == 0.0 or pd.isna(h_act):
                return "🟢 Operativo"

            if pd.notna(h_act) and pd.notna(h_mnto) and h_mnto > 0:
                if h_act >= (h_mnto - umbral_val):
                    return "🔴 Mantenimiento"
                else:
                    return "🟢 Operativo"
            return "🟢 Operativo"

        df_pm_full["estado_actual"] = df_pm_full.apply(calc_estado_semaforo, axis=1)

        with tab_control_pm:
            st.subheader("📊 Reporte Semanal de Programa de Mantenimiento")

            cnt_manto = sum(1 for e in df_pm_full["estado_actual"] if "Mantenimiento" in e)
            cnt_oper = sum(1 for e in df_pm_full["estado_actual"] if "Operativo" in e)

            k_pm1, k_pm2, k_pm3 = st.columns(3)
            k_pm1.metric("Total Flota Activa", len(df_pm_full))
            k_pm2.metric("🔴 En Umbral / Requiere Mantenimiento", cnt_manto)
            k_pm3.metric("🟢 Operativo Preventivo", cnt_oper)

            st.divider()

            cols_orden_cliente = [
                "tipo_flota", "marca", "modelo", "frente_asignado", "placa", "codigo_interno",
                "semana_anterior", "promedio", "ultimo_pm", "fecha_manual", "horometro_actual",
                "horometro_mnto", "estado_actual", "fecha_actual", "fecha_aprox",
                "horometro_faltante", "dias_faltante"
            ]

            cols_disp_pm = [c for c in cols_orden_cliente if c in df_pm_full.columns]

            st.subheader("🔍 Filtros de Búsqueda de Programa Semanal")
            c_pm1, c_pm2, c_pm3 = st.columns([1.5, 1.5, 2])
            with c_pm1:
                col_filtro_pm = st.selectbox("1. Filtrar por Columna:", options=["NINGUNO"] + cols_disp_pm)
            with c_pm2:
                if col_filtro_pm != "NINGUNO":
                    vals_pm = ["TODOS"] + sorted(list(df_pm_full[col_filtro_pm].dropna().astype(str).unique()))
                    val_filtro_pm = st.selectbox(f"2. Valor de {col_filtro_pm}:", vals_pm)
                else:
                    val_filtro_pm = "TODOS"
                    st.selectbox("2. Valor:", ["TODOS"], disabled=True)
            with c_pm3:
                txt_pm = st.text_input("🔎 3. Búsqueda Libre (Placa, Código, Tipo Flota, Frente):").strip()

            df_pm_filtrado = df_pm_full.copy()
            if col_filtro_pm != "NINGUNO" and val_filtro_pm != "TODOS":
                df_pm_filtrado = df_pm_filtrado[df_pm_filtrado[col_filtro_pm].astype(str) == val_filtro_pm]

            if txt_pm:
                df_pm_filtrado = aplicar_busqueda_libre(df_pm_filtrado, cols_disp_pm, txt_pm)

            st.dataframe(df_pm_filtrado[cols_disp_pm], use_container_width=True)

            st.download_button(
                label="📥 Descargar Reporte de Programa de Mantenimiento (.xlsx)",
                data=generar_excel_bytes(df_pm_filtrado[cols_disp_pm], "Programa_Mantenimiento"),
                file_name=f"Programa_Mantenimiento_Semanal_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

        with tab_editar_pm:
            st.subheader("✏️ Actualizar Horómetros y Fechas de PM por Equipo")
            opciones_eq_pm = [f"{r['placa']} - {r['codigo_interno']} ({r['tipo_flota']})" for _, r in df_activos_pm.iterrows()]
            
            eq_sel_pm = st.selectbox("Seleccione el equipo a actualizar:", opciones_eq_pm)
            placa_sel_pm = eq_sel_pm.split(" - ")[0].strip()

            datos_prev_pm = {}
            if not df_programas.empty:
                match_pm = df_programas[df_programas["placa"] == placa_sel_pm]
                if not match_pm.empty:
                    datos_prev_pm = match_pm.iloc[0].to_dict()

            info_eq_pm = df_activos_pm[df_activos_pm["placa"] == placa_sel_pm].iloc[0].to_dict()
            frec_pm_val = float(info_eq_pm.get("frecuencia_mantenimiento", 250.0))
            tf_pm_val = info_eq_pm.get("tipo_flota", "")
            umbral_actual = obtener_valor_umbral(tf_pm_val)

            st.info(f"📌 **Frecuencia PM:** `{frec_pm_val} Horas/KM` | **Umbral de Alerta (`Valor`):** `{umbral_actual} Horas/KM`")

            with st.form("form_update_pm", clear_on_submit=False):
                cp1, cp2, cp3 = st.columns(3)
                with cp1:
                    sem_ant = st.number_input("Horómetro / KM Semana Anterior", min_value=0.0, step=10.0, value=float(datos_prev_pm.get("semana_anterior", 0.0)))
                    ult_pm = st.number_input("Último PM (Horómetro / KM)", min_value=0.0, step=10.0, value=float(datos_prev_pm.get("ultimo_pm", 0.0)))
                with cp2:
                    h_act = st.number_input("Horómetro / KM Actual *", min_value=0.0, step=10.0, value=float(datos_prev_pm.get("horometro_actual", 0.0)))
                    f_manual = st.date_input("Fecha Manual", value=parse_fecha(datos_prev_pm.get("fecha_manual")))
                with cp3:
                    h_mnto_calc = ult_pm + frec_pm_val
                    st.metric("Horómetro Próximo Mantenimiento", f"{h_mnto_calc:.1f}")
                    
                    if h_act == 0.0:
                        est_calc_form = "🟢 Operativo (Pendiente Lectura)"
                    else:
                        est_calc_form = "🔴 Mantenimiento" if h_act >= (h_mnto_calc - umbral_actual) else "🟢 Operativo"
                    st.info(f"Semáforo Estimado: **{est_calc_form}**")

                st.divider()
                guardar_pm_btn = st.form_submit_button("💾 Guardar Datos de Programa Mantenimiento", use_container_width=True)

                if guardar_pm_btn:
                    reg_save_pm = {
                        "placa": placa_sel_pm,
                        "semana_anterior": sem_ant,
                        "ultimo_pm": ult_pm,
                        "fecha_manual": str(f_manual),
                        "horometro_actual": h_act,
                        "horometro_mnto": h_mnto_calc,
                        "estado_actual": "Mantenimiento" if "Mantenimiento" in est_calc_form else "Operativo",
                        "fecha_actual": str(datetime.now().date())
                    }

                    exito_pm, res_pm = insertar_o_actualizar("programa_mantenimiento", reg_save_pm)
                    if exito_pm:
                        st.success(f"✅ Programa de mantenimiento actualizado correctamente para la Placa `{placa_sel_pm}`.")
                        st.rerun()
                    else:
                        st.error(f"❌ Error al guardar en Supabase: {res_pm}")

    else:
        st.info("No hay equipos activos en la Lista Maestra.")

# ==========================================
# MÓDULO 5: VALE DE COMBUSTIBLE & Z-SCORE
# ==========================================
elif modulo == "5. Vale de Combustible & Z-Score":
    st.header("⛽ Módulo 5: Vales de Combustible y Detección de Fugas (Z-Score)")
    st.caption("Control estricto de consumos de combustible y detección estadística de anomalías o desviaciones.")

    equipos = consultar_tabla("lista_maestra")
    vales = consultar_tabla("vale_combustible")

    df_equipos = pd.DataFrame(equipos) if equipos else pd.DataFrame()
    df_vales = pd.DataFrame(vales) if vales else pd.DataFrame()

    tab_reg_vale, tab_auditoria_z = st.tabs([
        "📝 Registro de Vale de Combustible",
        "📊 Auditoría de Fugas y Anomalías (Z-Score)"
    ])

    with tab_reg_vale:
        st.subheader("✍️ Registro de Abastecimiento en Campo")
        
        if df_equipos.empty:
            st.warning("⚠️ Debe registrar equipos en la Lista Maestra antes de registrar vales de combustible.")
        else:
            df_activos_comb = df_equipos[df_equipos["estado_operativo"] == "OPERATIVO"]
            
            if df_activos_comb.empty:
                st.warning("⚠️ No hay equipos con estado OPERATIVO en la Lista Maestra.")
            else:
                opciones_placas_comb = sorted(list(df_activos_comb["placa"].dropna().unique()))

                with st.form("form_vale_combustible", clear_on_submit=True):
                    st.markdown("##### ⛽ Datos del Despacho de Combustible")
                    cv1, cv2, cv3 = st.columns(3)
                    
                    with cv1:
                        fecha_abas = st.date_input("Fecha de Abastecimiento *", datetime.now().date())
                        placa_val_sel = st.selectbox("Placa / Código Equipo (Lista Maestra) *", opciones_placas_comb)
                        placa_cis_grifo = st.text_input("Placa Cisterna / Grifo *", placeholder="Ej: CIS-01 o GRIFO PRINCIPAL").upper().strip()
                        cantidad_abas = st.number_input("Cantidad Abastecida (Galones) *", min_value=0.0, step=0.1)

                    with cv2:
                        tipo_combustible = st.selectbox("Tipo Combustible *", ["DIESEL B5 S50", "GASOHOL REGULAR", "GASOHOL PREMIUM"])
                        horometro = st.number_input("Horómetro Actual", min_value=0.0, step=0.1)
                        kilometraje = st.number_input("Kilometraje Actual", min_value=0.0, step=1.0)
                        frente_asignado = st.text_input("Frente Asignado *", value="Frente Principal")

                    with cv3:
                        nombre_operador = st.text_input("Nombre Operador *", placeholder="Ej: Juan Pérez").title().strip()
                        dni_operador = st.text_input("DNI Operador *", max_chars=8).strip()
                        ing_responsable = st.text_input("Ing. Responsable *", placeholder="Ej: Ing. Carlos Gómez").title().strip()
                        detalle_consumo = st.text_area("Detalle / Observaciones", placeholder="Ej: Tanque lleno al final del turno nocturno", height=68)

                    st.divider()
                    guardar_vale_btn = st.form_submit_button("💾 Guardar Vale en Supabase", use_container_width=True)

                    if guardar_vale_btn:
                        if placa_val_sel not in opciones_placas_comb:
                            st.error("❌ La placa seleccionada no existe en la Lista Maestra de equipos.")
                        elif not dni_operador or cantidad_abas <= 0 or not placa_cis_grifo:
                            st.error("❌ Complete todos los campos obligatorios (*): Placa, Cisterna, DNI y Cantidad > 0.")
                        else:
                            payload_vale = {
                                "fecha_abastecimiento": str(fecha_abas),
                                "placa": placa_val_sel,
                                "placa_cis_grifo": placa_cis_grifo,
                                "cantidad_abas_campo": cantidad_abas,
                                "tipo_combustible": tipo_combustible,
                                "horometro": horometro,
                                "kilometraje": kilometraje,
                                "nombre_operador": nombre_operador,
                                "dni_operador": dni_operador,
                                "ing_responsable": ing_responsable,
                                "frente_asignado": frente_asignado,
                                "detalle_consumo": detalle_consumo
                            }

                            exito_v, res_v = insertar_registro("vale_combustible", payload_vale)
                            if exito_v:
                                st.success(f"✅ Vale registrado correctamente para la unidad `{placa_val_sel}`.")
                                st.rerun()
                            else:
                                st.error(f"❌ Error al guardar vale en Supabase: {res_v}")

    with tab_auditoria_z:
        st.subheader("🔍 Auditoría de Consumos, Ratios y Detección de Fugas (Z-Score)")

        if df_vales.empty:
            st.info("No hay vales de combustible registrados en la base de datos.")
        else:
            # Cruzar dinámicamente con Lista Maestra para obtener Tipo de Flota
            if not df_equipos.empty and "tipo_flota" in df_equipos.columns:
                df_vales = df_vales.merge(
                    df_equipos[["placa", "tipo_flota"]], 
                    on="placa", 
                    how="left"
                )
                df_vales["tipo_flota"] = df_vales["tipo_flota"].fillna("Sin Categoría")
            else:
                df_vales["tipo_flota"] = "Sin Categoría"

            df_vales["fecha_dt"] = pd.to_datetime(df_vales["fecha_abastecimiento"], errors="coerce")
            df_vales["cantidad_abas_campo"] = pd.to_numeric(df_vales["cantidad_abas_campo"], errors="coerce").fillna(0.0)
            df_vales["horometro"] = pd.to_numeric(df_vales["horometro"], errors="coerce").fillna(0.0)
            df_vales["kilometraje"] = pd.to_numeric(df_vales["kilometraje"], errors="coerce").fillna(0.0)

            # --- SECCIÓN DE FILTROS ---
            st.markdown("##### 🔍 Filtros de Auditoría")
            fc1, fc2, fc3 = st.columns(3)

            with fc1:
                lista_placas = ["TODOS"] + sorted(df_vales["placa"].dropna().astype(str).unique().tolist())
                filtro_placa = st.selectbox("Filtrar por Placa Equipo:", lista_placas)

            with fc2:
                lista_operadores = ["TODOS"] + sorted(df_vales["nombre_operador"].dropna().astype(str).unique().tolist())
                filtro_operador = st.selectbox("Filtrar por Nombre de Operador:", lista_operadores)

            with fc3:
                min_f = df_vales["fecha_dt"].min().date() if pd.notna(df_vales["fecha_dt"].min()) else datetime.now().date()
                max_f = df_vales["fecha_dt"].max().date() if pd.notna(df_vales["fecha_dt"].max()) else datetime.now().date()
                rango_fechas = st.date_input("Rango de Fechas (Inicio - Fin):", value=(min_f, max_f))

            # Aplicar filtros
            df_val_filt = df_vales.copy()

            if isinstance(rango_fechas, tuple) and len(rango_fechas) == 2:
                f_ini, f_fin = rango_fechas
                df_val_filt = df_val_filt[(df_val_filt["fecha_dt"].dt.date >= f_ini) & (df_val_filt["fecha_dt"].dt.date <= f_fin)]

            if filtro_placa != "TODOS":
                df_val_filt = df_val_filt[df_val_filt["placa"] == filtro_placa]

            if filtro_operador != "TODOS":
                df_val_filt = df_val_filt[df_val_filt["nombre_operador"] == filtro_operador]

            if df_val_filt.empty:
                st.warning("No hay datos de consumos que coincidan con los filtros seleccionados.")
            else:
                # Ordenamiento cronológico ascendente para cálculo del desplazamiento (shift)
                df_val_filt = df_val_filt.sort_values(by=["placa", "fecha_dt"], ascending=[True, True])

                df_val_filt["horometro_ant"] = df_val_filt.groupby("placa")["horometro"].shift(1)
                df_val_filt["kilometraje_ant"] = df_val_filt.groupby("placa")["kilometraje"].shift(1)

                df_val_filt["delta_hr"] = df_val_filt["horometro"] - df_val_filt["horometro_ant"]
                df_val_filt["delta_km"] = df_val_filt["kilometraje"] - df_val_filt["kilometraje_ant"]

                def calcular_ratio_consumo(row):
                    gal = row["cantidad_abas_campo"]
                    d_hr = row["delta_hr"]
                    d_km = row["delta_km"]
                    h_ant = row["horometro_ant"]
                    k_ant = row["kilometraje_ant"]

                    if pd.isna(h_ant) and pd.isna(k_ant):
                        return "1er Registro / N/A"

                    if gal <= 0:
                        return "0.00 Gln"

                    if pd.notna(d_hr) and d_hr > 0:
                        gln_hr = gal / d_hr
                        return f"{gln_hr:.2f} Gln/Hr"
                    elif pd.notna(d_km) and d_km > 0:
                        km_gln = d_km / gal
                        return f"{km_gln:.2f} KM/Gln"

                    return "0.00 (Misma Lectura)"

                df_val_filt["ratio_consumo"] = df_val_filt.apply(calcular_ratio_consumo, axis=1)

                # --- CÁLCULO ESTADÍSTICO DE Z-SCORE POR PLACA ---
                stats_placa = df_val_filt.groupby("placa")["cantidad_abas_campo"].agg(["mean", "std", "count"]).reset_index()
                stats_placa.rename(columns={"mean": "media_gal", "std": "desv_std", "count": "n_muestras"}, inplace=True)

                df_z = df_val_filt.merge(stats_placa, on="placa", how="left")

                def calcular_z(row):
                    std = row["desv_std"]
                    n = row["n_muestras"]
                    if pd.isna(std) or std == 0 or n < 3:
                        return 0.0
                    return (row["cantidad_abas_campo"] - row["media_gal"]) / std

                df_z["z_score"] = df_z.apply(calcular_z, axis=1).round(2)

                def clasificar_alerta(z):
                    abs_z = abs(z)
                    if abs_z > 3.0:
                        return "🔴 ALERTA CRÍTICA"
                    elif abs_z > 2.0:
                        return "🟡 SOSPECHOSO"
                    return "🟢 NORMAL"

                df_z["estado_alerta"] = df_z["z_score"].apply(clasificar_alerta)

                # KPIs de Consumo
                k1, k2, k3, k4 = st.columns(4)
                k1.metric("Galones Totales", f"{df_z['cantidad_abas_campo'].sum():,.1f} Gal")
                k2.metric("🟢 Abastecimientos Normales", len(df_z[df_z["estado_alerta"] == "🟢 NORMAL"]))
                k3.metric("🟡 Sospechosos (|Z| > 2)", len(df_z[df_z["estado_alerta"] == "🟡 SOSPECHOSO"]))
                k4.metric("🔴 Alertas Críticas (|Z| > 3)", len(df_z[df_z["estado_alerta"] == "🔴 ALERTA CRÍTICA"]))

                st.divider()

                # --- NOTA TÉCNICA OBLIGATORIA SOBRE EL Z-SCORE Y RATIO ---
                st.error("""
                📌 **NOTA OPERATIVA Y DE AUDITORÍA SOBRE EL Z-SCORE Y RATIOS:**
                
                - **Ratio de Consumo:** Indica la tasa de trabajo por galón en función de las Horas o Kilómetros recorridos entre abastecimientos consecutivos ($\text{Gln/Hr}$ o $\text{KM/Gln}$).
                - **Alertas Z-Score:** Marcadas como **🔴 ALERTA CRÍTICA (|Z| > 3.0)** o **🟡 SOSPECHOSO (|Z| > 2.0)** indican una variación estadística atípica respecto al promedio histórico propio del equipo.
                
                **Instrucciones de Verificación Obligatorias:**
                1. **Verificación de Campo:** Si un equipo presenta un disparo en galones desproporcionado a su ratio ($\text{Gln/Hr}$ elevado), inspeccionar de inmediato el tanque y validar si existió fuga física o inyectores defectuosos.
                2. **Auditoría de Vales vs. Cisterna:** Cruzar la `cantidad_abas_campo` reportada por la `placa_cis_grifo` con los comprobantes físicos.
                3. **Control Operacional:** Si el valor $Z > +3.0$ sin incremento en horas/kilómetros trabajados, **iniciar protocolo por posible ordeño de combustible o error de digitación**.
                """)

                # Ordenar la presentación descendentemente
                df_display = df_z.sort_values(by="fecha_dt", ascending=False).copy()
                df_display["fecha_abastecimiento"] = df_display["fecha_dt"].dt.strftime('%Y-%m-%d')

                cols_mostrar_z = [
                    "fecha_abastecimiento", "placa", "tipo_flota", "cantidad_abas_campo", "ratio_consumo",
                    "z_score", "estado_alerta", "nombre_operador", "placa_cis_grifo", 
                    "horometro", "kilometraje", "ing_responsable", "frente_asignado", "detalle_consumo"
                ]

                cols_existentes_z = [c for c in cols_mostrar_z if c in df_display.columns]

                st.dataframe(
                    df_display[cols_existentes_z],
                    column_config={
                        "fecha_abastecimiento": "Fecha",
                        "placa": "Placa",
                        "tipo_flota": "Tipo de Flota / Categoría",
                        "cantidad_abas_campo": st.column_config.NumberColumn("Galones Despachados", format="%.2f Gal"),
                        "ratio_consumo": st.column_config.TextColumn("Ratio de Consumo (Gln/Hr / KM/Gln)"),
                        "z_score": st.column_config.NumberColumn("Z-Score", format="%.2f"),
                        "estado_alerta": "Alerta Fuga / Desviación",
                    },
                    use_container_width=True,
                    hide_index=True
                )

                st.download_button(
                    label="📥 Descargar Auditoría de Combustible en Excel (.xlsx)",
                    data=generar_excel_bytes(df_display[cols_existentes_z], "Auditoria_Combustible"),
                    file_name=f"Auditoria_Combustible_Ratios_ZScore_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )

# ==========================================
# MÓDULO 7: VALORIZACIÓN & CATÁLOGO DE INSUMOS
# ==========================================
elif modulo == "7. Valorización & Catálogo de Insumos":
    st.header("💰 Módulo 7: Valorización de Trabajos por Equipo & Catálogo Maestro")
    st.caption("Generación de matriz de valorización filtrada por equipo y rango de fechas de ingreso, con catálogo de precios de almacén.")

    equipos = consultar_tabla("lista_maestra")
    reportes = consultar_tabla("reporte_diario")
    insumos_cat = consultar_tabla("lista_insumos")

    df_equipos = pd.DataFrame(equipos) if equipos else pd.DataFrame()
    df_reportes = pd.DataFrame(reportes) if reportes else pd.DataFrame()
    df_ins_cat = pd.DataFrame(insumos_cat) if insumos_cat else pd.DataFrame()

    tab_val_equipo, tab_cat_precios = st.tabs([
        "📊 Matriz de Valorización por Equipo",
        "📦 Catálogo Maestro de Precios de Almacén"
    ])

    with tab_val_equipo:
        st.subheader("💵 Valorización de Mantenimiento por Máquina / Periodo")
        
        if df_reportes.empty or df_equipos.empty:
            st.warning("⚠️ No hay suficientes datos registrados en la Lista Maestra o en el Reporte Diario para generar valorizaciones.")
        else:
            df_activos = df_equipos[df_equipos["estado_operativo"] == "OPERATIVO"]
            opciones_placa_val = [f"{r['placa']} - {r['codigo_interno']} ({r['tipo_flota']})" for _, r in df_activos.iterrows()]

            st.markdown("##### 1. Selección de Equipo y Rango de Fechas de Permanencia/Trabajo")
            c_v1, c_v2, c_v3 = st.columns(3)
            with c_v1:
                eq_val_sel = st.selectbox("Seleccione Equipo a Valorizar *", opciones_placa_val)
                placa_val_target = eq_val_sel.split(" - ")[0].strip()
            
            hoy = datetime.now().date()
            with c_v2:
                fecha_ini_val = st.date_input("Fecha Inicio Corte *", value=hoy - timedelta(days=30))
            with c_v3:
                fecha_fin_val = st.date_input("Fecha Fin Corte *", value=hoy)

            df_rep_copy = df_reportes.copy()
            df_rep_copy["fecha_dt"] = pd.to_datetime(df_rep_copy["fecha_reporte"], errors="coerce").dt.date
            
            df_val_filtrado = df_rep_copy[
                (df_rep_copy["placa"] == placa_val_target) &
                (df_rep_copy["fecha_dt"] >= fecha_ini_val) &
                (df_rep_copy["fecha_dt"] <= fecha_fin_val)
            ].sort_values(by="fecha_dt")

            if df_val_filtrado.empty:
                st.info(f"No se encontraron trabajos registrados para el equipo `{placa_val_target}` en el rango del `{fecha_ini_val}` al `{fecha_fin_val}`.")
            else:
                filas_valorizacion = []
                item_counter = 1

                for _, r in df_val_filtrado.iterrows():
                    p_mo = float(r.get("precio", 0.0) or 0.0)
                    p_ins = float(r.get("precio_insumo", 0.0) or 0.0)
                    p_total_row = p_mo + p_ins

                    desc_ejecutada = str(r.get("descripcion_trabajo", "") or "").strip()
                    det_ins = str(r.get("detalle_insumo", "") or "").strip()
                    
                    desc_completa = desc_ejecutada
                    if det_ins and det_ins != "NINGUNO":
                        desc_completa = f"{desc_ejecutada} / INSUMO: {det_ins}".strip(" /")

                    filas_valorizacion.append({
                        "ITEMS": item_counter,
                        "N° O.T.": r.get("numero_ot", r.get("codigo", "")),
                        "TIPO MANTTO": r.get("tipo_mantenimiento", "Preventivo"),
                        "FECHA": r.get("fecha_reporte", ""),
                        "DESCRIPCIÓN": desc_completa,
                        "C.U.": f"S/. {p_ins:.2f}" if p_ins > 0 else "-",
                        "TOTAL (S/.)": p_total_row
                    })
                    item_counter += 1

                df_matriz_val = pd.DataFrame(filas_valorizacion)
                
                st.divider()
                st.markdown(f"##### 📋 Resumen de Valorización - Equipo Placa: `{placa_val_target}`")
                
                m_v1, m_v2, m_v3 = st.columns(3)
                m_v1.metric("Total Mantenimientos", len(df_matriz_val))
                m_v2.metric("Mano de Obra Acumulada (S/.)", f"S/. {df_val_filtrado['precio'].astype(float).sum():,.2f}")
                
                total_acumulado_soles = df_matriz_val["TOTAL (S/.)"].sum()
                m_v3.metric("VALORIZACIÓN TOTAL (S/.)", f"S/. {total_acumulado_soles:,.2f}")

                df_matriz_val_display = df_matriz_val.copy()
                df_matriz_val_display["TOTAL (S/.)"] = df_matriz_val_display["TOTAL (S/.)"].apply(lambda x: f"S/. {x:,.2f}")

                st.dataframe(df_matriz_val_display, use_container_width=True)

                st.download_button(
                    label=f"📥 Descargar Reporte de Valorización de {placa_val_target} (.xlsx)",
                    data=generar_excel_bytes(df_matriz_val, f"Valorizacion_{placa_val_target}"),
                    file_name=f"Valorizacion_{placa_val_target}_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )

    with tab_cat_precios:
        st.subheader("📦 Catálogo Maestro de Precios Vigentes de Almacén")
        st.caption("Administre la lista oficial de repuestos con sus precios unitarios actualizados sin generar duplicados de lotes.")

        f_cat1, f_cat2 = st.columns([2, 1])
        with f_cat1:
            st.markdown("##### 📋 Repuestos Registrados en Almacén")
            if not df_ins_cat.empty:
                cols_ins_cat = ["id", "unidad", "detalle_insumo", "precio_insumo"]
                cols_disp_cat = [c for c in cols_ins_cat if c in df_ins_cat.columns]
                st.dataframe(df_ins_cat[cols_disp_cat], use_container_width=True)
            else:
                st.info("No hay precios de insumos registrados aún en el catálogo.")

        with f_cat2:
            st.markdown("##### ➕ / ✏️ Registrar o Actualizar Precio de Lote")
            with st.form("form_cat_insumos_vba", clear_on_submit=True):
                unidad_ins = st.selectbox("Unidad de Medida *", ["Unid", "Gln", "Juego", "Litro", "Kg", "Metro", "Pieza", "Caja", "Par", "Otro"])
                detalle_ins = st.text_input("Detalle Insumo / Nombre Repuesto *").upper().strip()
                precio_ins = st.number_input("Precio Unitario Vigente (S/.) *", min_value=0.0, step=5.0, value=0.0)

                st.divider()
                guardar_cat_btn = st.form_submit_button("💾 Guardar / Actualizar Precio", use_container_width=True)

                if guardar_cat_btn:
                    if not detalle_ins:
                        st.error("❌ El Detalle del Insumo es obligatorio.")
                    else:
                        reg_ins_cat = {
                            "unidad": unidad_ins,
                            "detalle_insumo": detalle_ins,
                            "precio_insumo": precio_ins
                        }
                        
                        if not df_ins_cat.empty:
                            match_cat = df_ins_cat[df_ins_cat["detalle_insumo"] == detalle_ins]
                            if not match_cat.empty:
                                reg_ins_cat["id"] = int(match_cat.iloc[0]["id"])

                        exito_c, res_c = insertar_o_actualizar("lista_insumos", reg_ins_cat)
                        if exito_c:
                            st.success(f"✅ Precio actualizado correctamente para `{detalle_ins}`.")
                            st.rerun()
                        else:
                            st.error(f"❌ Error al guardar en Supabase: {res_c}")

            st.divider()
            st.markdown("##### ❌ Eliminar Insumo del Catálogo")
            if not df_ins_cat.empty:
                opciones_del_cat = [f"{r['id']} - {r['detalle_insumo']}" for _, r in df_ins_cat.iterrows()]
                ins_del_sel = st.selectbox("Seleccione Insumo:", opciones_del_cat)
                id_ins_del = int(ins_del_sel.split(" - ")[0].strip())

                if st.button("🗑️ Eliminar Repuesto de Almacén", use_container_width=True):
                    if eliminar_registro("lista_insumos", "id", id_ins_del):
                        st.success("✅ Insumo eliminado del catálogo.")
                        st.rerun()
                    else:
                        st.error("❌ No se pudo eliminar el registro.")

else:
    st.info("Módulo en desarrollo para la siguiente fase de revisión.")
