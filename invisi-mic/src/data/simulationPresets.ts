import type { ImportedScene } from "@/store/slices/sceneSlice"

export interface SimulationPreset {
  id: string
  name: string
  scene: ImportedScene
}

const arc = (cx: number, cy: number, radius: number, start: number, end: number, steps = 20) =>
  Array.from({ length: steps + 1 }, (_, index) => {
    const angle = start + (end - start) * index / steps
    return { x: cx + Math.cos(angle) * radius, y: cy + Math.sin(angle) * radius }
  })

const roundedRectangle = (width: number, length: number, radius: number) => [
  ...arc(radius, radius, radius, -Math.PI / 2, -Math.PI, 6).reverse(),
  ...arc(width - radius, radius, radius, -Math.PI / 2, 0, 6).slice(1),
  ...arc(width - radius, length - radius, radius, 0, Math.PI / 2, 6).slice(1),
  ...arc(radius, length - radius, radius, Math.PI / 2, Math.PI, 6).slice(1),
]

export const SIMULATION_PRESETS: SimulationPreset[] = [
  {
    id: "lecture-hall",
    name: "Lecture Hall",
    scene: {
      room: {
        width: 24,
        length: 28,
        height: 8,
        outline: [
          { x: 4, y: 0 }, { x: 20, y: 0 }, { x: 22, y: 5 }, { x: 22, y: 17 },
          ...arc(12, 17, 10, 0, Math.PI).slice(1), { x: 2, y: 5 },
        ],
        tiers: [
          { startY: 4, endY: 7.5, elevation: 0.5 },
          { startY: 7.5, endY: 11, elevation: 1 },
          { startY: 11, endY: 14.5, elevation: 1.5 },
          { startY: 14.5, endY: 18, elevation: 2 },
          { startY: 18, endY: 21.5, elevation: 2.5 },
          { startY: 21.5, endY: 25, elevation: 3 },
        ],
      },
      material: "anechoic",
      speakers: [
        { id: "speaker-1", name: "Lectern", position: { x: 12, y: 2, z: 1.6 }, trackId: "lecture" },
      ],
      micArrays: Array.from({ length: 18 }, (_, index) => {
        const row = Math.floor(index / 3)
        const column = index % 3
        const tier = (row + 1) * 0.5
        const y = 5.75 + row * 3.5
        return {
          id: `mic-${index + 1}`,
          name: `Tier ${row + 1} · Array ${column + 1}`,
          position: { x: 6 + column * 6, y, z: 2.8 + tier },
          focusId: "speaker-1",
        }
      }),
      syncFocus: true,
    },
  },
  {
    id: "comedy-club",
    name: "Comedy Club",
    scene: {
      room: {
        width: 14,
        length: 12,
        height: 4.5,
        stage: { x: 2, y: 0.5, width: 10, length: 3.5, elevation: 0.65 },
        outline: [
          { x: 2, y: 0 }, { x: 12, y: 0 }, { x: 12, y: 7 },
          ...arc(7, 7, 5, 0, Math.PI).slice(1),
        ],
      },
      material: "brickwork",
      speakers: [
        { id: "speaker-1", name: "Stage", position: { x: 7, y: 1.5, z: 2.25 }, trackId: "conversation" },
      ],
      micArrays: [
        ...[0, 1, 2, 3, 4].map((index) => {
          const angle = Math.PI * index / 4
          return {
            id: `mic-${index + 1}`,
            name: `Audience arc ${index + 1}`,
            position: { x: 7 + 4 * Math.cos(angle), y: 7 + 4 * Math.sin(angle), z: 2.4 },
            focusId: "speaker-1",
          }
        }),
      ],
      syncFocus: true,
    },
  },
  {
    id: "large-conference-room",
    name: "Large Conference Room",
    scene: {
      room: {
        width: 32,
        length: 24,
        height: 6,
        outline: roundedRectangle(32, 24, 3),
        pillars: [
          { x: 5, y: 5, radius: 0.55, height: 6 },
          { x: 27, y: 5, radius: 0.55, height: 6 },
          { x: 5, y: 19, radius: 0.55, height: 6 },
          { x: 27, y: 19, radius: 0.55, height: 6 },
        ],
      },
      material: "hard_surface",
      speakers: [
        { id: "speaker-1", name: "Presenter 1", position: { x: 15, y: 2, z: 1.6 }, trackId: "discussion" },
        { id: "speaker-2", name: "Presenter 2", position: { x: 15, y: 3, z: 1.6 }, trackId: "question" },
      ],
      micArrays: Array.from({ length: 8 }, (_, index) => {
        const angle = 2 * Math.PI * index / 8
        return {
          id: `mic-${index + 1}`,
          name: `Round table ${index + 1}`,
          position: { x: 16 + 7 * Math.cos(angle), y: 12 + 4 * Math.sin(angle), z: 1.2 },
          focusId: index < 4 ? "speaker-1" : "speaker-2",
        }
      }),
      syncFocus: false,
    },
  },
]
