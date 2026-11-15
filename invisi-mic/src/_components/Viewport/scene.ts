import * as THREE from "three";
import type { ItemKind, ItemRef, Room, SceneItem, Vec3 } from "@/store/slices/sceneSlice";
import { focusSpeaker } from "@/store/slices/sceneSlice";
import type { Unit, ViewMode } from "@/store/slices/dimensionSlice";
import { DRAW_AREA, type Point } from "@/lib/roomShape";

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

const roomOutline = (room: Room) => room.outline?.length
  ? room.outline
  : [{ x: 0, y: 0 }, { x: room.width, y: 0 }, { x: room.width, y: room.length }, { x: 0, y: room.length }];

function clipFootprint(outline: { x: number; y: number }[], startY: number, endY: number) {
  const clip = (points: { x: number; y: number }[], boundary: number, keepAbove: boolean) => {
    const result: { x: number; y: number }[] = [];
    for (let index = 0; index < points.length; index++) {
      const current = points[index];
      const previous = points[(index + points.length - 1) % points.length];
      const currentInside = keepAbove ? current.y >= boundary : current.y <= boundary;
      const previousInside = keepAbove ? previous.y >= boundary : previous.y <= boundary;
      if (currentInside !== previousInside) {
        const ratio = (boundary - previous.y) / (current.y - previous.y);
        result.push({ x: previous.x + ratio * (current.x - previous.x), y: boundary });
      }
      if (currentInside) result.push(current);
    }
    return result;
  };
  return clip(clip(outline, startY, true), endY, false);
}

function footprintMesh(outline: { x: number; y: number }[], elevation: number, color: number) {
  if (outline.length < 3) return null;
  const shape = new THREE.Shape();
  shape.moveTo(outline[0].x, -outline[0].y);
  outline.slice(1).forEach((point) => shape.lineTo(point.x, -point.y));
  shape.closePath();
  const mesh = new THREE.Mesh(
    new THREE.ExtrudeGeometry(shape, { depth: elevation, bevelEnabled: false }).rotateX(-Math.PI / 2),
    new THREE.MeshBasicMaterial({ color, side: THREE.DoubleSide }),
  );
  return mesh;
}

function gridLines(room: Room) {
  const outline = roomOutline(room);
  const points: number[] = [];
  const intersections = (axis: "x" | "y", value: number) => {
    const other = axis === "x" ? "y" : "x";
    const values: number[] = [];
    outline.forEach((start, index) => {
      const end = outline[(index + 1) % outline.length];
      if ((start[axis] <= value && end[axis] > value) || (end[axis] <= value && start[axis] > value)) {
        values.push(start[other] + (value - start[axis]) * (end[other] - start[other]) / (end[axis] - start[axis]));
      }
    });
    return values.sort((a, b) => a - b);
  };
  for (let x = 0; x <= room.width; x++) {
    const crossings = intersections("x", x);
    for (let i = 0; i + 1 < crossings.length; i += 2) points.push(x, 0.001, crossings[i], x, 0.001, crossings[i + 1]);
  }
  for (let y = 0; y <= room.length; y++) {
    const crossings = intersections("y", y);
    for (let i = 0; i + 1 < crossings.length; i += 2) points.push(crossings[i], 0.001, y, crossings[i + 1], 0.001, y);
  }

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(points, 3));
  return new THREE.LineSegments(geometry, new THREE.LineBasicMaterial({ color: COLORS.grid }));
}

function dimensionLabel(text: string, position: THREE.Vector3, worldWidth: number) {
  const canvas = document.createElement("canvas");
  canvas.width = 512;
  canvas.height = 96;
  const context = canvas.getContext("2d");
  if (!context) return null;
  context.fillStyle = "#94a3b8";
  context.font = "600 42px sans-serif";
  context.textAlign = "center";
  context.textBaseline = "middle";
  context.fillText(text, canvas.width / 2, canvas.height / 2);

  const texture = new THREE.CanvasTexture(canvas);
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: texture, depthTest: false }));
  sprite.position.copy(position);
  sprite.scale.set(worldWidth, worldWidth * canvas.height / canvas.width, 1);
  sprite.renderOrder = 20;
  return sprite;
}

function dimensionLine(scene: THREE.Scene, from: THREE.Vector3, to: THREE.Vector3, extensions: [THREE.Vector3, THREE.Vector3], label: string, labelWidth: number, rotateLabel = false) {
  const tick = 0.12;
  const tickDirection = Math.abs(to.y - from.y) > Math.abs(to.x - from.x) + Math.abs(to.z - from.z)
    ? new THREE.Vector3(tick, 0, 0)
    : new THREE.Vector3(0, tick, 0);
  const points = [
    from, to,
    extensions[0], from,
    extensions[1], to,
    from.clone().sub(tickDirection), from.clone().add(tickDirection),
    to.clone().sub(tickDirection), to.clone().add(tickDirection),
  ];
  const geometry = new THREE.BufferGeometry().setFromPoints(points);
  scene.add(new THREE.LineSegments(geometry, new THREE.LineBasicMaterial({ color: 0x64748b })));
  const midpoint = from.clone().add(to).multiplyScalar(0.5);
  const sprite = dimensionLabel(label, midpoint, labelWidth);
  if (sprite) {
    if (rotateLabel) sprite.material.rotation = Math.PI / 2;
    scene.add(sprite);
  }
}

function addRoomDimensions(scene: THREE.Scene, room: Room, unit: Unit, view: ViewMode) {
  const convert = (value: number) => unit === "ft" ? value * 3.28084 : value;
  const suffix = unit;
  const value = (amount: number) => `${Math.round(convert(amount) * 100) / 100} ${suffix}`;
  const offset = Math.max(0.45, Math.min(room.width, room.length, room.height) * 0.12);
  const labelWidth = Math.max(1.7, Math.min(room.width, room.length) * 0.24);

  dimensionLine(
    scene,
    new THREE.Vector3(0, -offset, room.length + offset),
    new THREE.Vector3(room.width, -offset, room.length + offset),
    [new THREE.Vector3(0, 0, room.length), new THREE.Vector3(room.width, 0, room.length)],
    value(room.width),
    labelWidth,
  );
  dimensionLine(
    scene,
    new THREE.Vector3(room.width + offset, -offset, 0),
    new THREE.Vector3(room.width + offset, -offset, room.length),
    [new THREE.Vector3(room.width, 0, 0), new THREE.Vector3(room.width, 0, room.length)],
    value(room.length),
    labelWidth,
    true,
  );
  if (view === "2d") return;
  dimensionLine(
    scene,
    new THREE.Vector3(-offset, 0, room.length),
    new THREE.Vector3(-offset, room.height, room.length),
    [new THREE.Vector3(0, 0, room.length), new THREE.Vector3(0, room.height, room.length)],
    value(room.height),
    labelWidth,
  );
}

export function buildScene(
  room: Room,
  speakers: SceneItem[],
  micArrays: SceneItem[],
  selected: ItemRef | null,
  view: ViewMode,
  unit: Unit,
  showBeams = true,
) {
  // Top-down hides height, so higher objects are drawn larger to suggest it.
  const heightScale = (z: number) => (view === "2d" ? 1 + 0.8 * (z / Math.max(room.height, 0.01)) : 1);
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(COLORS.canvas);

  const outline = roomOutline(room);
  const floorShape = new THREE.Shape();
  floorShape.moveTo(outline[0].x, -outline[0].y);
  outline.slice(1).forEach((point) => floorShape.lineTo(point.x, -point.y));
  floorShape.closePath();
  const floor = new THREE.Mesh(new THREE.ShapeGeometry(floorShape).rotateX(-Math.PI / 2), new THREE.MeshBasicMaterial({ color: COLORS.floor }));
  scene.add(floor, gridLines(room));

  for (const [index, tier] of (room.tiers ?? []).entries()) {
    const tierOutline = clipFootprint(outline, tier.startY, tier.endY);
    const tierMesh = footprintMesh(tierOutline, tier.elevation, index % 2 ? 0x1b222d : 0x202834);
    if (tierMesh) scene.add(tierMesh);
  }

  if (room.stage) {
    const { x, y, width, length, elevation } = room.stage;
    const stage = new THREE.BoxGeometry(width, elevation, length).translate(x + width / 2, elevation / 2, y + length / 2);
    scene.add(
      new THREE.Mesh(stage, new THREE.MeshBasicMaterial({ color: 0x33231f })),
      new THREE.LineSegments(new THREE.EdgesGeometry(stage), new THREE.LineBasicMaterial({ color: COLORS.harmonic })),
    );
  }

  for (const pillar of room.pillars ?? []) {
    const geometry = new THREE.CylinderGeometry(pillar.radius, pillar.radius, pillar.height, 24);
    const mesh = new THREE.Mesh(geometry, new THREE.MeshBasicMaterial({ color: 0x3a414c }));
    mesh.position.set(pillar.x, pillar.height / 2, pillar.y);
    scene.add(mesh);
    const outlineGeometry = new THREE.EdgesGeometry(geometry);
    const outlineMesh = new THREE.LineSegments(outlineGeometry, new THREE.LineBasicMaterial({ color: COLORS.wall }));
    outlineMesh.position.copy(mesh.position);
    scene.add(outlineMesh);
  }

  const wallPoints: THREE.Vector3[] = [];
  outline.forEach((point, index) => {
    const next = outline[(index + 1) % outline.length];
    wallPoints.push(
      new THREE.Vector3(point.x, 0, point.y), new THREE.Vector3(next.x, 0, next.y),
      new THREE.Vector3(point.x, room.height, point.y), new THREE.Vector3(next.x, room.height, next.y),
      new THREE.Vector3(point.x, 0, point.y), new THREE.Vector3(point.x, room.height, point.y),
    );
  });
  scene.add(new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(wallPoints), new THREE.LineBasicMaterial({ color: COLORS.wall })));
  addRoomDimensions(scene, room, unit, view);

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
    if (!showBeams) continue;
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

// Fixed top-down workspace the camera frames while drawing, so corners can sit outside the current room.
export const DRAW_ROOM: Room = { ...DRAW_AREA, height: 3 };

const DRAFT_INVALID = 0xef4444;

export function buildDraftScene(points: Point[], room: Room, unit: Unit) {
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(COLORS.canvas);

  const floorShape = new THREE.Shape();
  floorShape.moveTo(0, 0);
  floorShape.lineTo(DRAW_ROOM.width, 0);
  floorShape.lineTo(DRAW_ROOM.width, -DRAW_ROOM.length);
  floorShape.lineTo(0, -DRAW_ROOM.length);
  floorShape.closePath();
  scene.add(
    new THREE.Mesh(new THREE.ShapeGeometry(floorShape).rotateX(-Math.PI / 2), new THREE.MeshBasicMaterial({ color: COLORS.floor })),
    gridLines(DRAW_ROOM),
  );

  // The room being replaced, as a dim reference.
  const previous = roomOutline(room).map((p) => new THREE.Vector3(p.x, 0.003, p.y));
  scene.add(new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(previous), new THREE.LineBasicMaterial({ color: 0x334155 })));

  if (points.length > 1) {
    const path = points.map((p) => new THREE.Vector3(p.x, 0.01, p.y));
    scene.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(path), new THREE.LineBasicMaterial({ color: COLORS.sonar })));
  }

  const dot = (radius: number, color: number, p: Point, height: number) => {
    const mesh = new THREE.Mesh(
      new THREE.CircleGeometry(radius, 24).rotateX(-Math.PI / 2),
      new THREE.MeshBasicMaterial({ color }),
    );
    mesh.position.set(p.x, height, p.y);
    return mesh;
  };
  points.forEach((p, index) => scene.add(index === 0 ? dot(0.28, COLORS.harmonic, p, 0.02) : dot(0.18, COLORS.sonar, p, 0.02)));

  const convert = (value: number) => unit === "ft" ? value * 3.28084 : value;
  for (let i = 1; i < points.length; i++) {
    const a = points[i - 1];
    const b = points[i];
    const length = Math.hypot(b.x - a.x, b.y - a.y);
    // Offset the label to one side so it doesn't sit on the wall.
    const label = dimensionLabel(
      `${Math.round(convert(length) * 100) / 100} ${unit}`,
      new THREE.Vector3((a.x + b.x) / 2 - ((b.y - a.y) / length) * 0.6, 0.05, (a.y + b.y) / 2 + ((b.x - a.x) / length) * 0.6),
      1.8,
    );
    if (label) scene.add(label);
  }

  const rubber = new THREE.Line(
    new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3()]),
    new THREE.LineBasicMaterial({ color: COLORS.sonar, transparent: true, opacity: 0.6 }),
  );
  rubber.name = "draft-rubber";
  rubber.visible = false;
  rubber.frustumCulled = false;
  const cursor = dot(0.14, 0xffffff, { x: 0, y: 0 }, 0.03);
  cursor.name = "draft-cursor";
  cursor.visible = false;
  scene.add(rubber, cursor);

  return scene;
}

// Moves the rubber-band wall and cursor marker without rebuilding the scene.
export function updateDraftCursor(scene: THREE.Scene, last: Point | null, hover: Point, valid: boolean) {
  const rubber = scene.getObjectByName("draft-rubber") as THREE.Line | undefined;
  const cursor = scene.getObjectByName("draft-cursor") as THREE.Mesh | undefined;
  if (!rubber || !cursor) return;
  const color = valid ? COLORS.sonar : DRAFT_INVALID;
  cursor.visible = true;
  cursor.position.set(hover.x, 0.03, hover.y);
  (cursor.material as THREE.MeshBasicMaterial).color.setHex(valid ? 0xffffff : DRAFT_INVALID);
  rubber.visible = last !== null;
  if (last) {
    rubber.geometry.setFromPoints([new THREE.Vector3(last.x, 0.015, last.y), new THREE.Vector3(hover.x, 0.015, hover.y)]);
    (rubber.material as THREE.LineBasicMaterial).color.setHex(color);
  }
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
