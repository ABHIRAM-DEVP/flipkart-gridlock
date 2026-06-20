import { NextResponse } from 'next/server'

export async function GET() {
  const sample = [
    { id: 'r1', lat: 12.9712, lng: 77.5932, type: 'Personnel', name: 'Officer Ramesh' },
    { id: 'r2', lat: 12.9690, lng: 77.5918, type: 'Asset', name: 'Barricade Set #4' },
  ]
  return NextResponse.json(sample)
}
