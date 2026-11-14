"use client"

import { useState } from "react"
import styles from "./Sidebar.module.css"

import { useAppDispatch, useAppSelector } from "@/store/hooks"
import { removeItem, setRoom, updateItem } from "@/store/slices/sceneSlice"

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
  const [absorption, setAbsorption] = useState("drywall")
  const [voice, setVoice] = useState("65")
  const [locked, setLocked] = useState(true)

  const dispatch = useAppDispatch()
  const room = useAppSelector((state) => state.scene.room)
  const selected = useAppSelector((state) => state.scene.selected)
  const node = useAppSelector((state) => {
    const { selected: ref, speakers, micArrays } = state.scene
    if (!ref) return undefined
    return (ref.kind === "speaker" ? speakers : micArrays).find((i) => i.id === ref.id)
  })
  const unit = useAppSelector((state) => state.dimension.currentUnit)

  const volume = toDisplay(1, unit) ** 3 * room.width * room.length * room.height

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
              <span>{Math.round(volume)} {unit}³</span>
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
          <button
            type="button"
            className={styles.iconBtn}
            aria-label="Delete node"
            disabled={!selected}
            onClick={() => selected && dispatch(removeItem(selected))}
          >
            <svg {...icon}>
              <path d="M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14M10 10v6M14 10v6" />
            </svg>
          </button>
        </div>

        {selected && node ? (
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
              </>
            )}
          </div>
        ) : (
          <div className={styles.body}>
            <div className={styles.nodeKind}>No node selected</div>
          </div>
        )}
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