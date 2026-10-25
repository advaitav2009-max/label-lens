/**
 * Label Lens - Core Application UI Logic
 */

document.addEventListener("DOMContentLoaded", () => {
  // Mobile / tab navigation handling
  initTabs();
  initSampleSelectors();
});

function initTabs() {
  const tabs = document.querySelectorAll(".tab-btn");
  if (!tabs.length) return;

  tabs.forEach(tab => {
    tab.addEventListener("click", () => {
      tabs.forEach(t => t.classList.remove("active"));
      tab.classList.add("active");

      const target = tab.getAttribute("data-target");
      document.querySelectorAll(".scan-panel").forEach(panel => {
        panel.style.display = "none";
      });

      const activePanel = document.getElementById(target);
      if (activePanel) {
        activePanel.style.display = "block";
      }

      // If switching away from camera, ensure stream stays paused or starts appropriately
      if (target === "camera-panel" && window.cameraInstance) {
        window.cameraInstance.startStream();
      }
    });
  });
}


function initSampleSelectors() {
  const samplePills = document.querySelectorAll(".sample-product-pill");
  samplePills.forEach(pill => {
    pill.addEventListener("click", () => {
      const name = pill.getAttribute("data-name");
      const category = pill.getAttribute("data-category");
      const price = pill.getAttribute("data-price");
      const servings = pill.getAttribute("data-servings");
      const ingredients = pill.getAttribute("data-ingredients");

      const nameInput = document.getElementById("product-name");
      const catSelect = document.getElementById("product-category");
      const priceInput = document.getElementById("packet-price");
      const servingsInput = document.getElementById("servings-input");
      const ingredientsInput = document.getElementById("ingredients-input");

      if (nameInput) nameInput.value = name || "";
      if (catSelect) catSelect.value = category || "General Packaged Food";
      if (priceInput) priceInput.value = price || "";
      if (servingsInput) servingsInput.value = servings || "1";
      if (ingredientsInput) ingredientsInput.value = ingredients || "";

      // Smooth scroll to submit button or review area
      if (ingredientsInput) {
        ingredientsInput.scrollIntoView({ behavior: "smooth", block: "center" });
        ingredientsInput.focus();
      }
    });
  });
}
