import { NextResponse } from 'next/server'

export async function GET() {
  const sample = [
    { id: 'e1', lat: 12.9716, lng: 77.5946, severity: 0.8, count: 42 },
    { id: 'e2', lat: 12.9705, lng: 77.5925, severity: 0.6, count: 18 },
  ]
  return NextResponse.json(sample)
}
