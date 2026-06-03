import streamlit as st
from streamlit_drawable_canvas import st_canvas
from PIL import Image
import shapely.geometry as sg
from shapely.validation import make_valid
import numpy as np
import plotly.graph_objects as go

# Configuración de la página estilo taller de diseño
st.set_page_config(
    page_title="Zonificador Arquitectónico Esquemático",
    page_icon="📐",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    h1, h2, h3 { color: #2C3E50; font-family: 'Helvetica Neue', Arial, sans-serif; }
    </style>
    """, unsafe_allow_html=True)

st.title("📐 Zonificador Arquitectónico Esquemático")
st.caption("Herramienta académica para el análisis de partido y zonificación preliminar.")

if "zonas" not in st.session_state:
    st.session_state.zonas = []
if "terreno_geom" not in st.session_state:
    st.session_state.terreno_geom = None

PALETA_PREDEFINIDA = {
    "Zona Cultural": "#f3a683",
    "Zona Histórica": "#cf6a87",
    "Zona de Convenciones": "#f7d794",
    "Zona Administrativa": "#778beb",
    "Zona Recreativa": "#78e08f",
    "Zona de Servicios": "#e77f67",
    "Zona Paisajística": "#63cdda",
    "Estacionamientos": "#cfd8dc",
    "Otro": "#a5b1c2"
}

with st.sidebar:
    st.header("1. Datos del Terreno")
    area_real_terreno = st.number_input("Área Real del Terreno (m²):", min_value=1.0, value=1000.0, step=50.0)
    
    st.markdown("---")
    st.header("2. Datos de la Zona")
    tipo_predeterminado = st.selectbox("Uso de Suelo:", list(PALETA_PREDEFINIDA.keys()))
    nombre_zona = st.text_input("Nombre específico:", value=tipo_predeterminado)
    subzona = st.text_input("Subzona:", value="General")
    color_zona = st.color_picker("Color:", value=PALETA_PREDEFINIDA[tipo_predeterminado])
    
    st.markdown("---")
    st.header("3. Herramienta")
    modo_dibujo = st.radio("¿Qué vas a trazar?:", ("Dibujar Límite del Terreno", "Dibujar Zona / Mancha"))

col_canvas, col_data = st.columns([3, 2])

with col_canvas:
    st.subheader("Lienzo de Trabajo")
    archivo_imagen = st.file_uploader("Cargar plano o lote (PNG, JPG):", type=["png", "jpg", "jpeg"])
    
    canvas_width, canvas_height = 700, 500
    bg_image = None
    if archivo_imagen:
        bg_image = Image.open(archivo_imagen)
        bg_image.thumbnail((canvas_width, canvas_height))
        canvas_width, canvas_height = bg_image.size

    stroke_color = "#FF0000" if modo_dibujo == "Dibujar Límite del Terreno" else color_zona
    
    canvas_result = st_canvas(
        fill_color=color_zona + "66",
        stroke_width=2,
        stroke_color=stroke_color,
        background_image=bg_image,
        height=canvas_height,
        width=canvas_width,
        drawing_mode="polygon",
        update_streamlit=True,
        key="canvas",
    )

if canvas_result.json_data is not None:
    objetos = canvas_result.json_data["objects"]
    zonas_temporales = []
    
    for i, obj in enumerate(objetos):
        if obj["type"] == "path":
            path = obj["path"]
            coords = []
            for comando in path:
                if comando[0] in ['M', 'L']:
                    coords.append((comando[1], comando[2]))
            
            if len(coords) >= 3:
                poly = make_valid(sg.Polygon(coords))
                if i == 0 and modo_dibujo == "Dibujar Límite del Terreno":
                    st.session_state.terreno_geom = poly
                else:
                    zonas_temporales.append(poly)

    if st.session_state.terreno_geom:
        area_pixeles_terreno = st.session_state.terreno_geom.area
        factor_escala = area_real_terreno / area_pixeles_terreno if area_pixeles_terreno > 0 else 1.0
        
        st.session_state.zonas = []
        contador = 1
        for poly in zonas_temporales:
            zona_recortada = poly.intersection(st.session_state.terreno_geom)
            area_zona_real = zona_recortada.area * factor_escala
            porcentaje = (area_zona_real / area_real_terreno) * 100
            
            st.session_state.zonas.append({
                "id": contador,
                "nombre": f"{nombre_zona} {contador}" if len(zonas_temporales) > 1 else nombre_zona,
                "subzona": subzona,
                "area": area_zona_real,
                "porcentaje": porcentaje,
                "color": color_zona,
                "geometria": zona_recortada
            })
            contador += 1

with col_data:
    st.subheader("Cuadro de Áreas")
    if st.session_state.terreno_geom:
        st.success(f"Terreno Base: {area_real_terreno:,.2f} m²")
    else:
        st.warning("⚠️ Dibuja primero el Límite del Terreno.")

    if st.session_state.zonas:
        datos_tabla = [{
            "ID": z["id"], "Zona": z["nombre"], "Subzona": z["subzona"],
            "Área (m²)": f"{z['area']:,.2f}", "Porcentaje": f"{z['porcentaje']:.1f}%"
        } for z in st.session_state.zonas]
        st.dataframe(datos_tabla, use_container_width=True)
    else:
        st.info("No hay zonas dibujadas todavía.")

st.markdown("---")
st.header("4. Lámina Arquitectónica Esquemática")

if st.session_state.terreno_geom:
    fig = go.Figure()
    x_terr, y_terr = st.session_state.terreno_geom.exterior.xy
    fig.add_trace(go.Scatter(
        x=list(x_terr), y=list(y_terr), fill="toself",
        fillcolor="rgba(240, 240, 240, 0.4)", line=dict(color="#2C3E50", width=3, dash="dash"),
        name="Terreno"
    ))

    for z in st.session_state.zonas:
        geom = z["geometria"]
        if not geom.is_empty:
            geoms = [geom] if geom.geom_type == 'Polygon' else list(geom.geoms)
            for g in geoms:
                x_z, y_z = g.exterior.xy
                hex_c = z["color"].lstrip('#')
                rgb = tuple(int(hex_c[i:i+2], 16) for i in (0, 2, 4))
                fig.add_trace(go.Scatter(
                    x=list(x_z), y=list(y_z), fill="toself",
                    fillcolor=f"rgba({rgb[0]},{rgb[1]},{rgb[2]}, 0.65)",
                    line=dict(color=z["color"], width=1.5),
                    name=f"<b>{z['nombre']}</b><br>{z['area']:,.1f} m² ({z['porcentaje']:.1f}%)"
                ))

    fig.update_layout(
        plot_bgcolor="white", paper_bgcolor="white",
        xaxis=dict(showgrid=False, showticklabels=False),
        yaxis=dict(showgrid=False, showticklabels=False, scaleanchor="x", scaleratio=1),
        height=600
    )
    st.plotly_chart(fig, use_container_width=True)