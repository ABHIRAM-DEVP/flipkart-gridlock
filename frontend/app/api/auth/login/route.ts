import { NextRequest, NextResponse } from 'next/server';
import { AUTH_COOKIE_NAME, AUTH_DEFAULT_PASSWORD, AUTH_DEFAULT_USER, isSecureCookie } from '@/lib/auth';

const SESSION_TOKEN = 'astram-session-v1';

export async function POST(req: NextRequest) {
  try {
    const body = await req.json().catch(() => ({}));
    const username = String(body?.username ?? '').trim();
    const password = String(body?.password ?? '');

    if (!username || !password) {
      return NextResponse.json(
        { error: 'MissingCredentials', details: 'Username and password are required.' },
        { status: 400 },
      );
    }

    if (username !== AUTH_DEFAULT_USER || password !== AUTH_DEFAULT_PASSWORD) {
      return NextResponse.json(
        { error: 'InvalidCredentials', details: 'The username or password is incorrect.' },
        { status: 401 },
      );
    }

    const response = NextResponse.json({ ok: true });
    response.cookies.set({
      name: AUTH_COOKIE_NAME,
      value: SESSION_TOKEN,
      httpOnly: true,
      sameSite: 'lax',
      secure: isSecureCookie(),
      path: '/',
      maxAge: 60 * 60 * 8,
    });

    return response;
  } catch {
    return NextResponse.json(
      { error: 'LoginFailed', details: 'Unable to complete login.' },
      { status: 500 },
    );
  }
}
