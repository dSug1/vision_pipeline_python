// Trivial Three.js scene: one cube, position driven by the fingertip
// landmark each frame. Deliberately minimal, per Specification.md §5 — the
// JS analog of Part Zero's cube_window.py (Movement_with_hand_detection/Resources/CubeWindow.py),
// not Pipeline B. No orbit controls, no physics, fixed camera.
import * as THREE from "three";

const CUBE_SIZE = 0.4;

export class CubeScene {
  constructor(canvas) {
    this.canvas = canvas;

    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x1e2128);

    this.camera = new THREE.PerspectiveCamera(50, 1, 0.1, 100);
    this.camera.position.set(0, 0, 6);

    const light = new THREE.DirectionalLight(0xffffff, 2);
    light.position.set(2, 3, 4);
    this.scene.add(light);
    this.scene.add(new THREE.AmbientLight(0x404040, 2));

    const geometry = new THREE.BoxGeometry(CUBE_SIZE, CUBE_SIZE, CUBE_SIZE);
    const material = new THREE.MeshStandardMaterial({ color: 0x00c8ff });
    this.cube = new THREE.Mesh(geometry, material);
    this.scene.add(this.cube);

    this._resizeToCanvas();
    window.addEventListener("resize", () => this._resizeToCanvas());
  }

  _resizeToCanvas() {
    const { clientWidth, clientHeight } = this.canvas;
    if (clientWidth === 0 || clientHeight === 0) return;
    this.renderer.setSize(clientWidth, clientHeight, false);
    this.camera.aspect = clientWidth / clientHeight;
    this.camera.updateProjectionMatrix();
  }

  /**
   * The camera's actual visible half-width/half-height at the cube's z=0
   * plane, derived from FOV/distance/aspect (not a guessed constant) — so
   * the cube's range of motion always fills the real window, matching
   * CubeWindow.py's clamp against the actual window bounds instead of an
   * assumed size (see Claude/PART_ZERO.md).
   */
  _getVisibleHalfExtents() {
    const distance = this.camera.position.z; // camera looks down -Z at the cube's z=0 plane
    const halfHeight = distance * Math.tan(THREE.MathUtils.degToRad(this.camera.fov) / 2);
    const halfWidth = halfHeight * this.camera.aspect;
    return { halfWidth, halfHeight };
  }

  /**
   * @param {number} normalizedX - [0,1], already mirrored to match "hand moves right -> cube moves right"
   * @param {number} normalizedY - [0,1], image-space (0 = top)
   */
  setCubePositionFromNormalized(normalizedX, normalizedY) {
    const { halfWidth, halfHeight } = this._getVisibleHalfExtents();
    // Subtract the cube's own half-size so its far edge reaches the visible
    // boundary exactly at normalizedX/Y 0 or 1, instead of overshooting past
    // the window or (as before) stopping well short of it.
    const rangeX = halfWidth - CUBE_SIZE / 2;
    const rangeY = halfHeight - CUBE_SIZE / 2;
    const worldX = (normalizedX - 0.5) * 2 * rangeX;
    const worldY = (0.5 - normalizedY) * 2 * rangeY; // flip: image Y-down -> world Y-up
    this.cube.position.set(worldX, worldY, 0);
  }

  render() {
    this.renderer.render(this.scene, this.camera);
  }
}
