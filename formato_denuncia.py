from fpdf import FPDF
import re
import os

# Texto base del formato con los campos a completar
TEXTO_BASE = """
FORMATO DE DENUNCIA EN MATERIA DE VIOLENCIA POLÍTICA CONTRA LAS MUJERES EN RAZÓN DE GÉNERO

UNIDAD TÉCNICA DE LO CONTENCIOSO ELECTORAL DE LA SECRETARÍA EJECUTIVA  
DEL INSTITUTO NACIONAL ELECTORAL

Yo, {nombre_completo}, por propio derecho, con número telefónico {telefono},  
señalando como domicilio para oír y recibir todo tipo de notificaciones y documentos en: {domicilio},  
como correo electrónico para notificaciones electrónicas: {correo},  
y autorizando para tales efectos a: {persona_autorizada1} y {persona_autorizada2},  
comparezco y expongo:

-------------------------------------------------
HECHOS  
1. Fecha de los hechos: {fecha_hechos}  
2. Lugar donde sucedieron los hechos: {lugar_hechos}  
3. Persona denunciada: {persona_denunciada}  
4. Relación con la persona denunciada: {relacion_denunciada}  
5. Narración de los hechos:  
   - {narracion1}  
   - {narracion2}  

Los hechos narrados han causado una afectación en la suscrita, toda vez que {afectacion}.

-------------------------------------------------
MEDIDAS CAUTELARES SOLICITADAS  

1. {medida1}  
2. {medida2}  
3. {medida3}  

-------------------------------------------------
DATOS PERSONALES DE LA QUEJOSA  

- Nombre completo: {nombre_completo}  
- Candidatura o puesto: {puesto}  
- Grupo étnico o comunidad indígena (si aplica): {grupo_etnico}  
- Teléfono y/o correo electrónico: {telefono}  
- Domicilio en donde pueda ser localizada: {domicilio}  
"""

def extraer_datos(texto):
    """Extrae los datos clave del texto proporcionado por el usuario usando expresiones regulares."""
    print(f"📜 Texto recibido en extraer_datos:\n{texto}\n")  # Depuración

    datos = {
        "nombre_completo": re.search(r"Mi nombre es ([^.,]+)", texto),
        "telefono": re.search(r"mi teléfono es ([^.,]+)", texto),
        "domicilio": re.search(r"vivo en ([^.,]+)", texto),
        "correo": re.search(r"mi correo es ([^.,]+)", texto),
        "persona_autorizada1": "",
        "persona_autorizada2": "",
        "fecha_hechos": re.search(r"el ([0-9]{1,2} de [a-zA-Z]+ de [0-9]{4})", texto, re.IGNORECASE),
        "lugar_hechos": re.search(r"en ([^.,]+) ocurrieron los hechos", texto),
        "persona_denunciada": re.search(
            r"(denuncio a|quiero denunciar a|quiero denunciar que|acuso a|reporto a|denuncio que|señalo a)[^\n]*? ([A-ZÁÉÍÓÚÑa-záéíóúñ]+(?:\s[A-ZÁÉÍÓÚÑa-záéíóúñ]+)*)", 
            texto, 
            re.IGNORECASE
        ),
        "relacion_denunciada": re.search(r"quien es mi ([^.,]+)", texto),
        "narracion1": re.search(r"porque (.+)", texto, re.IGNORECASE),
        "narracion2": "",
        "afectacion": re.search(r"esto me afectó porque ([^\n]+)", texto),
        "medida1": re.search(r"Solicito como medida ([^.,]+)", texto),
        "medida2": "",
        "medida3": "",
        "puesto": re.search(r"mi puesto es ([^.,]+)", texto),
        "grupo_etnico": re.search(r"pertenezco a ([^.,]+)", texto)
    }
    
    # Convertir los resultados de regex a cadenas de texto
    for key, match in datos.items():
        if key == "persona_denunciada" and match:
            datos[key] = match.group(2).strip()  # Extrae solo el nombre, ignorando la parte del disparador
        else:
            datos[key] = match.group(1).strip() if match else ""

        print(f"🔹 {key}: {datos[key]}")  # Depuración: Mostrar cada dato extraído

    # Definir qué datos son esenciales
    datos_esenciales = ["nombre_completo", "telefono", "domicilio", "fecha_hechos", "lugar_hechos", "persona_denunciada", "narracion1"]

    # Detectar qué datos esenciales faltan
    datos_faltantes = [campo for campo in datos_esenciales if not datos[campo]]

    return datos, datos_faltantes


def generar_pdf(datos, output_path="static/formato_denuncia.pdf"):
    """Genera un PDF con los datos proporcionados."""
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    
    texto_completo = TEXTO_BASE.format(**datos)
    
    for line in texto_completo.split("\n"):
        pdf.cell(0, 10, line, ln=True)
    
    pdf.output(output_path)
    return output_path

def procesar_denuncia(texto_usuario):
    print("🔍 Recibí solicitud para procesar denuncia.")  
    print(f"📜 Texto recibido: {texto_usuario}")  # Agregar esta línea para depuración
    
    datos, datos_faltantes = extraer_datos(texto_usuario)  # Extraer datos y detectar faltantes

    if datos_faltantes:
        print(f"❌ Faltan los siguientes datos: {', '.join(datos_faltantes)}")
        return {"error": "Faltan datos", "faltantes": datos_faltantes}  # Devuelve los datos faltantes

    pdf_path = generar_pdf(datos)

    if os.path.exists(pdf_path):
        print(f"✅ PDF generado correctamente: {pdf_path}")  
        return pdf_path  # 🔴 Aquí aseguramos que se devuelve solo la ruta del archivo como cadena
    else:
        print("❌ Error: El PDF no se generó correctamente.")
        return {"error": "No se pudo generar el PDF"}
