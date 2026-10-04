import * as Cesium from 'cesium';
import 'cesium/Build/Cesium/Widgets/widgets.css';
import './style.css';
import { createApplication } from '../app/application.js';
import { createApplicationViewer, installTrackpadPinchZoom } from '../app/viewer.js';
import { createApplicationEarthquakes } from '../app/layers/earthquakes.js';
import { initWorldOverlay, destroyWorldOverlay } from '../overlays/worldOverlay.js';
import { createProjectionReader, MAX_READS } from './model.js';

const byId = id => document.getElementById(id);
const reader = createProjectionReader();
let current = null;
let selectedId = null;
let busy = false;
let disposed = false;
let viewer;
let earthquakes;
let markerEntities = [];

function element(tag, content, className) {
  const node = document.createElement(tag);
  if (content !== undefined) node.textContent = content;
  if (className) node.className = className;
  return node;
}

function references(title, content) {
  const details = element('details');
  details.append(element('summary', title), element('p', content, 'answer-refs'));
  return details;
}

function budget() {
  byId('read-budget').textContent = `${reader.reads}/${MAX_READS} lectures locales utilisées. Aucune collecte automatique.`;
  byId('refresh').disabled = busy || reader.reads > MAX_READS - 2;
}

function overview() {
  viewer.camera.flyTo({ destination: Cesium.Cartesian3.fromDegrees(0, 20, 22000000),
    orientation: { heading: 0, pitch: -Math.PI / 2, roll: 0 }, duration: 1 });
}

function focus(event) {
  selectedId = event.id;
  const panel = byId('selection');
  panel.replaceChildren();
  panel.hidden = false;
  panel.append(element('h2', `M${event.mag} · ${event.place}`));
  const facts = [
    ['Nature', event.nature === 'simulation' ? 'SIMULATION' : `Observation USGS${event.historical ? ' historique' : ''}`],
    ['Événement UTC', event.eventAt], [event.nature === 'simulation' ? 'Révision de simulation UTC' : 'Révision USGS UTC', event.updatedAt],
    ['Collecte Syn UTC', event.collectedAt],
    ['Coordonnées', `${event.lat.toFixed(4)}°, ${event.lon.toFixed(4)}° · profondeur ${event.depthKm} km`],
    ['État', event.freshness],
  ];
  const dl = element('dl');
  for (const [label, value] of facts) dl.append(element('dt', label), element('dd', value));
  panel.append(dl);
  panel.append(references('Références Syn', `Preuve conservée : ${event.evidenceGlyphId}\nGlyph normalisé : ${event.normalizedGlyphId}`));
  if (event.nature === 'observation') {
    const link = element('a', 'Fiche de l’événement USGS');
    link.href = `https://earthquake.usgs.gov/earthquakes/eventpage/${encodeURIComponent(event.id)}`;
    link.target = '_blank'; link.rel = 'noreferrer'; panel.append(link);
  }
  for (const entity of markerEntities) {
    if (entity.point) entity.point.pixelSize = entity.id === `earthquake:${event.stableId}` ? 13 : 7;
  }
  // Camera command applies to the real GEV Cesium viewer; it is not a slide or mock image.
  viewer.camera.flyTo({ destination: Cesium.Cartesian3.fromDegrees(event.lon, event.lat, 600000),
    orientation: { heading: 0, pitch: -Math.PI / 2, roll: 0 }, duration: 1 });
}

function decorateMarkers(projection) {
  const events = new Map(projection.events.map(e => [e.stableId, e]));
  const dataSource = viewer.dataSources.getByName('earthquakes')[0];
  const entities = dataSource?.entities.values || [];
  for (const entity of entities) {
    const event = events.get(entity.id.slice('earthquake:'.length));
    const color = event.nature === 'simulation' ? Cesium.Color.MEDIUMPURPLE
      : event.depthKm < 70 ? Cesium.Color.RED : event.depthKm < 300 ? Cesium.Color.ORANGE : Cesium.Color.YELLOW;
    entity.point = { pixelSize: 7, color, outlineColor: Cesium.Color.WHITE, outlineWidth: 1,
      heightReference: Cesium.HeightReference.CLAMP_TO_GROUND };
    if (event.nature === 'simulation') {
      entity.ellipse.material = color.withAlpha(0.4);
      entity.ellipse.outlineColor = color;
    }
  }
  markerEntities = entities;
}

function displayProjection(projection, status) {
  byId('collection').textContent = projection.observedAt
    ? `Projection conservée le ${projection.observedAt} · ${projection.events.length} événement(s).`
    : 'Aucune observation conservée à ce stade.';
  const list = byId('events');
  list.replaceChildren();
  for (const e of projection.events) {
    const item = element('li');
    const button = element('button', `${e.nature === 'simulation' ? 'SIMULATION · ' : ''}M${e.mag} · ${e.place}`);
    button.type = 'button';
    button.addEventListener('click', () => focus(e));
    item.append(button, element('small', e.eventAt));
    list.append(item);
  }
  const q = byId('question');
  q.hidden = !projection.question;
  q.replaceChildren();
  if (projection.question) {
    q.append(element('p', projection.question.text));
    q.append(references('Références de la question', `Besoin : ${projection.question.needId}\nSources : ${projection.question.sourceIds.join(', ')}`));
  }
  const answer = byId('answer'); answer.hidden = !projection.answer; answer.replaceChildren();
  if (projection.answer) {
    const a = projection.answer;
    answer.append(element('h2', 'Réponse de Syn'), element('p', a.text, 'answer-text'));
    answer.append(references('Trace et portée du contrôle', `Cycle : ${a.cycleId}\nContexte : ${a.contextId}\nPortée du contrôle : ${a.verificationScope}`));
  }
  const limits = byId('limitations'); limits.replaceChildren();
  for (const limit of projection.limitations) limits.append(element('li', limit));
  const source = byId('source'); source.hidden = !projection.sourceUrl;
  if (projection.sourceUrl) source.href = projection.sourceUrl; else source.removeAttribute('href');
  const messages = { ok_events: 'Observations conservées par Syn ; fraîcheur indiquée dans chaque fiche.',
    ok_no_events: 'Aucun événement dans la fenêtre interrogée.',
    unavailable: 'La collecte USGS était indisponible ; consulter les limites.',
    empty_response: 'Réponse USGS vide ; absence de données non établie.',
    invalid_observations: 'Observations USGS invalides ; aucune observation valide établie.',
    not_collected: 'La collecte USGS n’a pas encore été lancée.' };
  byId('status').textContent = messages[status.status];
  byId('selection').hidden = true;
  selectedId = null;
  const event = projection.events.find(e => e.id === projection.focusId && e.nature === 'observation')
    || projection.events.find(e => e.id === projection.focusId) || projection.events[0];
  if (event) focus(event); else overview();
}

async function refresh() {
  if (busy || disposed) return;
  busy = true; budget();
  byId('status').textContent = 'Lecture des observations conservées…';
  try {
    const result = await reader.read();
    if (disposed) return;
    current = result.projection;
    const updated = await earthquakes.update(viewer);
    if (!updated) throw new Error('La couche séismes n’a pas reçu la projection.');
    decorateMarkers(current);
    displayProjection(current, result.status);
  } catch (error) {
    if (!disposed) byId('status').textContent = `${error.message}${current ? ' Le précédent journal reste affiché.' : ''}`;
  } finally {
    busy = false;
    if (!disposed) budget();
  }
}

const application = createApplication({
  createScene({ defer }) {
    viewer = createApplicationViewer({ container: 'cesiumContainer', creditContainer: byId('cesium-credits') });
    defer(() => { if (!viewer.isDestroyed()) viewer.destroy(); });
    viewer.terrainProvider = new Cesium.EllipsoidTerrainProvider();
    viewer.scene.globe.show = true;
    viewer.scene.globe.baseColor = Cesium.Color.fromCssColorString('#193c54');
    viewer.scene.globe.enableLighting = false;
    viewer.scene.skyBox.show = false;
    viewer.scene.skyAtmosphere.show = false;
    viewer.scene.requestRenderMode = true;
    viewer.targetFrameRate = 30;
    viewer.creditDisplay.addStaticCredit(new Cesium.Credit('God’s Eye View · Data courtesy of the U.S. Geological Survey'));
    overview();
    // NaturalEarthII ships with Cesium and is served locally, without an API key.
    Cesium.TileMapServiceImageryProvider.fromUrl(Cesium.buildModuleUrl('Assets/Textures/NaturalEarthII'))
      .then(provider => { if (!disposed && !viewer.isDestroyed()) viewer.imageryLayers.addImageryProvider(provider); })
      .catch(() => { if (!disposed) byId('map-note').textContent = 'Globe ellipsoïdal local · texture géographique indisponible · données USGS conservées'; });
    return { viewer };
  },
  createControls({ defer }) {
    initWorldOverlay(viewer); defer(destroyWorldOverlay);
    defer(installTrackpadPinchZoom(viewer));
    const handler = new Cesium.ScreenSpaceEventHandler(viewer.canvas);
    handler.setInputAction(click => {
      const picked = viewer.scene.pick(click.position)?.id;
      const event = current?.events.find(e => picked?.id === `earthquake:${e.stableId}`);
      if (event) focus(event);
    }, Cesium.ScreenSpaceEventType.LEFT_CLICK);
    defer(() => handler.destroy());
    return {};
  },
  createData({ defer }) {
    earthquakes = createApplicationEarthquakes({ source: {
      async getSnapshot({ signal }) { signal.throwIfAborted(); return current?.events || []; },
    } });
    earthquakes.init(viewer); defer(() => earthquakes.destroy(viewer));
    earthquakes.enable(viewer);
    return { earthquakes };
  },
  createTools({ defer }) {
    byId('refresh').addEventListener('click', refresh);
    byId('overview').addEventListener('click', overview);
    defer(() => byId('refresh').removeEventListener('click', refresh));
    defer(() => byId('overview').removeEventListener('click', overview));
    return {};
  },
});

// Read-only diagnostics for verifying the real renderer and camera integration.
window.__synGlobe = Object.freeze({
  getDiagnostics() {
    const c = viewer?.camera.positionCartographic;
    return { state: application.getState().status, reads: reader.reads,
      layerCount: earthquakes?.getStats().count || 0, selectedId,
      camera: c ? { lat: Cesium.Math.toDegrees(c.latitude), lon: Cesium.Math.toDegrees(c.longitude), altitude: c.height } : null,
      webgl: !!viewer?.scene.context, globeVisible: viewer?.scene.globe.show === true };
  },
});
window.addEventListener('pagehide', () => { disposed = true; application.destroy().catch(() => {}); }, { once: true });
application.start().then(refresh).catch(() => { byId('status').textContent = 'Le globe n’a pas pu démarrer. Vérifier la prise en charge WebGL du navigateur.'; });
