import type { APIRoute } from 'astro';
import verification from '../../public/googlea16c1f57cfbe64e5.html?raw';

export const prerender = false;

export const GET: APIRoute = () => new Response(verification, {
  headers: { 'content-type': 'text/html; charset=utf-8' },
});
