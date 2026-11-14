/**
 * Thin wrapper over MediaRecorder.
 *
 * Browser support is the awkward part: Chrome and Firefox produce WebM/Opus,
 * Safari produces MP4. Ask for the first format the browser admits to
 * supporting rather than hard-coding one, and let the thrown error carry the
 * permission denial up to the UI.
 */
export class Recorder {
  private recorder: MediaRecorder | null = null;
  private stream: MediaStream | null = null;
  private chunks: Blob[] = [];

  static isSupported(): boolean {
    return typeof window !== "undefined" && typeof window.MediaRecorder !== "undefined";
  }

  static mimeType(): string {
    if (!Recorder.isSupported()) return "";
    const candidates = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg"];
    return candidates.find((type) => MediaRecorder.isTypeSupported(type)) ?? "";
  }

  static extensionFor(mimeType: string): string {
    if (mimeType.includes("mp4")) return "m4a";
    if (mimeType.includes("ogg")) return "ogg";
    return "webm";
  }

  async start(): Promise<void> {
    if (!Recorder.isSupported()) {
      throw new Error("This browser cannot record audio. Try typing instead.");
    }

    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      });
    } catch (error) {
      const name = error instanceof DOMException ? error.name : "";
      if (name === "NotAllowedError" || name === "SecurityError") {
        throw new Error("Microphone access was blocked. Allow it in the browser and try again.");
      }
      if (name === "NotFoundError") {
        throw new Error("No microphone was found on this device. You can type instead.");
      }
      throw new Error("The microphone could not be opened.");
    }

    const mimeType = Recorder.mimeType();
    this.recorder = new MediaRecorder(this.stream, mimeType ? { mimeType } : undefined);
    this.chunks = [];

    this.recorder.addEventListener("dataavailable", (event) => {
      if (event.data.size > 0) this.chunks.push(event.data);
    });

    this.recorder.start();
  }

  stop(): Promise<Blob> {
    const recorder = this.recorder;
    if (!recorder) return Promise.reject(new Error("Nothing is being recorded."));

    return new Promise((resolve, reject) => {
      recorder.addEventListener("stop", () => {
        const type = recorder.mimeType || "audio/webm";
        const blob = new Blob(this.chunks, { type });
        this.release();
        resolve(blob);
      });
      recorder.addEventListener("error", () => {
        this.release();
        reject(new Error("The recording failed. Try again."));
      });
      recorder.stop();
    });
  }

  /** Stop without producing a blob — used when the component unmounts. */
  cancel(): void {
    try {
      this.recorder?.stop();
    } catch {
      // Already stopped; releasing the tracks is what matters.
    }
    this.release();
  }

  private release(): void {
    this.stream?.getTracks().forEach((track) => track.stop());
    this.stream = null;
    this.recorder = null;
    this.chunks = [];
  }
}
