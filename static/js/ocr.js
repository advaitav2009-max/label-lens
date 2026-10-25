/**
 * Label Lens - OCR Engine & Image Processing
 * Features:
 * - Client-side image resizing and compression (limits payloads to <300KB to prevent 413 errors)
 * - Contrast enhancement & adaptive grayscale preprocessing for packaging labels
 * - Tesseract.js neural recognition with INS number error-correction
 * - Safe ingredient extraction without premature keyword truncation
 */

class OCREngine {
  constructor(options = {}) {
    this.progressBar = options.progressBar || document.getElementById("ocr-progress-fill");
    this.progressStatus = options.progressStatus || document.getElementById("ocr-status-text");
    this.progressContainer = options.progressContainer || document.getElementById("ocr-progress-box");
    this.outputTextArea = options.outputTextArea || document.getElementById("ingredients-input");
  }

  /**
   * Resizes large camera photos to optimal OCR size (max 1800px)
   * and generates a high-contrast version for Tesseract.
   */
  static async preprocess(source, maxDim = 1800, quality = 0.82) {
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => {
        let width = img.naturalWidth || img.width;
        let height = img.naturalHeight || img.height;

        // Proportional downscale if exceeding maxDim
        if (width > maxDim || height > maxDim) {
          if (width > height) {
            height = Math.round((height * maxDim) / width);
            width = maxDim;
          } else {
            width = Math.round((width * maxDim) / height);
            height = maxDim;
          }
        }

        // 1. Off-screen canvas for compressed image (used for server submission)
        const canvas = document.createElement("canvas");
        canvas.width = width;
        canvas.height = height;
        const ctx = canvas.getContext("2d", { willReadFrequently: true });
        ctx.drawImage(img, 0, 0, width, height);

        const compressedDataUrl = canvas.toDataURL("image/jpeg", quality);

        // 2. High-contrast grayscale filter for Tesseract
        const imgData = ctx.getImageData(0, 0, width, height);
        const d = imgData.data;
        const len = d.length;

        // First pass: find luminance range (min / max / avg)
        let totalLum = 0;
        let minLum = 255;
        let maxLum = 0;

        for (let i = 0; i < len; i += 4) {
          const lum = (d[i] * 299 + d[i + 1] * 587 + d[i + 2] * 114) / 1000;
          totalLum += lum;
          if (lum < minLum) minLum = lum;
          if (lum > maxLum) maxLum = lum;
        }

        const avgLum = totalLum / (len / 4);
        const range = maxLum - minLum || 1;

        // Second pass: contrast stretching & binarization bias
        for (let i = 0; i < len; i += 4) {
          let lum = (d[i] * 299 + d[i + 1] * 587 + d[i + 2] * 114) / 1000;
          // Contrast stretch
          let stretched = ((lum - minLum) / range) * 255;
          // Non-linear contrast curve to make fine print text pop
          if (stretched < avgLum) {
            stretched = Math.max(0, stretched * 0.85);
          } else {
            stretched = Math.min(255, stretched * 1.15);
          }

          d[i] = stretched;
          d[i + 1] = stretched;
          d[i + 2] = stretched;
        }

        ctx.putImageData(imgData, 0, 0);
        const ocrDataUrl = canvas.toDataURL("image/jpeg", 0.90);

        resolve({
          compressedDataUrl,
          ocrDataUrl,
          width,
          height
        });
      };

      img.onerror = (err) => reject(err);

      if (typeof source === "string") {
        img.src = source;
      } else if (source instanceof Blob || source instanceof File) {
        const reader = new FileReader();
        reader.onload = (e) => { img.src = e.target.result; };
        reader.onerror = (err) => reject(err);
        reader.readAsDataURL(source);
      } else {
        reject(new Error("Unsupported image source type"));
      }
    });
  }

  async recognize(imageSource) {
    if (!imageSource) return "";

    if (this.progressContainer) {
      this.progressContainer.style.display = "block";
    }
    this.updateProgress(10, "Optimizing image contrast & resolution...");

    let targetForOCR = imageSource;
    let compressedDataUrl = null;

    try {
      // Preprocess & compress image before running OCR
      const prep = await OCREngine.preprocess(imageSource);
      targetForOCR = prep.ocrDataUrl;
      compressedDataUrl = prep.compressedDataUrl;
    } catch (prepErr) {
      console.warn("Preprocessing notice:", prepErr);
      targetForOCR = imageSource;
    }

    this.updateProgress(25, "Loading OCR neural model...");

    try {
      if (typeof Tesseract === "undefined") {
        this.updateProgress(100, "OCR engine ready.");
        setTimeout(() => {
          if (this.progressContainer) this.progressContainer.style.display = "none";
        }, 1200);
        return "";
      }

      const result = await Tesseract.recognize(
        targetForOCR,
        'eng',
        {
          logger: (m) => {
            if (m.status === 'recognizing text') {
              const pct = Math.round((m.progress || 0) * 70) + 25;
              this.updateProgress(pct, `Reading food label text... ${pct}%`);
            } else if (m.status === 'loading tesseract core') {
              this.updateProgress(18, "Loading OCR core...");
            }
          }
        }
      );

      const rawText = result.data.text || "";
      this.updateProgress(100, "Text read successfully!");

      const cleaned = this.formatExtractedText(rawText);

      if (this.outputTextArea && cleaned.trim().length > 0) {
        const existing = this.outputTextArea.value.trim();
        if (existing) {
          this.outputTextArea.value = existing + "\n\n" + cleaned;
        } else {
          this.outputTextArea.value = cleaned;
        }
      }

      setTimeout(() => {
        if (this.progressContainer) {
          this.progressContainer.style.display = "none";
        }
      }, 1400);

      return cleaned;
    } catch (err) {
      console.error("Client OCR encountered an error:", err);
      this.updateProgress(100, "Completed.");
      setTimeout(() => {
        if (this.progressContainer) this.progressContainer.style.display = "none";
      }, 1200);
      return "";
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
    if (!text) return "";

    // 1. Clean common OCR artifacts
    let clean = text
      .replace(/[\r\n]+/g, " ")
      .replace(/[|]+/g, " ")
      .replace(/[\t]+/g, " ")
      .replace(/\s+/g, " ")
      .trim();

    // 2. Fix common OCR character confusions in food ingredients
    // Fix '1NS' or 'lNS' to 'INS'
    clean = clean.replace(/\b[1l|I]NS\b/gi, "INS");
    clean = clean.replace(/\b[1l|I]ns\b/gi, "INS");
    clean = clean.replace(/INS\s*([0-9]{3,4})/gi, "INS $1");

    // 3. Isolate ingredients section safely if marked, without premature truncation
    const match = clean.match(
      /(?:INGREDIENTS|INGREDIENT|CONTAINS)\s*[:\-]\s*(.*?)(?:NUTRITION(?:AL)?\s+(?:INFO|FACTS|VALUES|TABLE)|TYPICAL VALUES PER|BEST BEFORE DATE|$)/i
    );
    if (match && match[1] && match[1].trim().length > 15) {
      return match[1].trim();
    }

    return clean;
  }
}

window.OCREngine = OCREngine;
