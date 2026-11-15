"use client"

import { useEffect, useRef, useState } from "react"
import styles from "./Sidebar.module.css"

import { useAppDispatch, useAppSelector } from "@/store/hooks"
import { ACCEPTED_AUDIO, AUDIO_TRACKS, findTrack, isSupportedAudio, type AudioTrack } from "@/data/audioTracks"
import { removeItem, setFocus, setMaterial, setRoom, setSyncFocus, setTrack, setUploads, updateItem } from "@/store/slices/sceneSlice"
import { setShowBeams, setUnlocking } from "@/store/slices/toolSlice"

const icon = {
  width: 15,
  height: 15,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.8,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
}

const M_TO_FT = 3.28084

type Unit = "m" | "ft"

const toDisplay = (meters: number, unit: Unit) => (unit === "ft" ? meters * M_TO_FT : meters)
const toMeters = (value: number, unit: Unit) => (unit === "ft" ? value / M_TO_FT : value)
const format = (value: number) => String(Math.round(value * 100) / 100)

interface FieldProps {
  label?: string
  value: string
  unit: string
  onChange: (value: string) => void
  onBlur?: () => void
}

function Field({ label, value, unit, onChange, onBlur }: FieldProps) {
  return (
    <div>
      {label && <span className={styles.label}>{label}</span>}
      <label className={styles.field}>
        <input
          className={styles.input}
          type="number"
          step="any"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onBlur={onBlur}
        />
        <span className={styles.unit}>{unit}</span>
      </label>
    </div>
  )
}

interface LengthFieldProps {
  label: string
  meters: number
  unit: Unit
  onChange: (meters: number) => void
}

// Keeps the raw text while editing so partial input like "1." isn't rewritten.
function LengthField({ label, meters, unit, onChange }: LengthFieldProps) {
  const [draft, setDraft] = useState<string | null>(null)

  return (
    <Field
      label={label}
      unit={unit}
      value={draft ?? format(toDisplay(meters, unit))}
      onChange={(text) => {
        setDraft(text)
        const parsed = parseFloat(text)
        if (!Number.isNaN(parsed)) onChange(toMeters(parsed, unit))
      }}
      onBlur={() => setDraft(null)}
    />
  )
}

export default function Sidebar() {
  const [roomOpen, setRoomOpen] = useState(false)
  const [nodeOpen, setNodeOpen] = useState(true)
  const [speakerOpen, setSpeakerOpen] = useState(false)
  const dispatch = useAppDispatch()
  const uploads = useAppSelector((state) => state.scene.uploads)
  const [materials, setMaterials] = useState<string[]>([])
  const [materialsError, setMaterialsError] = useState(false)
  const [voice, setVoice] = useState("65")
  const [locked, setLocked] = useState(true)
  const [previewing, setPreviewing] = useState(false)
  const [previewError, setPreviewError] = useState(false)
  const [uploadError, setUploadError] = useState(false)
  const [recording, setRecording] = useState(false)
  const [recordError, setRecordError] = useState("")
  const lockTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const previewAudio = useRef<HTMLAudioElement | null>(null)
  const uploadsRef = useRef<AudioTrack[]>([])
  const fileInput = useRef<HTMLInputElement | null>(null)
  const recorder = useRef<MediaRecorder | null>(null)
  const recordingStream = useRef<MediaStream | null>(null)
  const recordingChunks = useRef<Blob[]>([])

  useEffect(() => {
    let active = true
    fetch("/api/materials", { cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) throw new Error("Materials request failed")
        const body: { materials?: unknown } = await response.json()
        if (!Array.isArray(body.materials) || !body.materials.every((item) => typeof item === "string")) {
          throw new Error("Invalid materials response")
        }
        const names: string[] = body.materials
        if (active) {
          setMaterials(names)
          if (names[0]) dispatch(setMaterial(names[0]))
        }
      })
      .catch(() => {
        if (active) setMaterialsError(true)
      })
    return () => { active = false }
  }, [dispatch])

  useEffect(() => () => {
    if (lockTimer.current) clearTimeout(lockTimer.current)
    previewAudio.current?.pause()
    recorder.current?.stream.getTracks().forEach((track) => track.stop())
    recordingStream.current?.getTracks().forEach((track) => track.stop())
    uploadsRef.current.forEach((track) => URL.revokeObjectURL(track.src))
  }, [])

  const tracks = [...AUDIO_TRACKS, ...uploads]

  const selectedId = useAppSelector((state) => state.scene.selected?.id)

  // Pausing fires onpause, which resets the preview state.
  useEffect(() => () => previewAudio.current?.pause(), [selectedId])

  const stopPreview = () => {
    previewAudio.current?.pause()
    previewAudio.current = null
  }

  const togglePreview = (src: string) => {
    if (previewing) return stopPreview()
    setPreviewError(false)
    const audio = new Audio(src)
    audio.onpause = () => setPreviewing(false)
    audio.onended = () => setPreviewing(false)
    audio.onerror = () => {
      setPreviewError(true)
      setPreviewing(false)
    }
    previewAudio.current = audio
    setPreviewing(true)
    audio.play().catch(() => {
      setPreviewError(true)
      setPreviewing(false)
    })
  }

  const startRecording = async (speakerId: string) => {
    setRecordError("")
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setRecordError("Audio recording is not supported in this browser")
      return
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      recordingStream.current = stream
      recordingChunks.current = []
      const mimeType = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus"]
        .find((type) => MediaRecorder.isTypeSupported(type))
      const activeRecorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined)
      recorder.current = activeRecorder
      activeRecorder.ondataavailable = (event) => {
        if (event.data.size) recordingChunks.current.push(event.data)
      }
      activeRecorder.onerror = () => setRecordError("Recording failed. Please try again.")
      activeRecorder.onstop = () => {
        stream.getTracks().forEach((track) => track.stop())
        recordingStream.current = null
        setRecording(false)
        const blob = new Blob(recordingChunks.current, { type: activeRecorder.mimeType || "audio/webm" })
        recordingChunks.current = []
        if (!blob.size) {
          setRecordError("No audio was captured. Try recording again.")
          return
        }
        const track: AudioTrack = {
          id: `recording-${Date.now()}`,
          name: `Recording ${new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`,
          src: URL.createObjectURL(blob),
        }
        uploadsRef.current = [...uploadsRef.current, track]
        dispatch(setUploads(uploadsRef.current))
        dispatch(setTrack({ id: speakerId, trackId: track.id }))
      }
      activeRecorder.start()
      setRecording(true)
    } catch {
      recordingStream.current?.getTracks().forEach((track) => track.stop())
      recordingStream.current = null
      setRecordError("Microphone access was denied or unavailable")
    }
  }

  const room = useAppSelector((state) => state.scene.room)
  const material = useAppSelector((state) => state.scene.material)
  const selected = useAppSelector((state) => state.scene.selected)
  const node = useAppSelector((state) => {
    const { selected: ref, speakers, micArrays } = state.scene
    if (!ref) return undefined
    return (ref.kind === "speaker" ? speakers : micArrays).find((i) => i.id === ref.id)
  })
  const unit = useAppSelector((state) => state.dimension.currentUnit)
  const speakers = useAppSelector((state) => state.scene.speakers)
  const micArrays = useAppSelector((state) => state.scene.micArrays)
  const syncFocus = useAppSelector((state) => state.scene.syncFocus)
  const showBeams = useAppSelector((state) => state.tool.showBeams)

  const outline = room.outline
  const footprintArea = outline?.length
    ? Math.abs(outline.reduce((area, point, index) => {
      const next = outline[(index + 1) % outline.length]
      return area + point.x * next.y - next.x * point.y
    }, 0)) / 2
    : room.width * room.length
  const roomVolume = footprintArea * room.height
  const volume = toDisplay(1, unit) ** 3 * roomVolume
  return (
    <aside className={`${styles.sidebar} hud-scroll`}>
      <div className={`${styles.section} ${styles.header}`}>
        <svg {...icon} className={styles.headerIcon}>
          <path d="M4 6h8M16 6h4M4 12h3M11 12h9M4 18h10M18 18h2" />
          <path d="M14 4v4M9 10v4M16 16v4" />
        </svg>
        <span className={styles.headerTitle}>Properties</span>
        <span className={styles.tag}>Live</span>
      </div>

      <section className={styles.section}>
        <button
          type="button"
          className={styles.sectionToggle}
          onClick={() => setRoomOpen(!roomOpen)}
          aria-expanded={roomOpen}
        >
          <svg {...icon} className={styles.headerIcon}>
            <path d="M12 2 3 7v10l9 5 9-5V7l-9-5ZM3 7l9 5 9-5M12 12v10" />
          </svg>
          <span className={styles.headerTitle}>Room geometry</span>
          <svg
            {...icon}
            className={`${styles.chevron} ${roomOpen ? "" : styles.chevronOpen}`}
          >
            <path d="m6 9 6 6 6-6" />
          </svg>
        </button>

        {roomOpen && (
          <div className={styles.body}>
            <div className={`${styles.row} ${styles.cols2}`}>
              <LengthField
                label="Width"
                unit={unit}
                meters={room.width}
                onChange={(width) => dispatch(setRoom({ width }))}
              />
              <LengthField
                label="Length"
                unit={unit}
                meters={room.length}
                onChange={(length) => dispatch(setRoom({ length }))}
              />
            </div>
            <LengthField
              label="Ceiling height"
              unit={unit}
              meters={room.height}
              onChange={(height) => dispatch(setRoom({ height }))}
            />
            <div className={styles.lockRow}>
              <span className={styles.lockText}>Mic direction cones</span>
              <button
                type="button"
                role="switch"
                aria-checked={showBeams}
                aria-label="Show mic direction cones"
                className={`${styles.switch} ${showBeams ? styles.switchOn : ""}`}
                onClick={() => dispatch(setShowBeams(!showBeams))}
              />
            </div>
            <div>
              <span className={styles.label}>Wall acoustic absorption</span>
              <div className={styles.selectWrap}>
                <select
                  className={styles.select}
                  value={material}
                  onChange={(e) => dispatch(setMaterial(e.target.value))}
                  disabled={!materials.length}
                >
                  {!materials.length && (
                    <option value="">{materialsError ? "Materials unavailable" : "Loading materials…"}</option>
                  )}
                  {materials.map((material) => (
                    <option key={material} value={material}>
                      {material.replace(/[_-]+/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase())}
                    </option>
                  ))}
                </select>
                <svg {...icon} className={styles.selectChevron}>
                  <path d="m6 9 6 6 6-6" />
                </svg>
              </div>
            </div>
            <div className={styles.meta}>
              <span>Room volume</span>
              <span>{Math.round(volume)} {unit}³</span>
            </div>
          </div>
        )}
      </section>

      <section className={styles.section}>
        <div className={styles.header}>
          <button
            type="button"
            className={styles.sectionToggle}
            onClick={() => setNodeOpen((open) => !open)}
            aria-expanded={nodeOpen}
          >
            <svg {...icon} className={styles.headerIcon}>
              <circle cx="12" cy="12" r="9" />
              <circle cx="12" cy="12" r="5" />
              <circle cx="12" cy="12" r="1" />
            </svg>
            <span className={styles.headerTitle}>Selected node</span>
            {selected && <span className={styles.sectionSummary}>{node?.name}</span>}
            <svg {...icon} className={`${styles.chevron} ${nodeOpen ? "" : styles.chevronOpen}`}>
              <path d="m6 9 6 6 6-6" />
            </svg>
          </button>
          <button
            type="button"
            className={styles.iconBtn}
            aria-label="Delete node"
            disabled={!selected}
            onClick={() => selected && dispatch(removeItem(selected))}
          >
            <svg {...icon}><path d="M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14M10 10v6M14 10v6" /></svg>
          </button>
        </div>

        {nodeOpen && selected && node ? (
          <div className={styles.body}>
            <div className={styles.node}>
              <div
                className={`${styles.nodeIcon} ${selected.kind === "speaker" ? styles.speakerIcon : styles.micIcon}`}
              >
                <svg {...icon} width={18} height={18}>
                  {selected.kind === "speaker" ? (
                    <>
                      <circle cx="12" cy="8" r="4" />
                      <path d="M4 21c0-4 3.6-7 8-7s8 3 8 7" />
                    </>
                  ) : (
                    <>
                      <circle cx="12" cy="12" r="2" />
                      <path d="M4.9 19.1C1 15.2 1 8.8 4.9 4.9M7.8 16.2c-2.3-2.3-2.3-6.1 0-8.5M16.2 7.8c2.3 2.3 2.3 6.1 0 8.5M19.1 4.9C23 8.8 23 15.1 19.1 19" />
                    </>
                  )}
                </svg>
              </div>
              <div style={{ flex: 1 }}>
                <div className={styles.nodeName}>{node.name}</div>
                <div className={styles.nodeKind}>{selected.kind === "speaker" ? "Human speaker" : "Mic array"}</div>
              </div>
              <span className={styles.tag}>Active</span>
            </div>

            <div className={`${styles.row} ${styles.cols3}`}>
              {("xyz" as const).split("").map((axis) => (
                <LengthField
                  key={`${selected.id}-${axis}`}
                  label={axis.toUpperCase()}
                  unit={unit}
                  meters={node.position[axis as "x" | "y" | "z"]}
                  onChange={(value) => dispatch(updateItem({ ...selected, patch: { [axis]: value } }))}
                />
              ))}
            </div>

            {selected.kind === "speaker" && (
              <>
                <Field label="Voice level" unit="dB SPL" value={voice} onChange={setVoice} />

                <div>
                  <span className={styles.label}>Audio track</span>
                  <div className={styles.trackRow}>
                    <div className={`${styles.selectWrap} ${styles.trackSelect}`}>
                      <select
                        className={styles.select}
                        value={findTrack(node.trackId, tracks)?.id ?? ""}
                        onChange={(e) => {
                          stopPreview()
                          setPreviewError(false)
                          dispatch(setTrack({ id: selected.id, trackId: e.target.value || null }))
                        }}
                      >
                        <option value="">None (silent)</option>
                        {tracks.map((track) => (
                          <option key={track.id} value={track.id}>{track.name}</option>
                        ))}
                      </select>
                      <svg {...icon} className={styles.selectChevron}>
                        <path d="m6 9 6 6 6-6" />
                      </svg>
                    </div>
                    <button
                      type="button"
                      className={styles.previewBtn}
                      aria-label={previewing ? "Stop preview" : "Preview track"}
                      disabled={!findTrack(node.trackId, tracks)}
                      onClick={() => {
                        const track = findTrack(node.trackId, tracks)
                        if (track) togglePreview(track.src)
                      }}
                    >
                      <svg {...icon} fill="currentColor" stroke="none">
                        {previewing ? <rect x="6" y="6" width="12" height="12" rx="1" /> : <path d="M7 4.5v15a1 1 0 0 0 1.5.9l12-7.5a1 1 0 0 0 0-1.8l-12-7.5A1 1 0 0 0 7 4.5Z" />}
                      </svg>
                    </button>
                    <button
                      type="button"
                      className={`${styles.previewBtn} ${recording ? styles.recordingBtn : ""}`}
                      aria-label={recording ? "Stop recording" : "Record audio"}
                      title={recording ? "Stop recording" : "Record audio"}
                      onClick={() => {
                        if (recording) recorder.current?.stop()
                        else void startRecording(selected.id)
                      }}
                    >
                      <svg {...icon} fill={recording ? "currentColor" : "none"}>
                        {recording ? <rect x="7" y="7" width="10" height="10" rx="1" /> : <circle cx="12" cy="12" r="7" />}
                      </svg>
                    </button>
                    <button
                      type="button"
                      className={styles.previewBtn}
                      aria-label="Upload MP3 or WAV file"
                      onClick={() => fileInput.current?.click()}
                    >
                      <svg {...icon}>
                        <path d="M12 16V4M7 9l5-5 5 5M4 20h16" />
                      </svg>
                    </button>
                    <input
                      ref={fileInput}
                      type="file"
                      accept={ACCEPTED_AUDIO}
                      hidden
                      onChange={(e) => {
                        const file = e.target.files?.[0]
                        e.target.value = ""
                        if (!file) return
                        if (!isSupportedAudio(file)) return setUploadError(true)
                        setUploadError(false)
                        setPreviewError(false)
                        stopPreview()
                        const track: AudioTrack = {
                          id: `upload-${uploadsRef.current.length + 1}`,
                          name: file.name,
                          src: URL.createObjectURL(file),
                        }
                        uploadsRef.current = [...uploadsRef.current, track]
                        dispatch(setUploads(uploadsRef.current))
                        dispatch(setTrack({ id: selected.id, trackId: track.id }))
                      }}
                    />
                  </div>
                  {previewError && <div className={styles.nodeKind}>Unable to play track</div>}
                  {uploadError && <div className={styles.nodeKind}>Only MP3 or WAV files are supported</div>}
                  {recordError && <div className={styles.nodeKind} role="status">{recordError}</div>}
                  {recording && <div className={styles.nodeKind} role="status">Recording… select stop to use this audio</div>}
                </div>

                <div className={styles.lockRow}>
                  <svg {...icon} className={styles.lockIcon}>
                    <rect x="4" y="11" width="16" height="10" rx="2" />
                    <path d="M8 11V7a4 4 0 0 1 8 0v4" />
                  </svg>
                  <span className={styles.lockText}>
                    Active talker
                    <span className={styles.lockHint}>(lock beam)</span>
                  </span>
                  <button
                    type="button"
                    role="switch"
                    aria-checked={locked}
                    aria-label="Lock beam to active talker"
                    className={`${styles.switch} ${locked ? styles.switchOn : ""}`}
                    onClick={() => {
                      if (lockTimer.current) clearTimeout(lockTimer.current)
                      dispatch(setUnlocking(locked))
                      setLocked((current) => !current)
                      if (locked) {
                        lockTimer.current = setTimeout(() => {
                        dispatch(setUnlocking(false))
                        lockTimer.current = null
                        }, 250)
                      }
                    }}
                  />
                </div>
              </>
            )}
          </div>
        ) : nodeOpen ? (
          <div className={styles.body}>
            <div className={styles.nodeKind}>No node selected</div>
          </div>
        ) : null}
      </section>

      <section className={styles.section}>
        <button
          type="button"
          className={styles.sectionToggle}
          onClick={() => setSpeakerOpen((open) => !open)}
          aria-expanded={speakerOpen}
        >
          <svg {...icon} className={styles.headerIcon}>
            <circle cx="12" cy="8" r="4" />
            <path d="M4 21c0-4 3.6-7 8-7s8 3 8 7" />
          </svg>
          <span className={styles.headerTitle}>Human speaker</span>
          <svg {...icon} className={`${styles.chevron} ${speakerOpen ? "" : styles.chevronOpen}`}>
            <path d="m6 9 6 6 6-6" />
          </svg>
        </button>
        {speakerOpen && <div className={styles.body}>
          {micArrays.length === 0 && <div className={styles.nodeKind}>No mic arrays</div>}
          <div className={styles.lockRow}>
            <span className={styles.lockText}>
              Sync mics
              <span className={styles.lockHint}>(one human)</span>
            </span>
            <button
              type="button"
              role="switch"
              aria-checked={syncFocus}
              aria-label="Sync all mic arrays to one human speaker"
              className={`${styles.switch} ${syncFocus ? styles.switchOn : ""}`}
              onClick={() => dispatch(setSyncFocus(!syncFocus))}
            />
          </div>
          {syncFocus ? (
            micArrays.length > 0 && (
              <div>
                <span className={styles.label}>All mics focus</span>
                <div className={styles.selectWrap}>
                  <select
                    className={styles.select}
                    value={micArrays[0].focusId && speakers.some((s) => s.id === micArrays[0].focusId) ? micArrays[0].focusId : ""}
                    onChange={(e) => dispatch(setFocus({ id: micArrays[0].id, focusId: e.target.value || null }))}
                  >
                    <option value="">None</option>
                    {speakers.map((s) => (
                      <option key={s.id} value={s.id}>{s.name}</option>
                    ))}
                  </select>
                  <svg {...icon} className={styles.selectChevron}>
                    <path d="m6 9 6 6 6-6" />
                  </svg>
                </div>
              </div>
            )
          ) : (
            <div className={styles.nodeKind}>Each mic targets its nearest speaker.</div>
          )}
        </div>}
      </section>

      {/* <section className={styles.section}>
        <div className={styles.header}>
          <svg {...icon} className={styles.headerIcon}>
            <path d="M2 8c2-2 4-2 6 0s4 2 6 0 4-2 6 0M2 13c2-2 4-2 6 0s4 2 6 0 4-2 6 0M2 18c2-2 4-2 6 0s4 2 6 0 4-2 6 0" />
          </svg>
          <span className={styles.headerTitle}>Acoustic telemetry</span>
          <button
            type="button"
            className={styles.infoButton}
            aria-label="About acoustic telemetry"
            aria-expanded={telemetryInfoOpen}
            aria-controls="telemetry-info"
            onClick={() => setTelemetryInfoOpen((open) => !open)}
          >
            <svg {...icon}>
              <circle cx="12" cy="12" r="9" />
              <path d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.6.3-1 .9-1 1.5M12 17h.01" />
            </svg>
          </button>
        </div>

        <div className={styles.body}>
          {telemetryInfoOpen && (
            <div className={styles.telemetryInfo} id="telemetry-info">
              <strong>What these estimates mean</strong>
              <p><b>Estimated SNR:</b> the target voice level compared with background noise. Higher is clearer.</p>
              <p><b>Beam focus score:</b> how strongly the mic array is focused on the target speaker.</p>
              <p><b>Target tracking:</b> indicates whether speaker tracking estimates are updating.</p>
            </div>
          )}
          <Metric
            label="Estimated SNR"
            value={estimatedSnr === null ? "—" : `${estimatedSnr >= 0 ? "+" : ""}${estimatedSnr.toFixed(1)}`}
            unit="dB"
            valueClass={styles.green}
            percent={estimatedSnr === null ? undefined : Math.max(0, Math.min(100, ((estimatedSnr + 10) / 50) * 100))}
          />
          <Metric
            label="Beam focus score"
            value={focusScore === null ? "—" : String(Math.round(focusScore))}
            unit="%"
            valueClass={styles.cyan}
            percent={focusScore ?? undefined}
          />
          <div className={styles.statusLine}>
            <span className={styles.dot} />
            {averageDistance === null ? "No speaker target · estimates limited" : "Room and target estimates updating"}
          </div>
        </div>
      </section> */}

    </aside>
  )
}