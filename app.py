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
    """Extrae datos usando requests y BeautifulSoup (sin Selenium)"""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 1. Nombre del producto (h1)
        nombre = "No encontrado"
        h1 = soup.find('h1')
        if h1:
            nombre = h1.get_text(strip=True)
        
        # 2. Descripción corta
        desc_corta = "No disponible"
        selectores_desc_corta = [
            '.product-description p',
            '.description p',
            '[class*="description"] p',
            '.short-description',
            '.product-short-description'
        ]
        for selector in selectores_desc_corta:
            elemento = soup.select_one(selector)
            if elemento:
                desc_corta = elemento.get_text(strip=True)[:500]
                break
        
        # 3. Descripción larga
        desc_larga = desc_corta
        selectores_desc_larga = [
            '.technical-details',
            '.product-details',
            '.attributes',
            '[class*="detail"]',
            '[class*="spec"]',
            '.features',
            '.product-description'
        ]
        for selector in selectores_desc_larga:
            elemento = soup.select_one(selector)
            if elemento:
                texto = elemento.get_text(strip=True)
                if len(texto) > len(desc_larga):
                    desc_larga = texto[:2000]
                    break
        
        # 4. URL de la imagen
        url_imagen = None
        selectores_img = [
            '.product-gallery img',
            '.main-image img',
            '.carousel img',
            '[class*="gallery"] img',
            '[class*="image"] img',
            'meta[property="og:image"]',
            'img[property="image"]',
            '.product-image img',
            'img[class*="product"]'
        ]
        
        for selector in selectores_img:
            if selector.startswith('meta'):
                elemento = soup.find('meta', property='og:image')
                if elemento and elemento.get('content'):
                    url_imagen = elemento.get('content')
                    break
            else:
                elemento = soup.select_one(selector)
                if elemento and elemento.get('src'):
                    url_imagen = elemento.get('src')
                    if url_imagen and not url_imagen.startswith('data:'):
                        break
        
        # Convertir URL relativa a absoluta
        if url_imagen and not url_imagen.startswith('http'):
            url_imagen = urljoin(url, url_imagen)
        
        return {
            "nombre": nombre,
            "descripcion_corta": desc_corta,
            "descripcion_larga": desc_larga,
            "url_imagen": url_imagen if url_imagen else "No disponible",
            "url_producto": url
        }
        
    except Exception as e:
        return {
            "nombre": f"Error: {str(e)[:50]}",
            "descripcion_corta": "No se pudo extraer",
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
            # Verificar que sea una imagen
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
        
        # Descargar imagen si está disponible
        if extraer_imagenes and producto['url_imagen'] and producto['url_imagen'] != "No disponible":
            img_content, img_nombre = descargar_imagen(producto['url_imagen'], producto['nombre'])
            if img_content:
                imagenes_data.append((img_nombre, img_content))
        
        progress_bar.progress((i + 1) / len(urls))
    
    status_text.text("✅ Extracción completada!")
    
    # Mostrar resultados
    st.success(f"✅ Procesados {len(resultados)} productos")
    
    # Crear DataFrame
    df = pd.DataFrame(resultados)
    
    # Mostrar vista previa
    st.subheader("📊 Vista previa")
    st.dataframe(df[['nombre', 'descripcion_corta', 'url_producto']].head(10))
    
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
        else:
            st.info("No se descargaron imágenes")
    
    # Estadísticas
    st.subheader("📈 Estadísticas")
    c1, c2, c3 = st.columns(3)
    c1.metric("Productos", len(resultados))
    c2.metric("Imágenes", len(imagenes_data))
    c3.metric("Con descripción", sum(1 for r in resultados if r['descripcion_corta'] != "No disponible"))

else:
    st.info("👈 **Instrucciones:** Pega las URLs de los productos y haz clic en 'INICIAR EXTRACCIÓN'")
