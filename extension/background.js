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
    console.log("[MeliOps] Fetching URL:", url);
    let pdfResponse = await fetch(url, { credentials: "include" });
    if (!pdfResponse.ok) {
      throw new Error(`No se pudo descargar el PDF original de MercadoLibre (${index + 1}/${urls.length}).`);
    }
    let contentType = pdfResponse.headers.get("content-type") || "";
    if (!contentType.toLowerCase().includes("pdf") && !contentType.toLowerCase().includes("octet-stream")) {
      const text = await pdfResponse.text();
      console.log("[MeliOps] HTML devuelto para", url, text.substring(0, 500));
      
      const metaMatch = text.match(/url=([^"'>]+)/i);
      const jsMatch = text.match(/window\.location\s*=\s*['"]([^"']+)['"]/i);
      const redirectUrl = (metaMatch ? metaMatch[1] : null) || (jsMatch ? jsMatch[1] : null);
      
      if (redirectUrl) {
        let targetUrl = redirectUrl.replace(/&amp;/g, "&");
        if (!targetUrl.startsWith("http")) {
          targetUrl = new URL(targetUrl, url).href;
        }
        console.log("[MeliOps] Fetching redirect URL:", targetUrl);
        pdfResponse = await fetch(targetUrl, { credentials: "include" });
        if (!pdfResponse.ok) {
          throw new Error(`No se pudo descargar el PDF original de MercadoLibre (${index + 1}/${urls.length}).`);
        }
        contentType = pdfResponse.headers.get("content-type") || "";
        if (!contentType.toLowerCase().includes("pdf") && !contentType.toLowerCase().includes("octet-stream")) {
          throw new Error("El enlace " + url + " no devolvió un PDF válido.");
        }
      } else {
        throw new Error("El enlace " + url + " no devolvió un PDF válido.");
      }
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
  const pdfResponse = await fetch(url, { credentials: "include" });
  if (!pdfResponse.ok) {
    throw new Error("No se pudo descargar el PDF original de MercadoLibre.");
  }
  const contentType = pdfResponse.headers.get("content-type") || "";
  if (!contentType.toLowerCase().includes("pdf") && !contentType.toLowerCase().includes("octet-stream")) {
    throw new Error("El archivo descargado no es un PDF válido. Verifica tu sesión de MercadoLibre.");
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
