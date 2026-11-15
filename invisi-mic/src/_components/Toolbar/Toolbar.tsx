"use client"

import { useAppDispatch, useAppSelector } from "@/store/hooks"
import { setGridSnap, setTool, type Tool } from "@/store/slices/toolSlice"
import styles from "./Toolbar.module.css"

const icon = {
  width: 20,
  height: 20,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.8,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
}

const TOOLS: { id: Tool; label: string; icon: React.ReactNode }[] = [
  {
    id: "select",
    label: "Select and move",
    icon: (
      <path d="M4.04 4.69a.5.5 0 0 1 .65-.65l16 6.5a.5.5 0 0 1-.06.95l-6.12 1.58a2 2 0 0 0-1.44 1.44l-1.58 6.12a.5.5 0 0 1-.95.06z" />
    ),
  },
  {
    id: "mic",
    label: "Place mic array",
    icon: (
      <>
        <circle cx="12" cy="12" r="2" />
        <path d="M4.9 19.1C1 15.2 1 8.8 4.9 4.9M7.8 16.2c-2.3-2.3-2.3-6.1 0-8.5M16.2 7.8c2.3 2.3 2.3 6.1 0 8.5M19.1 4.9C23 8.8 23 15.1 19.1 19" />
      </>
    ),
  },
  {
    id: "speaker",
    label: "Place speaker",
    icon: (
      <>
        <circle cx="12" cy="8" r="4" />
        <path d="M4 21c0-4 3.6-7 8-7s8 3 8 7" />
      </>
    ),
  },
  {
    id: "room",
    label: "Draw room",
    icon: <path d="M4 7 12 3l8 5-2 11H7z" />,
  },
]

export default function Toolbar() {
  const dispatch = useAppDispatch()
  const activeTool = useAppSelector((state) => state.tool.activeTool)
  const gridSnap = useAppSelector((state) => state.tool.gridSnap)

  return (
    <div className={styles.toolbar} role="toolbar" aria-orientation="vertical" aria-label="Diagram tools">
      {TOOLS.map((tool) => (
        <div key={tool.id} className={styles.item}>
          {(tool.id === "mic" || tool.id === "room") && <div className={styles.divider} />}
          <button
            type="button"
            title={tool.label}
            aria-label={tool.label}
            aria-pressed={activeTool === tool.id}
            className={`${styles.button} ${activeTool === tool.id ? styles.active : ""}`}
            onClick={() => dispatch(setTool(tool.id))}
          >
            <svg {...icon}>{tool.icon}</svg>
          </button>
        </div>
      ))}
      {/* <div className={styles.item}>
        <div className={styles.divider} />
        <button
          type="button"
          title={gridSnap ? "Grid snap on" : "Grid snap off"}
          aria-label="Snap icons to grid"
          aria-pressed={gridSnap}
          className={`${styles.button} ${gridSnap ? styles.active : ""}`}
          onClick={() => dispatch(setGridSnap(!gridSnap))}
        >
          <svg {...icon}>
            <path d="M4 4h16v16H4zM4 10h16M4 16h16M10 4v16M16 4v16" />
          </svg>
        </button>
      </div> */}
    </div>
  )
}
