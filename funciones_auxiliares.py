from flask import jsonify, session
from flask_session import Session
import os
import gtts  # Google Text-to-Speech
from pydub import AudioSegment
from formato_denuncia import procesar_denuncia
import markdown
import re



# ----------------------------------------------------------------------
#                               AUDIO
# ----------------------------------------------------------------------


AUDIO_OUTPUT_FOLDER = "static/audio"
os.makedirs(AUDIO_OUTPUT_FOLDER, exist_ok=True)

def text_to_speech(text):
    """Genera un archivo de audio a partir del texto usando gTTS"""
    filename = f"response_{hash(text)}.mp3"
    filepath = os.path.join(AUDIO_OUTPUT_FOLDER, filename)

    tts = gtts.gTTS(text, lang="es")  # Generar audio en español
    tts.save(filepath)

    return f"/{filepath}"  # Retorna la URL relativa del archivo


# ----------------------------------------------------------------------
#                           HELPER FUNCTIONS
# ----------------------------------------------------------------------

def handle_cancelar_proceso():
    """Cancelar el llenado de datos."""
    session.pop("datos_faltantes", None)
    session.pop("datos_usuario", None)
    texto = "Proceso cancelado. ¿En qué más puedo ayudarte?"
    audio_response_path = text_to_speech(texto)
    return jsonify({
        "response": "❌ Proceso cancelado. ¿En qué más puedo ayudarte?",
        "audio_response": audio_response_path
    })


def handle_omitir_dato(dato_actual, datos_faltantes, datos_usuario):
    """
    Maneja la lógica de 'omitir' un dato (incluyendo la omisión automática 
    de otros campos dependientes si 'tipo_prueba' fue omitido).
    """
    datos_usuario[dato_actual] = "_________________________"
    remaining_faltantes = datos_faltantes[1:]  # Avanzamos al siguiente dato

    # Lógica especial para 'narraciones'
    if dato_actual == "narraciones":
        if "narraciones" not in datos_usuario:
            datos_usuario["narraciones"] = []
        if not session.get("ejemplo_narraciones_mostrado", False):
            session["ejemplo_narraciones_mostrado"] = True
            ejemplo_narracion = (
                "Ejemplo de narración de hechos:\n\n"
                "El cinco de febrero de dos mil diecisiete, estando presentes en la oficina de XXX, "
                "ubicada en las calles de XXX, el denunciado me agredió verbalmente al señalar que "
                "no debía participar como candidata al cargo de XXXX, indicando expresamente: "
                "“ustedes las mujeres no sirven para esto de la política, no tienen que salir de su casa "
                "y deben quedarse en la cocina”.\n\n"
                "Con estas expresiones, se vulneran derechos como la participación política, "
                "la no discriminación y la vida libre de violencia.\n\n"
                "Por favor, ingresa tu primer relato de hechos ahora. O escribe 'omitir' si no deseas narrarlo, "
                "o 'cancelar' para salir."
            )
            return jsonify({"response": ejemplo_narracion})

    # Lógica especial para 'tipo_prueba'
    if dato_actual == "tipo_prueba":
        session["tipo_prueba_omitido"] = True
        session["campos_dependientes_tipo_prueba"] = {
            "quien_desahoga", "numero_notarial", "notario_publico_numero",
            "donde_funciones_notario", "fecha_intrumento_notarial",
            "prueba_confesional", "prueba_testimonial", "documento_prueba",
            "numeros_prueba","folio","fecha_folio", "documentos_oficiales"
        }

    if session.get("tipo_prueba_omitido", False):
        remaining_faltantes = [
            d for d in remaining_faltantes if d not in session["campos_dependientes_tipo_prueba"]
        ]

    session["datos_faltantes"] = remaining_faltantes
    session["datos_usuario"] = datos_usuario

    # Construir el texto y su audio
    texto = f"Se ha omitido **{dato_actual}** automáticamente porque omitiste `tipo_prueba`"
    audio_response_path = text_to_speech(texto)
    
    # Si este mismo dato es dependiente de tipo_prueba
    if dato_actual in session.get("campos_dependientes_tipo_prueba", set()):
        return jsonify({
            "response": markdown.markdown(f"✅ Se ha omitido **{dato_actual}** automáticamente porque omitiste `tipo_prueba`."),
            "audio_response": audio_response_path
        })

    # Omitir automáticamente todos los siguientes dependientes
    while session["datos_faltantes"] and session["datos_faltantes"][0] in session.get("campos_dependientes_tipo_prueba", set()):
        omitido = session["datos_faltantes"].pop(0)
        datos_usuario[omitido] = "_________________________"

    # Si aún quedan datos
    if session["datos_faltantes"]:
        siguiente_dato = session["datos_faltantes"][0]
        # Manejo especial de medidas_cautelares, medidas_proteccion, etc.
        if siguiente_dato == "medidas_cautelares":
            opciones_str = "\n".join(f"{i+1}. {op}" for i, op in enumerate(MEDIDAS_CAUTELARES_OPCIONES))
            session["pidiendo_medidas_cautelares"] = True
            texto_ret = (
                f"Se ha omitido **{dato_actual}**. Ahora, selecciona las **medidas cautelares** que solicitas. "
                f"Opciones:\n{opciones_str}\nPara seleccionar, escribe los números separados por comas (ej: '1,3'). "
                "Escribe 'otra' para agregar una medida no listada. Cuando termines, escribe 'terminar'."
            )
            audio_response = text_to_speech(texto_ret)
            return jsonify({
                "response": markdown.markdown(
                    f"✅ Se ha omitido **{dato_actual}**.\n\n"
                    "Ahora, selecciona las **medidas cautelares** que solicitas...\n\n"
                    f"{opciones_str}\n\n"
                    "Para seleccionar, escribe los números separados por comas (ej: '1,3'). "
                    "Escribe 'otra' para agregar una medida no listada. "
                    "Cuando termines, escribe 'terminar'."
                ),
                "audio_response": audio_response
            })
        elif siguiente_dato == "medidas_proteccion":
            opciones_str = "\n".join(f"{i+1}. {op}" for i, op in enumerate(MEDIDAS_PROTECCION_OPCIONES))
            session["pidiendo_medidas_proteccion"] = True
            texto_ret = (
                f"✅ Se ha omitido **{dato_actual}**. "
                "Ahora, selecciona las **medidas de protección** que solicitas. "
                f"Estas son las opciones:\n{opciones_str}"
            )
            audio_response = text_to_speech(texto_ret)
            return jsonify({
                "response": markdown.markdown(
                    f"✅ Se ha omitido **{dato_actual}**.\n\n"
                    "Ahora, selecciona las **medidas de protección** que solicitas...\n\n"
                    f"{opciones_str}\n\n"
                    "Para seleccionar, escribe los números separados por comas (ej: '1,3'). "
                    "Escribe 'otra' para agregar una medida no listada. "
                    "Cuando termines, escribe 'terminar'."
                ),
                "audio_response": audio_response
            })
        elif siguiente_dato == "tipo_prueba":
            session["ha_preguntado_tipo_prueba"] = True
            texto_ret = (
                "¿Qué tipo de prueba deseas ofrecer? Elige una opción:\n"
                "1️⃣ Confesional\n2️⃣ Testimonial\n3️⃣ Documental Pública o Privada\n"
                "4️⃣ Presuncional Legal y Humana\n5️⃣ Instrumental de Actuaciones\n"
                "Escribe el número de la opción o 'omitir/cancelar'."
            )
            audio_response = text_to_speech(texto_ret)
            return jsonify({
                "response": texto_ret,
                "audio_response": audio_response
            })
        # Pregunta de forma genérica por el siguiente dato
        desc = field_info.get(siguiente_dato, {}).get("descripcion", "")
        ejemp = field_info.get(siguiente_dato, {}).get("ejemplo", "")
        texto_ret = (
            f"Se ha omitido **{dato_actual}**. Ahora, **{siguiente_dato}** es importante {desc}. {ejemp}. "
            "¿Podrías proporcionarlo ahora? O escribe 'omitir' si no deseas darlo, o 'cancelar' para detener."
        )
        audio_response = text_to_speech(texto_ret)
        return jsonify({
            "response": markdown.markdown(
                f"✅ Se ha omitido **{dato_actual}**.\n\n"
                f"Ahora, **{siguiente_dato}** es importante {desc}.\n\n"
                f"{ejemp}\n\n"
                "¿Podrías proporcionarlo ahora? "
                "O escribe 'omitir' si no deseas darlo, o 'cancelar' para detener el proceso."
            ),
            "audio_response": audio_response
        })
    else:
        # Si no hay más datos faltantes, generamos la denuncia
        return handle_generar_denuncia(datos_usuario)
    

def handle_generar_denuncia(datos_usuario):
    """Genera la denuncia y retorna la respuesta final en JSON."""
    try:
        resultado = procesar_denuncia(datos_usuario)
        if isinstance(resultado, dict) and "error" in resultado:
            # Faltan datos obligatorios
            session["datos_faltantes"] = resultado["faltantes"]
            return jsonify({
                "response": markdown.markdown(f"⚠️ Faltan datos: {', '.join(resultado['faltantes'])}. Por favor, ingrésalos para continuar.")
            })
        session["pdf_path"] = resultado
        # Limpiar la sesión
        session.pop("datos_faltantes", None)
        session.pop("datos_usuario", None)
        session.pop("tipo_prueba_omitido", None)
        session.pop("campos_dependientes_tipo_prueba", None)
        
        texto = ("La denuncia ha sido generada correctamente. Puedes descargarla en el link que te genere. "
                 "Este es un formato de denuncia con los datos proporcionados. "
                 "Puedes revisarlo y editarlo si lo deseas. ¡Estoy aquí para ayudarte!")
        audio_response_path = text_to_speech(texto)
        return jsonify({
            "response": (
                "✅ La denuncia ha sido generada correctamente. "
                "Puedes descargarla aquí: /download_sue\n\n"
                "Este es un formato de denuncia con los datos proporcionados. "
                "Puedes revisarlo y editarlo si lo deseas. ¡Estoy aquí para ayudarte! 😊"
            ),
            "audio_response": audio_response_path
        })
    except Exception as e:
        return jsonify({
            "response": f"❌ Error al generar la denuncia: {str(e)}"
        }), 500

# ----------------------------------------------------------------------
#                           VALIDACIONES
# ----------------------------------------------------------------------


def es_nombre_valido(valor: str) -> bool:
    # Ejemplo: Al menos 2 palabras y no solo números
    palabras = valor.split()
    return len(palabras) >= 2 and not valor.isdigit()

def es_telefono_valido(valor: str) -> bool:
    # Solo dígitos, 7-15 caracteres
    return valor.isdigit() and 7 <= len(valor) <= 15

def es_correo_valido(valor: str) -> bool:
    # Contiene @ y un dominio
    patron = r"^[^@\s]+@[^@\s]+\.[a-zA-Z0-9]+$"
    return re.match(patron, valor) is not None

def es_domicilio_valido(valor: str) -> bool:
    # Simplemente ejemplo: >= 10 caracteres
    return len(valor.strip()) >= 10

def es_narracion_valida(texto: str) -> bool:
    return len(texto.strip()) >= 10

# ... Repite para los campos que quieras ...

VALIDATION_RULES = {
    "nombre_completo": es_nombre_valido,
    "telefono": es_telefono_valido,
    "correo": es_correo_valido,
    "domicilio": es_domicilio_valido,
    "narraciones": es_narracion_valida,
    # etc...
}

# ----------------------------------------------------------------------
#                                LISTAS
# ----------------------------------------------------------------------
LISTA_CAMPOS_DENUNCIA = [
    "nombre_completo",
    "telefono",
    "domicilio",
    "correo",
    "persona_autorizada1",
    "persona_autorizada2",
    "fecha_hechos",
    "lugar_hechos",
    "ciudad",
    "persona_denunciada",
    "relacion_denunciada",
    "narraciones",
    "afectacion",
    "medidas_cautelares",
    "medidas_proteccion",
    "tipo_prueba",
    "prueba_confesional",
    "prueba_testimonial",
    "quien_desahoga",
    "numero_notarial",
    "notario_publico_numero",
    "donde_funciones_notario",
    "fecha_intrumento_notarial",
    "numeros_prueba",
    "documentos_oficiales",
    "folio",
    "fecha_folio",
    "documento_prueba"
]

MEDIDAS_CAUTELARES_OPCIONES = [
    "Suspender la difusión y transmisión de los promocionales de radio y tv (por incitar violencia).",
    "Suspender promocionales con lenguaje sexista que confunda a la ciudadanía.",
    "Retirar propaganda de espectaculares con lenguaje excluyente."
]

MEDIDAS_PROTECCION_OPCIONES = [
    "Prohibición de acercarse a determinada distancia de la víctima.",
    "Prohibición de comunicarse con la víctima.",
    "Limitación de asistir o acercarse al domicilio de la víctima.",
    "Entrega inmediata de objetos personales y documentos a la víctima.",
    "Prohibición de conductas de intimidación o molestia.",
    "Protección policial de la víctima o domicilio.",
    "Auxilio inmediato por la policía al domicilio donde se encuentre la víctima.",
    "Traslado de la víctima a refugios o albergues temporales."
]

field_info = {
    "nombre_completo": {
        "descripcion": "para identificar formalmente a la persona que presenta la denuncia",
        "ejemplo": "Por ejemplo: 'María Pérez González' (nombre y apellido)."
    },
    "telefono": {
        "descripcion": "para poder contactarte y resolver dudas o enviarte notificaciones",
        "ejemplo": "Por ejemplo: '5523456789'."
    },
    "domicilio": {
        "descripcion": "para notificaciones oficiales y posibles trámites legales",
        "ejemplo": "Por ejemplo: 'Calle Falsa 123, Col. Centro, C.P. 12345'."
    },
    "correo": {
        "descripcion": "para enviarte confirmaciones y seguimiento digital",
        "ejemplo": "Por ejemplo: 'ejemplo@dominio.com'."
    },
    "persona_autorizada1": {
        "descripcion": "para designar a alguien que reciba notificaciones en tu nombre",
        "ejemplo": "Por ejemplo: 'Juan López'."
    },
    "persona_autorizada2": {
        "descripcion": "para añadir a otra persona como contacto adicional",
        "ejemplo": "Por ejemplo: 'Ana Martínez'."
    },
    "fecha_hechos": {
        "descripcion": "para ubicar cuándo sucedieron los hechos que denuncias",
        "ejemplo": "Por ejemplo: '5 de febrero de 2023'."
    },
    "lugar_hechos": {
        "descripcion": "para saber dónde ocurrieron los hechos denunciados",
        "ejemplo": "Por ejemplo: 'Oficinas en Calle Principal #45, Colonia Centro'."
    },
    "ciudad": {
        "descripcion": "para ubicar la jurisdicción y dar contexto geográfico",
        "ejemplo": "Por ejemplo: 'Ensenada' o 'Ciudad de México'."
    },
    "persona_denunciada": {
        "descripcion": "para identificar a quién diriges la denuncia",
        "ejemplo": "Por ejemplo: 'Luis Hernández Gómez'."
    },
    "relacion_denunciada": {
        "descripcion": "para conocer el vínculo con la persona denunciada",
        "ejemplo": "Por ejemplo: 'es mi superior jerárquico' o 'colega de trabajo'."
    },
    "narraciones": {
        "descripcion": "para relatar con detalle los hechos de violencia política",
        "ejemplo": "Ejemplo: 'El cinco de febrero, en la oficina de XXX, me dijo...' (puedes agregar varios hechos)"
    },
    "afectacion": {
        "descripcion": "para explicar cómo estos hechos te han impactado",
        "ejemplo": "Por ejemplo: 'Me generó ansiedad y obstaculizó mi participación política'."
    },
    "medidas_cautelares": {
        "descripcion": "para solicitar una medida cautelar que proteja tus derechos",
        "ejemplo": "Por ejemplo: 'Suspender promociones que me difamen'."
    },
    "medidas_proteccion": {
        "descripcion": "para solicitar protección adicional contra posibles represalias",
        "ejemplo": "Por ejemplo: 'Asignar elementos de seguridad si hay amenazas'."
    },
    "prueba_confesional": {
        "descripcion": "para presentar pruebas derivadas de la confesión del denunciado",
        "ejemplo": "Por ejemplo: 'Confesó en un audio que me amenazó'."
    },
    "prueba_testimonial": {
        "descripcion": "para presentar testigos que respalden los hechos",
        "ejemplo": "Por ejemplo: 'María López y Juan Gómez presenciaron los hechos'."
    },
    "quien_desahoga": {
        "descripcion": "para indicar la persona que llevará a cabo la prueba ofrecida.",
        "ejemplo": "Por ejemplo: 'El testigo Juan Pérez' o 'El perito designado'."
    },
    "numero_notarial": {
        "descripcion": "para registrar el número del instrumento notarial que respalda un documento público.",
        "ejemplo": "Por ejemplo: 'Instrumento Notarial Número 12345'."
    },
    "notario_publico_numero": {
        "descripcion": "para identificar el número del notario público que certifica el documento.",
        "ejemplo": "Por ejemplo: 'Notario Público Número 15'."
    },
    "donde_funciones_notario": {
        "descripcion": "para indicar la localidad en la que ejerce el notario público.",
        "ejemplo": "Por ejemplo: 'Ciudad de México' o 'Guadalajara, Jalisco'."
    },
    "fecha_intrumento_notarial": {
        "descripcion": "para registrar la fecha en la que se expidió el instrumento notarial.",
        "ejemplo": "Por ejemplo: '15 de marzo de 2023'."
    },
    "numeros_prueba": {
        "descripcion": "para registrar los números de identificación o referencia de las pruebas documentales.",
        "ejemplo": "Por ejemplo: 'Expediente número 45678/2022'."
    },
    "documentos_oficiales": {
        "descripcion": "para listar documentos oficiales que sirvan como prueba.",
        "ejemplo": "Por ejemplo: 'Acta de nacimiento', 'Credencial de elector', 'Copia certificada de contrato'."
    },
    "folio": {
        "descripcion": "para registrar el número de folio del documento de prueba.",
        "ejemplo": "Por ejemplo: 'Folio 987654321'."
    },
    "fecha_folio": {
        "descripcion": "para indicar la fecha en la que se generó el folio del documento de prueba.",
        "ejemplo": "Por ejemplo: '10 de agosto de 2022'."
    },
    "documento_prueba": {
        "descripcion": "para cualquier documento que evidencie la agresión",
        "ejemplo": "Por ejemplo: 'Capturas de pantalla de mensajes, correos, etc.'."
    }
}


