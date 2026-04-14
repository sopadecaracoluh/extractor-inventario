import streamlit as st
import pandas as pd
import requests
import zipfile
import io
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin

st.set_page_config(page_title="Extractor IA", page_icon="🤖", layout="wide")

st.title("🤖 Extractor Automático de Inventario")
st.markdown("Extrae **nombre**, **descripciones** e **imágenes** de productos web")

# Sidebar
with st.sidebar:
    st.header("⚙️ Configuración")
    st.markdown("Pega las URLs de los productos (una por línea)")
    urls_input = st.text_area("📝 URLs", height=200, 
                               placeholder="https://www.nardioutdoor.com/es/productos/mesas/tevere-147-extensible_113_379.htm\nhttps://www.nardioutdoor.com/es/productos/tumbonas/plano_207_402.htm")
    
    extraer_imagenes = st.checkbox("📸 Descargar imágenes", value=True)
    iniciar = st.button("🚀 INICIAR EXTRACCIÓN", type="primary", use_container_width=True)

def extraer_producto(url):
    """Extrae datos usando requests y BeautifulSoup"""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 1. Nombre del producto
        nombre = "No encontrado"
        h1 = soup.find('h1')
        if h1:
            nombre = h1.get_text(strip=True)
        
        # 2. Descripción corta - Buscar en múltiples lugares
        desc_corta = "No disponible"
        
        # Método 1: Buscar el párrafo después del h1
        if h1:
            siguiente = h1.find_next('p')
            if siguiente and len(siguiente.get_text(strip=True)) > 20:
                desc_corta = siguiente.get_text(strip=True)
        
        # Método 2: Buscar clase específica de Nardi
        if desc_corta == "No disponible":
            posibles = soup.find_all(['p', 'div'], class_=re.compile(r'description|desc|product-description|abstract'))
            for elem in posibles:
                texto = elem.get_text(strip=True)
                if len(texto) > 30 and len(texto) < 500:
                    desc_corta = texto
                    break
        
        # Método 3: Buscar cualquier párrafo con texto significativo cerca del h1
        if desc_corta == "No disponible":
            for elem in soup.find_all('p'):
                texto = elem.get_text(strip=True)
                if 50 < len(texto) < 500 and not texto.startswith('Peso'):
                    desc_corta = texto
                    break
        
        # 3. Descripción larga (detalles técnicos, especificaciones)
        desc_larga = desc_corta
        
        # Buscar todas las secciones de detalles
        detalles = []
        
        # Tablas de especificaciones
        for tabla in soup.find_all('table'):
            texto_tabla = tabla.get_text(strip=True)
            if len(texto_tabla) > 20:
                detalles.append(texto_tabla)
        
        # Listas de características
        for lista in soup.find_all(['ul', 'dl']):
            texto_lista = lista.get_text(strip=True)
            if len(texto_lista) > 20:
                detalles.append(texto_lista)
        
        # Divs con clases específicas
        for div in soup.find_all('div', class_=re.compile(r'detail|spec|technical|attribute|feature|info')):
            texto_div = div.get_text(strip=True)
            if 30 < len(texto_div) < 2000:
                detalles.append(texto_div)
        
        if detalles:
            desc_larga = "\n\n".join(detalles[:3])  # Máximo 3 secciones
        
        # 4. URL de la imagen
        url_imagen = None
        
        # Intentar diferentes métodos
        # Meta tag og:image
        meta_og = soup.find('meta', property='og:image')
        if meta_og and meta_og.get('content'):
            url_imagen = meta_og.get('content')
        
        # Imagen principal del producto
        if not url_imagen:
            selectores_img = [
                '.product-gallery img',
                '.main-image img',
                '.carousel img',
                '.product-image img',
                'img[property="image"]',
                '.image-main img',
                '#main-image img'
            ]
            for selector in selectores_img:
                img = soup.select_one(selector)
                if img and img.get('src'):
                    url_imagen = img.get('src')
                    break
        
        # Cualquier imagen grande
        if not url_imagen:
            for img in soup.find_all('img'):
                src = img.get('src', '')
                clase = img.get('class', [])
                if 'logo' not in str(clase).lower() and 'icon' not in src.lower():
                    if 'jpg' in src.lower() or 'png' in src.lower() or 'webp' in src.lower():
                        if 'product' in str(clase).lower() or 'gallery' in str(clase).lower():
                            url_imagen = src
                            break
        
        # Convertir URL relativa a absoluta
        if url_imagen and not url_imagen.startswith('http'):
            url_imagen = urljoin(url, url_imagen)
        
        return {
            "nombre": nombre,
            "descripcion_corta": desc_corta,
            "descripcion_larga": desc_larga[:2000],
            "url_imagen": url_imagen if url_imagen else "No disponible",
            "url_producto": url
        }
        
    except Exception as e:
        return {
            "nombre": f"Error",
            "descripcion_corta": str(e)[:100],
            "descripcion_larga": "Error al conectar",
            "url_imagen": "No disponible",
            "url_producto": url
        }

def descargar_imagen(url, nombre):
    """Descarga una imagen desde URL"""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            content_type = response.headers.get('content-type', '')
            if 'image' in content_type:
                nombre_limpio = re.sub(r'[^\w\-_\.]', '_', nombre)
                return response.content, f"{nombre_limpio}.jpg"
    except:
        pass
    return None, None

if iniciar and urls_input:
    urls = [u.strip() for u in urls_input.split('\n') if u.strip()]
    
    st.info(f"🔄 Procesando {len(urls)} productos...")
    
    resultados = []
    imagenes_data = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, url in enumerate(urls):
        status_text.text(f"📌 Extrayendo {i+1}/{len(urls)}: {url[:80]}...")
        
        producto = extraer_producto(url)
        resultados.append(producto)
        
        # Mostrar qué se encontró
        st.write(f"  📝 {producto['nombre']}")
        if producto['descripcion_corta'] != "No disponible":
            st.write(f"  ✨ Descripción: {producto['descripcion_corta'][:100]}...")
        
        # Descargar imagen
        if extraer_imagenes and producto['url_imagen'] and producto['url_imagen'] != "No disponible":
            img_content, img_nombre = descargar_imagen(producto['url_imagen'], producto['nombre'])
            if img_content:
                imagenes_data.append((img_nombre, img_content))
                st.write(f"  🖼️ Imagen descargada")
        
        progress_bar.progress((i + 1) / len(urls))
    
    status_text.text("✅ Extracción completada!")
    
    # Mostrar resultados
    st.success(f"✅ Procesados {len(resultados)} productos")
    
    # Crear DataFrame
    df = pd.DataFrame(resultados)
    
    # Mostrar vista previa
    st.subheader("📊 Vista previa")
    st.dataframe(df[['nombre', 'descripcion_corta', 'url_producto']].head(10))
    
    # Mostrar ejemplo de descripción larga
    if resultados and resultados[0]['descripcion_larga'] != "No disponible":
        with st.expander("📖 Ver ejemplo de descripción larga"):
            st.write(resultados[0]['descripcion_larga'])
    
    # Botones de descarga
    col1, col2 = st.columns(2)
    
    with col1:
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Descargar CSV",
            data=csv,
            file_name="inventario_productos.csv",
            mime="text/csv"
        )
    
    with col2:
        if imagenes_data:
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
                for img_nombre, img_content in imagenes_data:
                    zip_file.writestr(img_nombre, img_content)
            st.download_button(
                label="🖼️ Descargar Imágenes (ZIP)",
                data=zip_buffer.getvalue(),
                file_name="imagenes_productos.zip",
                mime="application/zip"
            )
    
    # Estadísticas
    st.subheader("📈 Estadísticas")
    c1, c2, c3 = st.columns(3)
    c1.metric("Productos", len(resultados))
    c2.metric("Imágenes", len(imagenes_data))
    c3.metric("Con descripción", sum(1 for r in resultados if r['descripcion_corta'] != "No disponible"))

else:
    st.info("👈 **Instrucciones:** Pega las URLs de los productos y haz clic en 'INICIAR EXTRACCIÓN'")
