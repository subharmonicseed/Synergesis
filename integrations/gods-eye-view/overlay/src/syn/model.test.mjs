import test from 'node:test';
import assert from 'node:assert/strict';
import { readProjection, readStatus, createProjectionReader, MAX_BODY_BYTES } from './model.js';

function fixture() {
  const time = '2026-10-03T12:00:00Z';
  return { observed_at: time, source_url: 'https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson',
    geojson: { type: 'FeatureCollection', features: [{ type: 'Feature', id: 'us-test',
      geometry: { type: 'Point', coordinates: [12, 34, 10] }, properties: { place: 'Exemple <script>' } }] },
    events: [{ id: 'us-test', provider: 'USGS', event_at: time, updated_at: time, collected_at: time,
      longitude: 12, latitude: 34, depth_km: 10, magnitude: 1.4, nature: 'observation', historical: true,
      freshness: 'historical', normalized_glyph_id: 'g:normalized', evidence_glyph_id: 'g:evidence' }],
    focus_event_id: 'us-test', question: { text: 'Quelle source manque ?', need_id: 'g:need', source_glyph_ids: ['g:evidence'] }, limitations: [] };
}
const json = value => new Response(JSON.stringify(value), { headers: { 'Content-Type': 'application/json' } });

test('preserves real sub-M2.5 observations and evidence IDs without HTML interpretation', () => {
  const projection = readProjection(fixture());
  assert.equal(projection.events[0].mag, 1.4);
  assert.equal(projection.events[0].place, 'Exemple <script>');
  assert.equal(projection.events[0].evidenceGlyphId, 'g:evidence');
  assert.equal(projection.events[0].time, Date.parse('2026-10-03T12:00:00Z'));
  assert.equal(projection.focusId, 'us-test');
});
test('supports non-historical observations and explicitly tagged simulation', () => {
  const value = fixture(); value.events[0].historical = false; value.events[0].nature = 'simulation';
  assert.equal(readProjection(value).events[0].nature, 'simulation');
  assert.equal(readProjection(value).events[0].historical, false);
});
test('same USGS identifier stays distinct for observation and tagged simulation', () => {
  const value = fixture(); value.geojson.features[0].properties.nature = 'observation';
  const simulation = structuredClone(value.events[0]); simulation.nature = 'simulation';
  const feature = structuredClone(value.geojson.features[0]); feature.properties.nature = 'simulation';
  value.events.push(simulation); value.geojson.features.push(feature);
  const events = readProjection(value).events;
  assert.equal(events[0].id, events[1].id);
  assert.notEqual(events[0].stableId, events[1].stableId);
});
test('keeps optional model answer and its context/cycle references as inert text', () => {
  const value = fixture(); value.answer = { text: '<script>réponse</script>', cycle_glyph_id: 'g:cycle',
    context_glyph_id: 'g:context', verification_scope: 'remise du texte, pas sa véracité' };
  const answer = readProjection(value).answer;
  assert.equal(answer.text, '<script>réponse</script>'); assert.equal(answer.cycleId, 'g:cycle');
  assert.equal(answer.contextId, 'g:context');
  value.answer.text = 'x'.repeat(16001); assert.throws(() => readProjection(value), /invalide/);
});
test('rejects coordinate disagreement, duplicate identity and unknown focus', () => {
  let value = fixture(); value.geojson.features[0].geometry.coordinates[0] = 99;
  assert.throws(() => readProjection(value), /discordantes/);
  value = fixture(); value.events.push(value.events[0]); value.geojson.features.push(value.geojson.features[0]);
  assert.throws(() => readProjection(value), /invalide/);
  value = fixture(); value.focus_event_id = 'absent';
  assert.throws(() => readProjection(value), /absent/);
});
test('rejects untrusted source URL and missing provenance', () => {
  const value = fixture(); value.source_url = 'https://evil.example/';
  assert.throws(() => readProjection(value), /Source USGS/);
  value.source_url = 'https://earthquake.usgs.gov/fdsnws/event/1/query'; value.events[0].evidence_glyph_id = '';
  assert.throws(() => readProjection(value), /invalide/);
});
test('allows empty/not-collected projections without fabricated dates or source link', () => {
  const value = fixture(); value.events = []; value.geojson.features = [];
  value.focus_event_id = null; value.observed_at = null; value.source_url = null; value.question = null;
  const projection = readProjection(value);
  assert.equal(projection.observedAt, null); assert.equal(projection.sourceUrl, null);
  assert.equal(readStatus({ status: 'not_collected' }).status, 'not_collected');
  assert.equal(readStatus({ status: 'invalid_observations' }).status, 'invalid_observations');
});
test('observations still require collection timestamp and USGS source', () => {
  let value = fixture(); value.observed_at = null;
  assert.throws(() => readProjection(value), /collecte absente/);
  value = fixture(); value.source_url = null;
  assert.throws(() => readProjection(value), /invalide/);
});
test('no automatic requests, exactly two bounded loopback GETs per manual read, no retries', async () => {
  const calls = [];
  const reader = createProjectionReader({ fetchImpl: async (url, options) => {
    calls.push({ url, options });
    return json(url.endsWith('/api/status') ? { status: 'ok_events' } : fixture());
  } });
  assert.equal(calls.length, 0);
  await reader.read(); await reader.read(); await reader.read();
  assert.equal(calls.length, 6);
  await assert.rejects(reader.read(), /Budget/);
  assert.equal(calls.length, 6);
  for (const c of calls) {
    assert.match(c.url, /^http:\/\/127\.0\.0\.1:8765\/api\/(observations|status)$/);
    assert.equal(c.options.redirect, 'error'); assert.equal(c.options.credentials, 'omit');
  }
});
test('streaming byte cap rejects oversized payload without returning partial facts', async () => {
  const reader = createProjectionReader({ fetchImpl: async () => new Response(new Uint8Array(MAX_BODY_BYTES + 1),
    { headers: { 'Content-Type': 'application/json' } }) });
  await assert.rejects(reader.read(), /volumineux/); assert.equal(reader.reads, 2);
});
test('network exception never leaks response or URLs and is not retried', async () => {
  let calls = 0;
  const reader = createProjectionReader({ fetchImpl: async () => { calls++; throw new Error('secret response payload'); } });
  await assert.rejects(reader.read(), { message: 'Connexion au journal local impossible.' });
  assert.equal(calls, 2);
});
test('timeout aborts and returns safe diagnostic', async () => {
  const reader = createProjectionReader({ timeoutMs: 10, fetchImpl: async (_, options) =>
    new Promise((_, reject) => options.signal.addEventListener('abort', () => reject(new Error('aborted')))) });
  await assert.rejects(reader.read(), /délai/);
});
