// Referencias a elementos del DOM
const chatInput = document.getElementById("chatInput");
const sendButton = document.getElementById("sendButton");
const chatContainer = document.getElementById("chatContainer");
const welcomeMessage = document.getElementById("welcomeMessage");
const messages = document.getElementById("messages");

// Referencias a la entrada de bienvenida
const welcomeInput = document.getElementById("welcomeInput");
const welcomeSendButton = document.getElementById("welcomeSendButton");

// Función para actualizar la vista del chat
function updateChatView() {
    const hasMessages = messages.children.length > 0;
    const chatContainer = document.getElementById("chatContainer");
    
    let chatInputContainer, messageContainer;
    
    // Detecta si estamos en la versión de escritorio o móvil según la estructura
    if (chatContainer.querySelector(".input-container")) {
        // Versión de escritorio
        chatInputContainer = chatContainer.querySelector(".input-container");
        messageContainer = chatContainer.querySelector(".message-container");
    } else if (chatContainer.querySelector(".chat-input")) {
        // Versión móvil
        chatInputContainer = chatContainer.querySelector(".chat-input");
        messageContainer = document.getElementById("messages"); // En móvil, el contenedor de mensajes es el elemento con id "messages"
    } else {
        // Si no se detecta ninguna estructura, salimos de la función
        return;
    }
    
    if (hasMessages) {
        document.body.classList.add("has-messages");
        if (document.getElementById("welcomeMessage")) {
            document.getElementById("welcomeMessage").style.display = "none";
        }
        chatContainer.style.display = "flex";
        messageContainer.style.display = "flex";
        chatInputContainer.style.display = "flex";
    } else {
        document.body.classList.remove("has-messages");
        if (document.getElementById("welcomeMessage")) {
            document.getElementById("welcomeMessage").style.display = "flex";
        }
        chatContainer.style.display = "none";
        chatInputContainer.style.display = "none";
        messageContainer.style.display = "none";
    }
}


// Inicialización al cargar la página
document.addEventListener("DOMContentLoaded", function () {
    // Ocultar el contenedor del chat al inicio
    chatContainer.style.display = "none";
    // Mostrar el contenedor de bienvenida al inicio
    welcomeMessage.style.display = "flex";
    // Actualizar la vista del chat
    updateChatView();
});

// Función para iniciar el chat desde el contenedor de bienvenida
function startChat() {
    const text = welcomeInput.value.trim();
    if (!text) return; // Si no hay texto, no hacer nada

    // Ocultar el contenedor de bienvenida
    welcomeMessage.style.display = "none";
    // Mostrar el contenedor del chat
    chatContainer.style.display = "flex";
    // Enviar el mensaje
    sendMessage(text);
    // Limpiar el input de bienvenida
    welcomeInput.value = "";
}

// Evento para el botón de enviar en el contenedor de bienvenida
welcomeSendButton.addEventListener("click", startChat);

// Evento para la tecla "Enter" en el input de bienvenida
welcomeInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault(); // Evitar el salto de línea
        startChat(); // Iniciar el chat
    }
});

// Función para enviar un mensaje
async function sendMessage(text) {
    if (!text) return; // Si no hay texto, no hacer nada

    // Crear y mostrar el mensaje del usuario
    const userMessage = document.createElement("div");
    userMessage.classList.add("message", "user-message");
    userMessage.textContent = text;
    messages.appendChild(userMessage);
    messages.scrollTop = messages.scrollHeight; // Desplazar al final

    // Actualizar la vista del chat
    updateChatView();

    // Crear y mostrar el mensaje del bot (cargando)
    const botMessage = document.createElement("div");
    botMessage.classList.add("message", "bot-message");
    botMessage.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Pensando...';
    messages.appendChild(botMessage);
    messages.scrollTop = messages.scrollHeight;

    try {
        // Enviar el mensaje al servidor
        const response = await fetch("/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message: text }),
        });

        const data = await response.json();
        let botResponse = data.response;

        // 📄 Si el bot genera una denuncia, agregamos el enlace de descarga
        if (botResponse.includes("✅ He generado tu denuncia.")) {
            // Si ya hay un enlace en la respuesta, no agregamos otro
            if (!botResponse.includes("/download_sue")) {
                const pdfLink = `<a href="/download_sue" target="_blank" class="btn btn-success mt-2">📥 Descargar Denuncia</a>`;
                botResponse = botResponse.replace("✅ He generado tu denuncia. Puedes descargarla aquí:", `✅ He generado tu denuncia.<br>${pdfLink}`);
            }
        }
        

        // Reemplazar el enlace del formato vacío por un botón de descarga
        botResponse = botResponse.replace(
            "[Descargar formato de denuncia](/download_form)",
            `<a href="/download_form" target="_blank" class="btn btn-primary mt-2">📥 Descargar Formato de denuncia</a>`
        );

        // Convertir Markdown en HTML para hipervínculos
        botResponse = markdownToHtml(botResponse);

        // Convertir saltos de línea a <br> para mejorar la estructura
        botResponse = botResponse.replace(/\n/g, "<br>");

        // Actualizar el mensaje del bot con la respuesta formateada
        botMessage.innerHTML = botResponse;
    } catch (error) {
        // Manejar errores
        botMessage.innerHTML = "❌ Error en el servidor. Intenta nuevamente.";
    }
    messages.scrollTop = messages.scrollHeight; // Desplazar al final
}



// Evento para la tecla "Enter" en el input del chat
sendButton.addEventListener("click", () => {
    const text = chatInput.value.trim();
    if (text) {
        sendMessage(text);
        chatInput.value = ""; // Limpiar el input del chat
        updateChatView();
    }
});

chatInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault(); // Evitar el salto de línea
        const text = chatInput.value.trim();
        if (text) {
            sendMessage(text);
            chatInput.value = ""; // Limpiar el input del chat
            updateChatView();
        }
    }
});


// Evento para borrar la conversación
document.getElementById("confirmDelete").addEventListener("click", async () => {
    try {
        const response = await fetch("/confirm_clear", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
        });
        if (response.ok) {
            // Limpiar los mensajes
            messages.innerHTML = "";
            // Ocultar el modal de confirmación
            const modal = bootstrap.Modal.getInstance(document.getElementById("confirmModal"));
            modal.hide();
            // Actualizar la vista del chat
            updateChatView();
        }
    } catch (error) {
        console.error("Error:", error);
    }
});
// Lógica de grabación de audio (opcional)
const audioModalEl = document.getElementById("audioModal");
const audioModal = new bootstrap.Modal(audioModalEl);
const audioStatus = document.getElementById("audioStatus");
const startRecordingButton = document.getElementById("startRecording");
const stopRecordingButton = document.getElementById("stopRecording");

let mediaRecorder;
let audioChunks = [];

document.getElementById("Audio").addEventListener("click", () => {
    audioStatus.textContent = 'Presiona "Grabar" para iniciar la grabación.';
    startRecordingButton.disabled = false;
    stopRecordingButton.disabled = true;
    audioModal.show();
});

startRecordingButton.addEventListener("click", async () => {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream);
        audioChunks = [];

        mediaRecorder.ondataavailable = (event) => audioChunks.push(event.data);
        mediaRecorder.onstop = async () => {
            const audioBlob = new Blob(audioChunks, { type: "audio/webm" });
            if (audioBlob.size === 0) {
                audioStatus.textContent = "❌ Error: El audio está vacío.";
                return;
            }

            const formData = new FormData();
            formData.append("audio", audioBlob, "audio.webm");

            try {
                const response = await fetch("/audio", { method: "POST", body: formData });
                const data = await response.json();

                const userMessage = document.createElement("div");
                userMessage.classList.add("message", "user-message");
                userMessage.textContent = data.transcription;
                messages.appendChild(userMessage);

                const botMessage = document.createElement("div");
                botMessage.classList.add("message", "bot-message");
                botMessage.innerHTML = data.response;
                messages.appendChild(botMessage);
                messages.scrollTop = messages.scrollHeight;
            } catch (error) {
                console.error("Error al procesar el audio:", error);
                audioStatus.textContent = "❌ Error al procesar el audio.";
            }
        };

        mediaRecorder.start();
        startRecordingButton.disabled = true;
        stopRecordingButton.disabled = false;
        audioStatus.textContent = "🎙️ Grabando...";
    } catch (error) {
        console.error("Error accediendo al micrófono:", error);
        audioStatus.textContent = "❌ Error accediendo al micrófono.";
    }
});

stopRecordingButton.addEventListener("click", () => {
    if (mediaRecorder && mediaRecorder.state !== "inactive") {
        mediaRecorder.stop();
        startRecordingButton.disabled = false;
        stopRecordingButton.disabled = true;
    }
    audioModal.hide();
});

function markdownToHtml(text) {
    return text.replace(/\[(.*?)\]\((.*?)\)/g, '<a href="$2" target="_blank" class="text-primary">$1</a>');
}


if (window.innerWidth <= 768 && window.location.pathname !== "/movile") {
    window.location.href = "/movile";
} else if (window.innerWidth > 768 && window.location.pathname !== "/") {
    window.location.href = "/";
}
