import { NextResponse } from "next/server"

const backendUrl = (process.env.INVISI_MIC_API_URL ?? "http://127.0.0.1:5000").replace(/\/$/, "")

export async function GET() {
  try {
    const response = await fetch(`${backendUrl}/materials`, { cache: "no-store" })
    const body = await response.json().catch(() => ({ error: "Backend returned an invalid response" }))
    return NextResponse.json(body, { status: response.status })
  } catch {
    return NextResponse.json(
      { error: "Unable to reach the simulation API. Make sure the backend is running." },
      { status: 503 },
    )
  }
}