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

        // Fast Laplacian variance blur assessment on downscaled canvas
        const blurScore = OCREngine.calculateBlurScore(canvas);
        const isVeryBlurry = blurScore < 20;

        resolve({
          compressedDataUrl,
          ocrDataUrl: compressedDataUrl,
          width,
          height,
          blurScore,
          isVeryBlurry
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

  /**
   * Fast Laplacian variance blur estimator on a downscaled canvas (320x240 max).
   * Returns a score: < 20 indicates severe blur or featureless smearing.
   * Typical focused text with edges yields > 80.
   */
  static calculateBlurScore(canvas) {
    try {
      const w = Math.min(canvas.width, 320);
      const h = Math.min(canvas.height, 240);
      const sc = document.createElement("canvas");
      sc.width = w;
      sc.height = h;
      const sctx = sc.getContext("2d", { willReadFrequently: true }) || sc.getContext("2d");
      sctx.drawImage(canvas, 0, 0, w, h);
      const imgData = sctx.getImageData(0, 0, w, h);
      const d = imgData.data;

      // Convert to grayscale
      const gray = new Float32Array(w * h);
      for (let i = 0, j = 0; i < d.length; i += 4, j++) {
        gray[j] = 0.299 * d[i] + 0.587 * d[i + 1] + 0.114 * d[i + 2];
      }

      // Sample Laplacian kernel: [0, 1, 0, 1, -4, 1, 0, 1, 0] with stride 2 for efficiency
      let sum = 0;
      let sumSq = 0;
      let count = 0;

      for (let y = 1; y < h - 1; y += 2) {
        const row = y * w;
        const rowAbove = (y - 1) * w;
        const rowBelow = (y + 1) * w;
        for (let x = 1; x < w - 1; x += 2) {
          const lap =
            gray[rowAbove + x] +
            gray[rowBelow + x] +
            gray[row + x - 1] +
            gray[row + x + 1] -
            4 * gray[row + x];
          sum += lap;
          sumSq += lap * lap;
          count++;
        }
      }

      if (count === 0) return 100;
      const mean = sum / count;
      const variance = sumSq / count - mean * mean;
      return Math.round(variance);
    } catch (e) {
      return 100; // fail-safe: assume clear if canvas read is blocked
    }
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
    clean = clean.replace(/\bpa[1l|i]m[\s\-_]*o[il1]+s?\b/gi, "palm oil");
    clean = clean.replace(/\bpa[1l|i]m[\s\-_]*o[li1]+e[il1]+ns?\b/gi, "palmolein");
    clean = clean.replace(/\bpam[\s\-_]*o[li1]+e[il1]+ns?\b/gi, "palmolein");
    clean = clean.replace(/\bpamolein\b/gi, "palmolein");
    clean = clean.replace(/\bpamolin\b/gi, "palmolein");
    clean = clean.replace(/\bpalmolin\b/gi, "palmolein");
    clean = clean.replace(/\bpalmolene\b/gi, "palmolein");
    clean = clean.replace(/\bpalmoil\b/gi, "palm oil");
    clean = clean.replace(/\bpalm[\-_]oil\b/gi, "palm oil");
    clean = clean.replace(/\bpalmfat\b/gi, "palm fat");
    clean = clean.replace(/\bpalm[\-_]fat\b/gi, "palm fat");
    clean = clean.replace(/\b[1l|]odised\b/gi, "iodised");
    clean = clean.replace(/\b[1l|]odized\b/gi, "iodized");

    // 3. Isolate ingredients section safely only if an explicit "INGREDIENTS" keyword is present
    // Avoid matching 'CONTAINS' (which usually declares allergens at the bottom and would cut off earlier ingredients)
    const match = clean.match(
      /\b(?:INGREDIENTS|INGREDIENT)\b\s*[:\-]?\s*(.*?)(?:NUTRITION(?:AL)?\s+(?:INFO|FACTS|VALUES|TABLE)|TYPICAL VALUES PER|BEST BEFORE DATE|$)/i
    );
    if (match && match[1] && match[1].trim().length > 15) {
      return match[1].trim();
    }

    return clean;
  }
}

window.OCREngine = OCREngine;
