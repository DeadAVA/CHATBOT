from flask import Flask, request, render_template, jsonify, session, send_file
from flask_session import Session
from openai import OpenAI
import os
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from werkzeug.utils import secure_filename
from prompt import SYSTEM_PROMPT
from formato_denuncia import procesar_denuncia
import requests  # Asegúrate de importar requests
import threading
import glob


# Cargar variables de entorno
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
db_lock = threading.Lock()  # Evita condiciones de carrera en multi-threading
db = None  # Global para almacenar FAISS


app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

# Carpeta donde están los documentos PDF
PDF_FOLDER = "static/pdfs"
AUDIO_FOLDER = "uploads/audio"
INDEX_PATH = "faiss_index"  # Nombre del archivo donde guardaremos el índice
os.makedirs(AUDIO_FOLDER, exist_ok=True)  # Crear la carpeta si no existe

app.config["SESSION_TYPE"] = "filesystem"  # Tipo de sesión en archivos
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_FILE_DIR"] = "./flask_sessions"

Session(app)  # Ahora se inicializa correctamente

# Cargar modelo de embeddings
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

def get_db():
    global db
    with db_lock:  # Garantiza que solo un hilo cargue el índice
        if db is None:
            db = load_or_create_index()
        return db

# Función para cargar y procesar documentos PDF
def load_pdfs():
    documents = []
    if not os.path.exists(PDF_FOLDER):
        print("❌ Carpeta de PDFs no encontrada.")
        return []

    for filename in os.listdir(PDF_FOLDER):
        if filename.endswith(".pdf"):
            pdf_path = os.path.join(PDF_FOLDER, filename)
            loader = PyPDFLoader(pdf_path)
            docs = loader.load()
            if docs:
                print(f"📄 Cargado {filename} con {len(docs)} páginas.")
            documents.extend(docs)

    return documents

def load_or_create_index():
    """Carga el índice FAISS desde disco si existe, de lo contrario lo crea."""
    index_files = glob.glob(f"{INDEX_PATH}*")  # Verificar si hay archivos FAISS

    if index_files:
        print("🔄 Cargando índice FAISS desde disco...")
        try:
            db_instance = FAISS.load_local(INDEX_PATH, OpenAIEmbeddings(), allow_dangerous_deserialization=True)
            if db_instance is not None:
                return db_instance
        except Exception as e:
            print(f"⚠️ Error al cargar índice FAISS: {str(e)}. Se intentará regenerar.")

    print("📌 Generando nuevo índice FAISS...")

    # ⚠️ Cargar los PDFs antes de intentar dividirlos
    pdf_documents = load_pdfs()
    if not pdf_documents:
        print("❌ No hay documentos PDF disponibles. No se generará FAISS.")
        return None  # Evita errores si no hay documentos

    # 📝 Dividir documentos solo si hay documentos PDF cargados
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    split_docs = text_splitter.split_documents(pdf_documents)

    print(f"📌 Se generaron {len(split_docs)} fragmentos de texto para indexar.")

    # 🔹 Crear FAISS solo si hay fragmentos de texto
    if split_docs:
        db_instance = FAISS.from_documents(split_docs, OpenAIEmbeddings())
        db_instance.save_local(INDEX_PATH)
        print(f"✅ Índice FAISS guardado en {INDEX_PATH}")
        return db_instance
    else:
        print("❌ No se pudieron generar fragmentos de texto. Verifica los documentos PDF.")
        return None

db = load_or_create_index()

# Búsqueda en los documentos PDF
def search_in_pdfs(query, top_k=3):
    db_instance = get_db()
    if db_instance is None:
        print("⚠️ No hay documentos indexados aún.")
        return "⚠️ No hay documentos indexados aún."

    try:
        retrieved_docs = db_instance.similarity_search(query, k=top_k)
        retrieved_text = "\n".join([doc.page_content for doc in retrieved_docs])
        print(f"🔍 Búsqueda en FAISS: {retrieved_text[:500]}")
        return retrieved_text
    except Exception as e:
        print(f"❌ Error en búsqueda FAISS: {str(e)}")
        return "⚠️ Error al buscar en los documentos."

@app.route("/reload_index", methods=["POST"])
def reload_index():
    """Permite regenerar el índice FAISS manualmente sin reiniciar Flask"""
    global db
    with db_lock:
        print("♻️ Regenerando índice FAISS...")
        db = load_or_create_index()
    
    return jsonify({"message": "Índice FAISS regenerado correctamente."})


@app.route("/")
def home():
    return render_template("index.html")

@app.route("/movile")
def movile():
    return render_template("movil.html")

@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    user_message = data.get("message", "").strip()

    if not user_message:
        return jsonify({"response": "No recibí ningún mensaje. 😕"})

    # Obtener historial del chat
    messages = session.get("messages", [])
    messages.append({"role": "user", "content": user_message})

    # 🔍 Verificar si el usuario está pidiendo llenar un formato de denuncia
    keywords = ["llenar formato", "hacer denuncia", "formato de denuncia", "quiero denunciar", "generes una denuncia"]
    if any(keyword in user_message.lower() for keyword in keywords):
        try:
            # Hacer una solicitud interna a /generar_denuncia
            response = requests.post(request.url_root + "generar_denuncia", json={"texto": user_message})

            print(f"📩 Respuesta de /generar_denuncia: {response.status_code} - {response.text}")

            if response.status_code == 200:
                resultado = response.json()

                if "error" in resultado:
                    datos_faltantes = resultado["faltantes"]
                    response_text = f"Para completar tu denuncia, necesito los siguientes datos:\n- " + "\n- ".join(datos_faltantes)
                    return jsonify({"response": response_text})

                # Verificar si la clave "pdf_path" está en la respuesta
                if "pdf_path" in resultado:
                    pdf_path = resultado.get("pdf_path")

                    if not isinstance(pdf_path, str) or not pdf_path:  # 🔍 Asegurar que sea un string válido
                        print("❌ Error: La ruta del PDF no es válida.")
                        return jsonify({"response": "Ocurrió un error al generar la denuncia. Intenta de nuevo más tarde."})

                    pdf_path = str(pdf_path)  # 🔴 Asegurar que pdf_path sea una cadena

                    session["pdf_path"] = pdf_path  # ✅ Guarda solo la cadena en la sesión

                    print(f"✅ PDF guardado en sesión: {pdf_path}")  # 👈 Depuración

                else:
                    print("❌ Error: No se encontró 'pdf_path' en la respuesta.")
                    return jsonify({"response": "Ocurrió un error al generar la denuncia. Intenta de nuevo más tarde."})

            else:
                print("❌ Error al generar el PDF, respuesta inesperada")
                return jsonify({"response": "Ocurrió un error al generar la denuncia. Intenta de nuevo más tarde."})

        except Exception as e:
            print(f"❌ Error en la solicitud a /generar_denuncia: {str(e)}")
            return jsonify({"response": "Ocurrió un error al generar la denuncia. Intenta de nuevo más tarde."})

    # Continuación normal del chatbot
    try:
        completion = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + messages,
            max_tokens=500
        )
        
        bot_response = completion.choices[0].message.content if completion.choices else ""

        # Verificar si la respuesta del LLM es vaga
        vague_responses = ["no estoy seguro", "no tengo información", "no puedo responder"]
        if any(vague in bot_response.lower() for vague in vague_responses):
            print("🔍 Buscando en documentos porque la respuesta del LLM no es suficiente...")
            retrieved_context = search_in_pdfs(user_message)
            
            if retrieved_context:
                full_prompt = f"""
                {SYSTEM_PROMPT}

                El usuario ha preguntado: "{user_message}"
                No se encontró una respuesta clara, pero aquí hay información extraída de documentos relevantes:

                {retrieved_context}

                Responde de manera clara y útil, utilizando esta información.
                """

                
                completion = client.chat.completions.create(
                    model="gpt-4-turbo",
                    messages=[{"role": "system", "content": full_prompt}] + messages,
                    max_tokens=500
                )
                bot_response = completion.choices[0].message.content if completion.choices else "No se pudo obtener una respuesta clara."

        return jsonify({"response": bot_response})

    except Exception as e:
        return jsonify({"response": f"Error: {str(e)}"})
    
@app.route("/audio", methods=["POST"])
def audio():
    if "audio" not in request.files:
        return jsonify({"error": "No se recibió ningún archivo de audio."}), 400

    audio_file = request.files["audio"]
    if audio_file.filename == "":
        return jsonify({"error": "El archivo no tiene nombre."}), 400

    # Guardar el archivo en el servidor
    filename = secure_filename(audio_file.filename)
    file_path = os.path.join(AUDIO_FOLDER, filename)
    audio_file.save(file_path)

    try:
        # Transcribir el audio usando Whisper
        with open(file_path, "rb") as f:
            transcript = client.audio.transcriptions.create(model="whisper-1", file=f)

        transcription_text = transcript.text if hasattr(transcript, "text") else "[No se obtuvo transcripción]"

        # Enviar el texto transcrito como mensaje al chat
        chat_response = chat_request(transcription_text)

        return jsonify({
            "response": chat_response["response"],
            "transcription": transcription_text
        })

    except Exception as e:
        return jsonify({"error": f"Error al procesar el audio: {str(e)}"}), 500

def chat_request(user_message):
    """Función para enviar una consulta al chatbot desde texto."""
    messages = session.get("messages", [])
    messages.append({"role": "user", "content": user_message})

    try:
        completion = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + messages,
            max_tokens=500
        )
        bot_response = completion.choices[0].message.content if completion.choices else ""

        messages.append({"role": "assistant", "content": bot_response})
        session["messages"] = messages

        return {"response": bot_response}

    except Exception as e:
        return {"response": f"Error: {str(e)}"}
    
@app.route("/get_messages")
def get_messages():
    messages = session.get("messages", [])
    return jsonify({"messages": messages})

@app.route("/confirm_clear", methods=["POST"])
def confirm_clear():
    session.pop("messages", None)  # Eliminar historial del chat
    return jsonify({"response": "Memoria del chat eliminada. 🧹"})

@app.route("/download_form", methods=["GET"])
def download_form():
    pdf_path = "formato/Formulario_Formato_de_Denuncia_VPCMRG_listo.pdf"
    return send_file(pdf_path, as_attachment=True)

#GENERAR DENUNCIA
@app.route("/generar_denuncia", methods=["POST"])
def generar_denuncia():
    data = request.json
    texto_usuario = data.get("texto", "")
    if not texto_usuario:
        return jsonify({"error": "No se proporcionó texto para la denuncia."}), 400
    
    pdf_path = procesar_denuncia(texto_usuario)
    if isinstance(pdf_path, dict):  # 🔴 Si es un diccionario, significa que hubo un error
        return jsonify(pdf_path), 400  # Devolverlo tal cual
    
    return jsonify({"pdf_path": pdf_path})  # ✅ Aquí aseguramos que siempre se devuelve correctamente

@app.route("/download_sue", methods=["GET"])
def download_sue():
    pdf_path = session.get("pdf_path")

    if not pdf_path:
        print("❌ No hay un PDF en la sesión.")  # Debugging
        return jsonify({"error": "No se ha generado ningún archivo en la sesión."}), 404

    if not isinstance(pdf_path, str):
        print(f"❌ Error: pdf_path en sesión no es un string: {pdf_path}")  # Debugging
        return jsonify({"error": "Ruta de PDF inválida en la sesión."}), 500

    pdf_path = os.path.abspath(pdf_path)  # Convertir a ruta absoluta

    if not os.path.exists(pdf_path):
        print(f"❌ Error: El archivo no existe en {pdf_path}")  # Debugging
        return jsonify({"error": f"El archivo no existe en: {pdf_path}"}), 404

    return send_file(pdf_path, as_attachment=True)

@app.route("/get_pdf_path", methods=["GET"])
def get_pdf_path():
    pdf_path = session.get("pdf_path")

    if not pdf_path:
        return jsonify({"error": "No se ha generado ningún archivo en la sesión."}), 404

    return jsonify({"pdf_path": pdf_path})  # ✅ Ahora devuelve un diccionario válido


if __name__ == "__main__":
    with db_lock:  # Garantiza que solo un hilo cargue el índice FAISS
        if db is None and not app.debug:  
            db = load_or_create_index()

    app.run(host="0.0.0.0", port=5000, debug=True)
