"use client"

import { useEffect, useRef, useState } from "react"
import * as THREE from "three"
import { useAppDispatch, useAppSelector } from "@/store/hooks"
import { addItem, DEFAULT_HEIGHT, selectItem, updateItem, type ItemKind, type ItemRef } from "@/store/slices/sceneSlice"
import { buildScene, createCamera, DEFAULT_CAMERA, disposeScene, fitCamera, itemName, MAX_ELEVATION, parseItemName, type CameraState } from "./scene"
import ViewCube from "./ViewCube"
import styles from "./Viewport.module.css"

const clamp = (value: number, min: number, max: number) => Math.min(Math.max(value, min), max)

interface Latest {
  scene: THREE.Scene | null
  // Keyed by itemName(kind, id).
  heights: Record<string, number>
  render: () => void
}

export default function Viewport() {
  const hostRef = useRef<HTMLDivElement>(null)
  const latest = useRef<Latest>({ scene: null, heights: {}, render: () => {} })
  const dispatch = useAppDispatch()

  const view = useAppSelector((state) => state.dimension.viewMode)
  const room = useAppSelector((state) => state.scene.room)
  const speakers = useAppSelector((state) => state.scene.speakers)
  const micArrays = useAppSelector((state) => state.scene.micArrays)
  const selected = useAppSelector((state) => state.scene.selected)
  const unit = useAppSelector((state) => state.dimension.currentUnit)
  const tool = useAppSelector((state) => state.tool.activeTool)
  const [active, setActive] = useState<ItemRef | null>(null)
  const [orient, setOrient] = useState({ azimuth: DEFAULT_CAMERA.azimuth, elevation: DEFAULT_CAMERA.elevation })
  const cam = useRef<CameraState>({ ...DEFAULT_CAMERA })
  const current = active ? (active.kind === "micArray" ? micArrays : speakers).find((i) => i.id === active.id) : undefined

  // Aim from the dragged mic array to its nearest speaker: tilt is degrees below horizontal, bearing is 0 toward the front wall.
  let tilt = 0
  let bearing = 0
  if (current && active?.kind === "micArray" && speakers.length > 0) {
    const from = current.position
    const nearest = speakers.reduce((best, s) =>
      Math.hypot(s.position.x - from.x, s.position.y - from.y, s.position.z - from.z) <
      Math.hypot(best.position.x - from.x, best.position.y - from.y, best.position.z - from.z)
        ? s
        : best,
    )
    const d = { x: nearest.position.x - from.x, y: nearest.position.y - from.y, z: nearest.position.z - from.z }
    tilt = (Math.atan2(-d.z, Math.hypot(d.x, d.y)) * 180) / Math.PI
    bearing = (Math.atan2(d.x, -d.y) * 180) / Math.PI
  }

  // Kept in a ref so the resize observer always redraws with the newest view and room.
  const viewState = useRef({ view, room, tool })

  useEffect(() => {
    const host = hostRef.current
    if (!host) return
    const state = latest.current

    const renderer = new THREE.WebGLRenderer({ antialias: true })
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    host.appendChild(renderer.domElement)
    const camera = createCamera()

    state.render = () => {
      const { clientWidth: width, clientHeight: height } = host
      if (!state.scene || !width || !height) return
      renderer.setSize(width, height, false)
      fitCamera(camera, viewState.current.view, viewState.current.room, width / height, cam.current)
      camera.updateMatrixWorld(true)
      state.scene.traverse((object) => {
        if (object.name === "selection-ring") {
          object.quaternion.copy(camera.quaternion)
          object.updateMatrixWorld(true)
        }
      })
      renderer.render(state.scene, camera)
    }

    const observer = new ResizeObserver(() => state.render())
    observer.observe(host)

    const canvas = renderer.domElement
    const raycaster = new THREE.Raycaster()
    const ndc = new THREE.Vector2()
    let dragging: ItemRef | null = null
    let liveHeight = 0
    let lastY = 0
    let pxPerMeter = 1
    let navigating = false
    let lastX = 0
    let clickStart: { x: number; y: number } | null = null

    // Create a new item under the cursor, on the plane at its default height.
    const place = (e: PointerEvent) => {
      aim(e)
      const kind: ItemKind = viewState.current.tool === "mic" ? "micArray" : "speaker"
      const plane = new THREE.Plane(new THREE.Vector3(0, 1, 0), -DEFAULT_HEIGHT[kind])
      const point = raycaster.ray.intersectPlane(plane, new THREE.Vector3())
      if (!point) return
      const { room: bounds } = viewState.current
      dispatch(addItem({ kind, x: clamp(point.x, 0, bounds.width), y: clamp(point.z, 0, bounds.length) }))
    }

    const aim = (e: PointerEvent) => {
      const rect = canvas.getBoundingClientRect()
      ndc.set(((e.clientX - rect.left) / rect.width) * 2 - 1, -((e.clientY - rect.top) / rect.height) * 2 + 1)
      raycaster.setFromCamera(ndc, camera)
    }

    const pick = (): ItemRef | null => {
      if (!state.scene) return null
      const hit = raycaster
        .intersectObjects(state.scene.children, false)
        .find((i) => parseItemName(i.object.name))
      return hit ? parseItemName(hit.object.name) : null
    }

    const onDown = (e: PointerEvent) => {
      aim(e)
      const is3d = viewState.current.view === "3d"
      const placing = viewState.current.tool !== "select" && !e.metaKey
      // In 3D, dragging empty space (or holding Cmd over an icon) navigates the camera.
      dragging = (e.metaKey && is3d) || placing ? null : pick()
      if (!dragging) {
        clickStart = e.metaKey ? null : { x: e.clientX, y: e.clientY }
        if (!is3d) {
          if (clickStart) canvas.setPointerCapture(e.pointerId)
          return
        }
        navigating = true
        lastX = e.clientX
        lastY = e.clientY
        canvas.setPointerCapture(e.pointerId)
        canvas.style.cursor = "move"
        return
      }

      const alreadySelected = selected?.kind === dragging.kind && selected.id === dragging.id
      dispatch(selectItem(dragging))
      if (!alreadySelected) {
        dragging = null
        clickStart = null
        canvas.style.cursor = "default"
        return
      }

      canvas.setPointerCapture(e.pointerId)
      setActive(dragging)
      canvas.style.cursor = "grabbing"
      liveHeight = state.heights[itemName(dragging.kind, dragging.id)] ?? 0
      lastY = e.clientY

      // Screen pixels per meter of height; top-down has no vertical axis, so fall back to the horizontal scale.
      const base = new THREE.Vector3(0, 0, 0).project(camera)
      const up = new THREE.Vector3(0, 1, 0).project(camera)
      pxPerMeter = ((up.y - base.y) / 2) * canvas.clientHeight
      if (Math.abs(pxPerMeter) < 1e-3) pxPerMeter = canvas.clientHeight / (camera.top - camera.bottom)
    }

    const onMove = (e: PointerEvent) => {
      if (navigating) {
        const dx = e.clientX - lastX
        const dy = e.clientY - lastY
        lastX = e.clientX
        lastY = e.clientY
        const c = cam.current
        if (e.shiftKey) {
          const perPixel = (camera.top - camera.bottom) / canvas.clientHeight
          c.panX -= dx * perPixel
          c.panY += dy * perPixel
        } else {
          c.azimuth -= dx * 0.008
          c.elevation = clamp(c.elevation + dy * 0.008, -MAX_ELEVATION, MAX_ELEVATION)
          setOrient({ azimuth: c.azimuth, elevation: c.elevation })
        }
        state.render()
        return
      }
      aim(e)
      if (!dragging) {
        canvas.style.cursor = viewState.current.tool !== "select" ? "crosshair" : pick() ? "grab" : "default"
        return
      }

      const dy = lastY - e.clientY
      lastY = e.clientY
      if (e.shiftKey) {
        canvas.style.cursor = "ns-resize"
        liveHeight = clamp(liveHeight + dy / pxPerMeter, 0, viewState.current.room.height)
        const z = { z: liveHeight }
        dispatch(updateItem({ ...dragging, patch: z }))
        return
      }
      canvas.style.cursor = "grabbing"
      // Drag along a horizontal plane at the object's height so only x and depth change.
      const plane = new THREE.Plane(new THREE.Vector3(0, 1, 0), -liveHeight)
      const point = raycaster.ray.intersectPlane(plane, new THREE.Vector3())
      if (!point) return
      const { room: bounds } = viewState.current
      const position = { x: clamp(point.x, 0, bounds.width), y: clamp(point.z, 0, bounds.length) }
      dispatch(updateItem({ ...dragging, patch: position }))
    }

    const onUp = (e: PointerEvent) => {
      const start = clickStart
      clickStart = null
      // A click (not a drag): a placing tool creates an item, the select tool clears the selection.
      if (start && Math.hypot(e.clientX - start.x, e.clientY - start.y) < 4) {
        if (viewState.current.tool === "select") dispatch(selectItem(null))
        else place(e)
      }

      if (navigating || start) {
        navigating = false
        if (canvas.hasPointerCapture(e.pointerId)) canvas.releasePointerCapture(e.pointerId)
        canvas.style.cursor = viewState.current.tool !== "select" ? "crosshair" : "default"
        return
      }
      if (dragging) canvas.releasePointerCapture(e.pointerId)
      dragging = null
      setActive(null)
      canvas.style.cursor = "default"
    }

    const onWheel = (e: WheelEvent) => {
      if (viewState.current.view !== "3d") return
      e.preventDefault()
      cam.current.zoom = clamp(cam.current.zoom * Math.exp(-e.deltaY * 0.001), 0.3, 8)
      state.render()
    }

    canvas.addEventListener("wheel", onWheel, { passive: false })
    canvas.addEventListener("pointerdown", onDown)
    canvas.addEventListener("pointermove", onMove)
    canvas.addEventListener("pointerup", onUp)
    canvas.addEventListener("pointercancel", onUp)

    return () => {
      canvas.removeEventListener("wheel", onWheel)
      canvas.removeEventListener("pointerdown", onDown)
      canvas.removeEventListener("pointermove", onMove)
      canvas.removeEventListener("pointerup", onUp)
      canvas.removeEventListener("pointercancel", onUp)
      observer.disconnect()
      state.render = () => {}
      if (state.scene) disposeScene(state.scene)
      state.scene = null
      renderer.dispose()
      renderer.domElement.remove()
    }
  }, [dispatch])

  useEffect(() => {
    const state = latest.current
    viewState.current = { view, room, tool }
    state.heights = Object.fromEntries([
      ...speakers.map((s) => [itemName("speaker", s.id), s.position.z]),
      ...micArrays.map((m) => [itemName("micArray", m.id), m.position.z]),
    ])
    if (state.scene) disposeScene(state.scene)
    state.scene = buildScene(room, speakers, micArrays, selected, view)
    state.render()
  }, [view, room, tool, speakers, micArrays, selected])

  const setCamera = (patch: Partial<CameraState>) => {
    cam.current = { ...cam.current, ...patch }
    setOrient({ azimuth: cam.current.azimuth, elevation: cam.current.elevation })
    latest.current.render()
  }

  const hint =
    tool === "mic"
      ? "Click to place a new mic array"
      : tool === "speaker"
        ? "Click to place a new speaker"
        : view === "2d"
          ? "2D Floorplan · Shift + drag an icon for height"
          : "3D Isometric · Drag to orbit · Shift + drag to pan · Scroll to zoom · Shift + drag an icon for height"

  return (
    <div className={styles.root}>
      <div ref={hostRef} className={styles.host} />
      {view === "3d" && (
        <ViewCube
          azimuth={orient.azimuth}
          elevation={orient.elevation}
          onSelect={(azimuth, elevation) => setCamera({ azimuth, elevation })}
          onHome={() => setCamera({ ...DEFAULT_CAMERA })}
        />
      )}
      <span className={styles.label}>{hint}</span>
      {active && current && (
        <span className={`${styles.label} ${styles.readout}`}>
          {current.name} height{" "}
          {(Math.round((unit === "ft" ? current.position.z * 3.28084 : current.position.z) * 100) / 100)} {unit}
          {active.kind === "micArray" && speakers.length > 0 && (
            <>
              {" · "}angle {Math.round(tilt)}° tilt, {Math.round(bearing)}° bearing
            </>
          )}
        </span>
      )}
    </div>
  )
}
