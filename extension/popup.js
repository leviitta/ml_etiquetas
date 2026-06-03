document.getElementById("uploadBtn").addEventListener("click", () => {
  document.getElementById("fileInput").click();
});

document.getElementById("fileInput").addEventListener("change", async (event) => {
  const file = event.target.files[0];
  if (!file) return;

  const uploadBtn = document.getElementById("uploadBtn");
  const originalText = uploadBtn.innerText;
  uploadBtn.innerText = "⏳ Procesando...";
  uploadBtn.disabled = true;

  const formData = new FormData();
  formData.append("files", file);

  try {
    const BACKEND_URL = "https://www.meliops.cl";
    const response = await fetch(`${BACKEND_URL}/api/v1/extract`, {
      method: "POST",
      body: formData,
      credentials: "include"
    });

    if (!response.ok) {
      const errData = await response.json().catch(() => ({}));
      throw new Error(errData.error || "Error al procesar el archivo.");
    }

    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "etiquetas_optimizadas.pdf";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);

    uploadBtn.innerText = "¡Completado!";
  } catch (err) {
    alert("Error: " + err.message);
    uploadBtn.innerText = originalText;
  } finally {
    uploadBtn.disabled = false;
  }
});
