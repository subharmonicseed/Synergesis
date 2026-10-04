export const SYN_API = 'http://127.0.0.1:8765';
export const MAX_READS = 6;
export const MAX_BODY_BYTES = 1024 * 1024;
const MAX_EVENTS = 200;
const STATUSES = new Set(['ok_events', 'ok_no_events', 'unavailable', 'empty_response', 'invalid_observations', 'not_collected']);

function text(value, max = 256, optional = false) {
  if (optional && (value === null || value === undefined)) return null;
  if (typeof value !== 'string' || value.length > max || !value.trim())
    throw new Error('Texte du journal local invalide.');
  return value;
}

function number(value, min, max) {
  if (!Number.isFinite(value) || value < min || value > max)
    throw new Error('Coordonnées ou mesure du journal local invalides.');
  return value;
}

function timestamp(value) {
  text(value, 64);
  const ms = Date.parse(value);
  if (!Number.isFinite(ms)) throw new Error('Date du journal local invalide.');
  return ms;
}

function sourceUrl(value) {
  text(value, 4096);
  let url;
  try { url = new URL(value); } catch { throw new Error('Source USGS invalide.'); }
  if (url.protocol !== 'https:' || url.hostname !== 'earthquake.usgs.gov' ||
      url.port || url.username || url.password || url.hash ||
      url.pathname !== '/fdsnws/event/1/query')
    throw new Error('Source USGS invalide.');
  return url.href;
}

/** Validate both geographic facts and their Syn references before rendering. */
export function readProjection(payload) {
  if (!payload || !Array.isArray(payload.events) || payload.events.length > MAX_EVENTS ||
      payload.geojson?.type !== 'FeatureCollection' || !Array.isArray(payload.geojson.features) ||
      payload.geojson.features.length !== payload.events.length)
    throw new Error('Projection du journal local invalide.');
  const features = new Map();
  for (const f of payload.geojson.features) {
    const id = text(f?.id);
    const nature = f.properties?.nature;
    if (nature != null && !['observation', 'simulation'].includes(nature))
      throw new Error('Provenance géographique invalide.');
    const key = nature == null ? id : `${nature}:${id}`;
    if (f.type !== 'Feature' || f.geometry?.type !== 'Point' || features.has(key))
      throw new Error('Géométrie du journal local invalide.');
    features.set(key, f);
  }
  const seen = new Set();
  const eventIds = new Set();
  const events = payload.events.map(e => {
    const id = text(e?.id);
    const stableId = `${e.nature}:${id}`;
    const f = features.get(stableId) || features.get(id);
    if (seen.has(stableId) || !f || e.provider !== 'USGS' ||
        !['observation', 'simulation'].includes(e.nature) || typeof e.historical !== 'boolean')
      throw new Error('Provenance du journal local invalide.');
    seen.add(stableId); eventIds.add(id);
    const lon = number(e.longitude, -180, 180);
    const lat = number(e.latitude, -90, 90);
    const depthKm = number(e.depth_km, -100, 1000);
    const mag = number(e.magnitude, -2, 10);
    const coordinates = f.geometry.coordinates;
    if (!Array.isArray(coordinates) || coordinates.length < 3 ||
        coordinates.some(v => !Number.isFinite(v)) ||
        Math.abs(coordinates[0] - lon) > 1e-8 || Math.abs(coordinates[1] - lat) > 1e-8 ||
        Math.abs(coordinates[2] - depthKm) > 1e-8)
      throw new Error('Géométrie et observation discordantes.');
    const eventMs = timestamp(e.event_at);
    timestamp(e.updated_at);
    timestamp(e.collected_at);
    const rawPlace = f.properties?.place ?? e.place;
    const place = rawPlace == null || rawPlace === '' ? id : text(rawPlace, 512);
    return Object.freeze({
      id, stableId, usgsId: id, lon, lat, depthKm, mag, time: eventMs, place,
      eventAt: e.event_at, updatedAt: e.updated_at, collectedAt: e.collected_at,
      nature: e.nature, historical: e.historical, freshness: text(e.freshness, 80),
      evidenceGlyphId: text(e.evidence_glyph_id, 512),
      normalizedGlyphId: text(e.normalized_glyph_id, 512),
    });
  });
  const focusId = text(payload.focus_event_id, 256, true);
  if (focusId && !eventIds.has(focusId)) throw new Error('Événement focal absent du journal.');
  if (payload.observed_at == null) {
    if (events.length) throw new Error('Date de collecte absente pour des observations.');
  } else timestamp(payload.observed_at);
  let question = null;
  if (payload.question != null) {
    const q = payload.question;
    if (!Array.isArray(q.source_glyph_ids) || q.source_glyph_ids.length > 20)
      throw new Error('Références de question invalides.');
    question = Object.freeze({ text: text(q.text, 1500), needId: text(q.need_id, 512),
      sourceIds: q.source_glyph_ids.map(id => text(id, 512)) });
  }
  if (!Array.isArray(payload.limitations) || payload.limitations.length > 20)
    throw new Error('Limites du journal local invalides.');
  let answer = null;
  if (payload.answer != null) {
    const a = payload.answer;
    answer = Object.freeze({ text: text(a.text, 16000), cycleId: text(a.cycle_glyph_id, 512),
      contextId: text(a.context_glyph_id, 512), verificationScope: text(a.verification_scope, 1500) });
  }
  return Object.freeze({
    events, focusId, observedAt: payload.observed_at,
    sourceUrl: payload.source_url == null && !events.length ? null : sourceUrl(payload.source_url), question, answer,
    limitations: payload.limitations.map(l => text(l, 1500)),
  });
}

export function readStatus(payload) {
  if (!payload || !STATUSES.has(payload.status)) throw new Error('État du journal local invalide.');
  return { status: payload.status };
}

/** No polling, redirects, credentials or configurable remote URL. */
export function createProjectionReader({ fetchImpl = globalThis.fetch, timeoutMs = 8000 } = {}) {
  let reads = 0;
  async function get(path) {
    if (reads >= MAX_READS) throw new Error('Budget de lecture atteint (6 requêtes locales).');
    reads += 1;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    let reader;
    try {
      const response = await fetchImpl(`${SYN_API}${path}`, {
        signal: controller.signal, redirect: 'error', credentials: 'omit',
        cache: 'no-store', referrerPolicy: 'no-referrer', headers: { Accept: 'application/json' },
      });
      if (!response.ok) throw new Error('Journal local indisponible.');
      if (!(response.headers.get('content-type') || '').toLowerCase().includes('application/json'))
        throw new Error('Format du journal local invalide.');
      const declared = Number(response.headers.get('content-length'));
      if (Number.isFinite(declared) && declared > MAX_BODY_BYTES)
        throw new Error('Journal local trop volumineux.');
      if (!response.body?.getReader) throw new Error('Lecture bornée du journal indisponible.');
      reader = response.body.getReader();
      const chunks = [];
      let length = 0;
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        length += value.byteLength;
        if (length > MAX_BODY_BYTES) throw new Error('Journal local trop volumineux.');
        chunks.push(value);
      }
      const bytes = new Uint8Array(length);
      let offset = 0;
      for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.length; }
      let value;
      try { value = JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(bytes)); }
      catch { throw new Error('JSON du journal local invalide.'); }
      return value;
    } catch (error) {
      if (controller.signal.aborted) throw new Error('Journal local : délai de 8 secondes dépassé.');
      // Browser exceptions can contain URLs or arbitrary external payload text.
      if (error instanceof Error && /^(Journal local|Format du journal|Lecture bornée|JSON du journal)/.test(error.message))
        throw error;
      throw new Error('Connexion au journal local impossible.');
    } finally {
      clearTimeout(timer);
      if (reader) await reader.cancel().catch(() => {});
    }
  }
  return Object.freeze({
    get reads() { return reads; },
    async read() {
      if (reads > MAX_READS - 2) throw new Error('Budget de lecture atteint (6 requêtes locales).');
      const [projection, status] = await Promise.all([get('/api/observations'), get('/api/status')]);
      return { projection: readProjection(projection), status: readStatus(status) };
    },
  });
}
