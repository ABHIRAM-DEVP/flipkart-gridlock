export const AUTH_COOKIE_NAME = 'astram_session';

export const AUTH_DEFAULT_USER = process.env.ASTRAM_LOGIN_USER || 'astram-admin';
export const AUTH_DEFAULT_PASSWORD = process.env.ASTRAM_LOGIN_PASSWORD || 'astram-demo';

export const isSecureCookie = () => process.env.NODE_ENV === 'production';
