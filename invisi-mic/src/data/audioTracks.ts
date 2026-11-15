export interface AudioTrack {
  id: string
  name: string
  // Served from /public.
  src: string
}

export const AUDIO_TRACKS: AudioTrack[] = [
  { id: "lecture", name: "Lecture speech", src: "/audio/lecture.mp3" },
  { id: "conversation", name: "Conversation", src: "/audio/conversation.wav" },
  { id: "question", name: "Question", src: "/audio/question.mp3" },
  { id: "discussion", name: "Discussion", src: "/audio/discussion.mp3" },
]

export const findTrack = (id: string | undefined, tracks: AudioTrack[] = AUDIO_TRACKS) =>
  tracks.find((track) => track.id === id)

export const ACCEPTED_AUDIO = ".mp3,.wav,audio/mpeg,audio/wav,audio/x-wav,audio/wave"

export const isSupportedAudio = (file: File) =>
  /\.(mp3|wav)$/i.test(file.name) || ["audio/mpeg", "audio/wav", "audio/x-wav", "audio/wave"].includes(file.type)
