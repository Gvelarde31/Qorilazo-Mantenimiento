import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import io
import re

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
        if response.status_code in [200, 201]:
            try:
                res_json = response.json()
                return True, res_json
            except Exception:
                return True, []
        else:
            return False, response.text
    except Exception as e:
        return False, str(e)

# Conversor de URLs de Google Drive a URLs Directas de Imagen
def convertir_url_drive_a_directa(url):
    if not url or pd.isna(url) or not isinstance(url, str):
        return None
    url = url.strip()
    
    # Si es un enlace de carpeta, retornar original para botón de apertura externa
    if "/drive/folders/" in url:
        return url
        
    # Extraer ID del archivo individual de Google Drive
    patron_id = r'(?:/file/d/|id=)([\w-]+)'
    coincidencia = re.search(patron_id, url)
    
    if coincidencia:
        file_id = coincidencia.group(1)
        return f"https://lh3.googleusercontent.com/d/{file_id}"
    return url

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

# Función auxiliar para calcular rango semanal (Sábado a Viernes)
def obtener_rango_semana_sabado_viernes(fecha_ref):
    dias_desde_sabado = (fecha_ref.weekday() - 5) % 7
    inicio_sabado = fecha_ref - timedelta(days=dias_desde_sabado)
    fin_viernes = inicio_sabado + timedelta(days=6)
    return inicio_sabado, fin_viernes

# Menú Lateral de Navegación
modulo = st.sidebar.radio(
    "Navegación / Módulos:",
    [
        "1. Lista Maestra & Acreditación",
        "2. Registro Diario de Partes y Tareo",
        "3. Programación Semanal PM",
        "4. Historial de Mantenimientos",
        "5. Registro de Detalles y Consumo de Repuestos",
        "6. Catálogo de Repuestos",
        "7. KPIs y Ratio de Combustible",
        "8. Disponibilidad Mecánica",
        "9. Reporte Exportable & Evidencias A4"
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
            "fecha_venc_soat", "fecha_venc_poliza", "fecha_retorqueo_ruedas",
            "fecha_venc_citv", "fecha_venc_gps", "fecha_venc_tarjeta_mercancias",
            "fecha_venc_cert_operatividad", "fecha_venc_cert_inspección"
        ]
        nombres_amigables = {
            "fecha_venc_soat": "SOAT", "fecha_venc_poliza": "Póliza",
            "fecha_retorqueo_ruedas": "Retorqueo Ruedas", "fecha_venc_citv": "Revisión Técnica (CITV)",
            "fecha_venc_gps": "GPS", "fecha_venc_tarjeta_mercancias": "Tarjeta Mercancías",
            "fecha_venc_cert_operatividad": "Certif. Operatividad", "fecha_venc_cert_inspección": "Certif. Inspección"
        }

        resumen_alertas = []
        for col in cols_monitoreadas:
            if col in df.columns:
                resultados = df[col].apply(evaluar_fecha)
                df[f"estado_{col}"] = [r[0] for r in resultados]
                colores = [r[1] for r in resultados]
                resumen_alertas.append({
                    "Clave": col,
                    "Documento / Permiso": nombres_amigables.get(col, col),
                    "🔴 Crítico (≤15d)": colores.count("ROJO"),
                    "🟡 Alerta (16-31d)": colores.count("AMARILLO"),
                    "🟢 Vigente (≥32d)": colores.count("VERDE")
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
                st.metric(label=f"📌 {row['Documento / Permiso']}", value=alerta_texto)

        st.divider()
        st.subheader("🔍 Filtro de Flota por Permiso")
        doc_seleccionado = st.selectbox(
            "Selecciona un Permiso para inspeccionar:",
            options=["TODOS"] + [nombres_amigables.get(c, c) for c in cols_monitoreadas if c in df.columns]
        )
        columnas_base = [col for col in ["placa", "codigo_interno", "marca", "modelo", "comentario", "fotocheck"] if col in df.columns]
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
        lista_codigos = sorted(list(set(df_equipos["codigo_interno"].dropna().astype(str)))) if "codigo_interno" in df_equipos.columns else []
        
        st.subheader("📋 Formulario de Ingreso de Parte Diario")
        
        with st.form("form_parte_diario", clear_on_submit=True):
            st.markdown("##### 📍 Identificación del Equipo y Datos Operativos")
            col_1, col_2, col_3 = st.columns(3)
            
            with col_1:
                codigo_sel = st.selectbox("Código Interno del Equipo *", lista_codigos)
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
                st.info(f"**Horas Trabajadas (Cálculo Visual):** `{horas_trab:.1f} hrs`")

            with col_h2:
                st.caption(" 🛣️ Odómetro (Kilómetros)")
                km_init = st.number_input("Kilómetro Inicial", min_value=0.0, step=1.0)
                km_fin = st.number_input("Kilómetro Final", min_value=0.0, step=1.0)
                km_rec = max(0.0, km_fin - km_init)
                st.info(f"**Kilómetros Recorridos (Cálculo Visual):** `{km_rec:.1f} km`")

            if horas_trab > 0 and combustible > 0:
                ratio_turno = combustible / horas_trab
                st.caption(f"⛽ Ratio Estimado del Turno: **{ratio_turno:.2f} Gal/hrs**")

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
                        "kilometro_inicial": km_init,
                        "kilometro_final": km_fin,
                        "frente_asignado": frente_asignado,
                        "actividad": actividad,
                        "combustible_galones": combustible,
                        "observaciones": observaciones
                    }
                    
                    exito, msg = insertar_registro("partes_diarios", nuevo_parte)
                    if exito:
                        st.success(f"✅ Parte diario registrado con éxito para el equipo `{codigo_sel}`.")
                        st.rerun()
                    else:
                        st.error(f"❌ Error al guardar en Supabase: {msg}")

        st.divider()
        st.subheader("📊 Historial de Partes Diarios Registrados")
        partes_registrados = consultar_tabla("partes_diarios")
        if partes_registrados:
            df_partes_show = pd.DataFrame(partes_registrados)
            
            if "combustible_galones" in df_partes_show.columns and "horometro_final" in df_partes_show.columns and "horometro_inicial" in df_partes_show.columns:
                combust = pd.to_numeric(df_partes_show["combustible_galones"], errors="coerce").fillna(0.0)
                h_fin = pd.to_numeric(df_partes_show["horometro_final"], errors="coerce").fillna(0.0)
                h_ini = pd.to_numeric(df_partes_show["horometro_inicial"], errors="coerce").fillna(0.0)
                hrs = (h_fin - h_ini).clip(lower=0.0)
                
                ratio_series = combust.divide(hrs.replace(0, pd.NA)).fillna(0.0)
                df_partes_show["Ratio (Gal/hr)"] = ratio_series.astype(float).round(2)
                
            st.dataframe(df_partes_show, use_container_width=True)
        else:
            st.info("Aún no se han registrado partes diarios en la base de datos.")

# ==========================================
# MÓDULO 3: PROGRAMACIÓN SEMANAL PM
# ==========================================
elif modulo == "3. Programación Semanal PM":
    st.header("📅 Programación Semanal de Mantenimiento Preventivo (PM)")
    
    hoy = datetime.now().date()
    inicio_semana, fin_semana = obtener_rango_semana_sabado_viernes(hoy)
    
    st.info(f"📆 **Semana Operativa Actual:** Desde **Sábado {inicio_semana.strftime('%d/%m/%Y')}** hasta **Viernes {fin_semana.strftime('%d/%m/%Y')}**")

    equipos = consultar_tabla("equipos")
    partes = consultar_tabla("partes_diarios")
    mantenimientos = consultar_tabla("mantenimientos")

    if not equipos:
        st.warning("⚠️ No se encontraron equipos registrados en la tabla 'equipos'.")
    else:
        df_eq = pd.DataFrame(equipos)
        df_partes = pd.DataFrame(partes) if partes else pd.DataFrame()
        df_maint = pd.DataFrame(mantenimientos) if mantenimientos else pd.DataFrame()

        programacion_semanal = []

        for _, eq in df_eq.iterrows():
            cod = eq.get("codigo_interno") or eq.get("codigo_equipo")
            freq = float(eq.get("frecuencia_mantenimientos") or 250)
            
            um_raw = str(eq.get("unidad_medida", "")).strip().lower()
            es_km = "km" in um_raw or "kilomet" in um_raw
            tipo_unidad = "km" if es_km else "hrs"
            
            lectura_actual = 0.0
            if not df_partes.empty and "codigo_equipo" in df_partes.columns:
                partes_eq = df_partes[df_partes["codigo_equipo"] == cod]
                if not partes_eq.empty:
                    col_lectura = "kilometro_final" if es_km else "horometro_final"
                    if col_lectura in partes_eq.columns:
                        lectura_actual = float(partes_eq[col_lectura].max() or 0.0)

            ultimo_pm_lectura = 0.0
            if not df_maint.empty and "codigo_equipo" in df_maint.columns:
                maint_eq = df_maint[df_maint["codigo_equipo"] == cod]
                if not maint_eq.empty:
                    col_maint = "kilometraje_ejecucion" if es_km else "horometro_ejecucion"
                    if col_maint in maint_eq.columns:
                        ultimo_pm_lectura = float(maint_eq[col_maint].max() or 0.0)

            prox_pm_lectura = ultimo_pm_lectura + freq
            recorrido_restante = prox_pm_lectura - lectura_actual

            if recorrido_restante <= 0:
                estado_prog = "🔴 MANTENIMIENTO VENCIDO / URGENTE"
                prioridad = "ALTA"
            elif recorrido_restante <= (500 if es_km else 50):
                estado_prog = "🟡 CORRESPONDE ESTA SEMANA"
                prioridad = "MEDIA"
            else:
                estado_prog = "🟢 VIGENTE"
                prioridad = "BAJA"

            programacion_semanal.append({
                "Código Equipo": cod,
                "Medición": tipo_unidad.upper(),
                "Frecuencia": f"{freq:.0f} {tipo_unidad}",
                "Último PM Exec.": f"{ultimo_pm_lectura:.1f} {tipo_unidad}",
                "Lectura Actual": f"{lectura_actual:.1f} {tipo_unidad}",
                "Próximo PM": f"{prox_pm_lectura:.1f} {tipo_unidad}",
                "Restante para PM": f"{recorrido_restante:.1f} {tipo_unidad}",
                "Estado esta Semana": estado_prog,
                "Prioridad": prioridad
            })

        df_prog = pd.DataFrame(programacion_semanal)

        st.subheader("📋 Equipos Programados para Mantenimiento esta Semana")
        equipos_semana = df_prog[df_prog["Estado esta Semana"].str.contains("CORRESPONDE|VENCIDO")]

        if not equipos_semana.empty:
            st.dataframe(equipos_semana, use_container_width=True)
        else:
            st.success("✅ ¡Ningún equipo requiere mantenimiento programado para esta semana!")

        st.divider()
        st.subheader("🔍 Proyección Completa de la Flota (Horómetros vs. Kilometrajes)")
        st.dataframe(df_prog, use_container_width=True)

# ==========================================
# MÓDULO 4: HISTORIAL DE MANTENIMIENTOS
# ==========================================
elif modulo == "4. Historial de Mantenimientos":
    st.header("🔧 Registro de Mantenimientos Ejecutados")
    
    equipos = consultar_tabla("equipos")
    
    if not equipos:
        st.warning("⚠️ No se encontraron equipos en la tabla 'equipos'. Debe registrar primero la flota.")
    else:
        df_equipos = pd.DataFrame(equipos)
        lista_codigos = sorted(list(set(df_equipos["codigo_interno"].dropna().astype(str)))) if "codigo_interno" in df_equipos.columns else []

        st.subheader("📝 Registrar Servicio Mecánico (`mantenimientos`)")
        
        with st.form("form_mantenimientos", clear_on_submit=True):
            col_m1, col_m2, col_m3 = st.columns(3)
            
            with col_m1:
                codigo_sel = st.selectbox("Código del Equipo *", lista_codigos)
                tipo_maint = st.selectbox("Tipo de Mantenimiento *", ["Preventivo", "Correctivo", "Retorqueo", "Inspección Técnica"])
                nivel_pm = st.selectbox("Nivel PM *", [
                    "PM1 (250h)", 
                    "PM2 (500h)", 
                    "PM3 (1000h)", 
                    "PM4 (2000h)", 
                    "Correctivo / Reparación", 
                    "Otro"
                ])
            with col_m2:
                fecha_ejec = st.date_input("Fecha de Ejecución *", datetime.now().date())
                horo_ejec = st.number_input("Horómetro de Ejecución", min_value=0.0, step=0.1)
                km_ejec = st.number_input("Kilometraje de Ejecución", min_value=0.0, step=1.0)
            with col_m3:
                proveedor = st.text_input("Proveedor / Taller", value="Taller Principal")
                prox_horo = st.number_input("Próximo Horómetro Proyectado", min_value=0.0, step=10.0)
                prox_km = st.number_input("Próximo Kilometraje Proyectado", min_value=0.0, step=100.0)

            descripcion = st.text_area("Descripción de Trabajos Realizados")
            foto_url = st.text_input("URL / Enlace de Evidencia Fotográfica (Opcional)")

            guardar_maint = st.form_submit_button("💾 Guardar Mantenimiento en Supabase", use_container_width=True)
            
            if guardar_maint:
                nuevo_mantenimiento = {
                    "codigo_equipo": codigo_sel,
                    "tipo_mantenimiento": tipo_maint,
                    "fecha_ejecucion": str(fecha_ejec),
                    "horometro_ejecucion": horo_ejec,
                    "kilometraje_ejecucion": km_ejec,
                    "nivel_pm": nivel_pm,
                    "proximo_horometro": prox_horo,
                    "proximo_kilometraje": prox_km,
                    "proveedor_taller": proveedor,
                    "descripcion": descripcion,
                    "foto_evidencia_url": foto_url
                }
                
                exito, res_data = insertar_registro("mantenimientos", nuevo_mantenimiento)
                if exito:
                    maint_id = None
                    if isinstance(res_data, list) and len(res_data) > 0:
                        maint_id = res_data[0].get("id")
                    
                    st.success(f"✅ Mantenimiento registrado con éxito para `{codigo_sel}` (ID Generado: `{maint_id}`).")
                    st.rerun()
                else:
                    st.error(f"❌ Error al guardar en Supabase: {res_data}")

        st.divider()
        st.subheader("📊 Historial de Mantenimientos Registrados")
        historial_maint = consultar_tabla("mantenimientos")
        if historial_maint:
            st.dataframe(pd.DataFrame(historial_maint), use_container_width=True)
        else:
            st.info("Aún no hay intervenciones registradas en 'mantenimientos'.")

# ==========================================
# MÓDULO 5: REGISTRO DE DETALLES Y CONSUMO DE REPUESTOS
# ==========================================
elif modulo == "5. Registro de Detalles y Consumo de Repuestos":
    st.header("🛠️ Registro de Detalles y Consumo de Repuestos (`mantenimiento_detalles`)")
    
    mantenimientos = consultar_tabla("mantenimientos")
    repuestos_cat = consultar_tabla("repuestos_cat")
    
    if not mantenimientos:
        st.warning("⚠️ No se encontraron mantenimientos en la tabla 'mantenimientos'. Registre primero un servicio en el Módulo 4.")
    else:
        df_maint = pd.DataFrame(mantenimientos)
        df_rep = pd.DataFrame(repuestos_cat) if repuestos_cat else pd.DataFrame()

        opciones_maint = [
            f"ID: {r.get('id')} | Equipo: {r.get('codigo_equipo')} | Fecha: {r.get('fecha_ejecucion')} | {r.get('tipo_mantenimiento')}"
            for _, r in df_maint.iterrows()
        ]
        
        opciones_rep = ["Sin repuesto / Solo Mano de Obra"]
        dict_rep = {}
        if not df_rep.empty:
            for _, r in df_rep.iterrows():
                label = f"ID: {r.get('id')} | Code: {r.get('codigo_repuesto')} - {r.get('descripcion')}"
                opciones_rep.append(label)
                dict_rep[label] = r

        st.subheader("📝 Asignar Repuesto y Costo al Mantenimiento")
        
        with st.form("form_mantenimiento_detalles_dedicado", clear_on_submit=True):
            col_d1, col_d2 = st.columns(2)
            
            with col_d1:
                maint_sel = st.selectbox("Seleccionar Mantenimiento Ejecutado *", opciones_maint)
                rep_sel = st.selectbox("Seleccionar Repuesto Utilizado", opciones_rep)
                
            with col_d2:
                cant_usada = st.number_input("Cantidad Utilizada *", min_value=1, step=1, value=1)
                costo_mo = st.number_input("Costo de Mano de Obra / P.U. (PEN / USD)", min_value=0.0, step=1.0, value=0.0)
                
            subtotal_calc = cant_usada * costo_mo
            st.info(f"**Costo Subtotal Visual (Cantidad × P.U.):** `{subtotal_calc:.2f}` (Se autocalcula en Supabase)")
            
            guardar_detalle = st.form_submit_button("💾 Guardar Detalle en Supabase", use_container_width=True)
            
            if guardar_detalle:
                maint_id = int(maint_sel.split(" | ")[0].replace("ID: ", "").strip())
                
                nuevo_detalle = {
                    "mantenimiento_id": maint_id,
                    "cantidad": cant_usada,
                    "precio_unitario": costo_mo
                }
                
                if rep_sel != "Sin repuesto / Solo Mano de Obra" and rep_sel in dict_rep:
                    nuevo_detalle["repuesto_id"] = dict_rep[rep_sel].get("id")

                exito, res_det = insertar_registro("mantenimiento_detalles", nuevo_detalle)
                if exito:
                    st.success(f"✅ Detalle guardado correctamente en `mantenimiento_detalles` para el Mantenimiento ID `{maint_id}`.")
                    st.rerun()
                else:
                    st.error(f"❌ Error al guardar en Supabase: {res_det}")

        st.divider()
        st.subheader("📊 Historial de Detalles y Consumo de Repuestos")
        detalles_registrados = consultar_tabla("mantenimiento_detalles")
        if detalles_registrados:
            st.dataframe(pd.DataFrame(detalles_registrados), use_container_width=True)
        else:
            st.info("Aún no se han registrado detalles en 'mantenimiento_detalles'.")

# ==========================================
# MÓDULO 6: CATÁLOGO DE REPUESTOS
# ==========================================
elif modulo == "6. Catálogo de Repuestos":
    st.header("📦 Catálogo Maestro de Repuestos e Insumos (`repuestos_cat`)")
    repuestos = consultar_tabla("repuestos_cat")
    
    if repuestos:
        df_rep = pd.DataFrame(repuestos)
        k1, k2, k3 = st.columns(3)
        k1.metric("Total Repuestos en Catálogo", len(df_rep))
        k2.metric("Categorías Registradas", df_rep["categoria"].nunique() if "categoria" in df_rep.columns else 0)
        k3.metric("Ubicación Principal", "Almacén Central Mina")
        st.divider()

    st.subheader("➕ Registrar Nuevo Repuesto en Catálogo")
    with st.form("form_repuestos_cat", clear_on_submit=True):
        col_r1, col_r2, col_r3 = st.columns(3)
        with col_r1:
            cod_repuesto = st.text_input("Código de Repuesto / SKU (Opcional)")
            descripcion_rep = st.text_input("Descripción del Repuesto / Parte *")
        with col_r2:
            categoria_sel = st.selectbox("Categoría de Lista", [
                "Neumáticos", 
                "Filtros", 
                "Lubricantes", 
                "Eléctrico", 
                "Motor", 
                "Frenos", 
                "General",
                "Otro / Manual"
            ])
            if categoria_sel == "Otro / Manual":
                categoria = st.text_input("Especificar Categoría Manual *")
            else:
                categoria = categoria_sel
                
            unidad = st.selectbox("Unidad de Medida *", ["Unidad", "Galón", "Juego", "Litro", "Metro", "Caja"])
        with col_r3:
            precio_ref = st.number_input("Precio Referencial (USD / PEN)", min_value=0.0, step=1.0)

        guardar_rep = st.form_submit_button("💾 Guardar Repuesto en Catálogo", use_container_width=True)
        
        if guardar_rep:
            if not descripcion_rep.strip():
                st.error("❌ La descripción del repuesto es obligatoria.")
            else:
                nuevo_repuesto = {
                    "codigo_repuesto": cod_repuesto.strip() if cod_repuesto else None,
                    "descripcion": descripcion_rep.strip(),
                    "categoria": categoria.strip() if isinstance(categoria, str) else categoria,
                    "unidad_medida": unidad,
                    "precio_referencial": precio_ref
                }
                exito, msg = insertar_registro("repuestos_cat", nuevo_repuesto)
                if exito:
                    st.success("✅ Repuesto guardado con éxito en `repuestos_cat`.")
                    st.rerun()
                else:
                    st.error(f"❌ Error al guardar en Supabase: {msg}")

    st.divider()
    st.subheader("📋 Catálogo Maestro de Repuestos")
    if repuestos:
        st.dataframe(pd.DataFrame(repuestos), use_container_width=True)
    else:
        st.info("Aún no hay registros en la tabla 'repuestos_cat'.")

# ==========================================
# MÓDULO 7: KPIS Y RATIO DE COMBUSTIBLE
# ==========================================
elif modulo == "7. KPIs y Ratio de Combustible":
    st.header("⛽ Reporte y Análisis de Ratios de Combustible")
    st.caption("Consolidado acumulado de combustible abastecido versus horas / kilómetros trabajados por tipo de flota.")

    equipos = consultar_tabla("equipos")
    partes = consultar_tabla("partes_diarios")

    if not partes or not equipos:
        st.info("Aún no hay suficientes registros en 'partes_diarios' o 'equipos' para calcular los ratios de combustible.")
    else:
        df_p = pd.DataFrame(partes)
        df_eq = pd.DataFrame(equipos)

        col_tipo_flota = "tipo_flota" if "tipo_flota" in df_eq.columns else [c for c in df_eq.columns if "tipo" in c or "flota" in c][0]

        df_p["combustible_galones"] = pd.to_numeric(df_p["combustible_galones"], errors="coerce").fillna(0.0)
        df_p["horometro_final"] = pd.to_numeric(df_p["horometro_final"], errors="coerce").fillna(0.0)
        df_p["horometro_inicial"] = pd.to_numeric(df_p["horometro_inicial"], errors="coerce").fillna(0.0)
        df_p["kilometro_final"] = pd.to_numeric(df_p["kilometro_final"], errors="coerce").fillna(0.0)
        df_p["kilometro_inicial"] = pd.to_numeric(df_p["kilometro_inicial"], errors="coerce").fillna(0.0)

        df_p["horas_trabajadas"] = (df_p["horometro_final"] - df_p["horometro_inicial"]).clip(lower=0.0)
        df_p["km_recorridos"] = (df_p["kilometro_final"] - df_p["kilometro_inicial"]).clip(lower=0.0)

        df_merged = df_p.merge(
            df_eq[["codigo_interno", col_tipo_flota, "unidad_medida"]],
            left_on="codigo_equipo",
            right_on="codigo_interno",
            how="left"
        )

        resumen_combustible = []

        for cod_eq, grp in df_merged.groupby("codigo_equipo"):
            total_gal = float(grp["combustible_galones"].sum())
            total_hrs = float(grp["horas_trabajadas"].sum())
            total_km = float(grp["km_recorridos"].sum())

            tipo_flota_val = grp[col_tipo_flota].iloc[0] if col_tipo_flota in grp.columns else "Sin Tipo"
            um = grp["unidad_medida"].iloc[0] if "unidad_medida" in grp.columns else "Horas"

            ratio_hrs = (total_gal / total_hrs) if total_hrs > 0 else 0.0
            ratio_km = (total_gal / total_km) if total_km > 0 else 0.0

            resumen_combustible.append({
                "Código Equipo": cod_eq,
                "Tipo de Flota": tipo_flota_val or "General",
                "Medición": um or "Horas",
                "Total Galones Abastecidos": round(total_gal, 1),
                "Total Horas Operadas": round(total_hrs, 1),
                "Total KM Recorridos": round(total_km, 1),
                "Ratio (Gal / Horas)": round(ratio_hrs, 2),
                "Ratio (Gal / KM)": round(ratio_km, 2)
            })

        df_resumen_c = pd.DataFrame(resumen_combustible)

        st.subheader("🔍 Filtro por Tipo de Flota")
        tipos_disponibles = ["TODOS"] + sorted(list(df_resumen_c["Tipo de Flota"].dropna().unique()))
        tipo_flota_sel = st.selectbox("Selecciona la categoría de flota a analizar:", tipos_disponibles)

        if tipo_flota_sel != "TODOS":
            df_filtrado = df_resumen_c[df_resumen_c["Tipo de Flota"] == tipo_flota_sel]
        else:
            df_filtrado = df_resumen_c

        st.subheader(f"📊 Métricas Acumuladas: Flota {tipo_flota_sel}")
        k1, k2, k3 = st.columns(3)
        total_gal_sel = float(df_filtrado['Total Galones Abastecidos'].sum())
        total_hrs_sel = float(df_filtrado['Total Horas Operadas'].sum())

        ratio_promedio_hrs = (total_gal_sel / total_hrs_sel) if total_hrs_sel > 0 else 0.0

        k1.metric("Total Galones Consumidos", f"{total_gal_sel:,.1f} Gal")
        k2.metric("Total Horas Operadas", f"{total_hrs_sel:,.1f} hrs")
        k3.metric("Ratio Promedio Categoría", f"{ratio_promedio_hrs:,.2f} Gal/hr")

        st.divider()
        st.subheader("📋 Consolidado por Equipo")
        st.dataframe(df_filtrado, use_container_width=True)

        st.divider()
        st.subheader(f"📈 Comparativa de Consumo (Galones) - {tipo_flota_sel}")
        if not df_filtrado.empty:
            st.bar_chart(data=df_filtrado.set_index("Código Equipo")["Total Galones Abastecidos"])
        else:
            st.info("No hay datos para la categoría seleccionada.")

# ==========================================
# MÓDULO 8: DISPONIBILIDAD MECÁNICA POR EQUIPO Y FRENTE
# ==========================================
elif modulo == "8. Disponibilidad Mecánica":
    st.header("📈 Disponibilidad Mecánica de la Flota (%)")
    st.caption("Cálculo del porcentaje de operación vs. requerimiento mínimo del contrato (Meta: 90.0%).")

    hoy = datetime.now().date()
    inicio_semana, fin_semana = obtener_rango_semana_sabado_viernes(hoy)

    st.info(f"📆 **Semana Evaluada:** Desde **Sábado {inicio_semana.strftime('%d/%m/%Y')}** hasta **Viernes {fin_semana.strftime('%d/%m/%Y')}** (7 días base) | **🎯 Meta Contractual: 90.0%**")

    equipos = consultar_tabla("equipos")
    partes = consultar_tabla("partes_diarios")

    if not equipos:
        st.warning("⚠️ No se encontraron equipos en la tabla 'equipos'.")
    else:
        df_eq = pd.DataFrame(equipos)
        df_partes = pd.DataFrame(partes) if partes else pd.DataFrame()

        col_codigo = "codigo_interno" if "codigo_interno" in df_eq.columns else "codigo_equipo"
        col_frente_eq = "frente_trabajo" if "frente_trabajo" in df_eq.columns else [c for c in df_eq.columns if "frente" in c or "ubicacion" in c or "frente_asignado" in c]
        col_frente_eq_name = col_frente_eq[0] if isinstance(col_frente_eq, list) and col_frente_eq else "frente_trabajo"

        disp_lista = []

        for _, eq in df_eq.iterrows():
            cod = eq.get(col_codigo)
            frente = eq.get(col_frente_eq_name) or "Sin Frente Asignado"

            dias_operativos = 0
            if not df_partes.empty and "codigo_equipo" in df_partes.columns and "fecha" in df_partes.columns:
                partes_eq = df_partes[
                    (df_partes["codigo_equipo"] == cod) &
                    (df_partes["fecha"] >= str(inicio_semana)) &
                    (df_partes["fecha"] <= str(fin_semana))
                ]
                
                if not partes_eq.empty:
                    dias_operativos = partes_eq["fecha"].nunique()

            dias_op = min(dias_operativos, 7)
            dias_inop = 7 - dias_op
            porcentaje_disp = round((dias_op / 7.0) * 100, 1)

            if porcentaje_disp >= 90.0:
                estado_disp = "🟢 DENTRO DE CONTRATO (≥90%)"
            else:
                estado_disp = "🔴 INCUMPLIMIENTO CRÍTICO (<90%)"

            disp_lista.append({
                "Código Equipo": cod,
                "Frente de Trabajo": frente,
                "Días Operativos": dias_op,
                "Días Inoperativos": dias_inop,
                "Disponibilidad (%)": porcentaje_disp,
                "Estado Contrato": estado_disp
            })

        df_disp = pd.DataFrame(disp_lista)

        st.subheader("🔍 Filtro por Frente de Trabajo")
        frentes_unicos = ["TODOS LOS FRENTES"] + sorted(list(df_disp["Frente de Trabajo"].dropna().unique()))
        frente_sel = st.selectbox("Selecciona el frente de trabajo para inspeccionar:", frentes_unicos)

        if frente_sel != "TODOS LOS FRENTES":
            df_disp_fil = df_disp[df_disp["Frente de Trabajo"] == frente_sel]
        else:
            df_disp_fil = df_disp

        st.subheader(f"📊 Resumen SLA y Cumplimiento Contractual ({frente_sel})")
        m1, m2, k_prom = st.columns(3)
        prom_disp = df_disp_fil["Disponibilidad (%)"].mean() if not df_disp_fil.empty else 0.0
        cumplen_contrato = len(df_disp_fil[df_disp_fil["Disponibilidad (%)"] >= 90.0])

        m1.metric("Equipos Evaluados", len(df_disp_fil))
        m2.metric("Cumplen Contrato (≥90%)", f"{cumplen_contrato} equipos", delta=f"{((cumplen_contrato/max(1, len(df_disp_fil)))*100):.1f}% cumplimiento")
        k_prom.metric("Disponibilidad Promedio", f"{prom_disp:.1f}%", delta=f"{prom_disp - 90.0:.1f}% vs Meta (90%)")

        st.divider()
        st.subheader("📋 Matriz Semanal de Disponibilidad Mecánica por Equipo")
        st.dataframe(df_disp_fil, use_container_width=True)

        st.divider()
        st.subheader(f"📈 Gráfico de Disponibilidad Mecánica (%) por Equipo - {frente_sel}")
        if not df_disp_fil.empty:
            st.bar_chart(data=df_disp_fil.set_index("Código Equipo")["Disponibilidad (%)"])

# ==========================================
# MÓDULO 9: REPORTE EXPORTABLE DE MANTENIMIENTOS & EVIDENCIAS A4
# ==========================================
elif modulo == "9. Reporte Exportable & Evidencias A4":
    st.header("📄 Reporte Exportable de Mantenimientos & Dossier de Evidencias A4")
    st.caption("Consolidado con asignación manual de OT y estado, listo para exportación a Excel y vista previa A4.")

    mantenimientos = consultar_tabla("mantenimientos")
    equipos = consultar_tabla("equipos")

    if not mantenimientos:
        st.info("No hay intervenciones en 'mantenimientos' para generar el reporte.")
    else:
        df_maint = pd.DataFrame(mantenimientos)
        df_eq = pd.DataFrame(equipos) if equipos else pd.DataFrame()

        if not df_eq.empty and "codigo_interno" in df_eq.columns and "placa" in df_eq.columns:
            df_reporte = df_maint.merge(
                df_eq[["codigo_interno", "placa"]],
                left_on="codigo_equipo",
                right_on="codigo_interno",
                how="left"
            )
        else:
            df_reporte = df_maint.copy()
            df_reporte["placa"] = "S/P"

        df_reporte["placa"] = df_reporte["placa"].fillna("S/P")
        df_reporte["codigo_interno"] = df_reporte["codigo_equipo"]
        df_reporte["OT"] = df_reporte.get("OT", "OT-PENDIENTE")
        df_reporte["nivel_pm"] = df_reporte.get("nivel_pm", "PM General")
        df_reporte["creado_el"] = df_reporte.get("created_at", df_reporte.get("fecha_ejecucion", ""))
        df_reporte["estado"] = df_reporte.get("estado", "COMPLETADO")

        st.subheader("✏️ Edición Manual de OT y Estado antes de Exportar")
        cols_editor = ["id", "placa", "codigo_interno", "OT", "nivel_pm", "creado_el", "estado", "foto_evidencia_url"]
        cols_existentes = [c for c in cols_editor if c in df_reporte.columns]

        df_editado = st.data_editor(
            df_reporte[cols_existentes],
            column_config={
                "OT": st.column_config.TextColumn("OT (Orden de Trabajo) *", help="Escriba manualmente la OT"),
                "estado": st.column_config.SelectboxColumn("Estado *", options=["PROGRAMADO", "EN PROCESO", "COMPLETADO", "CANCELADO"]),
                "foto_evidencia_url": st.column_config.LinkColumn("Evidencia Fotográfica")
            },
            disabled=["id", "placa", "codigo_interno", "nivel_pm", "creado_el"],
            use_container_width=True,
            num_rows="fixed"
        )

        st.divider()

        # Generación de Excel Nativo (.xlsx) con captura segura de fallos
        buffer_excel = io.BytesIO()
        usar_excel_nativo = False

        try:
            with pd.ExcelWriter(buffer_excel, engine="openpyxl") as writer:
                cols_h1 = [c for c in ["placa", "codigo_interno", "OT", "nivel_pm", "creado_el", "estado"] if c in df_editado.columns]
                df_editado[cols_h1].to_excel(writer, sheet_name="Mantenimientos_OT", index=False)

                cols_h2 = [c for c in ["OT", "codigo_interno", "nivel_pm", "foto_evidencia_url"] if c in df_editado.columns]
                df_editado[cols_h2].to_excel(writer, sheet_name="Evidencias_Fotograficas", index=False)
            usar_excel_nativo = True
        except Exception:
            usar_excel_nativo = False

        if usar_excel_nativo:
            st.download_button(
                label="📊 Descargar Reporte en Excel Nativo (.xlsx)",
                data=buffer_excel.getvalue(),
                file_name=f"Reporte_Mantenimientos_Qorilazo_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        else:
            cols_csv = [c for c in ["placa", "codigo_interno", "OT", "nivel_pm", "creado_el", "estado", "foto_evidencia_url"] if c in df_editado.columns]
            csv_data = df_editado[cols_csv].to_csv(index=False, sep=";").encode('utf-8-sig')

            st.download_button(
                label="📥 Descargar Reporte Formateado (CSV con separador ;)",
                data=csv_data,
                file_name=f"Reporte_Mantenimientos_Qorilazo_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )

        st.divider()
        st.subheader("🖼️ Vista Previa Formato A4 - Dossier de Evidencias (2 Fotos por Línea)")
        st.caption("Formato optimizado para visualización y generación de reportes fotográficos.")

        df_fotos = df_editado[df_editado["foto_evidencia_url"].notna() & (df_editado["foto_evidencia_url"].astype(str).str.strip() != "")].copy()

        if df_fotos.empty:
            st.info("No se han adjuntado URLs de fotografía en las intervenciones registradas.")
        else:
            registros_fotos = df_fotos.to_dict(orient="records")
            for i in range(0, len(registros_fotos), 2):
                col_f1, col_f2 = st.columns(2)
                
                with col_f1:
                    item1 = registros_fotos[i]
                    raw_url1 = str(item1["foto_evidencia_url"]).strip()
                    direct_url1 = convertir_url_drive_a_directa(raw_url1)
                    
                    st.markdown(f"**OT: {item1['OT']}** | `{item1['codigo_interno']}` ({item1['placa']}) - {item1['nivel_pm']}")
                    try:
                        if "/drive/folders/" in raw_url1:
                            st.link_button("📁 Abrir Carpeta de Evidencias (Google Drive)", raw_url1, use_container_width=True)
                        else:
                            st.image(direct_url1, use_container_width=True)
                    except Exception:
                        st.link_button("🔗 Abrir Foto en Google Drive", raw_url1, use_container_width=True)
                
                if i + 1 < len(registros_fotos):
                    with col_f2:
                        item2 = registros_fotos[i+1]
                        raw_url2 = str(item2["foto_evidencia_url"]).strip()
                        direct_url2 = convertir_url_drive_a_directa(raw_url2)
                        
                        st.markdown(f"**OT: {item2['OT']}** | `{item2['codigo_interno']}` ({item2['placa']}) - {item2['nivel_pm']}")
                        try:
                            if "/drive/folders/" in raw_url2:
                                st.link_button("📁 Abrir Carpeta de Evidencias (Google Drive)", raw_url2, use_container_width=True)
                            else:
                                st.image(direct_url2, use_container_width=True)
                        except Exception:
                            st.link_button("🔗 Abrir Foto en Google Drive", raw_url2, use_container_width=True)
                
                st.write("---")
