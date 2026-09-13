import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import io

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
        return response.json() if response.status_code in [200, 201] else []
    except Exception:
        return []

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

# Menú Lateral
modulo = st.sidebar.radio(
    "Navegación / Módulos:",
    [
        "1. Lista Maestra (Alta y Baja)",
        "2. Estatus Equipo (En desarrollo)",
        "3. Reporte Diario (En desarrollo)",
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
    st.caption("Administración de datos maestros, altas, retiros y filtros dinámicos.")

    equipos = consultar_tabla("lista_maestra")
    df_equipos = pd.DataFrame(equipos) if equipos else pd.DataFrame()

    tab_activos, tab_agregar, tab_retirar, tab_inactivos = st.tabs([
        "📋 Flota Activa & Filtros", 
        "➕ Agregar Equipo", 
        "❌ Quitar Equipo",
        "📁 Equipos Retirados"
    ])

    # --- PESTAÑA 1: FLOTA ACTIVA Y FILTROS MULTIVARIABLE ---
    with tab_activos:
        if not df_equipos.empty and "estado_operativo" in df_equipos.columns:
            df_activos = df_equipos[df_equipos["estado_operativo"] == "OPERATIVO"].copy()
            
            st.subheader("🔍 Filtros de Búsqueda y Selección")
            
            # Panel de Filtros Interactivos
            f1, f2, f3, f4 = st.columns(4)
            
            with f1:
                frec_opciones = ["TODOS"] + sorted(list(df_activos["tipo_flota"].dropna().unique())) if "tipo_flota" in df_activos.columns else ["TODOS"]
                filtro_tipo = st.selectbox("Filtrar por Tipo de Flota:", frec_opciones)
                
            with f2:
                frentes_opciones = ["TODOS"] + sorted(list(df_activos["frente_asignado"].dropna().unique())) if "frente_asignado" in df_activos.columns else ["TODOS"]
                filtro_frente = st.selectbox("Filtrar por Frente Asignado:", frentes_opciones)
                
            with f3:
                prop_opciones = ["TODOS"] + sorted(list(df_activos["propietario"].dropna().unique())) if "propietario" in df_activos.columns else ["TODOS"]
                filtro_propietario = st.selectbox("Filtrar por Propietario:", prop_opciones)

            with f4:
                comu_opciones = ["TODOS"] + sorted(list(df_activos["comunidad"].dropna().unique())) if "comunidad" in df_activos.columns else ["TODOS"]
                filtro_comunidad = st.selectbox("Filtrar por Comunidad:", comu_opciones)

            # Aplicar Filtros en Cascada
            df_filtrado = df_activos.copy()
            if filtro_tipo != "TODOS":
                df_filtrado = df_filtrado[df_filtrado["tipo_flota"] == filtro_tipo]
            if filtro_frente != "TODOS":
                df_filtrado = df_filtrado[df_filtrado["frente_asignado"] == filtro_frente]
            if filtro_propietario != "TODOS":
                df_filtrado = df_filtrado[df_filtrado["propietario"] == filtro_propietario]
            if filtro_comunidad != "TODOS":
                df_filtrado = df_filtrado[df_filtrado["comunidad"] == filtro_comunidad]

            st.divider()
            
            # Métrica de Resumen Filtrado
            col_m1, col_m2 = st.columns([1, 3])
            with col_m1:
                st.metric("Total Equipos Filtrados", f"{len(df_filtrado)} de {len(df_activos)}")
            
            # Columnas exactas solicitadas
            cols_mostrar = [
                "codigo_interno", "placa", "tipo_flota", "frecuencia_mantenimiento", "anio",
                "marca", "modelo", "capacidad", "razon_social", "ruc", "contacto",
                "propietario", "comunidad", "potencia_kw", "potencia_hp", "potencia_cv",
                "fecha_ingreso_proyecto", "frente_asignado"
            ]
            cols_existentes = [c for c in cols_mostrar if c in df_filtrado.columns]
            
            st.dataframe(df_filtrado[cols_existentes], use_container_width=True)
            
            # Botón de Descargar Excel del resultado filtrado
            st.download_button(
                label="📥 Descargar Resultado Filtrado en Excel (.xlsx)",
                data=generar_excel_bytes(df_filtrado[cols_existentes], "Lista_Maestra_Filtrada"),
                file_name=f"Lista_Maestra_Filtrada_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        else:
            st.info("No hay equipos activos registrados en la base de datos.")

    # --- PESTAÑA 2: AGREGAR EQUIPO ---
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

    # --- PESTAÑA 3: QUITAR EQUIPO ---
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

    # --- PESTAÑA 4: EQUIPOS RETIRADOS ---
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

else:
    st.info("Módulo en desarrollo para el siguiente paso de revisión.")
