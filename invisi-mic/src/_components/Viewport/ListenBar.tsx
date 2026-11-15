"use client"

import { useEffect, useRef, useState } from "react"
import { useAppSelector } from "@/store/hooks"
import { focusSpeaker } from "@/store/slices/sceneSlice"
import styles from "./ListenBar.module.css"

const BEAM = "beam"

export default function ListenBar() {
  const [playing, setPlaying] = useState(false)
  const [choice, setChoice] = useState(BEAM)
  const player = useRef<HTMLAudioElement | null>(null)
  const simAudio = useAppSelector((state) => state.scene.simAudio)
  const beamAudio = useAppSelector((state) => state.scene.beamAudio)
  const micArrays = useAppSelector((state) => state.scene.micArrays)
  const speakers = useAppSelector((state) => state.scene.speakers)
  const selected = useAppSelector((state) => state.scene.selected)

  const selectedMicIndex = micArrays.findIndex((mic) => selected?.kind === "micArray" && mic.id === selected.id)
  const chosenMicIndex = micArrays.findIndex((mic) => mic.id === choice)
  const index = chosenMicIndex >= 0 ? chosenMicIndex : Math.max(0, selectedMicIndex)

  // The beam points at the mic array's focus speaker from the Human speaker section.
  const target = micArrays[index] ? focusSpeaker(micArrays[index], speakers) : undefined
  const beamUrl = target ? beamAudio[target.id] : undefined
  const beamed = choice === BEAM && !!beamUrl
  const url = beamed ? beamUrl : simAudio[index]
  const label = beamed ? `${target?.name} beamformed` : micArrays[index]?.name

  // Pausing fires onpause, which resets the playing state.
  useEffect(() => () => player.current?.pause(), [url])

  if (!micArrays.length || (!simAudio.length && !beamUrl)) return null

  const choose = (value: string) => {
    player.current?.pause()
    player.current = null
    setPlaying(false)
    setChoice(value)
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
        <span className={styles.srOnly}>Choose audio source</span>
        <select
          className={styles.selector}
          value={beamed ? BEAM : micArrays[index]?.id ?? ""}
          onChange={(event) => choose(event.target.value)}
          aria-label="Choose audio source"
        >
          <option value={BEAM} disabled={!beamUrl}>
            {target ? `${target.name} · beamformed` : "Beamformed"}{beamUrl ? "" : " · no audio"}
          </option>
          {micArrays.map((mic, micIndex) => (
            <option key={mic.id} value={mic.id} disabled={!simAudio[micIndex]}>
              {mic.name} · original{simAudio[micIndex] ? "" : " · no audio"}
            </option>
          ))}
        </select>
      </label>
      <button
        type="button"
        className={styles.listen}
        aria-label={playing ? `Stop ${label ?? "mic array"} audio` : `Play ${label ?? "mic array"} audio`}
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
