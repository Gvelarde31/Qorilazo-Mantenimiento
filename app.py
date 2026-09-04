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
        return response.json() if response.status_code in [200, 201] else []
    except Exception:
        return []

def insertar_registro(nombre_tabla, datos):
    url_endpoint = f"{SUPABASE_URL}/rest/v1/{nombre_tabla}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"  # <--- Solicita que Supabase retorne la fila insertada con su ID
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
        "4. Historial de Mantenimientos & Consumo",
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
            "Selecciona un Permiso:",
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
        st.warning("⚠️ No se encontraron equipos en la tabla 'equipos'.")
    else:
        df_equipos = pd.DataFrame(equipos)
        lista_codigos = sorted(list(set(df_equipos["codigo_interno"].dropna().astype(str)))) if "codigo_interno" in df_equipos.columns else []
        
        with st.form("form_parte_diario", clear_on_submit=True):
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

            col_h1, col_h2 = st.columns(2)
            with col_h1:
                horo_init = st.number_input("Horómetro Inicial", min_value=0.0, step=0.1)
                horo_fin = st.number_input("Horómetro Final", min_value=0.0, step=0.1)
            with col_h2:
                km_init = st.number_input("Kilómetro Inicial", min_value=0.0, step=1.0)
                km_fin = st.number_input("Kilómetro Final", min_value=0.0, step=1.0)

            observaciones = st.text_area("Observaciones")
            guardar = st.form_submit_button("💾 Guardar Parte Diario", use_container_width=True)
            
            if guardar:
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
                    st.success(f"✅ Parte diario registrado con éxito.")
                    st.rerun()
                else:
                    st.error(f"❌ Error Supabase: {msg}")

        st.divider()
        partes = consultar_tabla("partes_diarios")
        st.dataframe(pd.DataFrame(partes), use_container_width=True) if partes else st.info("Sin registros.")

# ==========================================
# MÓDULO 3: PROGRAMACIÓN SEMANAL PM
# ==========================================
elif modulo == "3. Programación Semanal PM":
    st.header("📅 Programación Semanal de Mantenimiento Preventivo (PM)")
    equipos = consultar_tabla("equipos")
    if equipos:
        df_equipos = pd.DataFrame(equipos)
        lista_codigos = sorted(list(set(df_equipos["codigo_interno"].dropna().astype(str)))) if "codigo_interno" in df_equipos.columns else []
        
        with st.form("form_programacion_pm", clear_on_submit=True):
            col_p1, col_p2, col_p3 = st.columns(3)
            with col_p1:
                codigo_sel = st.selectbox("Código Interno del Equipo *", lista_codigos)
                tipo_pm = st.selectbox("Tipo de Mantenimiento *", ["PM1 (250 hrs)", "PM2 (500 hrs)", "PM3 (1000 hrs)", "PM4 (2000 hrs)", "Correctivo Planificado"])
            with col_p2:
                fecha_prog = st.date_input("Fecha Programada *", datetime.now().date())
                horo_proyectado = st.number_input("Horómetro Proyectado", min_value=0.0, step=10.0)
            with col_p3:
                responsable = st.text_input("Taller / Responsable", value="Taller Principal")
                estado = st.selectbox("Estado Inicial", ["PROGRAMADO", "EN PROCESO", "COMPLETADO", "CANCELADO"])
                
            observaciones_pm = st.text_area("Observaciones")
            guardar_pm = st.form_submit_button("🗓️ Guardar Programación PM", use_container_width=True)
            
            if guardar_pm:
                nuevo_pm = {
                    "codigo_equipo": codigo_sel, "fecha_programada": str(fecha_prog),
                    "tipo_pm": tipo_pm, "horometro_proyectado": horo_proyectado,
                    "responsable": responsable, "estado": estado, "observaciones": observaciones_pm
                }
                exito, msg = insertar_registro("programacion_pm", nuevo_pm)
                if exito:
                    st.success("✅ PM Programado.")
                    st.rerun()
                else:
                    st.error(f"❌ Error Supabase: {msg}")

        prog = consultar_tabla("programacion_pm")
        st.dataframe(pd.DataFrame(prog), use_container_width=True) if prog else st.info("Sin registros.")

# ==========================================
# MÓDULO 4: HISTORIAL DE MANTENIMIENTOS & CONSUMO INTEGRADO
# ==========================================
elif modulo == "4. Historial de Mantenimientos & Consumo":
    st.header("🔧 Registro de Mantenimientos y Consumo de Repuestos")
    
    equipos = consultar_tabla("equipos")
    repuestos_cat = consultar_tabla("repuestos_cat")
    
    if not equipos:
        st.warning("⚠️ No se encontraron equipos en 'equipos'.")
    else:
        df_equipos = pd.DataFrame(equipos)
        lista_codigos = sorted(list(set(df_equipos["codigo_interno"].dropna().astype(str)))) if "codigo_interno" in df_equipos.columns else []

        opciones_repuestos = ["Sin repuesto adicional"]
        dict_repuestos = {}
        if repuestos_cat:
            for r in repuestos_cat:
                label = f"ID: {r.get('id')} | {r.get('codigo_repuesto')} - {r.get('descripcion')}"
                opciones_repuestos.append(label)
                dict_repuestos[label] = r

        st.subheader("📝 Registrar Servicio Mecánico, Repuestos y Mano de Obra")
        
        with st.form("form_mantenimientos_integrado", clear_on_submit=False):
            st.markdown("##### 📍 Datos Cabecera del Mantenimiento (`mantenimientos`)")
            col_m1, col_m2, col_m3 = st.columns(3)
            
            with col_m1:
                codigo_sel = st.selectbox("Código del Equipo *", lista_codigos)
                tipo_maint = st.selectbox("Tipo de Mantenimiento *", ["Preventivo", "Correctivo", "Retorqueo", "Inspección Técnica"])
                nivel_pm = st.selectbox("Nivel PM *", [
                    "PM1 (250h)", "PM2 (500h)", "PM3 (1000h)", "PM4 (2000h)", "Correctivo / Reparación", "Otro"
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

            st.divider()
            st.markdown("##### 🛠️ Detalle de Repuesto y Mano de Obra (`mantenimiento_detalles`)")
            
            col_r1, col_r2, col_r3 = st.columns(3)
            with col_r1:
                repuesto_sel = st.selectbox("Repuesto Utilizado (Opcional)", opciones_repuestos)
            with col_r2:
                cant_usada = st.number_input("Cantidad Utilizada", min_value=1, step=1, value=1)
            with col_r3:
                costo_mo = st.number_input("Costo de Mano de Obra / P.U. (M.O.)", min_value=0.0, step=1.0, value=0.0)

            subtotal_calc = cant_usada * costo_mo
            st.info(f"**Costo Subtotal (Cantidad × M.O.):** `{subtotal_calc:.2f}`")

            guardar_maint = st.form_submit_button("💾 Guardar Mantenimiento & Consumo en Supabase", use_container_width=True)
            
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
                    
                    st.success(f"✅ Cabecera de Mantenimiento guardada con ID: `{maint_id}`.")
                    
                    if maint_id:
                        nuevo_detalle = {
                            "mantenimiento_id": maint_id,
                            "cantidad": cant_usada,
                            "precio_unitario": costo_mo,
                            "costo_subtotal": subtotal_calc
                        }
                        if repuesto_sel != "Sin repuesto adicional" and repuesto_sel in dict_repuestos:
                            nuevo_detalle["repuesto_id"] = dict_repuestos[repuesto_sel].get("id")

                        exito_det, res_det = insertar_registro("mantenimiento_detalles", nuevo_detalle)
                        if exito_det:
                            st.success(f"✅ Detalle insertado en `mantenimiento_detalles` correctamente.")
                        else:
                            st.error(f"❌ Error de Supabase al guardar en mantenimiento_detalles: {res_det}")
                else:
                    st.error(f"❌ Error al guardar en mantenimientos: {res_data}")

        st.divider()
        tab_h1, tab_h2 = st.tabs(["📊 Historial de Mantenimientos", "🛠️ Detalle de Repuestos Usados (mantenimiento_detalles)"])
        
        with tab_h1:
            historial_maint = consultar_tabla("mantenimientos")
            st.dataframe(pd.DataFrame(historial_maint), use_container_width=True) if historial_maint else st.info("Sin registros.")

        with tab_h2:
            detalles_registrados = consultar_tabla("mantenimiento_detalles")
            st.dataframe(pd.DataFrame(detalles_registrados), use_container_width=True) if detalles_registrados else st.info("Sin registros.")

# ==========================================
# MÓDULO 5: CATÁLOGO DE REPUESTOS
# ==========================================
elif modulo == "5. Catálogo de Repuestos":
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
            cod_repuesto = st.text_input("Código de Repuesto / SKU *")
            descripcion_rep = st.text_input("Descripción del Repuesto / Parte *")
        with col_r2:
            categoria = st.selectbox("Categoría *", ["Filtros", "Lubricantes / Fluidos", "Sistema Eléctrico", "Neumáticos", "Motor", "Frenos / Suspensión", "Otros"])
            unidad = st.selectbox("Unidad de Medida *", ["Unidad", "Galón", "Juego / Kit", "Litro", "Metro", "Caja"])
        with col_r3:
            precio_ref = st.number_input("Precio Referencial (USD / PEN)", min_value=0.0, step=1.0)

        guardar_rep = st.form_submit_button("💾 Guardar Repuesto en Catálogo", use_container_width=True)
        
        if guardar_rep:
            if not cod_repuesto.strip() or not descripcion_rep.strip():
                st.error("❌ Debes ingresar el Código y la Descripción.")
            else:
                nuevo_repuesto = {
                    "codigo_repuesto": cod_repuesto.strip(),
                    "descripcion": descripcion_rep.strip(),
                    "categoria": categoria,
                    "unidad_medida": unidad,
                    "precio_referencial": precio_ref
                }
                exito, msg = insertar_registro("repuestos_cat", nuevo_repuesto)
                if exito:
                    st.success(f"✅ Repuesto `{cod_repuesto}` guardado.")
                    st.rerun()
                else:
                    st.error(f"❌ Error al guardar en Supabase: {msg}")

    st.divider()
    st.dataframe(pd.DataFrame(repuestos), use_container_width=True) if repuestos else st.info("Aún no hay registros.")
