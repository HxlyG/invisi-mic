"use client"

import { useEffect, useRef, useState } from "react"
import * as THREE from "three"
import { useAppDispatch, useAppSelector } from "@/store/hooks"
import { addItem, DEFAULT_HEIGHT, focusSpeaker, selectItem, updateItem, type ItemKind, type ItemRef } from "@/store/slices/sceneSlice"
import { setTool } from "@/store/slices/toolSlice"
import { buildScene, createCamera, DEFAULT_CAMERA, disposeScene, fitCamera, itemName, MAX_ELEVATION, parseItemName, type CameraState } from "./scene"
import ViewCube from "./ViewCube"
import ListenBar from "./ListenBar"
import styles from "./Viewport.module.css"

const clamp = (value: number, min: number, max: number) => Math.min(Math.max(value, min), max)
const snapToDimension = (value: number, dimension: number) => {
  const step = dimension < 2 ? 0.1 : dimension < 5 ? 0.25 : dimension < 10 ? 0.5 : 1
  return Math.round(value / step) * step
}
const insideRoom = (x: number, y: number, outline?: { x: number; y: number }[]) => {
  if (!outline?.length) return true
  let inside = false
  for (let i = 0, j = outline.length - 1; i < outline.length; j = i++) {
    const a = outline[i]
    const b = outline[j]
    if ((a.y > y) !== (b.y > y) && x < (b.x - a.x) * (y - a.y) / (b.y - a.y) + a.x) inside = !inside
  }
  return inside
}

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
  const selectedRef = useRef(selected)
  const unit = useAppSelector((state) => state.dimension.currentUnit)
  const tool = useAppSelector((state) => state.tool.activeTool)
  const gridSnap = useAppSelector((state) => state.tool.gridSnap)
  const unlocking = useAppSelector((state) => state.tool.unlocking)
  const showBeams = useAppSelector((state) => state.tool.showBeams)
  const [active, setActive] = useState<ItemRef | null>(null)
  const [orient, setOrient] = useState({ azimuth: DEFAULT_CAMERA.azimuth, elevation: DEFAULT_CAMERA.elevation })
  const cam = useRef<CameraState>({ ...DEFAULT_CAMERA })
  const current = active ? (active.kind === "micArray" ? micArrays : speakers).find((i) => i.id === active.id) : undefined

  // Aim from the dragged mic array to its nearest speaker: tilt is degrees below horizontal, bearing is 0 toward the front wall.
  let tilt = 0
  let bearing = 0
  if (current && active?.kind === "micArray") {
    const from = current.position
    const nearest = focusSpeaker(current, speakers)
    const d = nearest && { x: nearest.position.x - from.x, y: nearest.position.y - from.y, z: nearest.position.z - from.z }
    if (d) {
      tilt = (Math.atan2(-d.z, Math.hypot(d.x, d.y)) * 180) / Math.PI
      bearing = (Math.atan2(d.x, -d.y) * 180) / Math.PI
    }
  }

  // Kept in a ref so the resize observer always redraws with the newest view and room.
  const viewState = useRef({ view, room, tool, gridSnap })

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
    let unsnappedHeight = 0
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
      const snap = (value: number, dimension: number) =>
        viewState.current.gridSnap ? snapToDimension(value, dimension) : value
      const x = clamp(snap(point.x, bounds.width), 0, bounds.width)
      const y = clamp(snap(point.z, bounds.length), 0, bounds.length)
      if (!insideRoom(x, y, bounds.outline)) return
      dispatch(addItem({
        kind,
        x,
        y,
      }))
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

      const alreadySelected =
        selectedRef.current?.kind === dragging.kind && selectedRef.current.id === dragging.id
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
      unsnappedHeight = liveHeight
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
        unsnappedHeight = clamp(
          unsnappedHeight + dy / pxPerMeter,
          0,
          viewState.current.room.height,
        )
        const snappedHeight = viewState.current.gridSnap
          ? snapToDimension(unsnappedHeight, viewState.current.room.height)
          : unsnappedHeight
        liveHeight = clamp(snappedHeight, 0, viewState.current.room.height)
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
      const snap = (value: number, dimension: number) =>
        viewState.current.gridSnap ? snapToDimension(value, dimension) : value
      const position = {
        x: clamp(snap(point.x, bounds.width), 0, bounds.width),
        y: clamp(snap(point.z, bounds.length), 0, bounds.length),
      }
      if (!insideRoom(position.x, position.y, bounds.outline)) return
      dispatch(updateItem({ ...dragging, patch: position }))
    }

    const onUp = (e: PointerEvent) => {
      const start = clickStart
      clickStart = null
      // A click (not a drag): a placing tool creates an item, the select tool clears the selection.
      if (start && Math.hypot(e.clientX - start.x, e.clientY - start.y) < 4) {
        if (viewState.current.tool === "select") dispatch(selectItem(null))
        else {
          place(e)
          dispatch(setTool("select"))
        }
      }

      if (navigating || start) {
        navigating = false
        if (canvas.hasPointerCapture(e.pointerId)) canvas.releasePointerCapture(e.pointerId)
        canvas.style.cursor = "default"
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
    selectedRef.current = selected
    viewState.current = { view, room, tool, gridSnap }
    state.heights = Object.fromEntries([
      ...speakers.map((s) => [itemName("speaker", s.id), s.position.z]),
      ...micArrays.map((m) => [itemName("micArray", m.id), m.position.z]),
    ])
    if (state.scene) disposeScene(state.scene)
    state.scene = buildScene(room, speakers, micArrays, selected, view, unit, showBeams)
    state.render()
  }, [view, room, tool, gridSnap, speakers, micArrays, selected, unit, showBeams])

  useEffect(() => {
    if (!unlocking) return
    const startedAt = performance.now()
    let frame = 0
    const animateRing = (now: number) => {
      const progress = clamp((now - startedAt) / 250, 0, 1)
      const ring = latest.current.scene?.getObjectByName("selection-ring")
      if (ring) {
        ring.scale.setScalar(progress)
        const material = (ring as THREE.Mesh).material as THREE.MeshBasicMaterial
        material.opacity = 0.65 * progress
      }
      latest.current.render()
      if (progress < 1) frame = requestAnimationFrame(animateRing)
    }
    frame = requestAnimationFrame(animateRing)
    return () => cancelAnimationFrame(frame)
  }, [unlocking])

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
      <ListenBar />
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
