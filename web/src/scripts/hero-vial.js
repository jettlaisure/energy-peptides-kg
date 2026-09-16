// Reuse the repository's MIT-licensed Three.js build, bundled locally by Vite.
import * as THREE from '../../../render/vendor/three/three.module.js';
import { createVial } from './vial-model.js';

export async function mountVial(host) {
  const canvas = host.querySelector('canvas');
  const controls = host.querySelector('.vial-controls');
  const poster = host.querySelector('.vial-poster');
  const stage = host.querySelector('.vial-stage');
  const events = new AbortController();
  const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
  let renderer, environment, vial, resize, visibility;
  let frame = 0, visible = true, disposed = false, pointer = null;
  const scene = new THREE.Scene();
  // An opaque studio backdrop is also the refraction source for the clear glass.
  const backdrop = document.createElement('canvas');
  backdrop.width = backdrop.height = 512;
  const paint = backdrop.getContext('2d');
  const gradient = paint.createRadialGradient(256, 230, 0, 256, 256, 280);
  gradient.addColorStop(0, '#142440');
  gradient.addColorStop(0.55, '#0a142b');
  gradient.addColorStop(1, '#060c1f');
  paint.fillStyle = gradient;
  paint.fillRect(0, 0, 512, 512);
  scene.background = new THREE.CanvasTexture(backdrop);
  scene.background.colorSpace = THREE.SRGBColorSpace;
  const camera = new THREE.PerspectiveCamera(24, 1, 1, 500);
  const home = { x: 0.07, y: 0, z: -0.12 };
  const target = { ...home };

  function disposeObject(object) {
    object.traverse(child => {
      child.geometry?.dispose();
      if (child.material) {
        const materials = Array.isArray(child.material) ? child.material : [child.material];
        materials.forEach(material => {
          material.map?.dispose();
          material.dispose();
        });
      }
    });
  }
  function cleanup() {
    if (disposed) return;
    disposed = true;
    cancelAnimationFrame(frame);
    events.abort();
    resize?.disconnect();
    visibility?.disconnect();
    disposeObject(scene);
    scene.background.dispose();
    environment?.dispose();
    renderer?.dispose();
    host.removeAttribute('data-ready');
    controls.hidden = true;
    canvas.tabIndex = -1;
    canvas.setAttribute('aria-hidden', 'true');
    poster?.removeAttribute('aria-hidden');
  }

  try {
    renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: 'low-power' });
    renderer.setPixelRatio(Math.min(devicePixelRatio, 1.75));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.NeutralToneMapping;
    renderer.toneMappingExposure = 1;
    renderer.setClearColor(0x060c1f, 0);

    // Photographic softboxes reflected in the glass and brushed aluminium.
    // The environment is baked once; no external HDR image or continuous render loop.
    const studio = new THREE.Scene();
    const walls = new THREE.Mesh(new THREE.BoxGeometry(200, 160, 200), new THREE.MeshBasicMaterial({ color: 0x343c49, side: THREE.BackSide }));
    studio.add(walls);
    function softbox(w, h, position, intensity, color = 0xffffff) {
      const panel = new THREE.Mesh(new THREE.PlaneGeometry(w, h), new THREE.MeshBasicMaterial({ color: new THREE.Color(color).multiplyScalar(intensity), side: THREE.DoubleSide }));
      panel.position.set(...position);
      panel.lookAt(0, 0, 0);
      studio.add(panel);
    }
    softbox(18, 85, [-45, 10, 35], 7);
    softbox(8, 70, [45, 10, -15], 5, 0xd6e6ff);
    softbox(65, 45, [0, 65, 10], 3);
    softbox(20, 65, [40, 0, 55], 1.5);
    const pmrem = new THREE.PMREMGenerator(renderer);
    environment = pmrem.fromScene(studio, 0.025, 1, 300);
    scene.environment = environment.texture;
    pmrem.dispose();
    disposeObject(studio);

    const label = await new THREE.TextureLoader().loadAsync(host.dataset.label);
    if (!host.isConnected) { label.dispose(); cleanup(); return cleanup; }
    label.colorSpace = THREE.SRGBColorSpace;
    label.anisotropy = Math.min(8, renderer.capabilities.getMaxAnisotropy());
    vial = createVial(THREE, label);
    vial.rotation.set(home.x, home.y, home.z);
    scene.add(vial);
    scene.add(new THREE.HemisphereLight(0xffffff, 0x182744, 1.1));
    const key = new THREE.DirectionalLight(0xfff6e8, 2.4);
    key.position.set(-30, 50, 60); scene.add(key);
    const fill = new THREE.DirectionalLight(0xbfd6ff, 1.2);
    fill.position.set(40, 10, 35); scene.add(fill);
    camera.position.set(0, 3, 118);
    camera.lookAt(0, 0, 0);

    function render() {
      frame = 0;
      if (!visible || document.hidden || disposed) return;
      const factor = reducedMotion.matches ? 1 : 0.16;
      for (const axis of ['x', 'y', 'z']) vial.rotation[axis] += (target[axis] - vial.rotation[axis]) * factor;
      renderer.render(scene, camera);
      if (['x', 'y', 'z'].some(axis => Math.abs(target[axis] - vial.rotation[axis]) > 0.0001)) requestRender();
    }
    function requestRender() {
      if (!frame && visible && !document.hidden && !disposed) frame = requestAnimationFrame(render);
    }
    function size() {
      const { width, height } = stage.getBoundingClientRect();
      if (!width || !height) return;
      renderer.setSize(width, height, false);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      requestRender();
    }
    resize = new ResizeObserver(size);
    resize.observe(stage);
    size();
    renderer.render(scene, camera);
    host.dataset.ready = '';
    controls.hidden = false;
    canvas.tabIndex = 0;
    canvas.removeAttribute('aria-hidden');
    poster?.setAttribute('aria-hidden', 'true');

    visibility = new IntersectionObserver(([entry]) => {
      visible = entry.isIntersecting;
      if (visible) requestRender();
      else { cancelAnimationFrame(frame); frame = 0; }
    });
    visibility.observe(stage);
    const listen = (element, type, callback) => element.addEventListener(type, callback, { signal: events.signal });
    listen(document, 'visibilitychange', () => {
      if (document.hidden) { cancelAnimationFrame(frame); frame = 0; }
      else requestRender();
    });
    listen(reducedMotion, 'change', requestRender);
    listen(canvas, 'pointerdown', event => {
      if (event.button !== 0 || pointer) return;
      pointer = { id: event.pointerId, x: event.clientX, y: event.clientY, rotation: target.y, tilt: target.x };
      canvas.setPointerCapture(event.pointerId);
    });
    listen(canvas, 'pointermove', event => {
      if (!pointer || event.pointerId !== pointer.id) return;
      target.y = pointer.rotation + (event.clientX - pointer.x) * 0.012;
      target.x = THREE.MathUtils.clamp(pointer.tilt + (event.clientY - pointer.y) * 0.004, -0.35, 0.35);
      requestRender();
    });
    const release = () => { pointer = null; };
    listen(canvas, 'pointerup', release);
    listen(canvas, 'pointercancel', release);
    listen(canvas, 'lostpointercapture', release);
    function reset() {
      // Take the shortest path back after any number of complete rotations.
      vial.rotation.y = THREE.MathUtils.euclideanModulo(vial.rotation.y + Math.PI, Math.PI * 2) - Math.PI;
      Object.assign(target, home);
      requestRender();
    }
    listen(controls.querySelector('button'), 'click', reset);
    listen(canvas, 'keydown', event => {
      if (!['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'Home'].includes(event.key)) return;
      event.preventDefault();
      if (event.key === 'Home') return reset();
      if (event.key === 'ArrowLeft') target.y -= 0.25;
      if (event.key === 'ArrowRight') target.y += 0.25;
      if (event.key === 'ArrowUp') target.x = Math.max(-0.35, target.x - 0.08);
      if (event.key === 'ArrowDown') target.x = Math.min(0.35, target.x + 0.08);
      requestRender();
    });
    // A context loss restores the useful photograph and removes unavailable controls.
    listen(canvas, 'webglcontextlost', cleanup);
    listen(window, 'pagehide', event => { if (!event.persisted) cleanup(); });
    return cleanup;
  } catch (error) {
    cleanup();
    throw error;
  }
}
