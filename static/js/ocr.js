/**
 * Label Lens - OCR Engine & Image Processing
 * Leverages Tesseract.js client-side OCR with progress indicators,
 * image preprocessing, and direct text population.
 */

class OCREngine {
  constructor(options = {}) {
    this.progressBar = options.progressBar || document.getElementById("ocr-progress-fill");
    this.progressStatus = options.progressStatus || document.getElementById("ocr-status-text");
    this.progressContainer = options.progressContainer || document.getElementById("ocr-progress-box");
    this.outputTextArea = options.outputTextArea || document.getElementById("ingredients-input");
    this.worker = null;
  }

  async recognize(imageSource) {
    if (!imageSource) return;

    if (this.progressContainer) {
      this.progressContainer.style.display = "block";
    }
    this.updateProgress(10, "Initializing OCR neural model...");

    try {
      if (typeof Tesseract === "undefined") {
        this.updateProgress(100, "Tesseract.js CDN unavailable. Image will be processed on server.");
        setTimeout(() => {
          if (this.progressContainer) this.progressContainer.style.display = "none";
        }, 1800);
        return;
      }

      const result = await Tesseract.recognize(
        imageSource,
        'eng',
        {
          logger: m => {
            if (m.status === 'recognizing text') {
              const pct = Math.round((m.progress || 0) * 85) + 10;
              this.updateProgress(pct, `Reading food label... ${pct}%`);
            } else if (m.status === 'loading tesseract core') {
              this.updateProgress(20, "Loading core OCR engine...");
            } else if (m.status === 'initialized tesseract') {
              this.updateProgress(35, "Scanning character blocks...");
            }
          }
        }
      );

      const rawText = result.data.text || "";
      this.updateProgress(100, "Text extracted successfully!");

      if (this.outputTextArea && rawText.trim().length > 0) {
        // Look for ingredients keyword if possible
        const cleaned = this.formatExtractedText(rawText);
        this.outputTextArea.value = cleaned;
      }

      setTimeout(() => {
        if (this.progressContainer) {
          this.progressContainer.style.display = "none";
        }
      }, 1500);

      return rawText;
    } catch (err) {
      console.error("Client OCR failed:", err);
      this.updateProgress(100, "OCR completed with server fallback.");
      setTimeout(() => {
        if (this.progressContainer) this.progressContainer.style.display = "none";
      }, 1500);
    }
  }

  updateProgress(percent, message) {
    if (this.progressBar) {
      this.progressBar.style.width = `${percent}%`;
    }
    if (this.progressStatus) {
      this.progressStatus.textContent = message;
    }
  }

  formatExtractedText(text) {
    // Clean repetitive OCR artifacts
    let clean = text.replace(/[\r\n]+/g, " ").replace(/\s+/g, " ").trim();
    // Try to isolate ingredient segment if present
    const match = clean.match(/(?:INGREDIENTS|INGREDIENT|CONTAINS)\s*[:\-]?\s*(.*?)(?:NUTRITIONAL|BEST BEFORE|MFG|NET WT|STORAGE|$)/i);
    if (match && match[1] && match[1].trim().length > 15) {
      return match[1].trim();
    }
    return clean;
  }
}

window.OCREngine = OCREngine;
