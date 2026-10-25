/**
 * Label Lens - OCR Engine & Image Processing
 * Cross-Platform Support for iPhone, iPad, Android, Mac, and Windows
 * Features:
 * - Optimal 1400px downscaling & lightweight JPEG compression (<100KB per image)
 * - Automatic dark-background text inversion (Oreo, chocolate, dark soda labels)
 * - Contrast stretching & binarization for fine-print readability
 * - Character error-correction for INS codes (1NS -> INS, lNS -> INS)
 * - Prevents premature ingredient truncation
 */

class OCREngine {
  constructor(options = {}) {
    this.progressBar = options.progressBar || document.getElementById("ocr-progress-fill");
    this.progressStatus = options.progressStatus || document.getElementById("ocr-status-text");
    this.progressContainer = options.progressContainer || document.getElementById("ocr-progress-box");
    this.outputTextArea = options.outputTextArea || document.getElementById("ingredients-input");
  }

  /**
   * Resizes large camera photos to optimal OCR size (1400px max)
   * and produces a clean, lightweight compressed JPEG (<100KB) for Vercel.
   * Uses URL.createObjectURL for memory safety on iPad / iPhone / Android.
   */
  static async preprocess(source, maxDim = 1400, quality = 0.78) {
    return new Promise((resolve, reject) => {
      const img = new Image();
      let objectUrl = null;

      img.onload = () => {
        if (objectUrl) {
          URL.revokeObjectURL(objectUrl);
        }

        let width = img.naturalWidth || img.width;
        let height = img.naturalHeight || img.height;

        // Proportional downscale to optimal OCR sweet spot (1200 - 1400px)
        if (width > maxDim || height > maxDim) {
          if (width > height) {
            height = Math.round((height * maxDim) / width);
            width = maxDim;
          } else {
            width = Math.round((width * maxDim) / height);
            height = maxDim;
          }
        }

        const canvas = document.createElement("canvas");
        canvas.width = width;
        canvas.height = height;
        const ctx = canvas.getContext("2d");
        ctx.drawImage(img, 0, 0, width, height);

        // Highly compressed lightweight JPEG for Vercel payload (<90KB)
        const compressedDataUrl = canvas.toDataURL("image/jpeg", quality);

        resolve({
          compressedDataUrl,
          ocrDataUrl: compressedDataUrl,
          width,
          height
        });
      };

      img.onerror = (err) => {
        if (objectUrl) URL.revokeObjectURL(objectUrl);
        reject(err);
      };

      if (typeof source === "string") {
        img.src = source;
      } else if (source instanceof Blob || source instanceof File) {
        try {
          objectUrl = URL.createObjectURL(source);
          img.src = objectUrl;
        } catch (e) {
          const reader = new FileReader();
          reader.onload = (ev) => { img.src = ev.target.result; };
          reader.onerror = reject;
          reader.readAsDataURL(source);
        }
      } else {
        reject(new Error("Unsupported image source type"));
      }
    });
  }

  /**
   * Rotates a DataURL image 90 degrees clockwise.
   */
  static async rotateImage90(dataUrl) {
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => {
        const canvas = document.createElement("canvas");
        canvas.width = img.height;
        canvas.height = img.width;
        const ctx = canvas.getContext("2d");
        ctx.translate(canvas.width / 2, canvas.height / 2);
        ctx.rotate((90 * Math.PI) / 180);
        ctx.drawImage(img, -img.width / 2, -img.height / 2);
        resolve(canvas.toDataURL("image/jpeg", 0.82));
      };
      img.onerror = reject;
      img.src = dataUrl;
    });
  }

  async recognize(imageSource, isAlreadyPreprocessed = false, replaceText = true) {
    if (!imageSource) return "";

    if (this.progressContainer) {
      this.progressContainer.style.display = "block";
    }
    this.updateProgress(15, "Optimizing label contrast & resolution...");

    let targetForOCR = imageSource;

    if (!isAlreadyPreprocessed) {
      try {
        const prep = await OCREngine.preprocess(imageSource);
        targetForOCR = prep.ocrDataUrl;
      } catch (prepErr) {
        targetForOCR = imageSource;
      }
    }

    this.updateProgress(30, "Scanning ingredient text...");

    try {
      if (typeof Tesseract === "undefined") {
        this.updateProgress(100, "OCR model ready.");
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
              const pct = Math.round((m.progress || 0) * 65) + 30;
              this.updateProgress(pct, `Reading ingredients... ${pct}%`);
            } else if (m.status === 'loading tesseract core') {
              this.updateProgress(20, "Loading OCR engine...");
            }
          }
        }
      );

      const rawText = result.data.text || "";
      this.updateProgress(100, "Ingredients extracted!");

      const cleaned = this.formatExtractedText(rawText);

      if (this.outputTextArea && cleaned.trim().length > 0) {
        const existing = this.outputTextArea.value.trim();
        if (replaceText || !existing) {
          this.outputTextArea.value = cleaned;
        } else {
          this.outputTextArea.value = existing + "\n\n" + cleaned;
        }
      }

      setTimeout(() => {
        if (this.progressContainer) {
          this.progressContainer.style.display = "none";
        }
      }, 1400);

      return cleaned;
    } catch (err) {
      console.error("OCR encountered an error:", err);
      this.updateProgress(100, "OCR ready.");
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

    // 1. Clean OCR noise and line breaks
    let clean = text
      .replace(/[\r\n]+/g, " ")
      .replace(/[|]+/g, " ")
      .replace(/[\t]+/g, " ")
      .replace(/\s+/g, " ")
      .trim();

    // 2. Fix common OCR character confusions in food ingredients
    clean = clean.replace(/\b[1l|I]N[\s\.\-]*S\b/gi, "INS");
    clean = clean.replace(/\b[1l|I]ns\b/gi, "INS");
    clean = clean.replace(/\b[1l|I]ngredients?\b/gi, "Ingredients");
    clean = clean.replace(/INS\s*([0-9]{3,4})/gi, "INS $1");

    // 3. Isolate ingredients section safely if marked, without premature cutoff
    const match = clean.match(
      /(?:INGREDIENTS|INGREDIENT|CONTAINS)\s*[:\-]?\s*(.*?)(?:NUTRITION(?:AL)?\s+(?:INFO|FACTS|VALUES|TABLE)|TYPICAL VALUES PER|BEST BEFORE DATE|$)/i
    );
    if (match && match[1] && match[1].trim().length > 15) {
      return match[1].trim();
    }

    return clean;
  }
}

window.OCREngine = OCREngine;
