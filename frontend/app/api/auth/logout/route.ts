import { NextResponse } from 'next/server';
import { AUTH_COOKIE_NAME, isSecureCookie } from '@/lib/auth';

export async function POST() {
  const response = NextResponse.json({ ok: true });
  response.cookies.set({
    name: AUTH_COOKIE_NAME,
    value: '',
    httpOnly: true,
    sameSite: 'lax',
    secure: isSecureCookie(),
    path: '/',
    maxAge: 0,
  });
  return response;
}
