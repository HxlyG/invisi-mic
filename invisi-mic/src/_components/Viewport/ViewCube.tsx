"use client"

import * as THREE from "three"
import { cameraDirection, MAX_ELEVATION } from "./scene"
import styles from "./ViewCube.module.css"

const SIZE = 52
const HALF = SIZE / 2

// Each face is labeled by the side of the room the camera views from.
const FACES = [
  { label: "Back", transform: `translateZ(${HALF}px)`, azimuth: 0, elevation: 0 },
  { label: "Front", transform: `rotateY(180deg) translateZ(${HALF}px)`, azimuth: Math.PI, elevation: 0 },
  { label: "Right", transform: `rotateY(90deg) translateZ(${HALF}px)`, azimuth: Math.PI / 2, elevation: 0 },
  { label: "Left", transform: `rotateY(-90deg) translateZ(${HALF}px)`, azimuth: -Math.PI / 2, elevation: 0 },
  { label: "Top", transform: `rotateX(90deg) translateZ(${HALF}px)`, azimuth: 0, elevation: MAX_ELEVATION },
  { label: "Bottom", transform: `rotateX(-90deg) translateZ(${HALF}px)`, azimuth: 0, elevation: -MAX_ELEVATION },
]

// World-to-camera rotation expressed in CSS axes (y points down), so the cube mirrors the scene.
function cubeMatrix(azimuth: number, elevation: number) {
  const z = cameraDirection(azimuth, elevation)
  const x = new THREE.Vector3(0, 1, 0).cross(z).normalize()
  const y = z.clone().cross(x)
  return `matrix3d(${x.x},${-y.x},${z.x},0, ${-x.y},${y.y},${-z.y},0, ${x.z},${-y.z},${z.z},0, 0,0,0,1)`
}

interface ViewCubeProps {
  azimuth: number
  elevation: number
  onSelect: (azimuth: number, elevation: number) => void
  onHome: () => void
}

export default function ViewCube({ azimuth, elevation, onSelect, onHome }: ViewCubeProps) {
  return (
    <div className={styles.root}>
      <div className={styles.scene}>
        <div className={styles.cube} style={{ transform: cubeMatrix(azimuth, elevation) }}>
          {FACES.map((face) => (
            <button
              key={face.label}
              type="button"
              className={styles.face}
              style={{ transform: face.transform }}
              onClick={() => onSelect(face.azimuth, face.elevation)}
            >
              {face.label}
            </button>
          ))}
        </div>
      </div>
      <button type="button" className={styles.home} onClick={onHome} aria-label="Reset to isometric view">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <path d="M3 11 12 3l9 8M5 10v10h14V10" />
        </svg>
      </button>
    </div>
  )
}
