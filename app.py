import streamlit as st
import requests
import pandas as pd
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

def obtener_rango_sabado_viernes(fecha_ref):
    # Sábado previo a fecha_ref hasta el viernes siguiente
    dias_desde_sabado = (fecha_ref.weekday() - 5) % 7
    sabado = fecha_ref - timedelta(days=dias_desde_sabado)
    viernes = sabado + timedelta(days=6)
    return sabado, viernes

# Menú Lateral
modulo = st.sidebar.radio(
    "Navegación / Módulos:",
    [
        "1. Lista Maestra (Alta y Baja)",
        "2. Estatus Equipo (Acreditaciones)",
        "3. Reporte Diario (Hoja RD)",
        "4. Programa Mantenimiento (En desarrollo)",
        "5. Vale de Combustible (En desarrollo)",
        "6. Registro Cisterna (En desarrollo)",
        "7. Lista Insumos (En desarrollo)"
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
    st.header("🛡️ Estatus del Equipo & Control de Acreditaciones (`estatus_equipo`)")
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
    st.caption("Ficha de ingreso réplica de la hoja 'REGISTRO' y exportación filtrada conforme al formato 'RD'.")

    equipos = consultar_tabla("lista_maestra")
    reportes = consultar_tabla("reporte_diario")

    df_equipos = pd.DataFrame(equipos) if equipos else pd.DataFrame()
    df_reportes = pd.DataFrame(reportes) if reportes else pd.DataFrame()

    tab_registro_rd, tab_consulta_rd = st.tabs([
        "✍️ Registrar Trabajo Diario (Ficha REGISTRO)",
        "📊 Consolidado Reporte Diario & Filtros de Fecha"
    ])

    # --- PESTAÑA 1: FORMULARIO DE INGRESO RÉPLICA DE LA HOJA REGISTRO ---
    with tab_registro_rd:
        st.subheader("📋 Panel de Registro Diario (Ficha de Campo)")
        if df_equipos.empty:
            st.warning("⚠️ Debe registrar equipos en la Lista Maestra antes de ingresar partes diarios.")
        else:
            df_activos = df_equipos[df_equipos["estado_operativo"] == "OPERATIVO"]
            opciones_placa = [f"{r['placa']} - {r['codigo_interno']} ({r['tipo_flota']})" for _, r in df_activos.iterrows()]

            with st.form("form_registro_diario", clear_on_submit=True):
                st.markdown("##### 🚜 1. Información de la Máquina")
                r1, r2, r3 = st.columns(3)
                with r1:
                    fecha_rep = st.date_input("FECHA del Trabajo *", datetime.now().date())
                    eq_sel_rd = st.selectbox("PLACA / SERIE *", opciones_placa)
                    placa_rd = eq_sel_rd.split(" - ")[0].strip()
                    
                    # Auto-completado desde lista_maestra
                    info_eq = df_activos[df_activos["placa"] == placa_rd].iloc[0].to_dict()
                    cod_int_rd = info_eq.get("codigo_interno", "")
                    tipo_flota_rd = info_eq.get("tipo_flota", "")
                    frente_default = info_eq.get("frente_asignado", "Frente Principal")

                    st.info(f"📌 **Código Interno:** `{cod_int_rd}` | **Equipo:** `{tipo_flota_rd}`")

                with r2:
                    frente_rd = st.text_input("FRENTE TRABAJO", value=frente_default)
                    n_ot = st.text_input("ORDEN DE TRABAJO (N° OT)")
                    estado_rd = st.selectbox("ESTADO DE MÁQUINA", ["Operativo", "Inoperativo", "Stand By"])

                with r3:
                    hr_val = st.number_input("Horómetro (HR)", min_value=0.0, step=0.1, value=0.0)
                    km_val = st.number_input("Kilometraje (KM)", min_value=0.0, step=0.1, value=0.0)
                    tec_resp = st.text_input("Técnico / Operador Responsable")

                st.divider()
                st.markdown("##### ⏱️ 2. Horario de Trabajo y Mantenimiento")
                r4, r5, r6 = st.columns(3)
                with r4:
                    h_inicio = st.time_input("Hora Inicio", value=time(6, 0))
                    h_fin = st.time_input("Hora Final", value=time(17, 0))
                    
                    # Cálculo de Horas Hombre
                    dt_start = datetime.combine(fecha_rep, h_inicio)
                    dt_end = datetime.combine(fecha_rep, h_fin)
                    duracion_hrs = round(max(0.0, (dt_end - dt_start).total_seconds() / 3600.0), 2)
                    st.success(f"⏱️ **Duración Obra:** `{duracion_hrs} Horas`")

                with r5:
                    tipo_manto = st.selectbox("TIPO MANTENIMIENTO", [
                        "Operación Normal", "Preventivo (PM)", "Mantenimiento Correctivo Programado (MCP)",
                        "Mantenimiento Correctivo Mayor (MCM)", "Mantenimiento Correctivo Menor (MCMn)",
                        "Lubricación (LUBR)", "Inspección (INSP)", "Abastecimiento (ABS)"
                    ])
                    actividad_rd = st.text_input("ACTIVIDAD ESPECÍFICA")
                    horas_mc = st.number_input("Horas Mantenimiento Correctivo (Horas MC)", min_value=0.0, max_value=24.0, step=0.5, value=0.0)

                with r6:
                    hb_val = st.number_input("Horas Base Turno (HB)", min_value=1.0, max_value=24.0, step=1.0, value=10.0)
                    dm_calc = round(max(0.0, (hb_val - horas_mc) / hb_val), 2) if hb_val > 0 else 1.0
                    st.metric("Disponibilidad Mecánica (DM)", f"{int(dm_calc * 100)}%")

                st.divider()
                st.markdown("##### 🛠️ 3. Trabajos Ejcutados, Backlog e Insumos")
                r7, r8 = st.columns(2)
                with r7:
                    desc_trabajo = st.text_area("DESCRIPCIÓN DE TRABAJOS EJECUTADOS")
                    backlog_rd = st.text_input("BACKLOG / OBSERVACIONES PENDIENTES")
                with r8:
                    detalle_insumo = st.text_input("DETALLE INSUMO / REPUESTO")
                    c_p1, c_p2 = st.columns(2)
                    with c_p1:
                        precio_mo = st.number_input("Costo Mano de Obra (S/.)", min_value=0.0, step=10.0, value=0.0)
                    with c_p2:
                        precio_insumo = st.number_input("Precio Insumo / Repuesto (S/.)", min_value=0.0, step=10.0, value=0.0)

                st.divider()
                guardar_rd_btn = st.form_submit_button("💾 Guardar Parte Diario en Supabase", use_container_width=True)

                if guardar_rd_btn:
                    # timestamps para horas inicio y fin
                    str_h_inicio = f"{fecha_rep}T{h_inicio.strftime('%H:%M:%S')}"
                    str_h_fin = f"{fecha_rep}T{h_fin.strftime('%H:%M:%S')}"

                    nuevo_rd = {
                        "fecha_reporte": str(fecha_rep),
                        "placa": placa_rd,
                        "frente_asignado": frente_rd,
                        "codigo": n_ot if n_ot else cod_int_rd,
                        "estado": estado_rd,
                        "hr": hr_val,
                        "km": km_val,
                        "tecnico_responsable": tec_resp,
                        "descripcion_trabajo": desc_trabajo,
                        "backlog": backlog_rd,
                        "hora_inicio": str_h_inicio,
                        "hora_fin": str_h_fin,
                        "tipo_mantenimiento": tipo_manto,
                        "actividad": actividad_rd,
                        "horas_mc": horas_mc,
                        "precio": precio_mo,
                        "detalle_insumo": detalle_insumo,
                        "precio_insumo": precio_insumo
                    }

                    exito_rd, res_rd = insertar_registro("reporte_diario", nuevo_rd)
                    if exito_rd:
                        st.success(f"✅ Parte Diario registrado correctamente para la Placa `{placa_rd}`.")
                        st.rerun()
                    else:
                        st.error(f"❌ Error al guardar en Supabase: {res_rd}")

    # --- PESTAÑA 2: CONSOLIDADO Y FILTROS POR FECHA Y EQUIPO ---
    with tab_consulta_rd:
        st.subheader("🔍 Consulta Consolidada del Reporte Diario (`RD`)")
        st.caption("Filtre por Ciclo Semanal (Sábado a Viernes), Rango de Fechas Personalizado y/o Placa específica.")

        if df_reportes.empty:
            st.info("No hay partes diarios registrados en la base de datos.")
        else:
            # Enriquecer reporte con datos maestros de la placa
            if not df_equipos.empty:
                df_rd_full = df_reportes.merge(
                    df_equipos[["placa", "codigo_interno", "tipo_flota"]],
                    on="placa", how="left"
                )
            else:
                df_rd_full = df_reportes.copy()
                df_rd_full["codigo_interno"] = ""
                df_rd_full["tipo_flota"] = ""

            # Convertir fecha_reporte a datetime.date
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

            # Aplicar Filtros de Fecha y Equipo
            df_rd_filtrado = df_rd_full.copy()

            if fecha_inicio_filtro and fecha_fin_filtro:
                df_rd_filtrado = df_rd_filtrado[
                    (df_rd_filtrado["fecha_reporte_dt"] >= fecha_inicio_filtro) &
                    (df_rd_filtrado["fecha_reporte_dt"] <= fecha_fin_filtro)
                ]

            if placa_filtro_rd != "TODOS LOS EQUIPOS":
                df_rd_filtrado = df_rd_filtrado[df_rd_filtrado["placa"] == placa_filtro_rd]

            # Calcular columnas calculadas requeridas por la hoja RD
            df_rd_filtrado["hb"] = 10.0
            df_rd_filtrado["horas_mc"] = pd.to_numeric(df_rd_filtrado["horas_mc"], errors="coerce").fillna(0.0)
            df_rd_filtrado["dm"] = ((df_rd_filtrado["hb"] - df_rd_filtrado["horas_mc"]) / df_rd_filtrado["hb"]).round(2)

            st.divider()
            
            # Orden exacto de columnas para el reporte exportable "RD"
            cols_export_rd = [
                "codigo", "fecha_reporte", "codigo_interno", "placa", "tipo_flota",
                "frente_asignado", "estado", "hr", "km", "tecnico_responsable",
                "descripcion_trabajo", "backlog", "hora_inicio", "hora_fin",
                "tipo_mantenimiento", "actividad", "hb", "horas_mc", "dm",
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

else:
    st.info("Módulo en desarrollo para la siguiente fase de revisión.")
