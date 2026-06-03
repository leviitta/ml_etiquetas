const BACKEND_URL = "https://www.meliops.cl";

chrome.runtime.onMessage.addListener((request, _sender, sendResponse) => {
  if (request.action === "process_multiple_pdfs") {
    processMultiplePdfs(request.urls)
      .then(blob => {
        const reader = new FileReader();
        reader.onloadend = () => {
          chrome.downloads.download({
            url: reader.result,
            filename: "etiquetas_optimizadas.pdf",
            saveAs: true
          });
          sendResponse({ success: true });
        };
        reader.readAsDataURL(blob);
      })
      .catch(err => {
        sendResponse({ success: false, error: err.message });
      });
    return true;
  }

  if (request.action === "process_pdf_url") {
    processPdfUrl(request.url)
      .then(blob => {
        const reader = new FileReader();
        reader.onloadend = () => {
          chrome.downloads.download({
            url: reader.result,
            filename: "etiquetas_optimizadas.pdf",
            saveAs: true
          });
          sendResponse({ success: true });
        };
        reader.readAsDataURL(blob);
      })
      .catch(err => {
        sendResponse({ success: false, error: err.message });
      });
    return true;
  }
});

async function processMultiplePdfs(urls) {
  const fetchPromises = urls.map(async (url, index) => {
    const pdfResponse = await fetch(url);
    if (!pdfResponse.ok) {
      throw new Error(`No se pudo descargar el PDF original de MercadoLibre (${index + 1}/${urls.length}).`);
    }
    const pdfBlob = await pdfResponse.blob();
    return { blob: pdfBlob, filename: `etiqueta_${index + 1}.pdf` };
  });

  const results = await Promise.all(fetchPromises);

  const formData = new FormData();
  for (const res of results) {
    formData.append("files", res.blob, res.filename);
  }

  const response = await fetch(`${BACKEND_URL}/api/v1/extract`, {
    method: "POST",
    body: formData,
    credentials: "include"
  });

  if (!response.ok) {
    const errData = await response.json().catch(() => ({}));
    throw new Error(errData.error || "Error en el servidor de MeliOps.");
  }

  return await response.blob();
}

async function processPdfUrl(url) {
  const pdfResponse = await fetch(url);
  if (!pdfResponse.ok) {
    throw new Error("No se pudo descargar el PDF original de MercadoLibre.");
  }
  const pdfBlob = await pdfResponse.blob();

  const formData = new FormData();
  formData.append("files", pdfBlob, "etiqueta.pdf");

  const response = await fetch(`${BACKEND_URL}/api/v1/extract`, {
    method: "POST",
    body: formData,
    credentials: "include"
  });

  if (!response.ok) {
    const errData = await response.json().catch(() => ({}));
    throw new Error(errData.error || "Error en el servidor de MeliOps.");
  }

  return await response.blob();
}
