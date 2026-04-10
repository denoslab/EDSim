/**
 * `ThreeFloorPlan` — full 3D floor plan renderer using Three.js.
 *
 * Full 3D floor plan renderer:
 *  - **Floors**: flat PlaneGeometry per zone, textured with the same
 *    raster PNGs the 2D renderer uses.
 *  - **Walls**: extruded BoxGeometry along every wall segment, with a
 *    white MeshStandardMaterial and real shadow casting.
 *  - **Furniture**: Kenney `.glb` models loaded via `useGLTF` and
 *    positioned at each equipment tile.
 *  - **Lighting**: DirectionalLight (with shadow map) + soft
 *    AmbientLight for fill.
 *  - **Camera**: OrbitControls — drag to rotate, scroll to zoom,
 *    right-drag to pan.
 *
 * The component consumes the same {@link MapLayout} data model that the
 * 2D layers use, so the parser, sidebar, and test infrastructure are
 * completely unchanged.
 *
 * @packageDocumentation
 */

import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Canvas, useLoader, useThree } from '@react-three/fiber';
import { OrbitControls } from '@react-three/drei';
import type { OrbitControls as OrbitControlsImpl } from 'three-stdlib';
import * as THREE from 'three';
import { TextureLoader } from 'three';
import { FBXLoader } from 'three/examples/jsm/loaders/FBXLoader.js';
import type { MapLayout, EquipmentPlacement, ZoneRegion } from '@/parser/types';
import { ZONE_TEXTURE_URLS } from '@/assets';
import { ZONE_COLORS, CANVAS_BACKGROUND_COLOR } from '@/theme/colors';

/** Props for {@link ThreeFloorPlan}. */
export interface ThreeFloorPlanProps {
  /** Parsed map layout. */
  layout: MapLayout;
  /** Show zone labels. */
  showZoneLabels?: boolean;
  /** Show spawning overlay. */
  showSpawnOverlay?: boolean;
}

/** Scale: 1 tile = 1 Three.js unit. */
const WALL_HEIGHT = 2.5;
const WALL_THICKNESS = 0.25;
const FLOOR_Y = 0;

/**
 * FBX model URL mapping for each equipment type.
 *
 * Models are from the Hospital interior asset pack, copied to
 * `public/models/hospital/`. They share a common texture atlas
 * (`Texture_Atlas_Colors_2.png`) loaded once and applied to every
 * model's materials.
 */
const MODEL_URLS: Record<string, string> = {
  bed: '/models/hospital/bed.fbx',
  chair: '/models/hospital/chair.fbx',
  waiting_room_chair: '/models/hospital/waiting_chair.fbx',
  computer: '/models/hospital/computer.fbx',
  diagnostic_table: '/models/hospital/diagnostic_table.fbx',
  medical_equipment: '/models/hospital/medical_equipment.fbx',
  wheelchair: '/models/hospital/wheelchair.fbx'
};

/** Path to the shared texture atlas used by all hospital FBX models. */
const TEXTURE_ATLAS_URL = '/models/hospital/Texture_Atlas_Colors_2.png';

/**
 * Scale factors per equipment type, calculated from measured FBX
 * bounding boxes. The hospital FBX models are authored in millimetres
 * (a bed is ~1404 mm long). Each factor converts the model to
 * Three.js units where 1 unit = 1 map tile.
 *
 * Measured bounding boxes (width × depth × height in mm):
 *   bed:              589.7 × 1403.7 × 533.4  → target 1.2 tiles
 *   chair:            319.2 × 371.6  × 520.2  → target 0.5 tiles
 *   waiting_chair:    1826.7 × 385.7 × 579.2  → target 0.8 tiles
 *   computer:         328.5 × 47.4   × 221.5  → target 0.4 tiles
 *   medical_equipment:327.8 × 298.8  × 765.6  → target 0.4 tiles
 *   wheelchair:       399.7 × 646.7  × 565.0  → target 0.6 tiles
 *   diagnostic_table: 456.1 × 1244.8 × 653.8  → target 1.0 tiles
 */
const MODEL_SCALE: Record<string, number> = {
  bed: 0.00085,
  chair: 0.00135,
  waiting_room_chair: 0.00044,
  computer: 0.00122,
  diagnostic_table: 0.0008,
  medical_equipment: 0.00122,
  wheelchair: 0.00093
};

/* ZONE_COLORS and CANVAS_BACKGROUND_COLOR imported from @/theme/colors */

/* -------------------------------------------------------------------------- */
/* Floor zones                                                                */
/* -------------------------------------------------------------------------- */

function ZoneFloor({ zone }: { zone: ZoneRegion }) {
  const textureUrl = ZONE_TEXTURE_URLS[zone.zoneId];
  const texture = useLoader(TextureLoader, textureUrl);

  // Configure texture for tiling
  useMemo(() => {
    texture.wrapS = THREE.RepeatWrapping;
    texture.wrapT = THREE.RepeatWrapping;
    const tilesPerRepeat = 4;
    const repeatX = (zone.bounds.maxX - zone.bounds.minX + 1) / tilesPerRepeat;
    const repeatY = (zone.bounds.maxY - zone.bounds.minY + 1) / tilesPerRepeat;
    texture.repeat.set(repeatX, repeatY);
  }, [texture, zone]);

  const width = zone.bounds.maxX - zone.bounds.minX + 1;
  const depth = zone.bounds.maxY - zone.bounds.minY + 1;
  const centerX = zone.bounds.minX + width / 2;
  const centerZ = zone.bounds.minY + depth / 2;

  return (
    <mesh
      position={[centerX, FLOOR_Y, centerZ]}
      rotation={[-Math.PI / 2, 0, 0]}
      receiveShadow
    >
      <planeGeometry args={[width, depth]} />
      <meshStandardMaterial
        map={texture}
        color={ZONE_COLORS[zone.zoneId] ?? '#CCCCCC'}
        roughness={0.85}
        metalness={0.05}
      />
    </mesh>
  );
}

/* -------------------------------------------------------------------------- */
/* Walls                                                                      */
/* -------------------------------------------------------------------------- */

function Walls({ layout }: { layout: MapLayout }) {
  // Merge wall segments into BoxGeometry instances.
  const wallMeshes = useMemo(() => {
    return layout.walls.map((wall, i) => {
      const x1 = wall.x1;
      const z1 = wall.y1;
      const x2 = wall.x2;
      const z2 = wall.y2;

      let width: number;
      let depth: number;
      let cx: number;
      let cz: number;

      if (wall.orientation === 'horizontal') {
        width = Math.abs(x2 - x1);
        depth = WALL_THICKNESS;
        cx = (x1 + x2) / 2;
        cz = z1;
      } else {
        width = WALL_THICKNESS;
        depth = Math.abs(z2 - z1);
        cx = x1;
        cz = (z1 + z2) / 2;
      }

      return { key: i, width, depth, cx, cz };
    });
  }, [layout.walls]);

  return (
    <>
      {wallMeshes.map(({ key, width, depth, cx, cz }) => (
        <mesh
          key={key}
          position={[cx, WALL_HEIGHT / 2, cz]}
          castShadow
          receiveShadow
        >
          <boxGeometry args={[width, WALL_HEIGHT, depth]} />
          <meshStandardMaterial
            color="#F0EDE4"
            roughness={0.7}
            metalness={0.02}
          />
        </mesh>
      ))}
    </>
  );
}

/* -------------------------------------------------------------------------- */
/* Ground plane (surrounding area)                                            */
/* -------------------------------------------------------------------------- */

function GroundPlane({ layout }: { layout: MapLayout }) {
  const size = Math.max(layout.widthInTiles, layout.heightInTiles) * 3;
  return (
    <mesh
      position={[layout.widthInTiles / 2, -0.05, layout.heightInTiles / 2]}
      rotation={[-Math.PI / 2, 0, 0]}
      receiveShadow
    >
      <planeGeometry args={[size, size]} />
      <meshStandardMaterial color="#5A6058" roughness={1} metalness={0} />
    </mesh>
  );
}

/* -------------------------------------------------------------------------- */
/* Furniture                                                                  */
/* -------------------------------------------------------------------------- */

/**
 * Load an FBX model, apply the shared hospital texture atlas, clone
 * it, and configure shadow casting. Uses a module-level cache so each
 * model URL is loaded only once regardless of how many placements
 * reference it.
 */
const fbxCache = new Map<string, THREE.Group>();
const textureCache: { atlas: THREE.Texture | null } = { atlas: null };

function useFBXModel(modelUrl: string): THREE.Group | null {
  const [model, setModel] = useState<THREE.Group | null>(
    () => fbxCache.get(modelUrl)?.clone(true) ?? null
  );

  useEffect(() => {
    if (fbxCache.has(modelUrl)) {
      setModel(fbxCache.get(modelUrl)!.clone(true));
      return;
    }

    const loader = new FBXLoader();
    const texLoader = new TextureLoader();

    // Load the shared texture atlas once.
    const loadAtlas = (): Promise<THREE.Texture> => {
      if (textureCache.atlas) return Promise.resolve(textureCache.atlas);
      return new Promise((resolve) => {
        texLoader.load(TEXTURE_ATLAS_URL, (tex) => {
          tex.colorSpace = THREE.SRGBColorSpace;
          textureCache.atlas = tex;
          resolve(tex);
        });
      });
    };

    // Set the resource path so the FBXLoader can find the shared
    // texture atlas files (Texture_Atlas_Colors_2.png, etc.)
    // that the FBX materials reference.
    loader.setResourcePath('/models/hospital/');

    let cancelled = false;
    loadAtlas().then((atlas) => {
      loader.load(
        modelUrl,
        (fbx) => {
          if (cancelled) return;
          fbx.traverse((child) => {
            if (child instanceof THREE.Mesh) {
              child.castShadow = true;
              child.receiveShadow = true;
              // Apply the shared texture atlas to meshes that lack a
              // texture. Keep the original material colour so the
              // model's vertex colours / face colours show through.
              // The FBX models use a colour palette atlas. Apply it as
              // the texture map and keep Phong shading (which these
              // low-poly models were designed for).
              const mats = Array.isArray(child.material)
                ? child.material
                : [child.material];
              mats.forEach((m) => {
                const phong = m as THREE.MeshPhongMaterial;
                if (!phong.map) phong.map = atlas;
                phong.side = THREE.DoubleSide;
                phong.shininess = 20;
              });
            }
          });
          fbxCache.set(modelUrl, fbx);
          setModel(fbx.clone(true));
        },
        undefined,
        (err) => {
          if (!cancelled) console.warn('Failed to load FBX:', modelUrl, err);
        }
      );
    });

    return () => { cancelled = true; };
  }, [modelUrl]);

  return model;
}

/**
 * Renders a single hospital FBX model at the given equipment
 * placement's tile position.
 */
function FurnitureModel({
  piece,
  modelUrl
}: {
  piece: EquipmentPlacement;
  modelUrl: string;
}) {
  const model = useFBXModel(modelUrl);
  const scale = MODEL_SCALE[piece.type] ?? 0.012;

  if (!model) return null;
  return (
    <primitive
      object={model}
      position={[piece.tileX + 0.5, FLOOR_Y, piece.tileY + 0.5]}
      scale={[scale, scale, scale]}
    />
  );
}

/**
 * Renders all furniture placements from the parsed layout.
 */
function Furniture({ layout }: { layout: MapLayout }) {
  return (
    <>
      {layout.equipment.map((piece) => {
        const modelUrl = MODEL_URLS[piece.type];
        if (!modelUrl) return null;
        return (
          <FurnitureModel
            key={piece.equipmentId}
            piece={piece}
            modelUrl={modelUrl}
          />
        );
      })}
    </>
  );
}

/* -------------------------------------------------------------------------- */
/* Lighting                                                                   */
/* -------------------------------------------------------------------------- */

function Lighting({ layout }: { layout: MapLayout }) {
  const targetRef = useRef<THREE.Object3D>(null);
  const cx = layout.widthInTiles / 2;
  const cz = layout.heightInTiles / 2;
  const mapDiag = Math.max(layout.widthInTiles, layout.heightInTiles);

  return (
    <>
      <ambientLight intensity={1.5} color="#FFFFFF" />
      <hemisphereLight intensity={0.6} color="#FFFFFF" groundColor="#8C7A5A" />
      <directionalLight
        position={[cx - mapDiag * 0.4, mapDiag * 0.8, cz - mapDiag * 0.4]}
        intensity={1.8}
        color="#FFFAF0"
        castShadow
        shadow-mapSize-width={2048}
        shadow-mapSize-height={2048}
        shadow-camera-left={-mapDiag}
        shadow-camera-right={mapDiag}
        shadow-camera-top={mapDiag}
        shadow-camera-bottom={-mapDiag}
        shadow-camera-near={0.1}
        shadow-camera-far={mapDiag * 3}
        shadow-bias={-0.002}
      >
        {targetRef.current && <primitive object={targetRef.current} />}
      </directionalLight>
      <object3D ref={targetRef} position={[cx, 0, cz]} />
    </>
  );
}

/* -------------------------------------------------------------------------- */
/* Main scene                                                                 */
/* -------------------------------------------------------------------------- */

function Scene({
  layout,
  controlsRef
}: {
  layout: MapLayout;
  controlsRef: React.RefObject<OrbitControlsImpl | null>;
}) {
  const cx = layout.widthInTiles / 2;
  const cz = layout.heightInTiles / 2;
  const mapDiag = Math.max(layout.widthInTiles, layout.heightInTiles);

  return (
    <>
      <Lighting layout={layout} />
      <GroundPlane layout={layout} />
      {layout.zones.map((zone) => (
        <ZoneFloor key={zone.zoneRegionId} zone={zone} />
      ))}
      <Walls layout={layout} />
      <Furniture layout={layout} />
      <OrbitControls
        ref={controlsRef as React.RefObject<OrbitControlsImpl>}
        target={[cx, 0, cz]}
        maxPolarAngle={Math.PI / 2.2}
        minDistance={3}
        maxDistance={mapDiag * 2.5}
        enableDamping
        dampingFactor={0.08}
      />
    </>
  );
}

/**
 * Helper component rendered inside the Canvas to give the navigation
 * overlay access to the Three.js camera. Exposes `getCamera` via a
 * ref callback so the parent HTML overlay can read camera state.
 */
function CameraExposer({
  cameraRef
}: {
  cameraRef: React.MutableRefObject<THREE.Camera | null>;
}) {
  const { camera } = useThree();
  cameraRef.current = camera;
  return null;
}

/* -------------------------------------------------------------------------- */
/* Navigation overlay (Google Maps style)                                     */
/* -------------------------------------------------------------------------- */

const NAV_BUTTON_STYLE: React.CSSProperties = {
  width: 40,
  height: 40,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  background: '#FFFFFF',
  border: '1px solid #D0D0D0',
  borderRadius: 4,
  cursor: 'pointer',
  fontSize: 20,
  fontWeight: 500,
  color: '#333',
  fontFamily: 'system-ui, sans-serif',
  padding: 0,
  lineHeight: 1,
  userSelect: 'none',
  boxShadow: '0 1px 4px rgba(0,0,0,0.15)'
};

interface NavControlsProps {
  controlsRef: React.RefObject<OrbitControlsImpl | null>;
  cameraRef: React.MutableRefObject<THREE.Camera | null>;
  layout: MapLayout;
}

function NavControls({ controlsRef, cameraRef, layout }: NavControlsProps) {
  const ZOOM_STEP = 0.8;
  const ROTATE_STEP = Math.PI / 8;

  const zoom = useCallback(
    (factor: number) => {
      const controls = controlsRef.current;
      const camera = cameraRef.current;
      if (!controls || !camera) return;
      const target = controls.target;
      const dir = camera.position.clone().sub(target);
      dir.multiplyScalar(factor);
      camera.position.copy(target.clone().add(dir));
      controls.update();
    },
    [controlsRef, cameraRef]
  );

  const rotate = useCallback(
    (angle: number) => {
      const controls = controlsRef.current;
      const camera = cameraRef.current;
      if (!controls || !camera) return;
      const target = controls.target;
      const offset = camera.position.clone().sub(target);
      const cos = Math.cos(angle);
      const sin = Math.sin(angle);
      const x = offset.x * cos - offset.z * sin;
      const z = offset.x * sin + offset.z * cos;
      camera.position.set(target.x + x, camera.position.y, target.z + z);
      controls.update();
    },
    [controlsRef, cameraRef]
  );

  const resetCamera = useCallback(() => {
    const controls = controlsRef.current;
    const camera = cameraRef.current;
    if (!controls || !camera) return;
    const cx = layout.widthInTiles / 2;
    const cz = layout.heightInTiles / 2;
    const mapDiag = Math.max(layout.widthInTiles, layout.heightInTiles);
    camera.position.set(cx + mapDiag * 0.5, mapDiag * 0.7, cz + mapDiag * 0.5);
    controls.target.set(cx, 0, cz);
    controls.update();
  }, [controlsRef, cameraRef, layout]);

  return (
    <div
      style={{
        position: 'absolute',
        right: 16,
        top: 16,
        display: 'flex',
        flexDirection: 'column',
        gap: 2,
        zIndex: 10
      }}
      data-testid="nav-controls"
    >
      {/* Zoom group */}
      <button
        type="button"
        style={{ ...NAV_BUTTON_STYLE, borderRadius: '4px 4px 0 0' }}
        onClick={() => zoom(ZOOM_STEP)}
        title="Zoom in"
        data-testid="nav-zoom-in"
      >
        +
      </button>
      <button
        type="button"
        style={{ ...NAV_BUTTON_STYLE, borderRadius: '0 0 4px 4px' }}
        onClick={() => zoom(1 / ZOOM_STEP)}
        title="Zoom out"
        data-testid="nav-zoom-out"
      >
        −
      </button>

      <div style={{ height: 8 }} />

      {/* Rotate group */}
      <button
        type="button"
        style={{ ...NAV_BUTTON_STYLE, borderRadius: '4px 4px 0 0' }}
        onClick={() => rotate(-ROTATE_STEP)}
        title="Rotate left"
        data-testid="nav-rotate-left"
      >
        ↺
      </button>
      <button
        type="button"
        style={{ ...NAV_BUTTON_STYLE, borderRadius: '0 0 4px 4px' }}
        onClick={() => rotate(ROTATE_STEP)}
        title="Rotate right"
        data-testid="nav-rotate-right"
      >
        ↻
      </button>

      <div style={{ height: 8 }} />

      {/* Reset */}
      <button
        type="button"
        style={NAV_BUTTON_STYLE}
        onClick={resetCamera}
        title="Reset camera"
        data-testid="nav-reset"
      >
        ⌂
      </button>
    </div>
  );
}

/**
 * Top-level Three.js floor plan canvas. Drop-in replacement for
 * Takes the same `MapLayout` the parser produces and renders a real
 * 3D scene with Google Maps-style navigation controls.
 */
export function ThreeFloorPlan({ layout }: ThreeFloorPlanProps) {
  const mapDiag = Math.max(layout.widthInTiles, layout.heightInTiles);
  const controlsRef = useRef<OrbitControlsImpl | null>(null);
  const cameraRef = useRef<THREE.Camera | null>(null);

  return (
    <div
      style={{ width: '100%', height: '100%', background: CANVAS_BACKGROUND_COLOR, position: 'relative' }}
      data-testid="three-floor-plan"
    >
      <Canvas
        shadows
        camera={{
          position: [
            layout.widthInTiles / 2 + mapDiag * 0.5,
            mapDiag * 0.7,
            layout.heightInTiles / 2 + mapDiag * 0.5
          ],
          fov: 45,
          near: 0.1,
          far: mapDiag * 10
        }}
        gl={{ antialias: true, toneMapping: THREE.NoToneMapping }}
      >
        <Suspense fallback={null}>
          <Scene layout={layout} controlsRef={controlsRef} />
          <CameraExposer cameraRef={cameraRef} />
        </Suspense>
      </Canvas>
      <NavControls
        controlsRef={controlsRef}
        cameraRef={cameraRef}
        layout={layout}
      />
    </div>
  );
}
