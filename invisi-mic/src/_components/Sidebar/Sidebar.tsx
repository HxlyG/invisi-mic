"use client"

import { useState } from "react"
import styles from "./Sidebar.module.css"

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

const FT3_TO_M3 = 0.0283168

interface FieldProps {
  label?: string
  value: string
  unit: string
  onChange: (value: string) => void
}

function Field({ label, value, unit, onChange }: FieldProps) {
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
        />
        <span className={styles.unit}>{unit}</span>
      </label>
    </div>
  )
}

interface MetricProps {
  label: string
  value: string
  unit: string
  valueClass?: string
  percent?: number
}

function Metric({ label, value, unit, valueClass, percent }: MetricProps) {
  return (
    <div className={styles.metric}>
      <div className={styles.metricHead}>
        <span>{label}</span>
        <span>
          <span className={`${styles.metricValue} ${valueClass ?? ""}`}>{value}</span>
          <span className={styles.metricUnit}>{unit}</span>
        </span>
      </div>
      {percent !== undefined && (
        <div className={styles.bar}>
          <div className={styles.barFill} style={{ width: `${percent}%` }} />
        </div>
      )}
    </div>
  )
}

export default function Sidebar() {
  const [roomOpen, setRoomOpen] = useState(true)
  const [room, setRoom] = useState({ width: "45.93", length: "32.81", height: "14.76" })
  const [absorption, setAbsorption] = useState("drywall")
  const [pos, setPos] = useState({ x: "22.97", y: "4.92", z: "5.25" })
  const [voice, setVoice] = useState("65")
  const [locked, setLocked] = useState(true)

  const volume =
    Number(room.width) * Number(room.length) * Number(room.height) * FT3_TO_M3

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
              <Field
                label="Width"
                unit="ft"
                value={room.width}
                onChange={(width) => setRoom({ ...room, width })}
              />
              <Field
                label="Length"
                unit="ft"
                value={room.length}
                onChange={(length) => setRoom({ ...room, length })}
              />
            </div>
            <Field
              label="Ceiling height"
              unit="ft"
              value={room.height}
              onChange={(height) => setRoom({ ...room, height })}
            />
            <div>
              <span className={styles.label}>Wall acoustic absorption</span>
              <div className={styles.selectWrap}>
                <select
                  className={styles.select}
                  value={absorption}
                  onChange={(e) => setAbsorption(e.target.value)}
                >
                  <option value="drywall">Standard Drywall</option>
                  <option value="concrete">Concrete</option>
                  <option value="glass">Glass</option>
                  <option value="acoustic">Acoustic Panels</option>
                </select>
                <svg {...icon} className={styles.selectChevron}>
                  <path d="m6 9 6 6 6-6" />
                </svg>
              </div>
            </div>
            <div className={styles.meta}>
              <span>Room volume</span>
              <span>{Math.round(volume)} m³</span>
            </div>
          </div>
        )}
      </section>

      <section className={styles.section}>
        <div className={styles.header}>
          <svg {...icon} className={styles.headerIcon}>
            <circle cx="12" cy="12" r="9" />
            <circle cx="12" cy="12" r="5" />
            <circle cx="12" cy="12" r="1" />
          </svg>
          <span className={styles.headerTitle}>Selected node</span>
          <button type="button" className={styles.iconBtn} aria-label="Delete node">
            <svg {...icon}>
              <path d="M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14M10 10v6M14 10v6" />
            </svg>
          </button>
        </div>

        <div className={styles.body}>
          <div className={styles.node}>
            <div className={styles.nodeIcon}>
              <svg {...icon} width={18} height={18}>
                <circle cx="12" cy="8" r="4" />
                <path d="M4 21c0-4 3.6-7 8-7s8 3 8 7" />
              </svg>
            </div>
            <div style={{ flex: 1 }}>
              <div className={styles.nodeName}>Speaker 01</div>
              <div className={styles.nodeKind}>Human speaker</div>
            </div>
            <span className={styles.tag}>Active</span>
          </div>

          <div className={`${styles.row} ${styles.cols3}`}>
            <Field label="X" unit="ft" value={pos.x} onChange={(x) => setPos({ ...pos, x })} />
            <Field label="Y" unit="ft" value={pos.y} onChange={(y) => setPos({ ...pos, y })} />
            <Field label="Z" unit="ft" value={pos.z} onChange={(z) => setPos({ ...pos, z })} />
          </div>

          <Field label="Voice level" unit="dB SPL" value={voice} onChange={setVoice} />

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
              onClick={() => setLocked(!locked)}
            />
          </div>
        </div>
      </section>

      <section className={styles.section}>
        <div className={styles.header}>
          <svg {...icon} className={styles.headerIcon}>
            <path d="M2 8c2-2 4-2 6 0s4 2 6 0 4-2 6 0M2 13c2-2 4-2 6 0s4 2 6 0 4-2 6 0M2 18c2-2 4-2 6 0s4 2 6 0 4-2 6 0" />
          </svg>
          <span className={styles.headerTitle}>Acoustic telemetry</span>
          <svg {...icon} className={styles.headerIcon}>
            <circle cx="12" cy="12" r="9" />
            <path d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.6.3-1 .9-1 1.5M12 17h.01" />
          </svg>
        </div>

        <div className={styles.body}>
          <Metric label="Estimated SNR" value="+17.4" unit="dB" valueClass={styles.green} percent={58} />
          <Metric label="Beam focus score" value="91" unit="%" valueClass={styles.cyan} percent={91} />
          <Metric label="Reverb RT60" value="0.82" unit="s" />
          <div className={styles.statusLine}>
            <span className={styles.dot} />
            Target tracking · estimates updating
          </div>
        </div>
      </section>

      <div className={styles.footer}>
        <span>Simulation engine</span>
        <span>v0.1.0 / PoC</span>
      </div>
    </aside>
  )
}