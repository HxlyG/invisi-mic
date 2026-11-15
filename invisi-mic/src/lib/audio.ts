// Must match SAMPLE_RATE in backend/sim/sim.py.
export const SIM_SAMPLE_RATE = 16000
const SIM_SECONDS = 30

const toBase64 = (bytes: Uint8Array) => {
  let binary = ""
  for (let i = 0; i < bytes.length; i += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000))
  }
  return btoa(binary)
}

const fromBase64 = (encoded: string) => Uint8Array.from(atob(encoded), (char) => char.charCodeAt(0))

function encodeWav(samples: Float32Array) {
  const view = new DataView(new ArrayBuffer(44 + samples.length * 2))
  const write = (offset: number, text: string) =>
    [...text].forEach((char, i) => view.setUint8(offset + i, char.charCodeAt(0)))
  write(0, "RIFF")
  view.setUint32(4, 36 + samples.length * 2, true)
  write(8, "WAVEfmt ")
  view.setUint32(16, 16, true)
  view.setUint16(20, 1, true)
  view.setUint16(22, 1, true)
  view.setUint32(24, SIM_SAMPLE_RATE, true)
  view.setUint32(28, SIM_SAMPLE_RATE * 2, true)
  view.setUint16(32, 2, true)
  view.setUint16(34, 16, true)
  write(36, "data")
  view.setUint32(40, samples.length * 2, true)
  samples.forEach((sample, i) => view.setInt16(44 + i * 2, Math.max(-1, Math.min(1, sample)) * 32767, true))
  return new Uint8Array(view.buffer)
}

// Decodes any browser-supported track to mono 16-bit WAV at the simulation rate, as base64.
// Output is always SIM_SECONDS long: longer tracks are cut and shorter ones loop.
export async function trackToWavBase64(src: string) {
  const response = await fetch(src)
  if (!response.ok) throw new Error("Unable to load audio track")
  const context = new AudioContext()
  try {
    const decoded = await context.decodeAudioData(await response.arrayBuffer())
    const offline = new OfflineAudioContext(1, SIM_SECONDS * SIM_SAMPLE_RATE, SIM_SAMPLE_RATE)
    const source = offline.createBufferSource()
    source.buffer = decoded
    source.loop = true
    source.connect(offline.destination)
    source.start()
    const rendered = await offline.startRendering()
    return toBase64(encodeWav(rendered.getChannelData(0)))
  } finally {
    void context.close()
  }
}

export const wavBase64ToUrl = (encoded: string) =>
  URL.createObjectURL(new Blob([fromBase64(encoded)], { type: "audio/wav" }))
