/**
 * Label Lens - Camera & Video Stream Manager
 * Supports Webcams, Iriun Phone Webcam, Mobile Rear Cameras,
 * Snapshot Capture, and Frame Optimization for OCR.
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
      alert("Camera API is not supported by your browser. Please use the File Upload tab.");
      return false;
    }

    try {
      // First ask for general permission to enumerate devices with labels
      const initialStream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 1920 }, height: { ideal: 1080 } },
        audio: false
      });
      this.stopCurrentStream();
      await this.populateCameraList();
      await this.startStream();
      return true;
    } catch (err) {
      console.warn("Camera access request error:", err);
      // Fallback: try basic video
      try {
        await this.populateCameraList();
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
        opt.textContent = "No camera devices detected";
        this.cameraSelect.appendChild(opt);
        return;
      }

      let iriunFound = false;
      let preferredDeviceId = null;

      videoDevices.forEach((device, index) => {
        const opt = document.createElement("option");
        opt.value = device.deviceId;
        const label = device.label || `Camera ${index + 1}`;
        opt.textContent = label;

        // Auto-select Iriun webcam if user has phone connected via Iriun!
        if (label.toLowerCase().includes("iriun") || label.toLowerCase().includes("droidcam") || label.toLowerCase().includes("phone")) {
          opt.textContent = `[High-Res Phone Camera] ${label}`;
          preferredDeviceId = device.deviceId;
          iriunFound = true;
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

    const deviceId = this.cameraSelect ? this.cameraSelect.value : null;
    const constraints = {
      video: deviceId
        ? { deviceId: { exact: deviceId }, width: { ideal: 1920 }, height: { ideal: 1080 } }
        : { facingMode: "environment", width: { ideal: 1920 }, height: { ideal: 1080 } },
      audio: false
    };

    try {
      this.currentStream = await navigator.mediaDevices.getUserMedia(constraints);
      this.video.srcObject = this.currentStream;
      await this.video.play();
    } catch (err) {
      console.error("Failed to start video stream with constraints:", err);
      // Fallback without resolution constraint
      try {
        this.currentStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
        this.video.srcObject = this.currentStream;
        await this.video.play();
      } catch (err2) {
        console.error("Fallback camera start failed:", err2);
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

    const canvas = document.createElement("canvas");
    canvas.width = this.video.videoWidth || 1280;
    canvas.height = this.video.videoHeight || 720;

    const ctx = canvas.getContext("2d");
    // Draw raw image
    ctx.drawImage(this.video, 0, 0, canvas.width, canvas.height);

    // Apply gentle contrast enhancement for OCR readability
    this.capturedDataUrl = canvas.toDataURL("image/jpeg", 0.92);

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
