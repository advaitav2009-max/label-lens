/**
 * Label Lens - Camera & Video Stream Manager
 * Features:
 * - High-resolution stream with continuous autofocus for mobile & webcam
 * - Automatic Iriun Webcam & rear mobile sensor selection
 * - Lightweight client-side snapshot capture (<250KB) to prevent 413 payload limits
 */

class CameraManager {
  constructor(videoElementId, cameraSelectId, onCaptureCallback) {
    this.video = document.getElementById(videoElementId);
    this.cameraSelect = document.getElementById(cameraSelectId);
    this.onCaptureCallback = onCaptureCallback;
    this.currentStream = null;
    this.capturedDataUrl = null;

    if (this.cameraSelect) {
      this.cameraSelect.addEventListener("change", () => this.switchCamera());
    }
  }

  async init() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      alert("Camera API is not supported by your browser. Please use the Attach Photos tab.");
      return false;
    }

    try {
      await this.populateCameraList();
      await this.startStream();
      return true;
    } catch (err) {
      console.warn("Camera init retry:", err);
      try {
        await this.startStream();
        return true;
      } catch (err2) {
        console.error("Camera initialisation failed:", err2);
        return false;
      }
    }
  }

  async populateCameraList() {
    if (!this.cameraSelect) return;
    try {
      const devices = await navigator.mediaDevices.enumerateDevices();
      const videoDevices = devices.filter(d => d.kind === "videoinput");

      this.cameraSelect.innerHTML = "";
      if (videoDevices.length === 0) {
        const opt = document.createElement("option");
        opt.value = "";
        opt.textContent = "Camera ready (Default sensor)";
        this.cameraSelect.appendChild(opt);
        return;
      }

      let preferredDeviceId = null;

      videoDevices.forEach((device, index) => {
        const opt = document.createElement("option");
        opt.value = device.deviceId;
        const label = device.label || `Camera ${index + 1}`;
        opt.textContent = label;

        // Auto-select Iriun webcam or rear environment camera
        const l = label.toLowerCase();
        if (l.includes("iriun") || l.includes("droidcam") || l.includes("back") || l.includes("rear") || l.includes("environment")) {
          preferredDeviceId = device.deviceId;
        }

        this.cameraSelect.appendChild(opt);
      });

      if (preferredDeviceId) {
        this.cameraSelect.value = preferredDeviceId;
      }
    } catch (err) {
      console.error("Error enumerating video devices:", err);
    }
  }

  async startStream() {
    this.stopCurrentStream();
    if (!this.video) return;

    const deviceId = this.cameraSelect && this.cameraSelect.value ? this.cameraSelect.value : null;

    // Advanced constraints for sharp macro text reading
    const constraints = {
      video: deviceId
        ? {
            deviceId: { exact: deviceId },
            width: { ideal: 1920, min: 1280 },
            height: { ideal: 1080, min: 720 }
          }
        : {
            facingMode: { ideal: "environment" },
            width: { ideal: 1920, min: 1280 },
            height: { ideal: 1080, min: 720 }
          },
      audio: false
    };

    try {
      this.currentStream = await navigator.mediaDevices.getUserMedia(constraints);
      this.video.srcObject = this.currentStream;
      await this.video.play();

      // Attempt to enable continuous focus if supported by hardware
      const track = this.currentStream.getVideoTracks()[0];
      if (track && typeof track.applyConstraints === "function") {
        try {
          const capabilities = track.getCapabilities ? track.getCapabilities() : {};
          const advanced = {};
          if (capabilities.focusMode && capabilities.focusMode.includes("continuous")) {
            advanced.focusMode = "continuous";
          }
          if (capabilities.exposureMode && capabilities.exposureMode.includes("continuous")) {
            advanced.exposureMode = "continuous";
          }
          if (Object.keys(advanced).length > 0) {
            await track.applyConstraints({ advanced: [advanced] });
          }
        } catch (capErr) {
          // Non-critical, ignore
        }
      }
    } catch (err) {
      console.warn("Retrying camera with basic fallback constraints:", err);
      try {
        this.currentStream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: "environment" },
          audio: false
        });
        this.video.srcObject = this.currentStream;
        await this.video.play();
      } catch (err2) {
        console.error("Camera stream failed entirely:", err2);
      }
    }
  }

  async switchCamera() {
    await this.startStream();
  }

  captureSnapshot() {
    if (!this.video || !this.currentStream) {
      alert("Please start the camera first.");
      return null;
    }

    const vw = this.video.videoWidth || 1280;
    const vh = this.video.videoHeight || 720;

    // Rescale to max 1800px to maintain crisp detail without exceeding payload limits
    const maxDim = 1800;
    let width = vw;
    let height = vh;
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

    const ctx = canvas.getContext("2d", { willReadFrequently: true });
    ctx.drawImage(this.video, 0, 0, width, height);

    // Compressed JPEG (<250KB)
    this.capturedDataUrl = canvas.toDataURL("image/jpeg", 0.82);

    if (this.onCaptureCallback) {
      this.onCaptureCallback(this.capturedDataUrl);
    }

    return this.capturedDataUrl;
  }

  stopCurrentStream() {
    if (this.currentStream) {
      this.currentStream.getTracks().forEach(track => track.stop());
      this.currentStream = null;
    }
    if (this.video) {
      this.video.srcObject = null;
    }
  }
}

window.CameraManager = CameraManager;
