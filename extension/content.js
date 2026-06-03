function showLoadingOverlay(text) {
  let overlay = document.getElementById("meliops-loading-overlay");
  if (!overlay) {
    overlay = document.createElement("div");
    overlay.id = "meliops-loading-overlay";
    overlay.style.position = "fixed";
    overlay.style.top = "0";
    overlay.style.left = "0";
    overlay.style.width = "100vw";
    overlay.style.height = "100vh";
    overlay.style.backgroundColor = "rgba(0, 0, 0, 0.7)";
    overlay.style.zIndex = "9999999";
    overlay.style.display = "flex";
    overlay.style.flexDirection = "column";
    overlay.style.justifyContent = "center";
    overlay.style.alignItems = "center";
    overlay.style.color = "#FFFFFF";
    overlay.style.fontFamily = "Proxima Nova, -apple-system, sans-serif";
    overlay.style.fontSize = "20px";
    overlay.style.fontWeight = "bold";
    
    const spinner = document.createElement("div");
    spinner.style.border = "4px solid rgba(255, 255, 255, 0.3)";
    spinner.style.borderTop = "4px solid #FFE600";
    spinner.style.borderRadius = "50%";
    spinner.style.width = "40px";
    spinner.style.height = "40px";
    spinner.style.animation = "spin 1s linear infinite";
    spinner.style.marginBottom = "20px";
    
    const style = document.createElement("style");
    style.innerHTML = `
      @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
      }
    `;
    document.head.appendChild(style);
    
    overlay.appendChild(spinner);
    
    const textEl = document.createElement("div");
    textEl.id = "meliops-loading-text";
    overlay.appendChild(textEl);
    
    document.body.appendChild(overlay);
  }
  document.getElementById("meliops-loading-text").textContent = text;
}

function hideLoadingOverlay() {
  const overlay = document.getElementById("meliops-loading-overlay");
  if (overlay) {
    overlay.remove();
  }
}

function matchesKeywords(a) {
  if (!a.href) return false;
  const href = (a.href || "").toLowerCase();
  const text = (a.textContent || "").toLowerCase();
  const keywords = ["pdf", "label", "print", "reprint", "reimprimir"];
  return keywords.some(kw => href.includes(kw) || text.includes(kw));
}

async function extractHiddenLinks() {
  const urls = new Set();
  
  const addValidUrl = (a) => {
    if (!a.href?.startsWith("http")) {
      return;
    }
    const baseHref = a.href.split("#")[0];
    const baseUrl = window.location.href.split("#")[0];
    if (baseHref === baseUrl) {
      return;
    }
    if (a.href.includes("/publicaciones/listado")) {
      return;
    }
    urls.add(a.href);
    console.log("[MeliOps] Capturado enlace:", a.href);
  };

  const visibleLinks = Array.from(document.querySelectorAll("a")).filter(a => {
    const isVisible = a.offsetWidth > 0 || a.offsetHeight > 0 || a.getClientRects().length > 0;
    return isVisible && matchesKeywords(a);
  });
  for (const a of visibleLinks) {
    addValidUrl(a);
  }
  
  const menus = document.querySelectorAll('.andes-floating-menu.secondary-actions, .andes-floating-menu');
  for (const menu of menus) {
    if (menu.scrollIntoView) {
      menu.scrollIntoView({ block: "center" });
    }
    menu.click();
    await new Promise(r => setTimeout(r, 200));
    
    const menuLinks = Array.from(document.querySelectorAll('a')).filter(matchesKeywords);
    for (const a of menuLinks) {
      addValidUrl(a);
    }
    
    menu.click();
    await new Promise(r => setTimeout(r, 100));
  }
  
  return Array.from(urls);
}

const button = document.createElement("button");
button.textContent = "🏷️ Optimizar Etiquetas";
button.style.position = "fixed";
button.style.bottom = "20px";
button.style.right = "20px";
button.style.zIndex = "999999";
button.style.padding = "12px 20px";
button.style.backgroundColor = "#FFE600";
button.style.color = "#2D3277";
button.style.border = "none";
button.style.borderRadius = "24px";
button.style.fontWeight = "bold";
button.style.cursor = "pointer";
button.style.boxShadow = "0 4px 12px rgba(0,0,0,0.15)";
button.style.fontSize = "14px";
button.style.fontFamily = "Proxima Nova, -apple-system, sans-serif";
button.style.transition = "transform 0.2s, box-shadow 0.2s";

button.addEventListener("mouseenter", () => {
  button.style.transform = "scale(1.05)";
  button.style.boxShadow = "0 6px 16px rgba(0,0,0,0.2)";
});

button.addEventListener("mouseleave", () => {
  button.style.transform = "scale(1)";
  button.style.boxShadow = "0 4px 12px rgba(0,0,0,0.15)";
});

button.addEventListener("click", async () => {
  showLoadingOverlay("⏳ Procesando etiquetas y buscando reimpresiones...");
  button.disabled = true;

  try {
    const linksArray = await extractHiddenLinks();

    if (linksArray.length === 0) {
      alert("No se encontraron enlaces de etiquetas PDF en esta página. Intenta subir el archivo manualmente desde la extensión o la web.");
      button.disabled = false;
      hideLoadingOverlay();
      return;
    }

    chrome.runtime.sendMessage({ action: "process_multiple_pdfs", urls: linksArray }, (response) => {
      button.disabled = false;
      hideLoadingOverlay();
      if (response?.success) {
        alert("¡Etiquetas optimizadas con éxito! La descarga comenzará en breve.");
      } else {
        alert(`Error al optimizar etiquetas: ${response?.error || "Error desconocido"}`);
      }
    });
  } catch (error) {
    console.error("Error extracting links:", error);
    button.disabled = false;
    hideLoadingOverlay();
    alert("Ocurrió un error al buscar las etiquetas.");
  }
});

document.body.appendChild(button);
