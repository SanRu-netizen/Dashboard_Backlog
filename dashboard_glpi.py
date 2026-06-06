import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date, timedelta
import numpy as np
import io

# Configuración de la página
st.set_page_config(page_title="Dashboard GLPI - Mesa de Servicio", layout="wide")

st.title("📊 Dashboard GLPI - Mesa de Servicio")
st.markdown("---")

# ============================================================================
# DEFINICIONES Y CONFIGURACIONES
# ============================================================================

tipos_transcripcion = [
    'Reportar Falla: Novedad en equipo/dispositivo tecnológico',
    'Reportar Falla: Error o novedad con aplicación',
    'Reportar Falla: Bloqueo de usuario',
    'Reportar Falla: Novedad con Internet o señal wifi',
    'Reportar Falla: Novedad de seguridad informática',
    'Reportar Falla: Novedad con RPA'
]

# Etiquetas cortas para el gráfico de barras (sin "Reportar Falla: ")
etiquetas_falla = {t: t.replace('Reportar Falla: ', '') for t in tipos_transcripcion}

estados_validos = ['En curso (asignada)', 'En curso (planificada)', 'En espera']

grupos_backlog = [
    'Grupos Activos > TGCS - Mesa Servicio N2',
    'Grupos Activos > TGCS - Mesa Servicio N1'
]
GRUPO_N1 = 'Grupos Activos > TGCS - Mesa Servicio N1'
GRUPO_N2 = 'Grupos Activos > TGCS - Mesa Servicio N2'

# ============================================================================
# FUNCIONES AUXILIARES
# ============================================================================

def mostrar_detalle_ids(titulo, df_filtrado, columnas_a_mostrar=None):
    if columnas_a_mostrar is None:
        columnas_a_mostrar = ['ID', 'Título', 'Fecha de apertura', 'Estados', 'Asignado a - Técnico']
    columnas_a_mostrar = [c for c in columnas_a_mostrar if c in df_filtrado.columns]
    if not df_filtrado.empty:
        with st.expander(f"📋 Ver detalle de IDs - {titulo}"):
            st.dataframe(df_filtrado[columnas_a_mostrar], use_container_width=True)
            st.info(f"Total de casos: {len(df_filtrado)}")
    else:
        with st.expander(f"📋 Ver detalle de IDs - {titulo}"):
            st.info("No hay casos para mostrar")


def leer_csv(archivo):
    contenido = archivo.read()
    for enc in ('utf-8-sig', 'utf-8', 'latin-1'):
        try:
            df = pd.read_csv(io.BytesIO(contenido), sep=';', encoding=enc, on_bad_lines='skip')
            break
        except Exception:
            continue
    df = df.loc[:, ~df.columns.str.startswith('Unnamed')]
    for col in ['ID', 'Estados', 'Título', 'Asignado a - Técnico', 'Asignado a - Grupo técnico']:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()
    return df


def colorear_tecnicos(df_pivot, hoy):
    """
    Aplica color rojo/amarillo a filas de técnicos según la antigüedad
    del caso más antiguo abierto. Excluye la fila 'Total general'.
    """
    # dias_map: técnico -> días desde su caso más antiguo
    dias_map = {}
    if 'Asignado a - Técnico' in df_pivot.columns:
        for _, row in df_pivot.iterrows():
            tec = row['Asignado a - Técnico']
            if tec == 'Total general':
                dias_map[tec] = -1
                continue
            # El pivot solo tiene conteos; calculamos antigüedad desde df_tec global
            dias_map[tec] = row.get('_dias_max', -1)

    def estilo_fila(row):
        tec = row['Asignado a - Técnico'] if 'Asignado a - Técnico' in row.index else ''
        d = dias_map.get(tec, -1)
        if d > 4:
            return ['background-color: #FF4444; color: white; font-weight:bold'] * len(row)
        elif d > 2:
            return ['background-color: #FFD600; color: #333; font-weight:bold'] * len(row)
        else:
            return [''] * len(row)

    return estilo_fila


# ============================================================================
# INTERFAZ PRINCIPAL - UPLOAD
# ============================================================================

GLPI_URL = (
    "https://mservicios.grupo-exito.com/front/ticket.php?is_deleted=0&as_map=0&browse=0"
    "&criteria%5B0%5D%5Blink%5D=AND&criteria%5B0%5D%5Bfield%5D=8"
    "&criteria%5B0%5D%5Bsearchtype%5D=contains&criteria%5B0%5D%5Bvalue%5D=TGCS%20-%20Mesa"
    "&criteria%5B1%5D%5Blink%5D=AND%20NOT&criteria%5B1%5D%5Bfield%5D=12"
    "&criteria%5B1%5D%5Bsearchtype%5D=equals&criteria%5B1%5D%5Bvalue%5D=old"
    "&itemtype=Ticket&start=25"
    "&_glpi_csrf_token=4944824202c134481270c4c34e7714529ba7a8f14774f9a9ac62d5787bfd206b"
    "&sort%5B%5D=15&order%5B%5D=DESC"
)

st.markdown(
    f"""
    <div style='margin-bottom: 8px;'>
        📥 <a href="{GLPI_URL}" target="_blank" style="color:#4A9EFF; font-weight:600;">
            Descarga el archivo en GLPI según este filtro (Todas las páginas en CSV)
        </a>
    </div>
    """,
    unsafe_allow_html=True,
)

archivo = st.file_uploader(
    "📤 Sube tu archivo GLPI exportado (CSV)",
    type=['csv', 'xlsx'],
    help="Exporta desde GLPI usando el enlace de arriba. Selecciona 'CSV' como formato de exportación."
)

if archivo:
    try:
        nombre = archivo.name.lower()
        if nombre.endswith('.csv'):
            df = leer_csv(archivo)
        else:
            df = pd.read_excel(archivo)

        df['Fecha de apertura'] = pd.to_datetime(df['Fecha de apertura'], errors='coerce')
        df = df.dropna(subset=['Fecha de apertura'])
        df['Día'] = df['Fecha de apertura'].dt.date
        df['Día_str'] = df['Fecha de apertura'].dt.strftime('%d-%b')

        # ============================================================================
        # 1. DASHBOARD (CASOS POR ESTADO Y DIAS)
        # ============================================================================
        st.header("📋 Dashboard (casos por estado y dias)")

        df_estados_validos = df[df['Estados'].isin(estados_validos)].copy()

        tickets_estados_dias = df_estados_validos.pivot_table(
            index='Día_str', columns='Estados', values='ID',
            aggfunc='count', fill_value=0
        ).reset_index()

        for estado in estados_validos:
            if estado not in tickets_estados_dias.columns:
                tickets_estados_dias[estado] = 0

        column_order = ['Día_str'] + estados_validos
        tickets_estados_dias = tickets_estados_dias[column_order]
        tickets_estados_dias['Total general'] = tickets_estados_dias[estados_validos].sum(axis=1)

        totales_estados = tickets_estados_dias[estados_validos].sum().to_dict()
        total_general_estados = int(tickets_estados_dias['Total general'].sum())

        fila_totales = {'Día_str': 'Total general'}
        for estado in estados_validos:
            fila_totales[estado] = totales_estados[estado]
        fila_totales['Total general'] = total_general_estados

        tickets_estados_dias = pd.concat(
            [tickets_estados_dias, pd.DataFrame([fila_totales])], ignore_index=True
        )

        # Datos por día para sparkline (excluye fila total)
        df_spark = tickets_estados_dias[tickets_estados_dias['Día_str'] != 'Total general'].copy()
        dias_spark = df_spark['Día_str'].tolist()
        vals_spark = df_spark['Total general'].tolist()

        col_tabla1, col_grafico1 = st.columns([2, 2])

        with col_tabla1:
            st.dataframe(tickets_estados_dias, use_container_width=True)

            st.markdown("---")
            col_filtro1, col_filtro2 = st.columns(2)
            with col_filtro1:
                dia_seleccionado = st.selectbox(
                    "Selecciona un día para ver IDs:",
                    options=['Total general'] + list(df_estados_validos['Día_str'].unique()),
                    key="dia_estados"
                )
            with col_filtro2:
                estado_seleccionado = st.selectbox(
                    "Selecciona un estado:",
                    options=estados_validos,
                    key="estado_filtro"
                )

            if dia_seleccionado and estado_seleccionado:
                if dia_seleccionado == 'Total general':
                    df_filtrado = df_estados_validos[df_estados_validos['Estados'] == estado_seleccionado]
                    titulo = f"Total General - {estado_seleccionado}"
                else:
                    df_filtrado = df_estados_validos[
                        (df_estados_validos['Día_str'] == dia_seleccionado) &
                        (df_estados_validos['Estados'] == estado_seleccionado)
                    ]
                    titulo = f"{dia_seleccionado} - {estado_seleccionado}"
                mostrar_detalle_ids(titulo, df_filtrado)

        with col_grafico1:
            if len(tickets_estados_dias) > 1:
                df_grafico = tickets_estados_dias[tickets_estados_dias['Día_str'] != 'Total general']
                df_melted = df_grafico.melt(
                    id_vars=['Día_str'], value_vars=estados_validos,
                    var_name='Estado', value_name='Cantidad'
                )
                fig1 = px.bar(
                    df_melted, x='Día_str', y='Cantidad', color='Estado',
                    title='Casos por Estado y Día',
                    color_discrete_sequence=px.colors.qualitative.Set3
                )
                fig1.update_layout(height=400, showlegend=True)
                st.plotly_chart(fig1, use_container_width=True)

        st.markdown("---")

        # ============================================================================
        # 2. CASOS MESA SERVICIO PARA TRANSCRIPCION
        #    → Gráfico de barras por tipo de falla (etiqueta corta, siempre 6 barras)
        # ============================================================================
        st.header("📝 Casos Mesa Servicio para Transcripcion")

        df_transcripcion = df[
            df['Título'].isin(tipos_transcripcion) &
            df['Estados'].isin(['En curso (asignada)', 'En curso (planificada)'])
        ].copy()

        casos_transcripcion_dia = df_transcripcion.groupby('Día_str').agg(
            {'ID': 'count'}
        ).reset_index().rename(columns={'ID': 'Casos Transcripción'})

        if not casos_transcripcion_dia.empty:
            total_transcripcion_general = casos_transcripcion_dia['Casos Transcripción'].sum()
            fila_total_trans = pd.DataFrame({
                'Día_str': ['Total general'],
                'Casos Transcripción': [total_transcripcion_general]
            })
            casos_transcripcion_dia = pd.concat(
                [casos_transcripcion_dia, fila_total_trans], ignore_index=True
            )

        total_transcripcion = len(df_transcripcion)

        # Conteo por tipo de falla — siempre los 6 tipos, con 0 si no hay casos
        conteo_fallas = df_transcripcion.groupby('Título')['ID'].count().reset_index()
        conteo_fallas.columns = ['Título', 'Cantidad']
        # Aseguramos que estén todos los tipos aunque no haya casos
        df_fallas_completo = pd.DataFrame({'Título': tipos_transcripcion})
        df_fallas_completo = df_fallas_completo.merge(conteo_fallas, on='Título', how='left').fillna(0)
        df_fallas_completo['Cantidad'] = df_fallas_completo['Cantidad'].astype(int)
        df_fallas_completo['Falla'] = df_fallas_completo['Título'].map(etiquetas_falla)

        col_tabla2, col_grafico2 = st.columns([2, 2])

        with col_tabla2:
            if not casos_transcripcion_dia.empty:
                st.dataframe(casos_transcripcion_dia, use_container_width=True)
            else:
                st.info("No hay casos de transcripción en este período")

            st.markdown("---")
            dia_transcripcion = st.selectbox(
                "Selecciona un día para ver IDs de transcripción:",
                options=['Total general'] + list(df_transcripcion['Día_str'].unique())
                if not df_transcripcion.empty else ['Total general'],
                key="dia_transcripcion"
            )

            if dia_transcripcion:
                if dia_transcripcion == 'Total general':
                    df_filtrado_trans = df_transcripcion.copy()
                    titulo = "Total General - Transcripción"
                else:
                    df_filtrado_trans = df_transcripcion[df_transcripcion['Día_str'] == dia_transcripcion]
                    titulo = f"Transcripción - {dia_transcripcion}"
                mostrar_detalle_ids(titulo, df_filtrado_trans)

        with col_grafico2:
            # Gráfico de barras por tipo de falla (etiqueta corta, siempre 6 tipos)
            fig2 = px.bar(
                df_fallas_completo,
                x='Cantidad',
                y='Falla',
                orientation='h',
                title='Casos de Transcripción por Tipo de Falla',
                color='Falla',
                color_discrete_sequence=px.colors.qualitative.Pastel,
                text='Cantidad'
            )
            fig2.update_traces(textposition='outside')
            fig2.update_layout(
                height=420,
                showlegend=False,
                xaxis_tickangle=-30,
                xaxis_title='',
                yaxis_title='Cantidad de casos',
                uniformtext_minsize=10
            )
            st.plotly_chart(fig2, use_container_width=True)

        st.markdown("---")

        # ============================================================================
        # 3. CASOS AGENTES DE MESA DE SERVICIO
        #    → Tabla centrada con coloring por antigüedad. Sin gráfico.
        #    → Amarillo: caso más antiguo > 2 días | Rojo: > 4 días
        # ============================================================================
        st.header("👥 Casos Agentes de Mesa de Servicio")

        df_tecnicos = df[
            df['Asignado a - Técnico'].notna() &
            (df['Asignado a - Técnico'].str.strip() != '') &
            (df['Asignado a - Técnico'].str.strip() != 'nan')
        ].copy()

        if not df_tecnicos.empty:
            hoy_real = pd.Timestamp(date.today())

            # Calcular días desde el caso más antiguo por técnico
            antigüedad_tec = df_tecnicos.groupby('Asignado a - Técnico')['Fecha de apertura'].min().reset_index()
            antigüedad_tec['dias_max'] = (hoy_real - antigüedad_tec['Fecha de apertura']).dt.days
            antigüedad_tec = antigüedad_tec.set_index('Asignado a - Técnico')['dias_max'].to_dict()

            casos_tecnicos = df_tecnicos.pivot_table(
                index='Asignado a - Técnico',
                columns='Día_str',
                values='ID',
                aggfunc='count',
                fill_value=0
            ).reset_index()

            columnas_dias = [col for col in casos_tecnicos.columns if col != 'Asignado a - Técnico']
            casos_tecnicos['Total general'] = casos_tecnicos[columnas_dias].sum(axis=1)

            totales_por_dia = casos_tecnicos[columnas_dias].sum().to_dict()
            total_general_tecnicos = int(casos_tecnicos['Total general'].sum())

            fila_totales_tecnicos = {'Asignado a - Técnico': 'Total general'}
            for dia in columnas_dias:
                fila_totales_tecnicos[dia] = totales_por_dia[dia]
            fila_totales_tecnicos['Total general'] = total_general_tecnicos

            casos_tecnicos = pd.concat(
                [casos_tecnicos, pd.DataFrame([fila_totales_tecnicos])], ignore_index=True
            )

            # Agregar columna oculta con días de antigüedad para el styling
            casos_tecnicos['_dias_max'] = casos_tecnicos['Asignado a - Técnico'].map(
                lambda t: antigüedad_tec.get(t, -1)
            )

            # Función de estilo por fila
            def estilo_fila_tec(row):
                d = row.get('_dias_max', -1)
                tec = row.get('Asignado a - Técnico', '')
                if tec == 'Total general':
                    return [''] * len(row)
                if d > 4:
                    return ['background-color: #FF4444; color: white; font-weight: bold'] * len(row)
                elif d > 2:
                    return ['background-color: #FFD600; color: #333; font-weight: bold'] * len(row)
                else:
                    return [''] * len(row)

            # Columnas visibles (ocultamos _dias_max)
            cols_visibles = [c for c in casos_tecnicos.columns if c != '_dias_max']
            df_mostrar = casos_tecnicos[cols_visibles + ['_dias_max']].copy()

            styled = df_mostrar.style.apply(estilo_fila_tec, axis=1)

            # Leyenda de colores
            st.markdown("""
            <div style='display:flex; gap:20px; margin-bottom:8px; align-items:center;'>
                <span style='background:#FFD600;color:#333;padding:3px 10px;border-radius:4px;font-size:13px;font-weight:bold;'>🟡 Caso más antiguo &gt; 2 días abierto</span>
                <span style='background:#FF4444;color:white;padding:3px 10px;border-radius:4px;font-size:13px;font-weight:bold;'>🔴 Caso más antiguo &gt; 4 días abierto</span>
            </div>
            """, unsafe_allow_html=True)

            # Tabla centrada — columna _dias_max oculta via hide
            st.dataframe(
                styled.hide(axis='columns', subset=['_dias_max']),
                use_container_width=True
            )

            st.markdown("---")
            col_filtro3, col_filtro4 = st.columns(2)
            with col_filtro3:
                tecnico_seleccionado = st.selectbox(
                    "Selecciona un técnico:",
                    options=df_tecnicos['Asignado a - Técnico'].unique(),
                    key="tecnico_filtro"
                )
            with col_filtro4:
                dia_tecnico = st.selectbox(
                    "Selecciona un día:",
                    options=['Total general'] + list(df_tecnicos['Día_str'].unique()),
                    key="dia_tecnico"
                )

            if tecnico_seleccionado and dia_tecnico:
                if dia_tecnico == 'Total general':
                    df_filtrado_tecnico = df_tecnicos[
                        df_tecnicos['Asignado a - Técnico'] == tecnico_seleccionado
                    ]
                    titulo = f"Total General - {tecnico_seleccionado}"
                else:
                    df_filtrado_tecnico = df_tecnicos[
                        (df_tecnicos['Asignado a - Técnico'] == tecnico_seleccionado) &
                        (df_tecnicos['Día_str'] == dia_tecnico)
                    ]
                    titulo = f"{tecnico_seleccionado} - {dia_tecnico}"
                mostrar_detalle_ids(titulo, df_filtrado_tecnico)

        st.markdown("---")

        # ============================================================================
        # 4. CASOS PENDIENTES/BACKLOG
        #    → Dos contadores separados N1 y N2, sumados en total
        #    → Gráfico de barras HORIZONTAL amarillo por grupo
        # ============================================================================
        st.header("⏳ Casos Pendientes/Backlog (Espera en N1/N2)")

        df_backlog_espera = df[
            df['Título'].isin(tipos_transcripcion) &
            df['Estados'].isin(['En espera']) &
            df['Asignado a - Grupo técnico'].isin(grupos_backlog)
        ].copy()

        # Contadores por grupo
        backlog_n1 = int(len(df_backlog_espera[df_backlog_espera['Asignado a - Grupo técnico'] == GRUPO_N1]))
        backlog_n2 = int(len(df_backlog_espera[df_backlog_espera['Asignado a - Grupo técnico'] == GRUPO_N2]))
        total_backlog_general = backlog_n1 + backlog_n2

        # Tabla por día
        casos_backlog_dia = df_backlog_espera.groupby('Día_str').agg(
            {'ID': 'count'}
        ).reset_index().rename(columns={'ID': 'Casos Pendientes/Backlog'})

        if not casos_backlog_dia.empty:
            fila_total_backlog = pd.DataFrame({
                'Día_str': ['Total general'],
                'Casos Pendientes/Backlog': [total_backlog_general]
            })
            casos_backlog_dia = pd.concat(
                [casos_backlog_dia, fila_total_backlog], ignore_index=True
            )

        col_tabla4, col_grafico4 = st.columns([2, 2])

        with col_tabla4:
            # Mini-KPIs N1 / N2
            kc1, kc2, kc3 = st.columns(3)
            kc1.metric("Mesa N1", backlog_n1)
            kc2.metric("Mesa N2", backlog_n2)
            kc3.metric("Total Backlog", total_backlog_general)

            st.markdown("")
            if not casos_backlog_dia.empty:
                st.dataframe(casos_backlog_dia, use_container_width=True)
            else:
                st.info("No hay casos pendientes/backlog en este período")

            st.markdown("---")
            dia_backlog = st.selectbox(
                "Selecciona un día para ver IDs de backlog:",
                options=['Total general'] + list(df_backlog_espera['Día_str'].unique())
                if not df_backlog_espera.empty else ['Total general'],
                key="dia_backlog"
            )

            if dia_backlog:
                if dia_backlog == 'Total general':
                    df_filtrado_backlog = df_backlog_espera.copy()
                    titulo = "Total General - Backlog"
                else:
                    df_filtrado_backlog = df_backlog_espera[df_backlog_espera['Día_str'] == dia_backlog]
                    titulo = f"Backlog - {dia_backlog}"
                mostrar_detalle_ids(
                    titulo, df_filtrado_backlog,
                    ['ID', 'Título', 'Fecha de apertura', 'Estados', 'Asignado a - Grupo técnico']
                )

        with col_grafico4:
            # Gráfico de barras HORIZONTAL por grupo — color amarillo
            df_grupos = pd.DataFrame({
                'Grupo': ['Mesa N1', 'Mesa N2'],
                'Casos': [backlog_n1, backlog_n2]
            })
            fig4 = px.bar(
                df_grupos,
                x='Casos',
                y='Grupo',
                orientation='h',
                title='Casos Pendientes/Backlog por Grupo',
                color_discrete_sequence=['#FFD600'],
                text='Casos'
            )
            fig4.update_traces(textposition='outside')
            fig4.update_layout(
                height=300,
                showlegend=False,
                yaxis_title='',
                xaxis_title='Cantidad de casos',
                plot_bgcolor='rgba(0,0,0,0)'
            )
            st.plotly_chart(fig4, use_container_width=True)

        st.markdown("---")

        # ============================================================================
        # 5. RESUMEN EJECUTIVO
        #    → Total Tickets con sparkline por día
        #    → Transcripción con desglose N1/N2
        #    → Backlog con desglose N1/N2
        # ============================================================================
        st.header("📊 Resumen Ejecutivo - Backlog Mesa de Servicio")

        total_tickets_estados = total_general_estados
        total_casos_tecnicos = total_general_tecnicos if not df_tecnicos.empty else 0
        backlog_calculado = total_backlog_general

        # Desglose transcripción por N1/N2
        trans_n1 = int(len(df_transcripcion[df_transcripcion['Asignado a - Grupo técnico'] == GRUPO_N1]))
        trans_n2 = int(len(df_transcripcion[df_transcripcion['Asignado a - Grupo técnico'] == GRUPO_N2]))

        col_datos, col_grafico5 = st.columns([2, 3])

        with col_datos:
            hora_actual = datetime.now().strftime("%H:%M")

            # ── Sparkline datos ──────────────────────────────────────────
            # Usamos df_spark calculado en la sección 1
            spark_filas = ""
            if dias_spark:
                headers = "".join(
                    f"""  <th style='border:1px solid #cccccc;padding:1px 10px;color:#888;font-size:20px;font-weight:normal;'>{d}</th>"""
                    for d in dias_spark
                )
                values = "".join(
                    f"""  <td style='border:1px solid #cccccc;padding:1px 10px;text-align:center;font-size:25px;font-weight:600;color:#2e86ab;'>{v}</td>"""
                    for v in vals_spark
                )
                spark_filas = f"""
                        <table style='line-height: 1;border-collapse:collapse;margin-top:2px;width:100%;'>
                            <tr>{headers}</tr>
                            <tr>{values}</tr>
                        </table>
                """

            st.markdown(f"""
            <div style='background-color: #f0f2f6; padding: 20px; border-radius: 10px;'>
                <h3 style='color: #1f77b4; margin-bottom: 20px; text-align: center;'>HORA: {hora_actual} hr</h3>
                <div style='display: flex; flex-direction: column; gap: 15px;'>
                    <!-- Total Tickets con sparkline -->
                    <div style='justify-items: center ;background-color: white; padding: 10px 14px; border-radius: 8px; border-top: 5px solid #2e86ab;'>
                        <h4 style='line-height: 0.1;color: #333; margin: 0 0 4px 0;'>Total Casos</h4>
                        <h2 style='line-height: 0.1;color: #2e86ab; margin: 0;'>{total_tickets_estados}</h2>
                        <div>{spark_filas}</div>
                    </div>
                    <!-- Agentes -->
                    <div style='justify-items: center ;background-color: white; padding: 10px 14px; border-radius: 8px; border-top: 5px solid #a23b72;'>
                        <h4 style='color: #333; margin: 0;'>Casos Agentes de Mesa de Servicio</h4>
                        <h2 style='line-height: 0.1;color: #2e86ab; margin: 5px 0 0 0;'>{total_casos_tecnicos}</h2>
                    </div>
                    <!-- Transcripción con N1/N2 -->
                    <div style='justify-items: center ;background-color: white; padding: 10px 14px; border-radius: 8px; border-top: 5px solid #f18f01;'>
                        <h4 style='color: #333; margin: 0 0 4px 0;'>Casos Mesa Servicio para Transcripcion</h4>
                        <div style='display:flex; gap:12px;'>
                            <h2 style='line-height: 0.1 ;color: #a23b72; margin: 0 0 0px 0;'>{total_transcripcion}</h2>
                            <span style='justify-items: center ;background:#fff3e0;border:1px solid #f18f01;border-radius:4px;padding:3px 10px;font-size:13px;color:#7b5800;font-weight:600;'>Mesa-N1 = {trans_n1}</span>
                            <span style='background:#fff3e0;border:1px solid #f18f01;border-radius:4px;padding:3px 10px;font-size:13px;color:#7b5800;font-weight:600;'>Mesa-N2 = {trans_n2}</span>
                        </div>
                    </div>
                    <!-- Backlog con N1/N2 -->
                    <div style='justify-items: center ;background-color: white; padding: 10px 14px; border-radius: 8px; border: 3px solid #c73e1d;'>
                        <h4 style='color: #333; margin: 0 0 4px 0;'>Casos Pendientes/Backlog</h4>
                        <div style='display:flex; gap:12px;'>
                            <h2 style='line-height: 0.1;color: #f18f01; margin: 0 0 6px 0;'>{backlog_calculado}</h2>
                            <span style='background:#fff0ee;border:1px solid #c73e1d;border-radius:4px;padding:3px 10px;font-size:13px;color:#7b1a0e;font-weight:600;'>Mesa-N1 = {backlog_n1}</span>
                            <span style='background:#fff0ee;border:1px solid #c73e1d;border-radius:4px;padding:3px 10px;font-size:13px;color:#7b1a0e;font-weight:600;'>Mesa-N2 = {backlog_n2}</span>
                    </div>
                    

                
            """, unsafe_allow_html=True)

            st.info(f"""
            **Fórmula del Backlog (Pt2):**
            ```
            Backlog = Casos "Reportar Falla" en estado "En espera"
                      y grupo técnico N1/N2
            Total: {backlog_calculado} casos pendientes
            ```
            """)

        with col_grafico5:
            if total_tickets_estados > 0:
                labels = ['Casos Agentes', 'Casos Transcripción', 'Casos Pendientes']
                valores = [total_casos_tecnicos, total_transcripcion, backlog_calculado]
                colores = ['#2E86AB', '#F18F01', '#C73E1D']

                if sum(valores) > 0:
                    fig5 = go.Figure(data=[go.Pie(
                        labels=labels,
                        values=valores,
                        hole=0.4,
                        marker=dict(colors=colores),
                        textinfo='label+percent+value',
                        insidetextorientation='radial'
                    )])
                    fig5.update_layout(
                        title='Distribución de Casos - Resumen Ejecutivo',
                        height=450,
                        showlegend=True,
                        annotations=[dict(
                            text=f'Total: {total_tickets_estados}',
                            x=0.5, y=0.5, font_size=18, showarrow=False,
                            font=dict(color='white', size=16)
                        )]
                    )
                    st.plotly_chart(fig5, use_container_width=True)

    except Exception as e:
        st.error(f"Error al procesar el archivo: {str(e)}")
        st.info("Asegúrate de que el archivo tenga la estructura correcta de GLPI (exportado en CSV con separador ';')")
        import traceback
        st.code(traceback.format_exc())

else:
    st.info("👆 Por favor, sube un archivo CSV exportado desde GLPI para comenzar el análisis.")

# ============================================================================
# INFORMACIÓN ADICIONAL
# ============================================================================

with st.expander("📌 Notas y Aclaraciones"):
    st.markdown("""
    ### **Definiciones de las métricas:**

    **1. Total Tickets Estados:**
    - Todos los casos con estados: 'En curso (asignada)', 'En curso (planificada)', 'En espera'
    - El sparkline muestra el total de casos (todos los estados) por cada día presente en el archivo

    **2. Casos Agentes de Mesa de Servicio:**
    - Todos los casos que tienen un técnico asignado (no vacío)

    **3. Casos Mesa Servicio para Transcripción (Pt1):**
    - Tipos de caso: Reportar Falla (6 tipos)
    - Estados requeridos: 'En curso (asignada)' o 'En curso (planificada)'
    - Se desglosa por Mesa N1 / Mesa N2 en el Resumen Ejecutivo

    **4. Casos Pendientes/Backlog (Pt2):**
    - Mismos tipos de caso que Transcripción
    - Estado: 'En espera'
    - Grupo técnico: Mesa Servicio N1 o N2
    - Se desglosa por Mesa N1 / Mesa N2 en el Resumen Ejecutivo

    **5. Alertas de color en Agentes:**
    - 🟡 **Amarillo**: el caso más antiguo del técnico lleva más de 2 días abierto
    - 🔴 **Rojo**: el caso más antiguo del técnico lleva más de 4 días abierto

    **6. Formato de archivo:**
    - **CSV** (recomendado): separador `;`, UTF-8 o Latin-1
    - **XLSX**: compatibilidad con exportaciones anteriores
    """)

