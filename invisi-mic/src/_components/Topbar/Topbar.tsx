"use client"

import { useEffect, useState } from "react"
import { useAppDispatch, useAppSelector } from "@/store/hooks"
import { setUnit, setViewMode } from "@/store/slices/dimensionSlice"
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
  const dispatch = useAppDispatch()
  const view = useAppSelector((state) => state.dimension.viewMode)
  const unit = useAppSelector((state) => state.dimension.currentUnit)
  const room = useAppSelector((state) => state.scene.room)
  const speakers = useAppSelector((state) => state.scene.speakers)
  const micArrays = useAppSelector((state) => state.scene.micArrays)

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
    const startedAt = performance.now()
    try {
      const is2d = view === "2d"
      const response = await fetch("/api/simulation", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          is_2_dimensional: is2d,
          shoebox: is2d ? [room.width, room.length] : [room.width, room.length, room.height],
          mics: micArrays.map(({ position }) => is2d
            ? [position.x, position.y]
            : [position.x, position.y, position.z]),
          talkers: speakers.map(({ position }) => is2d
            ? [position.x, position.y]
            : [position.x, position.y, position.z]),
        }),
      })
      const result = await response.json()
      setLatency(Math.round(performance.now() - startedAt))
      if (!response.ok) throw new Error(result.error ?? "Simulation request failed")
      setApiState("connected")
      setRunMessage("Simulation request completed")
    } catch (error) {
      setApiState("disconnected")
      setRunMessage(error instanceof Error ? error.message : "Simulation request failed")
    } finally {
      setRunning(false)
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
        <select name="presets" className={styles.select} defaultValue="hall">
          <option value="hall">Main Conference Hall</option>
          <option value="preset2">Preset 2</option>
          <option value="preset3">Preset 3</option>
          <option value="preset4">Preset 4</option>
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


      <div className={styles.group} style={{ border: "none" }}>
        <button className={styles.iconBtn} aria-label="Undo">
          <svg {...icon}>
            <path d="M9 14 4 9l5-5" />
            <path d="M4 9h10a6 6 0 0 1 0 12h-3" />
          </svg>
        </button>
        <button className={styles.iconBtn} aria-label="Redo">
          <svg {...icon}>
            <path d="m15 14 5-5-5-5" />
            <path d="M20 9H10a6 6 0 0 0 0 12h3" />
          </svg>
        </button>
      </div>

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

      <button className={styles.exportBtn}>
        <svg {...icon}>
          <path d="m16 18 6-6-6-6M8 6l-6 6 6 6" />
        </svg>
        Export JSON
      </button>

      <button className={styles.runBtn} onClick={runSimulation} disabled={running || apiState === "checking"}>
        <svg {...icon} width={20} height={20} fill="currentColor" stroke="none">
          <path d="M6 3.5v17a1 1 0 0 0 1.5.9l14-8.5a1 1 0 0 0 0-1.8l-14-8.5A1 1 0 0 0 6 3.5Z" />
        </svg>
        {running ? "Running…" : "Run Simulation"}
      </button>
    </header>
  )
}
