"use client"

import { useEffect, useRef, useState } from "react"
import { useAppSelector } from "@/store/hooks"
import styles from "./ListenBar.module.css"

export default function ListenBar() {
  const [playing, setPlaying] = useState(false)
  const [chosenMicId, setChosenMicId] = useState("")
  const player = useRef<HTMLAudioElement | null>(null)
  const simAudio = useAppSelector((state) => state.scene.simAudio)
  const micArrays = useAppSelector((state) => state.scene.micArrays)
  const selected = useAppSelector((state) => state.scene.selected)

  const selectedMicIndex = micArrays.findIndex((mic) => selected?.kind === "micArray" && mic.id === selected.id)
  const chosenMicIndex = micArrays.findIndex((mic) => mic.id === chosenMicId)
  const index = chosenMicIndex >= 0 ? chosenMicIndex : Math.max(0, selectedMicIndex)
  const url = simAudio[index]
  const micName = micArrays[index]?.name

  // Pausing fires onpause, which resets the playing state.
  useEffect(() => () => player.current?.pause(), [url])

  if (!micArrays.length || !simAudio.length) return null

  const chooseMic = (id: string) => {
    player.current?.pause()
    player.current = null
    setPlaying(false)
    setChosenMicId(id)
  }

  const toggle = () => {
    if (playing) return player.current?.pause()
    const audio = new Audio(url)
    audio.onplay = () => setPlaying(true)
    audio.onpause = () => setPlaying(false)
    audio.onended = () => setPlaying(false)
    audio.onerror = () => setPlaying(false)
    player.current = audio
    audio.play().catch(() => setPlaying(false))
  }

  return (
    <div className={styles.listenBar}>
      <label className={styles.selectorLabel}>
        <span className={styles.srOnly}>Choose mic array audio</span>
        <select
          className={styles.selector}
          value={micArrays[index]?.id ?? ""}
          onChange={(event) => chooseMic(event.target.value)}
          aria-label="Choose mic array audio"
        >
          {micArrays.map((mic, micIndex) => (
            <option key={mic.id} value={mic.id} disabled={!simAudio[micIndex]}>
              {mic.name}{simAudio[micIndex] ? "" : " · no audio"}
            </option>
          ))}
        </select>
      </label>
      <button
        type="button"
        className={styles.listen}
        aria-label={playing ? `Stop ${micName ?? "mic array"} audio` : `Play ${micName ?? "mic array"} audio`}
        disabled={!url}
        onClick={toggle}
      >
        <svg width={16} height={16} viewBox="0 0 24 24" fill="currentColor" stroke="none">
          {playing
            ? <rect x="6" y="6" width="12" height="12" rx="1" />
            : <path d="M7 4.5v15a1 1 0 0 0 1.5.9l12-7.5a1 1 0 0 0 0-1.8l-12-7.5A1 1 0 0 0 7 4.5Z" />}
        </svg>
        {playing ? "Stop" : "Listen"}
      </button>
    </div>
  )
}
