"use client"

import { useEffect, useRef, useState } from "react"
import { useAppDispatch, useAppSelector } from "@/store/hooks"
import { setUnit, setViewMode } from "@/store/slices/dimensionSlice"
import { loadSimulation, setSimAudio, type ImportedScene, type SceneItem } from "@/store/slices/sceneSlice"
import { AUDIO_TRACKS, findTrack } from "@/data/audioTracks"
import { SIMULATION_PRESETS } from "@/data/simulationPresets"
import { trackToWavBase64, wavBase64ToUrl } from "@/lib/audio"
import styles from "./Topbar.module.css"

const icon = {
  width: 18,
  height: 18,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.8,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
}

export default function Topbar() {
  const [apiState, setApiState] = useState<"checking" | "connected" | "disconnected">("checking")
  const [running, setRunning] = useState(false)
  const [latency, setLatency] = useState<number | null>(null)
  const [runMessage, setRunMessage] = useState("")
  const [activePreset, setActivePreset] = useState("custom")
  const importInput = useRef<HTMLInputElement | null>(null)
  const dispatch = useAppDispatch()
  const view = useAppSelector((state) => state.dimension.viewMode)
  const unit = useAppSelector((state) => state.dimension.currentUnit)
  const room = useAppSelector((state) => state.scene.room)
  const material = useAppSelector((state) => state.scene.material)
  const speakers = useAppSelector((state) => state.scene.speakers)
  const micArrays = useAppSelector((state) => state.scene.micArrays)
  const syncFocus = useAppSelector((state) => state.scene.syncFocus)
  const uploads = useAppSelector((state) => state.scene.uploads)
  const simAudio = useAppSelector((state) => state.scene.simAudio)

  useEffect(() => () => simAudio.forEach((url) => URL.revokeObjectURL(url)), [simAudio])
  useEffect(() => {
    const controller = new AbortController()
    fetch("/api/simulation", { signal: controller.signal, cache: "no-store" })
      .then((response) => setApiState(response.ok ? "connected" : "disconnected"))
      .catch(() => {
        if (!controller.signal.aborted) setApiState("disconnected")
      })
    return () => controller.abort()
  }, [])

  const runSimulation = async () => {
    setRunning(true)
    setRunMessage("")
    dispatch(setSimAudio([]))
    const startedAt = performance.now()
    try {
      const is2d = view === "2d"
      const talkerAudio = await Promise.all(speakers.map(async ({ trackId }) => {
        const track = findTrack(trackId, [...AUDIO_TRACKS, ...uploads])
        return track ? trackToWavBase64(track.src) : null
      }))
      const response = await fetch("/api/simulation", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          is_2_dimensional: is2d,
          shoebox: is2d ? [room.width, room.length] : [room.width, room.length, room.height],
          outline: room.outline?.map(({ x, y }) => [x, y]) ?? null,
          mics: micArrays.map(({ position }) => is2d
            ? [position.x, position.y]
            : [position.x, position.y, position.z]),
          talkers: speakers.map(({ position }) => is2d
            ? [position.x, position.y]
            : [position.x, position.y, position.z]),
          material: material || null,
          talker_tracks: speakers.map(({ trackId }) => trackId ?? null),
          mic_focus: micArrays.map(({ focusId }) => {
            const index = speakers.findIndex((speaker) => speaker.id === focusId)
            return index === -1 ? null : index
          }),
          talker_audio: talkerAudio,
        }),
      })
      const result = await response.json()
      setLatency(Math.round(performance.now() - startedAt))
      if (!response.ok) throw new Error(result.error ?? "Simulation request failed")
      setApiState("connected")
      const micAudio = Array.isArray(result.mic_audio)
        ? result.mic_audio.map((output: { audio: string }) => output.audio)
        : result.audio
      if (Array.isArray(micAudio)) dispatch(setSimAudio(micAudio.map(wavBase64ToUrl)))
      const rt60 = typeof result.rt60 === "number" ? ` · RT60 ${result.rt60.toFixed(2)} s` : ""
      setRunMessage(micAudio?.length
        ? `Simulation complete${rt60} · audio ready`
        : `Simulation complete${rt60} · assign an audio track to hear it`)
    } catch (error) {
      setApiState("disconnected")
      setRunMessage(error instanceof Error ? error.message : "Simulation request failed")
    } finally {
      setRunning(false)
    }
  }

  const applyPreset = (presetId: string) => {
    const preset = SIMULATION_PRESETS.find((entry) => entry.id === presetId)
    setActivePreset(preset ? presetId : "custom")
    if (!preset) return
    dispatch(loadSimulation(preset.scene))
    dispatch(setViewMode("3d"))
    dispatch(setUnit("m"))
    setRunMessage(`${preset.name} preset loaded`)
  }

  const exportSimulation = () => {
    const allTracks = [...AUDIO_TRACKS, ...uploads]
    const simulation = {
      format: "invisi-mic-simulation",
      version: 1,
      exportedAt: new Date().toISOString(),
      units: "meters",
      view,
      room: {
        dimensions: { width: room.width, length: room.length, height: room.height },
        outline: room.outline ?? null,
        tiers: room.tiers ?? [],
        stage: room.stage ?? null,
        pillars: room.pillars ?? [],
        material: material || null,
      },
      speakers: speakers.map((speaker, index) => {
        const track = findTrack(speaker.trackId, allTracks)
        return {
          id: speaker.id,
          name: speaker.name,
          position: speaker.position,
          audioTrack: track
            ? { id: track.id, name: track.name, source: track.src, uploaded: track.id.startsWith("upload-") }
            : null,
          simulationIndex: index,
        }
      }),
      micArrays: micArrays.map((mic, index) => ({
        id: mic.id,
        name: mic.name,
        position: mic.position,
        focusSpeakerId: mic.focusId ?? null,
        focusSpeakerIndex: mic.focusId ? speakers.findIndex((speaker) => speaker.id === mic.focusId) : null,
        simulationIndex: index,
      })),
      settings: {
        is2d: view === "2d",
        sampleRate: 16000,
        audioDurationSeconds: 30,
        synchronizedMicFocus: syncFocus,
      },
    }
    const blob = new Blob([JSON.stringify(simulation, null, 2)], { type: "application/json" })
    const url = URL.createObjectURL(blob)
    const link = document.createElement("a")
    link.href = url
    link.download = `invisi-mic-simulation-${new Date().toISOString().replace(/[:.]/g, "-")}.json`
    link.click()
    URL.revokeObjectURL(url)
  }

  const importSimulation = async (file: File) => {
    try {
      const data: unknown = JSON.parse(await file.text())
      if (!data || typeof data !== "object") throw new Error("Invalid JSON structure")
      const input = data as Record<string, unknown>
      if (input.format !== "invisi-mic-simulation" || input.version !== 1) {
        throw new Error("Unsupported simulation JSON format")
      }
      const roomData = input.room as Record<string, unknown> | null
      const dimensions = roomData?.dimensions as Record<string, unknown> | null
      const validDimension = (value: unknown): value is number => typeof value === "number" && Number.isFinite(value) && value > 0
      const validCoordinate = (value: unknown): value is number => typeof value === "number" && Number.isFinite(value)
      if (!dimensions || !validDimension(dimensions.width) || !validDimension(dimensions.length) || !validDimension(dimensions.height)) {
        throw new Error("Room dimensions must be positive numbers")
      }
      const roomWidth = dimensions.width as number
      const roomLength = dimensions.length as number
      const roomHeight = dimensions.height as number
      const outline = roomData?.outline
      if (outline !== null && outline !== undefined && (!Array.isArray(outline) || outline.length < 3
        || !outline.every((point) => point && typeof point === "object"
          && validCoordinate((point as Record<string, unknown>).x)
          && validCoordinate((point as Record<string, unknown>).y)))) {
        throw new Error("Room outline must contain at least three valid points")
      }
      const tiers = roomData?.tiers ?? []
      if (!Array.isArray(tiers) || !tiers.every((tier) => {
        if (!tier || typeof tier !== "object") return false
        const row = tier as Record<string, unknown>
        if (![row.startY, row.endY, row.elevation].every(validCoordinate)) return false
        const { startY, endY, elevation } = row as Record<string, number>
        return startY >= 0 && endY > startY && endY <= roomLength && elevation >= 0 && elevation < roomHeight
      })) throw new Error("Room tiers contain invalid values")
      const stage = roomData?.stage
      if (stage !== null && stage !== undefined) {
        if (typeof stage !== "object") throw new Error("Room stage is invalid")
        const row = stage as Record<string, unknown>
        if (![row.x, row.y, row.width, row.length, row.elevation].every(validCoordinate)) {
          throw new Error("Room stage contains invalid values")
        }
        const { x, y, width, length, elevation } = row as Record<string, number>
        if (x < 0 || y < 0 || width <= 0 || length <= 0 || elevation <= 0
          || x + width > roomWidth || y + length > roomLength || elevation >= roomHeight) {
          throw new Error("Room stage contains invalid values")
        }
      }
      const pillars = roomData?.pillars ?? []
      if (!Array.isArray(pillars) || !pillars.every((pillar) => {
        if (!pillar || typeof pillar !== "object") return false
        const row = pillar as Record<string, unknown>
        if (![row.x, row.y, row.radius, row.height].every(validCoordinate)) return false
        const { x, y, radius, height } = row as Record<string, number>
        return x >= 0 && y >= 0 && radius > 0 && height > 0
          && x + radius <= roomWidth && y + radius <= roomLength && height <= roomHeight
      })) throw new Error("Room pillars contain invalid values")
      if (!Array.isArray(input.speakers) || !Array.isArray(input.micArrays)) {
        throw new Error("Simulation must include speaker and mic-array lists")
      }
      const parseItems = (items: unknown[], kind: "speaker" | "micArray"): SceneItem[] => items.map((item) => {
        if (!item || typeof item !== "object") throw new Error(`Invalid ${kind} entry`)
        const row = item as Record<string, unknown>
        const pos = row.position as Record<string, unknown> | null
        if (typeof row.id !== "string" || typeof row.name !== "string" || !pos
          || !validCoordinate(pos.x) || !validCoordinate(pos.y) || !validCoordinate(pos.z)) {
          throw new Error(`Invalid ${kind} identity or position`)
        }
        const position = { x: pos.x, y: pos.y, z: pos.z }
        if (kind === "speaker") {
          const track = row.audioTrack as Record<string, unknown> | null
          const trackId = typeof track?.id === "string" && AUDIO_TRACKS.some((entry) => entry.id === track.id)
            ? track.id
            : undefined
          return { id: row.id, name: row.name, position, ...(trackId ? { trackId } : {}) }
        }
        return {
          id: row.id,
          name: row.name,
          position,
          ...(typeof row.focusSpeakerId === "string" ? { focusId: row.focusSpeakerId } : {}),
        }
      })
      const speakers = parseItems(input.speakers, "speaker")
      const micArrays = parseItems(input.micArrays, "micArray")
      if (new Set(speakers.map((item) => item.id)).size !== speakers.length
        || new Set(micArrays.map((item) => item.id)).size !== micArrays.length) {
        throw new Error("Simulation contains duplicate item IDs")
      }
      const scene: ImportedScene = {
        room: {
          width: roomWidth,
          length: roomLength,
          height: roomHeight,
          ...(Array.isArray(outline) ? { outline: outline as { x: number; y: number }[] } : {}),
          ...(tiers.length ? { tiers: tiers as { startY: number; endY: number; elevation: number }[] } : {}),
          ...(stage ? { stage: stage as ImportedScene["room"]["stage"] } : {}),
          ...(pillars.length ? { pillars: pillars as NonNullable<ImportedScene["room"]["pillars"]> } : {}),
        },
        material: typeof roomData?.material === "string" ? roomData.material : "",
        speakers,
        micArrays,
        syncFocus: Boolean((input.settings as Record<string, unknown> | undefined)?.synchronizedMicFocus),
      }
      const importedView = input.view === "3d" ? "3d" : input.view === "2d" ? "2d" : null
      if (!importedView) throw new Error("View must be either 2d or 3d")

      dispatch(loadSimulation(scene))
      dispatch(setViewMode(importedView))
      dispatch(setUnit("m"))
      const includesUploads = input.speakers.some((item) => {
        const track = (item as Record<string, unknown>)?.audioTrack as Record<string, unknown> | null
        return Boolean(track?.uploaded)
      })
      setRunMessage(includesUploads
        ? "Simulation imported · uploaded audio files must be selected again"
        : "Simulation imported")
    } catch (error) {
      setRunMessage(error instanceof Error ? error.message : "Unable to import simulation JSON")
    }
  }

  return (
    <header className={`${styles.topbar} p-10 `}>
      <div className={styles.brand}>
        <svg {...icon} width={30} height={30} stroke="var(--color-sonar-400)">
          <path d="M3 10v4M7 6v12M11 3v18M15 7v10M19 10v4" />
        </svg>
        <span className={styles.title}>BeamStage</span>
        <span className={styles.badge}>PoC</span>
      </div>

      <div className={styles.divider} />

      <div className={styles.selectWrap}>
        <select
          name="presets"
          className={styles.select}
          value={activePreset}
          onChange={(event) => applyPreset(event.target.value)}
          aria-label="Load simulation preset"
        >
          <option value="custom">Custom layout</option>
          {SIMULATION_PRESETS.map((preset) => (
            <option key={preset.id} value={preset.id}>{preset.name}</option>
          ))}
        </select>
        <svg {...icon} width={14} height={14} className={styles.chevron}>
          <path d="m6 9 6 6 6-6" />
        </svg>
      </div>

      <div className={styles.divider} />


      <div className={styles.units}>
        <button
          onClick={() => dispatch(setViewMode("2d"))}
          className={`${styles.unitBtn} ${view === "2d" ? styles.active : ""} flex flex-row gap-2`}
        >
          <svg {...icon} >
            <rect x="3" y="3" width="18" height="18" rx="2" />
            <path d="M3 12h18M12 3v18" />
          </svg>
          2D Floorplan
        </button>
        <button
          onClick={() => dispatch(setViewMode("3d"))}
          className={`${styles.unitBtn} ${view === "3d" ? styles.active : ""} flex flex-row gap-2`}
        >
          <svg {...icon}>
            <path d="M12 2 3 7v10l9 5 9-5V7l-9-5ZM3 7l9 5 9-5M12 12v10" />
          </svg>
          3D Isometric
        </button>
      </div>

      <div className={styles.divider} />

      <div className={styles.units}>
        <button
          onClick={() => dispatch(setUnit("m"))}
          className={`${styles.unitBtn} ${unit === "m" ? styles.active : ""}`}
        >
          m
        </button>
        <button
          onClick={() => dispatch(setUnit("ft"))}
          className={`${styles.unitBtn} ${unit === "ft" ? styles.active : ""}`}
        >
          ft
        </button>
      </div>

      <div className={styles.spacer} />

      <div className={styles.status}>
        <span className={`${styles.dot} ${apiState === "disconnected" ? styles.dotDisconnected : ""}`} />
        <span>{apiState === "checking" ? "Connecting…" : apiState === "connected" ? "API connected" : "API offline"}</span>
        {latency !== null && <span className={styles.latency}>· {latency} ms</span>}
        {runMessage && <span className={styles.runMessage} role="status">{runMessage}</span>}
      </div>

      <div className={styles.group} style={{ border: "none" }}>
        <button className={styles.exportBtn} onClick={() => importInput.current?.click()}>
          <svg {...icon}>
            <path d="M12 16V4m0 0L7 9m5-5 5 5M4 20h16" />
          </svg>
          Import JSON
        </button>
        <input
          ref={importInput}
          type="file"
          accept="application/json,.json"
          hidden
          onChange={(event) => {
            const file = event.target.files?.[0]
            event.target.value = ""
            if (file) void importSimulation(file)
          }}
        />
        <button className={styles.exportBtn} onClick={exportSimulation}>
          <svg {...icon}>
            <path d="m16 18 6-6-6-6M8 6l-6 6 6 6" />
          </svg>
          Export JSON
        </button>
      </div>

      <button className={styles.runBtn} onClick={runSimulation} disabled={running || apiState === "checking"}>
        <svg {...icon} width={20} height={20} fill="currentColor" stroke="none">
          <path d="M6 3.5v17a1 1 0 0 0 1.5.9l14-8.5a1 1 0 0 0 0-1.8l-14-8.5A1 1 0 0 0 6 3.5Z" />
        </svg>
        {running ? "Running…" : "Run Simulation"}
      </button>
    </header>
  )
}
