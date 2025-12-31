import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date, timedelta
import numpy as np

# Configuración de la página
st.set_page_config(page_title="Dashboard GLPI - Mesa de Servicio", layout="wide")

st.title("📊 Dashboard GLPI - Mesa de Servicio")
st.markdown("---")

# ============================================================================
# DEFINICIONES Y CONFIGURACIONES
# ============================================================================

# Tipos de reportes para transcripción (Pt1)
tipos_transcripcion = [
    'Reportar Falla: Novedad en equipo/dispositivo tecnológico',
    'Reportar Falla: Error o novedad con aplicación',
    'Reportar Falla: Bloqueo de usuario',
    'Reportar Falla: Novedad con Internet o señal wifi',
    'Reportar Falla: Novedad de seguridad informática',
    'Reportar Falla: Novedad con RPA'
]

# Estados válidos
estados_validos = ['En curso (asignada)', 'En curso (planificada)', 'En espera']

# Grupos técnicos para backlog (Pt2)
grupos_backlog = [
    'Grupos Activos > TGCS - Mesa Servicio N2',
    'Grupos Activos > TGCS - Mesa Servicio N1'
]

# ============================================================================
# FUNCIONES AUXILIARES
# ============================================================================

def mostrar_detalle_ids(titulo, df_filtrado, columnas_a_mostrar=None):
    """
    Función para mostrar IDs en un expander (Pt0)
    """
    if columnas_a_mostrar is None:
        columnas_a_mostrar = ['ID', 'Título', 'Fecha de apertura', 'Estados', 'Asignado a - Técnico']
    
    if not df_filtrado.empty:
        with st.expander(f"📋 Ver detalle de IDs - {titulo}"):
            st.dataframe(df_filtrado[columnas_a_mostrar], width='stretch')
            st.info(f"Total de casos: {len(df_filtrado)}")
    else:
        with st.expander(f"📋 Ver detalle de IDs - {titulo}"):
            st.info("No hay casos para mostrar")

# ============================================================================
# INTERFAZ PRINCIPAL
# ============================================================================

# Subir archivo principal
archivo = st.file_uploader("📤 Sube tu archivo GLPI exportado (Excel)", type=['xlsx'])

if archivo:
    try:
        # Leer el archivo
        df = pd.read_excel(archivo)
        
        # Limpiar y preparar datos
        df['Fecha de apertura'] = pd.to_datetime(df['Fecha de apertura'], errors='coerce')
        df = df.dropna(subset=['Fecha de apertura'])
        df['Día'] = df['Fecha de apertura'].dt.date
        df['Día_str'] = df['Fecha de apertura'].dt.strftime('%d-%b')
        
        # ============================================================================
        # 1. DASHBOARD (CASOS POR ESTADO Y DIAS) CON GRÁFICO A LA DERECHA
        # ============================================================================
        st.header("📋 Dashboard (casos por estado y dias)")
        
        # Filtrar por estados válidos
        df_estados_validos = df[df['Estados'].isin(estados_validos)].copy()
        
        # Crear tabla pivote para estados por día
        tickets_estados_dias = df_estados_validos.pivot_table(
            index='Día_str',
            columns='Estados',
            values='ID',
            aggfunc='count',
            fill_value=0
        ).reset_index()
        
        # Asegurar que tenemos todas las columnas de estados
        for estado in estados_validos:
            if estado not in tickets_estados_dias.columns:
                tickets_estados_dias[estado] = 0
        
        # Reordenar columnas
        column_order = ['Día_str'] + estados_validos
        tickets_estados_dias = tickets_estados_dias[column_order]
        
        # Calcular total general por día
        tickets_estados_dias['Total general'] = tickets_estados_dias[estados_validos].sum(axis=1)
        
        # Calcular total general por estado
        totales_estados = tickets_estados_dias[estados_validos].sum().to_dict()
        total_general_estados = tickets_estados_dias['Total general'].sum()
        
        # Agregar fila de totales
        fila_totales = {'Día_str': 'Total general'}
        for estado in estados_validos:
            fila_totales[estado] = totales_estados[estado]
        fila_totales['Total general'] = total_general_estados
        
        tickets_estados_dias = pd.concat([tickets_estados_dias, pd.DataFrame([fila_totales])], ignore_index=True)
        
        # Layout de dos columnas: Tabla a la izquierda, Gráfico a la derecha
        col_tabla1, col_grafico1 = st.columns([2, 2])
        
        with col_tabla1:
            # Tabla
            st.dataframe(tickets_estados_dias, width='stretch')
            
            # Pt0: Mostrar IDs para tabla de estados
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
                    # Mostrar todos los casos del estado seleccionado
                    df_filtrado = df_estados_validos[df_estados_validos['Estados'] == estado_seleccionado]
                    titulo = f"Total General - {estado_seleccionado}"
                else:
                    # Mostrar casos del día y estado específicos
                    df_filtrado = df_estados_validos[
                        (df_estados_validos['Día_str'] == dia_seleccionado) & 
                        (df_estados_validos['Estados'] == estado_seleccionado)
                    ]
                    titulo = f"{dia_seleccionado} - {estado_seleccionado}"
                
                mostrar_detalle_ids(titulo, df_filtrado)
        
        with col_grafico1:
            # Gráfico de barras apiladas
            if len(tickets_estados_dias) > 1:
                df_grafico = tickets_estados_dias[tickets_estados_dias['Día_str'] != 'Total general']
                df_melted = df_grafico.melt(id_vars=['Día_str'], value_vars=estados_validos, 
                                           var_name='Estado', value_name='Cantidad')
                
                fig1 = px.bar(df_melted, x='Día_str', y='Cantidad', color='Estado',
                             title='Casos por Estado y Día',
                             color_discrete_sequence=px.colors.qualitative.Set3)
                fig1.update_layout(height=400, showlegend=True)
                st.plotly_chart(fig1, use_container_width=True)
        
        st.markdown("---")
        
        # ============================================================================
        # 2. CASOS MESA SERVICIO PARA TRANSCRIPCION CON GRÁFICO A LA DERECHA (Pt1)
        # ============================================================================
        st.header("📝 Casos Mesa Servicio para Transcripcion")
        
        # Filtrar casos de transcripción según Pt1
        df_transcripcion = df[
            df['Título'].isin(tipos_transcripcion) & 
            df['Estados'].isin(['En curso (asignada)', 'En curso (planificada)'])
        ]
        
        # Agrupar por día
        casos_transcripcion_dia = df_transcripcion.groupby('Día_str').agg({
            'ID': 'count'
        }).reset_index().rename(columns={'ID': 'Casos Transcripción'})
        
        # Agregar fila de Total general
        if not casos_transcripcion_dia.empty:
            total_transcripcion_general = casos_transcripcion_dia['Casos Transcripción'].sum()
            fila_total_trans = pd.DataFrame({
                'Día_str': ['Total general'],
                'Casos Transcripción': [total_transcripcion_general]
            })
            casos_transcripcion_dia = pd.concat([casos_transcripcion_dia, fila_total_trans], ignore_index=True)
        
        total_transcripcion = len(df_transcripcion)
        
        # Layout de dos columnas
        col_tabla2, col_grafico2 = st.columns([2, 2])
        
        with col_tabla2:
            if not casos_transcripcion_dia.empty:
                st.dataframe(casos_transcripcion_dia, width='stretch')
            else:
                st.info("No hay casos de transcripción en este período")
            
            # Pt0: Mostrar IDs para casos de transcripción
            st.markdown("---")
            dia_transcripcion = st.selectbox(
                "Selecciona un día para ver IDs de transcripción:",
                options=['Total general'] + list(df_transcripcion['Día_str'].unique()) if not df_transcripcion.empty else ['Total general'],
                key="dia_transcripcion"
            )
            
            if dia_transcripcion:
                if dia_transcripcion == 'Total general':
                    # Mostrar todos los casos de transcripción
                    df_filtrado_trans = df_transcripcion.copy()
                    titulo = "Total General - Transcripción"
                else:
                    # Mostrar casos de transcripción del día específico
                    df_filtrado_trans = df_transcripcion[df_transcripcion['Día_str'] == dia_transcripcion]
                    titulo = f"Transcripción - {dia_transcripcion}"
                
                mostrar_detalle_ids(titulo, df_filtrado_trans)
        
        with col_grafico2:
            if not casos_transcripcion_dia.empty:
                # Filtrar fila de total general para el gráfico
                df_grafico_trans = casos_transcripcion_dia[casos_transcripcion_dia['Día_str'] != 'Total general']
                if not df_grafico_trans.empty:
                    fig2 = px.bar(df_grafico_trans, x='Día_str', y='Casos Transcripción',
                                 title='Casos de Transcripción por Día',
                                 color_discrete_sequence=['#FFA500'])
                    fig2.update_layout(height=400)
                    st.plotly_chart(fig2, use_container_width=True)
        
        st.markdown("---")
        
        # ============================================================================
        # 3. CASOS AGENTES DE MESA DE SERVICIO CON GRÁFICO A LA DERECHA
        # ============================================================================
        st.header("👥 Casos Agentes de Mesa de Servicio")
        
        # Filtrar técnicos no vacíos
        df_tecnicos = df[df['Asignado a - Técnico'].notna() & 
                        (df['Asignado a - Técnico'].str.strip() != '')].copy()
        
        if not df_tecnicos.empty:
            # Crear tabla pivote para técnicos por día
            casos_tecnicos = df_tecnicos.pivot_table(
                index='Asignado a - Técnico',
                columns='Día_str',
                values='ID',
                aggfunc='count',
                fill_value=0
            ).reset_index()
            
            # Calcular total por técnico
            columnas_dias = [col for col in casos_tecnicos.columns if col != 'Asignado a - Técnico']
            casos_tecnicos['Total general'] = casos_tecnicos[columnas_dias].sum(axis=1)
            
            # Calcular totales por día
            totales_por_dia = casos_tecnicos[columnas_dias].sum().to_dict()
            total_general_tecnicos = casos_tecnicos['Total general'].sum()
            
            # Agregar fila de totales
            fila_totales_tecnicos = {'Asignado a - Técnico': 'Total general'}
            for dia in columnas_dias:
                fila_totales_tecnicos[dia] = totales_por_dia[dia]
            fila_totales_tecnicos['Total general'] = total_general_tecnicos
            
            casos_tecnicos = pd.concat([casos_tecnicos, pd.DataFrame([fila_totales_tecnicos])], ignore_index=True)
            
            # Layout de dos columnas
            col_tabla3, col_grafico3 = st.columns([2, 2])
            
            with col_tabla3:
                # Mostrar tabla
                st.dataframe(casos_tecnicos, width='stretch')
                
                # Información sobre resaltado amarillo
                st.info("💡 **Nota:** Las celdas resaltadas en amarillo indican técnicos con casos de días anteriores al actual (pendientes sin cierre)")
                
                # Pt0: Mostrar IDs para casos de técnicos
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
                        # Mostrar todos los casos del técnico
                        df_filtrado_tecnico = df_tecnicos[df_tecnicos['Asignado a - Técnico'] == tecnico_seleccionado]
                        titulo = f"Total General - {tecnico_seleccionado}"
                    else:
                        # Mostrar casos del técnico en el día específico
                        df_filtrado_tecnico = df_tecnicos[
                            (df_tecnicos['Asignado a - Técnico'] == tecnico_seleccionado) & 
                            (df_tecnicos['Día_str'] == dia_tecnico)
                        ]
                        titulo = f"{tecnico_seleccionado} - {dia_tecnico}"
                    
                    mostrar_detalle_ids(titulo, df_filtrado_tecnico)
            
            with col_grafico3:
                # Gráfico de total por técnico (excluyendo fila de totales)
                df_grafico_tecnicos = casos_tecnicos[casos_tecnicos['Asignado a - Técnico'] != 'Total general']
                if not df_grafico_tecnicos.empty:
                    fig3 = px.bar(df_grafico_tecnicos, 
                                 x='Asignado a - Técnico', 
                                 y='Total general',
                                 title='Total de Casos por Técnico',
                                 color_discrete_sequence=['#2E86AB'])
                    fig3.update_layout(height=400, xaxis_tickangle=-45)
                    st.plotly_chart(fig3, use_container_width=True)
        
        st.markdown("---")
        
        # ============================================================================
        # 4. CASOS PENDIENTES/BACKLOG (Pt2)
        # ============================================================================
        st.header("⏳ Casos Pendientes/Backlog (Espera en N1/N2)")
        
        # Filtrar casos para backlog según Pt2
        df_backlog_espera = df[
            df['Título'].isin(tipos_transcripcion) &
            df['Estados'].isin(['En espera']) &
            df['Asignado a - Grupo técnico'].isin(grupos_backlog)
        ]
        
        # Agrupar por día
        casos_backlog_dia = df_backlog_espera.groupby('Día_str').agg({
            'ID': 'count'
        }).reset_index().rename(columns={'ID': 'Casos Pendientes/Backlog'})
        
        # Agregar fila de Total general
        if not casos_backlog_dia.empty:
            total_backlog_general = casos_backlog_dia['Casos Pendientes/Backlog'].sum()
            fila_total_backlog = pd.DataFrame({
                'Día_str': ['Total general'],
                'Casos Pendientes/Backlog': [total_backlog_general]
            })
            casos_backlog_dia = pd.concat([casos_backlog_dia, fila_total_backlog], ignore_index=True)
        
        total_backlog_espera = len(df_backlog_espera)
        
        # Layout de dos columnas
        col_tabla4, col_grafico4 = st.columns([2, 2])
        
        with col_tabla4:
            if not casos_backlog_dia.empty:
                st.dataframe(casos_backlog_dia, width='stretch')
            else:
                st.info("No hay casos pendientes/backlog en este período")
            
            # Pt0: Mostrar IDs para casos de backlog
            st.markdown("---")
            dia_backlog = st.selectbox(
                "Selecciona un día para ver IDs de backlog:",
                options=['Total general'] + list(df_backlog_espera['Día_str'].unique()) if not df_backlog_espera.empty else ['Total general'],
                key="dia_backlog"
            )
            
            if dia_backlog:
                if dia_backlog == 'Total general':
                    # Mostrar todos los casos de backlog
                    df_filtrado_backlog = df_backlog_espera.copy()
                    titulo = "Total General - Backlog"
                else:
                    # Mostrar casos de backlog del día específico
                    df_filtrado_backlog = df_backlog_espera[df_backlog_espera['Día_str'] == dia_backlog]
                    titulo = f"Backlog - {dia_backlog}"
                
                mostrar_detalle_ids(titulo, df_filtrado_backlog, 
                                  ['ID', 'Título', 'Fecha de apertura', 'Estados', 'Asignado a - Grupo técnico'])
        
        with col_grafico4:
            if not casos_backlog_dia.empty:
                # Filtrar fila de total general para el gráfico
                df_grafico_backlog = casos_backlog_dia[casos_backlog_dia['Día_str'] != 'Total general']
                if not df_grafico_backlog.empty:
                    fig4 = px.bar(df_grafico_backlog, x='Día_str', y='Casos Pendientes/Backlog',
                                 title='Casos Pendientes/Backlog por Día',
                                 color_discrete_sequence=['#FF0000'])
                    fig4.update_layout(height=400)
                    st.plotly_chart(fig4, use_container_width=True)
        
        st.markdown("---")
        
        # ============================================================================
        # 5. RESUMEN EJECUTIVO - BACKLOG MESA DE SERVICIO CON GRÁFICO CIRCULAR
        # ============================================================================
        st.header("📊 Resumen Ejecutivo - Backlog Mesa de Servicio")
        
        # Calcular totales para el resumen
        total_tickets_estados = total_general_estados
        total_casos_tecnicos = total_general_tecnicos if not df_tecnicos.empty else 0
        
        # Usar el total general de backlog
        backlog_calculado = total_backlog_general if 'total_backlog_general' in locals() else 0
        
        # Layout de dos columnas: Datos a la izquierda, Gráfico a la derecha
        col_datos, col_grafico5 = st.columns([2, 3])
        
        with col_datos:
            # Mostrar datos en formato similar a imagen 3
            hora_actual = datetime.now().strftime("%H:%M")
            
            st.markdown(f"""
            <div style='background-color: #f0f2f6; padding: 20px; border-radius: 10px;'>
                <h3 style='color: #1f77b4; margin-bottom: 20px; text-align: center;'>HORA: {hora_actual} hr</h3>
                <div style='display: flex; flex-direction: column; gap: 15px;'>
                    <div style='background-color: white; padding: 1px; border-radius: 8px; border-top: 5px solid #2e86ab;justify-items : center'>
                        <h4 style='color: #333; margin: 0;'>Total Tickets Estados</h4>
                        <h2 style='color: #2e86ab; margin: 5px 0;'>{total_tickets_estados}</h2>
                    </div>
                    <div style='background-color: white; padding: 1px; border-radius: 8px; border-top: 5px solid #a23b72;justify-items : center'>
                        <h4 style='color: #333; margin: 0;'>Casos Agentes de Mesa de Servicio</h4>
                        <h2 style='color: #2e86ab; margin: 5px 0;'>{total_casos_tecnicos}</h2>
                    </div>
                    <div style='background-color: white; padding: 1px; border-radius: 8px; border-top: 5px solid #f18f01;justify-items : center'>
                        <h4 style='color: #333; margin: 0;'>Casos Mesa Servicio para Transcripcion</h4>
                        <h2 style='color: #a23b72; margin: 5px 0;'>{total_transcripcion}</h2>
                    </div>
                    <div style='background-color: white; padding: 1px; border-radius: 8px; border: 3px solid #c73e1d;justify-items : center'>
                        <h4 style='color: #333; margin: 0;'>Casos Pendientes/Backlog</h4>
                        <h2 style='color: #f18f01; margin: 5px 0;'>{backlog_calculado}</h2>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Mostrar fórmula del backlog
            st.info(f"""
            **Fórmula del Backlog (Pt2):**
            ```
            Backlog = Casos "Reportar Falla" en estado "En espera" 
                      y grupo técnico N1/N2
            Total: {backlog_calculado} casos pendientes
            ```
            """)
        
        with col_grafico5:
            # Crear gráfico circular con 3 categorías
            if total_tickets_estados > 0:
                # Preparar datos para el gráfico
                labels = ['Casos Agentes', 'Casos Transcripción', 'Casos Pendientes']
                valores = [total_casos_tecnicos, total_transcripcion, backlog_calculado]
                colores = ['#2E86AB', '#F18F01', '#C73E1D']
                
                # Solo mostrar si hay datos
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
        st.error(f"Error al procesar el archivo principal: {str(e)}")
        st.info("Asegúrate de que el archivo tenga la estructura correcta de GLPI")

else:
    st.info("👆 Por favor, sube un archivo Excel exportado desde GLPI para comenzar el análisis.")

# ============================================================================
# INFORMACIÓN ADICIONAL
# ============================================================================

with st.expander("📌 Notas y Aclaraciones"):
    st.markdown("""
    ### **Definiciones de las métricas:**
    
    **1. Total Tickets Estados:**
    - Todos los casos con estados: 'En curso (asignada)', 'En curso (planificada)', 'En espera'
    
    **2. Casos Agentes de Mesa de Servicio:**
    - Todos los casos que tienen un técnico asignado (no vacío)
    
    **3. Casos Mesa Servicio para Transcripción (Pt1):**
    - Tipos de caso:
      - Reportar Falla: Novedad en equipo/dispositivo tecnológico
      - Reportar Falla: Error o novedad con aplicación
      - Reportar Falla: Bloqueo de usuario
      - Reportar Falla: Novedad con Internet o señal wifi
      - Reportar Falla: Novedad de seguridad informática
      - Reportar Falla: Novedad con RPA
    - Estados requeridos: 'En curso (asignada)' o 'En curso (planificada)'
    
    **4. Casos Pendientes/Backlog (Pt2):**
    - Mismos tipos de caso que Transcripción
    - Estado: 'En espera'
    - Grupo técnico: 'Grupos Activos > TGCS - Mesa Servicio N1' o 'Grupos Activos > TGCS - Mesa Servicio N2'
    
    **5. Cómo ver los IDs detallados:**
    - Cada tabla tiene selectores para filtrar por día/técnico/estado
    - La opción "Total general" muestra todos los casos sin filtrar por día
    - Los resultados se muestran en un expander debajo de cada tabla
    """)

# Instrucciones de instalación
with st.expander("🔧 Instalación de Dependencias"):
    st.code("""
pip install streamlit pandas plotly openpyxl
streamlit run dashboard_glpi.py
""")