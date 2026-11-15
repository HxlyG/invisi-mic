import * as THREE from "three";
import type { ItemKind, ItemRef, Room, SceneItem, Vec3 } from "@/store/slices/sceneSlice";
import { focusSpeaker } from "@/store/slices/sceneSlice";
import type { ViewMode } from "@/store/slices/dimensionSlice";

// Hex values mirror the design tokens in styles/globals.css.
const COLORS = {
  canvas: 0x0b0d10,
  floor: 0x0f1218,
  grid: 0x1e2430,
  wall: 0x94a3b8,
  sonar: 0x22d3ee,
  harmonic: 0xf59e0b,
};

const BEAM_HALF_ANGLE = (15 * Math.PI) / 180;

// Scene object names encode the item so pointer picks can be mapped back to the store.
export const itemName = (kind: ItemKind, id: string) => `${kind}:${id}`;

export function parseItemName(name: string): ItemRef | null {
  const [kind, id] = name.split(":");
  return (kind === "speaker" || kind === "micArray") && id ? { kind, id } : null;
}

// Invisible oversized sphere so small icons are easy to grab.
function hitTarget(name: string, position: THREE.Vector3) {
  const mesh = new THREE.Mesh(new THREE.SphereGeometry(0.6, 8, 6), new THREE.MeshBasicMaterial());
  mesh.name = name;
  mesh.visible = false;
  mesh.position.copy(position);
  return mesh;
}

// Store coordinates (x, depth y, height z) map to three.js (x, y up, z depth).
const toWorld = (v: Vec3) => new THREE.Vector3(v.x, v.z, v.y);

function floorRing(position: THREE.Vector3, color: number) {
  const mesh = new THREE.Mesh(
    new THREE.RingGeometry(0.3, 0.37, 32).rotateX(-Math.PI / 2),
    new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.6, side: THREE.DoubleSide }),
  );
  mesh.position.set(position.x, 0.002, position.z);
  return mesh;
}

function stem(position: THREE.Vector3, color: number) {
  const geometry = new THREE.BufferGeometry().setFromPoints([
    position,
    new THREE.Vector3(position.x, 0, position.z),
  ]);
  return new THREE.Line(geometry, new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.5 }));
}

function gridLines(room: Room) {
  const points: number[] = [];
  for (let x = 0; x <= room.width; x++) points.push(x, 0.001, 0, x, 0.001, room.length);
  for (let z = 0; z <= room.length; z++) points.push(0, 0.001, z, room.width, 0.001, z);

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(points, 3));
  return new THREE.LineSegments(geometry, new THREE.LineBasicMaterial({ color: COLORS.grid }));
}

export function buildScene(
  room: Room,
  speakers: SceneItem[],
  micArrays: SceneItem[],
  selected: ItemRef | null,
  view: ViewMode,
) {
  // Top-down hides height, so higher objects are drawn larger to suggest it.
  const heightScale = (z: number) => (view === "2d" ? 1 + 0.8 * (z / Math.max(room.height, 0.01)) : 1);
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(COLORS.canvas);

  const floor = new THREE.Mesh(
    new THREE.PlaneGeometry(room.width, room.length).rotateX(-Math.PI / 2).translate(room.width / 2, 0, room.length / 2),
    new THREE.MeshBasicMaterial({ color: COLORS.floor }),
  );
  scene.add(floor, gridLines(room));

  const box = new THREE.BoxGeometry(room.width, room.height, room.length).translate(
    room.width / 2,
    room.height / 2,
    room.length / 2,
  );
  scene.add(new THREE.LineSegments(new THREE.EdgesGeometry(box), new THREE.LineBasicMaterial({ color: COLORS.wall })));
  box.dispose();

  const isSelected = (kind: ItemKind, id: string) => selected?.kind === kind && selected.id === id;

  const highlight = (position: THREE.Vector3) => {
    const ring = new THREE.Mesh(
      new THREE.RingGeometry(0.6, 0.64, 48),
      new THREE.MeshBasicMaterial({
        color: 0x94a3b8,
        transparent: true,
        opacity: 0.65,
        side: THREE.DoubleSide,
        depthTest: false,
      }),
    );
    ring.position.copy(position);
    ring.name = "selection-ring";
    ring.renderOrder = 10;
    return ring;
  };

  for (const speaker of speakers) {
    const pos = toWorld(speaker.position);
    const mesh = new THREE.Mesh(
      new THREE.SphereGeometry(0.25, 24, 16),
      new THREE.MeshBasicMaterial({ color: COLORS.harmonic }),
    );
    mesh.position.copy(pos);
    mesh.scale.setScalar(heightScale(speaker.position.z));
    scene.add(mesh, stem(pos, COLORS.harmonic), floorRing(pos, COLORS.harmonic));
    scene.add(hitTarget(itemName("speaker", speaker.id), pos));
    if (isSelected("speaker", speaker.id)) scene.add(highlight(pos));
  }

  for (const micArray of micArrays) {
    const pos = toWorld(micArray.position);
    const mesh = new THREE.Mesh(
      new THREE.CylinderGeometry(0.35, 0.35, 0.1, 32),
      new THREE.MeshBasicMaterial({ color: COLORS.sonar }),
    );
    mesh.position.copy(pos);
    mesh.scale.setScalar(heightScale(micArray.position.z));
    scene.add(mesh, stem(pos, COLORS.sonar), floorRing(pos, COLORS.sonar));
    scene.add(hitTarget(itemName("micArray", micArray.id), pos));
    if (isSelected("micArray", micArray.id)) scene.add(highlight(pos));

    // Each array aims at its chosen focus speaker, if any.
    const target = focusSpeaker(micArray, speakers);
    if (!target) continue;
    const nearest = toWorld(target.position);
    const direction = nearest.clone().sub(pos);
    const length = direction.length();
    if (length <= 0.01) continue;

    // Cone apex sits at the array and opens toward the speaker.
    const beam = new THREE.Mesh(
      new THREE.ConeGeometry(length * Math.tan(BEAM_HALF_ANGLE), length, 32, 1, true).translate(0, -length / 2, 0),
      new THREE.MeshBasicMaterial({
        color: COLORS.sonar,
        transparent: true,
        opacity: 0.14,
        side: THREE.DoubleSide,
        depthWrite: false,
      }),
    );
    beam.position.copy(pos);
    beam.quaternion.setFromUnitVectors(new THREE.Vector3(0, -1, 0), direction.normalize());
    scene.add(beam);
  }

  return scene;
}

export function disposeScene(scene: THREE.Scene) {
  scene.traverse((obj) => {
    const item = obj as THREE.Mesh;
    item.geometry?.dispose();
    const material = item.material as THREE.Material | THREE.Material[] | undefined;
    if (Array.isArray(material)) material.forEach((m) => m.dispose());
    else material?.dispose();
  });
}

export function createCamera() {
  return new THREE.OrthographicCamera(-1, 1, 1, -1, 0.1, 1000);
}

export interface CameraState {
  azimuth: number;
  elevation: number;
  // Pan is in view-space meters; zoom multiplies the default framing.
  panX: number;
  panY: number;
  zoom: number;
}

// Just short of vertical so the camera's up vector never degenerates.
export const MAX_ELEVATION = (89.5 * Math.PI) / 180;

export const DEFAULT_CAMERA: CameraState = {
  azimuth: Math.PI / 4,
  elevation: Math.atan(1 / Math.SQRT2),
  panX: 0,
  panY: 0,
  zoom: 1,
};

// Unit vector from the look-at target toward the camera.
export function cameraDirection(azimuth: number, elevation: number) {
  return new THREE.Vector3(
    Math.cos(elevation) * Math.sin(azimuth),
    Math.sin(elevation),
    Math.cos(elevation) * Math.cos(azimuth),
  );
}

// Points the camera at the room and sizes the frustum so the whole room fits.
export function fitCamera(
  camera: THREE.OrthographicCamera,
  view: ViewMode,
  room: Room,
  aspect: number,
  orbit: CameraState = DEFAULT_CAMERA,
) {
  const target = new THREE.Vector3(room.width / 2, view === "3d" ? room.height / 2 : 0, room.length / 2);

  if (view === "2d") {
    camera.up.set(0, 0, -1);
    camera.position.set(target.x, 100, target.z);
  } else {
    camera.up.set(0, 1, 0);
    camera.position.copy(target).add(cameraDirection(orbit.azimuth, orbit.elevation).multiplyScalar(100));
  }
  camera.lookAt(target);
  camera.updateMatrixWorld(true);

  if (view === "3d") {
    // Frame the room's bounding sphere so the scale stays constant while orbiting.
    const half = (0.5 * Math.hypot(room.width, room.height, room.length) * 1.05) / orbit.zoom;
    const halfW = aspect >= 1 ? half * aspect : half;
    const halfH = aspect >= 1 ? half : half / aspect;
    camera.left = orbit.panX - halfW;
    camera.right = orbit.panX + halfW;
    camera.top = orbit.panY + halfH;
    camera.bottom = orbit.panY - halfH;
    camera.updateProjectionMatrix();
    return;
  }

  const min = new THREE.Vector2(Infinity, Infinity);
  const max = new THREE.Vector2(-Infinity, -Infinity);
  for (const x of [0, room.width]) {
    for (const y of [0, room.height]) {
      for (const z of [0, room.length]) {
        const p = new THREE.Vector3(x, y, z).applyMatrix4(camera.matrixWorldInverse);
        min.min(p);
        max.max(p);
      }
    }
  }

  const padding = 1.15;
  let halfW = ((max.x - min.x) / 2) * padding;
  let halfH = ((max.y - min.y) / 2) * padding;
  if (halfW / halfH < aspect) halfW = halfH * aspect;
  else halfH = halfW / aspect;

  const cx = (min.x + max.x) / 2;
  const cy = (min.y + max.y) / 2;
  camera.left = cx - halfW;
  camera.right = cx + halfW;
  camera.top = cy + halfH;
  camera.bottom = cy - halfH;
  camera.updateProjectionMatrix();
}
