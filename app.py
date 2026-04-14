import streamlit as st
import pandas as pd
import requests
import os
import zipfile
import io
import time
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

st.set_page_config(page_title="Extractor IA", page_icon="🤖", layout="wide")

st.title("🤖 Extractor Automático de Inventario")
st.markdown("Extrae **nombre real**, **descripciones** e **imágenes** de productos")

# Sidebar
with st.sidebar:
    st.header("⚙️ Configuración")
    st.markdown("Pega las URLs de los productos (una por línea)")
    urls_input = st.text_area("📝 URLs", height=200, 
                               placeholder="https://www.nardioutdoor.com/es/productos/mesas/tevere-147-extensible_113_379.htm\nhttps://www.nardioutdoor.com/es/productos/tumbonas/plano_207_402.htm")
    
    extraer_imagenes = st.checkbox("📸 Descargar imágenes", value=True)
    iniciar = st.button("🚀 INICIAR EXTRACCIÓN", type="primary", use_container_width=True)

def extraer_producto(driver, url):
    """Extrae datos reales de una página de producto"""
    try:
        driver.get(url)
        time.sleep(3)
        
        # Nombre del producto (h1)
        try:
            nombre = driver.find_element(By.CSS_SELECTOR, "h1").text
        except:
            nombre = "No encontrado"
        
        # Descripción corta
        try:
            desc_corta = driver.find_element(By.CSS_SELECTOR, ".product-description p, .description p, [class*='description'] p").text
        except:
            desc_corta = "No disponible"
        
        # Descripción larga
        try:
            desc_larga_elements = driver.find_elements(By.CSS_SELECTOR, ".technical-details, .product-details, .attributes, [class*='detail'], [class*='spec'], .features")
            desc_larga = "\n".join([el.text for el in desc_larga_elements if el.text])
            if not desc_larga:
                desc_larga = desc_corta
        except:
            desc_larga = desc_corta
        
        # URL de la imagen
        url_imagen = None
        try:
            selectores_imagen = [
                ".product-gallery img",
                ".main-image img",
                ".carousel img",
                "[class*='gallery'] img",
                "[class*='image'] img",
                "img[property='image']"
            ]
            for selector in selectores_imagen:
                try:
                    img = driver.find_element(By.CSS_SELECTOR, selector)
                    url_imagen = img.get_attribute("src")
                    if url_imagen and not url_imagen.startswith("data:"):
                        break
                except:
                    continue
        except:
            pass
        
        return {
            "nombre": nombre,
            "descripcion_corta": desc_corta,
            "descripcion_larga": desc_larga,
            "url_imagen": url_imagen,
            "url_producto": url
        }
    except Exception as e:
        return {"error": str(e), "url_producto": url}

def descargar_imagen(url, nombre):
    """Descarga una imagen y devuelve su contenido"""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            nombre_limpio = re.sub(r'[^\w\-_\.]', '_', nombre)
            return response.content, f"{nombre_limpio}.jpg"
    except:
        pass
    return None, None

if iniciar and urls_input:
    urls = [u.strip() for u in urls_input.split('\n') if u.strip()]
    
    st.info(f"🔄 Procesando {len(urls)} productos... Esto puede tomar unos minutos")
    
    # Configurar driver
    with st.spinner("Inicializando navegador..."):
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    
    resultados = []
    imagenes_data = []
    progress_bar = st.progress(0)
    
    for i, url in enumerate(urls):
        st.write(f"📌 Extrayendo {i+1}/{len(urls)}: {url[:60]}...")
        
        producto = extraer_producto(driver, url)
        resultados.append(producto)
        
        if extraer_imagenes and producto.get('url_imagen'):
            img_content, img_nombre = descargar_imagen(producto['url_imagen'], producto.get('nombre', 'producto'))
            if img_content:
                imagenes_data.append((img_nombre, img_content))
        
        progress_bar.progress((i + 1) / len(urls))
    
    driver.quit()
    
    # Mostrar resultados
    st.success(f"✅ Extracción completada! {len(resultados)} productos procesados")
    
    # Crear DataFrame
    df = pd.DataFrame(resultados)
    
    # Mostrar vista previa
    st.subheader("📊 Vista previa de datos extraídos")
    st.dataframe(df[['nombre', 'descripcion_corta', 'url_producto']].head(10))
    
    # Preparar descargas
    col1, col2 = st.columns(2)
    
    with col1:
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Descargar CSV", csv, "inventario_completo.csv", "text/csv")
    
    with col2:
        if imagenes_data:
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
                for img_nombre, img_content in imagenes_data:
                    zip_file.writestr(img_nombre, img_content)
            st.download_button("🖼️ Descargar Imágenes (ZIP)", zip_buffer.getvalue(), "imagenes.zip", "application/zip")
    
    # Estadísticas
    st.subheader("📈 Estadísticas")
    c1, c2, c3 = st.columns(3)
    c1.metric("Productos extraídos", len(resultados))
    c2.metric("Imágenes descargadas", len(imagenes_data))
    c3.metric("Con descripción", sum(1 for r in resultados if r.get('descripcion_corta') != "No disponible"))
    
    st.info("💡 **Tip:** Para más productos, pega más URLs. El script extrae datos REALES de cada página.")

else:
    st.info("👈 **Instrucciones:** Pega las URLs de los productos en el panel izquierdo y haz clic en 'INICIAR EXTRACCIÓN'")
