try:
    import cloudscraper
except ImportError:
    cloudscraper = None

import requests
import pandas as pd
import json
from bs4 import BeautifulSoup
from urllib.parse import urlsplit, urlunsplit


def limpiar_link(url):
    parsed = urlsplit(url)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, '', ''))


def es_fuera_de_capital(ubicacion):
    texto = ubicacion.lower()
    return all(keyword not in texto for keyword in ['capital federal', 'caba', 'ciudad autónoma'])


def create_scraper():
    if cloudscraper is not None:
        return cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'desktop': True
            }
        )

    print('⚠️ cloudscraper no está disponible. Usando requests como respaldo.')
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'es-AR,es;q=0.9,en;q=0.8',
    })
    return session


def esta_disponible(scraper, url):
    try:
        response = scraper.get(url, timeout=20, allow_redirects=True)
        # Zonaprop usa 410 para avisos caídos/no disponibles.
        # También verificamos si redirige a la home de búsqueda o si el contenido indica que no está disponible
        if response.status_code == 410 or "not-found" in response.url or "/departamentos-alquiler" in response.url:
            return False
        
        # Validación de contenido (por si Zonaprop devuelve un 200 pero con cartel de finalizado)
        soup = BeautifulSoup(response.text, 'html.parser')
        texto_pagina = soup.get_text().lower()
        if "finalizado" in texto_pagina or "ya no está disponible" in texto_pagina or "aviso pausado" in texto_pagina:
            return False
            
        return True
    except Exception:
        return False

def hacer_scraping():
    # Configuración del "disfraz" para saltar bloqueos o usar requests si cloudscraper no está instalado
    scraper = create_scraper()
    
    print("🚀 Iniciando búsqueda de oportunidades reales...")
    
    resultados = []

    search_targets = [
        ("Capital Federal", "https://www.zonaprop.com.ar/departamentos-alquiler-capital-federal-dueno-directo-orden-publicado-descendente.html"),
        ("Fuera de Capital", "https://www.zonaprop.com.ar/departamentos-alquiler.html")
    ]
    seen_links = set()

    for target_name, target_url in search_targets:
        print(f"🔎 Buscando {target_name}...")
        try:
            response = scraper.get(target_url, timeout=30)
            if response.status_code != 200:
                print(f"⚠️ No se pudo acceder a {target_name}: {response.status_code}")
                continue

            soup = BeautifulSoup(response.text, 'html.parser')
            propiedades = soup.find_all('div', {'data-qa': 'posting PROPERTY'})

            for prop in propiedades:
                try:
                    enlace = prop.find('a', href=True)
                    if not enlace or '/propiedades/' not in enlace['href']:
                        continue

                    link_final = limpiar_link("https://www.zonaprop.com.ar" + enlace['href'])
                    if link_final in seen_links:
                        continue
                    seen_links.add(link_final)

                    precio = prop.find(attrs={"data-qa": "POSTING_CARD_PRICE"}).text.strip()
                    ubicacion = prop.find(attrs={"data-qa": "POSTING_CARD_LOCATION"}).text.strip()
                    titulo = prop.find('h3').text.strip()

                    if target_name == "Fuera de Capital" and not es_fuera_de_capital(ubicacion):
                        continue

                    resultados.append({
                        "Zona": target_name,
                        "Barrio": ubicacion,
                        "Precio": precio,
                        "Descripcion": titulo,
                        "Link": link_final
                    })
                except Exception:
                    continue
        except Exception as e:
            print(f"❌ Error en la conexión de {target_name}: {e}")

    # --- PROCESAMIENTO Y LIMPIEZA ---
    if resultados:
        df = pd.DataFrame(resultados)
        
        # Filtro de Calidad: Eliminamos duplicados basados en el contenido
        # (Si el barrio, precio y descripción son iguales, es la misma propiedad)
        total_sucios = len(df)
        df = df.drop_duplicates(subset=['Barrio', 'Precio', 'Descripcion'], keep='first')
        total_limpios = len(df)
        df = df[df['Link'].apply(lambda link: esta_disponible(scraper, link))]
        total_disponibles = len(df)
        
        print(f"🔥 ¡ÉXITO! Se capturaron {total_sucios} avisos.")
        print(f"✨ Limpieza completada: Se eliminaron {total_sucios - total_limpios} repetidos.")
        print(f"✅ Disponibilidad validada: {total_disponibles} avisos activos.")
        
        # Guardar JSON para la web
        resultados_limpios = df.to_dict(orient='records')
        with open('propiedades.json', 'w', encoding='utf-8') as f:
            json.dump(resultados_limpios, f, indent=4, ensure_ascii=False)
        
        # Guardar Excel para el cliente
        df.to_excel('Reporte_Oportunidades_InmoData.xlsx', index=False)
        print("✅ Reporte_Oportunidades_InmoData.xlsx generado y limpio.")
    else:
        print("⚠️ No se encontraron resultados nuevos. Verifica el sitio o el respaldo.")

if __name__ == "__main__":
    hacer_scraping()
