/**
 * KAZI-KASI GALAXY v2 — Immersive 3D Job Universe
 * 
 * Features:
 * - Post-processing bloom for glowing orbs
 * - 5000+ particle starfield
 * - Warp drive animation on job click
 * - Cinematic autopilot camera path
 * - Spatial audio design
 * - Interactive search/filter
 * - Mini-map overlay
 * - Particle trails between skills and jobs
 */

import * as THREE from 'https://esm.sh/three@0.160.0';
import { EffectComposer } from 'https://esm.sh/three@0.160.0/examples/jsm/postprocessing/EffectComposer.js';
import { RenderPass } from 'https://esm.sh/three@0.160.0/examples/jsm/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'https://esm.sh/three@0.160.0/examples/jsm/postprocessing/UnrealBloomPass.js';

// ============================================================
// GALAXY CONFIG
// ============================================================

const CONFIG = {
  jobCount: 150,
  particleCount: 5000,
  cameraDistance: 300,
  cameraFov: 65,
  bloomStrength: 1.2,
  bloomRadius: 0.5,
  bloomThreshold: 0.2,
  rotationSpeed: 0.0002,
  warpSpeed: 3,
};

// ============================================================
// GLOBALS
// ============================================================

let scene, camera, renderer, composer, clock;
let bloomPass;
let jobs = [], skills = [], nebulae = [], connections = [];
let hoveredObject = null, selectedJob = null;
let raycaster, mouse;
let galaxyGroup, skillGroup, nebulaGroup, particleSystem;
let autopilotMode = false, autopilotTime = 0;
let warpTarget = null, warpProgress = 0;
let searchQuery = '', searchFilter = '';
let audioCtx = null, ambientOsc = null;
let minimapCamera, minimapRenderer;

// ============================================================
// SHADERS
// ============================================================

const JOB_VERTEX_SHADER = `
  varying vec3 vNormal;
  varying vec3 vPosition;
  uniform float uTime;
  uniform float uHover;
  
  void main() {
    vNormal = normalize(normalMatrix * normal);
    vPosition = position;
    
    // Pulsing effect
    float pulse = sin(uTime * 2.0 + uHover * 5.0) * 0.08 + 1.0;
    vec3 newPosition = position * pulse;
    
    gl_Position = projectionMatrix * modelViewMatrix * vec4(newPosition, 1.0);
  }
`;

const JOB_FRAGMENT_SHADER = `
  uniform vec3 uColor;
  uniform float uIntensity;
  uniform float uTime;
  uniform float uHover;
  uniform float uSearchMatch;
  varying vec3 vNormal;
  varying vec3 vPosition;
  
  void main() {
    // Fresnel glow
    float fresnel = pow(1.0 - abs(dot(vNormal, vec3(0.0, 0.0, 1.0))), 2.5);
    
    // Pulsing core
    float core = sin(uTime * 3.0) * 0.2 + 0.8;
    
    // Search highlight
    float highlight = uSearchMatch * 0.5;
    
    vec3 glowColor = uColor * uIntensity * (1.0 + uHover * 0.5);
    vec3 coreColor = mix(uColor, vec3(1.0), 0.6) * core;
    
    vec3 finalColor = mix(coreColor, glowColor, fresnel);
    finalColor += highlight;
    
    float alpha = 1.0 - uHover * 0.2;
    gl_FragColor = vec4(finalColor, alpha);
  }
`;

const NEBULA_VERTEX_SHADER = `
  varying vec2 vUv;
  varying vec3 vPosition;
  
  void main() {
    vUv = uv;
    vPosition = position;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

const NEBULA_FRAGMENT_SHADER = `
  uniform vec3 uColor;
  uniform float uOpacity;
  uniform float uTime;
  varying vec2 vUv;
  varying vec3 vPosition;
  
  vec3 mod289(vec3 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
  vec4 mod289(vec4 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
  vec4 permute(vec4 x) { return mod289(((x*34.0)+1.0)*x); }
  vec4 taylorInvSqrt(vec4 r) { return 1.79284291400159 - 0.85373472095314 * r; }
  
  float snoise(vec3 v) {
    const vec2 C = vec2(1.0/6.0, 1.0/3.0);
    const vec4 D = vec4(0.0, 0.5, 1.0, 2.0);
    vec3 i = floor(v + dot(v, C.yyy));
    vec3 x0 = v - i + dot(i, C.xxx);
    vec3 g = step(x0.yzx, x0.xyz);
    vec3 l = 1.0 - g;
    vec3 i1 = min(g.xyz, l.zxy);
    vec3 i2 = max(g.xyz, l.zxy);
    vec3 x1 = x0 - i1 + C.xxx;
    vec3 x2 = x0 - i2 + C.yyy;
    vec3 x3 = x0 - D.yyy;
    i = mod289(i);
    vec4 p = permute(permute(permute(
      i.z + vec4(0.0, i1.z, i2.z, 1.0))
      + i.y + vec4(0.0, i1.y, i2.y, 1.0))
      + i.x + vec4(0.0, i1.x, i2.x, 1.0));
    float n_ = 0.142857142857;
    vec3 ns = n_ * D.wyz - D.xzx;
    vec4 j = p - 49.0 * floor(p * ns.z * ns.z);
    vec4 x_ = floor(j * ns.z);
    vec4 y_ = floor(j - 7.0 * x_);
    vec4 x = x_ *ns.x + ns.yyyy;
    vec4 y = y_ *ns.x + ns.yyyy;
    vec4 h = 1.0 - abs(x) - abs(y);
    vec4 b0 = vec4(x.xy, y.xy);
    vec4 b1 = vec4(x.zw, y.zw);
    vec4 s0 = floor(b0)*2.0 + 1.0;
    vec4 s1 = floor(b1)*2.0 + 1.0;
    vec4 sh = -step(h, vec4(0.0));
    vec4 a0 = b0.xzyw + s0.xzyw*sh.xxyy;
    vec4 a1 = b1.xzyw + s1.xzyw*sh.zzww;
    vec3 p0 = vec3(a0.xy, h.x);
    vec3 p1 = vec3(a0.zw, h.y);
    vec3 p2 = vec3(a1.xy, h.z);
    vec3 p3 = vec3(a1.zw, h.w);
    vec4 norm = taylorInvSqrt(vec4(dot(p0,p0), dot(p1,p1), dot(p2,p2), dot(p3,p3)));
    p0 *= norm.x; p1 *= norm.y; p2 *= norm.z; p3 *= norm.w;
    vec4 m = max(0.6 - vec4(dot(x0,x0), dot(x1,x1), dot(x2,x2), dot(x3,x3)), 0.0);
    m = m * m;
    return 42.0 * dot(m*m, vec4(dot(p0,x0), dot(p1,x1), dot(p2,x2), dot(p3,x3)));
  }
  
  void main() {
    vec3 pos = vPosition * 0.3;
    float noise = snoise(pos + uTime * 0.05);
    float noise2 = snoise(pos * 1.5 - uTime * 0.08);
    float noise3 = snoise(pos * 3.0 + uTime * 0.12);
    
    float alpha = smoothstep(-0.4, 0.9, noise) * 0.25;
    alpha += smoothstep(0.1, 1.0, noise2) * 0.15;
    alpha += smoothstep(0.3, 1.0, noise3) * 0.1;
    alpha *= uOpacity;
    
    vec3 color = uColor * (0.9 + noise * 0.3);
    
    gl_FragColor = vec4(color, alpha);
  }
`;

// ============================================================
// INITIALIZATION
// ============================================================

export function initGalaxy(container, galaxyData, options = {}) {
  // Scene setup
  scene = new THREE.Scene();
  scene.fog = new THREE.FogExp2(0x000000, 0.0015);
  
  camera = new THREE.PerspectiveCamera(
    CONFIG.cameraFov,
    container.clientWidth / container.clientHeight,
    0.1,
    3000
  );
  camera.position.set(0, 50, CONFIG.cameraDistance);
  
  renderer = new THREE.WebGLRenderer({ 
    antialias: true, 
    alpha: true,
    powerPreference: "high-performance"
  });
  renderer.setSize(container.clientWidth, container.clientHeight);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.2;
  container.appendChild(renderer.domElement);
  
  // Post-processing
  composer = new EffectComposer(renderer);
  const renderPass = new RenderPass(scene, camera);
  composer.addPass(renderPass);
  
  bloomPass = new UnrealBloomPass(
    new THREE.Vector2(container.clientWidth, container.clientHeight),
    CONFIG.bloomStrength,
    CONFIG.bloomRadius,
    CONFIG.bloomThreshold
  );
  composer.addPass(bloomPass);
  
  clock = new THREE.Clock();
  raycaster = new THREE.Raycaster();
  mouse = new THREE.Vector2();
  
  // Groups
  galaxyGroup = new THREE.Group();
  skillGroup = new THREE.Group();
  nebulaGroup = new THREE.Group();
  
  scene.add(galaxyGroup);
  scene.add(skillGroup);
  scene.add(nebulaGroup);
  
  // Build galaxy
  createStarfield();
  createNebulae(galaxyData.nebulae);
  createSkillStars(galaxyData.skills);
  createJobOrbs(galaxyData.jobs);
  createConnections(galaxyData.jobs, galaxyData.skills);
  
  // Minimap
  createMinimap();
  
  // Events
  container.addEventListener('mousemove', onMouseMove);
  container.addEventListener('click', onMouseClick);
  container.addEventListener('wheel', onScroll, { passive: true });
  window.addEventListener('resize', onResize);
  container.addEventListener('click', initAudio, { once: true });
  
  // Search
  const searchInput = document.getElementById('galaxy-search');
  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      searchQuery = e.target.value.toLowerCase();
      updateSearchHighlights();
    });
  }
  
  // Start
  animate();
  
  return {
    update: (newData) => updateGalaxy(newData),
    enableAutopilot: () => { autopilotMode = true; },
    disableAutopilot: () => { autopilotMode = false; },
  };
}

// ============================================================
// AUDIO
// ============================================================

function initAudio() {
  if (audioCtx) return;
  audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  startAmbientDrone();
}

function startAmbientDrone() {
  if (!audioCtx) return;
  
  ambientOsc = audioCtx.createOscillator();
  const gainNode = audioCtx.createGain();
  const filter = audioCtx.createBiquadFilter();
  
  ambientOsc.type = 'sine';
  ambientOsc.frequency.value = 60;
  
  filter.type = 'lowpass';
  filter.frequency.value = 150;
  
  gainNode.gain.value = 0.025;
  
  ambientOsc.connect(filter);
  filter.connect(gainNode);
  gainNode.connect(audioCtx.destination);
  
  ambientOsc.start();
  
  // Slow modulation
  setInterval(() => {
    const freq = 50 + Math.random() * 30;
    if (ambientOsc) {
      ambientOsc.frequency.exponentialRampToValueAtTime(freq, audioCtx.currentTime + 3);
    }
  }, 4000);
}

function playHoverSound() {
  if (!audioCtx) return;
  
  const osc = audioCtx.createOscillator();
  const gain = audioCtx.createGain();
  
  osc.type = 'sine';
  osc.frequency.value = 800 + Math.random() * 200;
  
  gain.gain.setValueAtTime(0.04, audioCtx.currentTime);
  gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.2);
  
  osc.connect(gain);
  gain.connect(audioCtx.destination);
  
  osc.start();
  osc.stop(audioCtx.currentTime + 0.2);
}

function playWarpSound() {
  if (!audioCtx) return;
  
  const osc = audioCtx.createOscillator();
  const gain = audioCtx.createGain();
  const filter = audioCtx.createBiquadFilter();
  
  osc.type = 'sawtooth';
  osc.frequency.setValueAtTime(100, audioCtx.currentTime);
  osc.frequency.exponentialRampToValueAtTime(1500, audioCtx.currentTime + 0.8);
  
  filter.type = 'lowpass';
  filter.frequency.value = 800;
  
  gain.gain.setValueAtTime(0.08, audioCtx.currentTime);
  gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 1.2);
  
  osc.connect(filter);
  filter.connect(gain);
  gain.connect(audioCtx.destination);
  
  osc.start();
  osc.stop(audioCtx.currentTime + 1.2);
}

// ============================================================
// CREATE OBJECTS
// ============================================================

function createStarfield() {
  const geometry = new THREE.BufferGeometry();
  const positions = new Float32Array(CONFIG.particleCount * 3);
  const colors = new Float32Array(CONFIG.particleCount * 3);
  const sizes = new Float32Array(CONFIG.particleCount);
  
  for (let i = 0; i < CONFIG.particleCount; i++) {
    const i3 = i * 3;
    positions[i3] = (Math.random() - 0.5) * 1500;
    positions[i3 + 1] = (Math.random() - 0.5) * 1500;
    positions[i3 + 2] = (Math.random() - 0.5) * 1500;
    
    colors[i3] = 0.7 + Math.random() * 0.3;
    colors[i3 + 1] = 0.7 + Math.random() * 0.3;
    colors[i3 + 2] = 0.8 + Math.random() * 0.2;
    
    sizes[i] = Math.random() * 2;
  }
  
  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
  geometry.setAttribute('size', new THREE.BufferAttribute(sizes, 1));
  
  const material = new THREE.PointsMaterial({
    size: 1.5,
    vertexColors: true,
    transparent: true,
    opacity: 0.7,
    blending: THREE.AdditiveBlending,
  });
  
  particleSystem = new THREE.Points(geometry, material);
  scene.add(particleSystem);
}

function createNebulae(nebulaData) {
  nebulaData.forEach((nebula) => {
    const geometry = new THREE.SphereGeometry(40, 32, 32);
    const material = new THREE.ShaderMaterial({
      vertexShader: NEBULA_VERTEX_SHADER,
      fragmentShader: NEBULA_FRAGMENT_SHADER,
      uniforms: {
        uColor: { value: new THREE.Color(nebula.color) },
        uOpacity: { value: 0.2 },
        uTime: { value: 0 },
      },
      transparent: true,
      side: THREE.DoubleSide,
      blending: THREE.AdditiveBlending,
    });
    
    const mesh = new THREE.Mesh(geometry, material);
    mesh.position.set(
      nebula.position[0],
      nebula.position[1],
      nebula.position[2]
    );
    mesh.userData = { type: 'nebula', data: nebula };
    
    nebulaGroup.add(mesh);
    nebulae.push(mesh);
  });
}

function createSkillStars(skillData) {
  skillData.forEach((skill) => {
    const geometry = new THREE.SphereGeometry(2.5, 16, 16);
    const material = new THREE.MeshBasicMaterial({
      color: 0xFFFFFF,
    });
    
    const star = new THREE.Mesh(geometry, material);
    star.position.set(
      skill.position[0],
      skill.position[1],
      skill.position[2]
    );
    star.userData = { type: 'skill', data: skill };
    
    // Glow
    const glowGeometry = new THREE.SphereGeometry(5, 16, 16);
    const glowMaterial = new THREE.MeshBasicMaterial({
      color: 0xFFFFFF,
      transparent: true,
      opacity: 0.3,
    });
    const glow = new THREE.Mesh(glowGeometry, glowMaterial);
    star.add(glow);
    
    skillGroup.add(star);
    skills.push(star);
  });
}

function createJobOrbs(jobData) {
  jobData.forEach((job) => {
    const geometry = new THREE.SphereGeometry(job.size, 32, 32);
    const material = new THREE.ShaderMaterial({
      vertexShader: JOB_VERTEX_SHADER,
      fragmentShader: JOB_FRAGMENT_SHADER,
      uniforms: {
        uColor: { value: new THREE.Color(job.color) },
        uIntensity: { value: 1.5 },
        uTime: { value: 0 },
        uHover: { value: 0 },
        uSearchMatch: { value: 0 },
      },
    });
    
    const orb = new THREE.Mesh(geometry, material);
    orb.position.set(
      job.position[0],
      job.position[1],
      job.position[2]
    );
    orb.userData = { type: 'job', data: job, originalColor: job.color };
    
    // Outer glow ring
    const ringGeometry = new THREE.RingGeometry(job.size * 1.8, job.size * 2.5, 32);
    const ringMaterial = new THREE.MeshBasicMaterial({
      color: job.color,
      transparent: true,
      opacity: 0.25,
      side: THREE.DoubleSide,
    });
    const ring = new THREE.Mesh(ringGeometry, ringMaterial);
    ring.lookAt(camera.position);
    orb.add(ring);
    
    galaxyGroup.add(orb);
    jobs.push(orb);
  });
}

function createConnections(jobData, skillData) {
  jobData.forEach((job) => {
    if (!job.connections || job.connections.length === 0) return;
    
    job.connections.forEach((skillId) => {
      const skill = skillData.find(s => s.id === skillId);
      if (!skill) return;
      
      const jobOrb = jobs.find(j => j.userData.data.id === job.id);
      const skillStar = skills.find(s => s.userData.data.id === skillId);
      
      if (!jobOrb || !skillStar) return;
      
      // Create particle trail
      const trailLength = 20;
      const trailGeometry = new THREE.BufferGeometry();
      const positions = new Float32Array(trailLength * 3);
      
      for (let i = 0; i < trailLength; i++) {
        const t = i / (trailLength - 1);
        positions[i * 3] = jobOrb.position.x + (skillStar.position.x - jobOrb.position.x) * t;
        positions[i * 3 + 1] = jobOrb.position.y + (skillStar.position.y - jobOrb.position.y) * t;
        positions[i * 3 + 2] = jobOrb.position.z + (skillStar.position.z - jobOrb.position.z) * t;
      }
      
      trailGeometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
      
      const trailMaterial = new THREE.LineBasicMaterial({
        color: job.color,
        transparent: true,
        opacity: 0.4,
      });
      
      const trail = new THREE.Line(trailGeometry, trailMaterial);
      galaxyGroup.add(trail);
      connections.push(trail);
    });
  });
}

function createMinimap() {
  const minimapContainer = document.getElementById('minimap');
  if (!minimapContainer) return;
  
  minimapCamera = new THREE.OrthographicCamera(-200, 200, 200, -200, 0.1, 1000);
  minimapCamera.position.set(0, 400, 0);
  minimapCamera.lookAt(0, 0, 0);
  
  minimapRenderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
  minimapRenderer.setSize(150, 150);
  minimapContainer.appendChild(minimapRenderer.domElement);
}

// ============================================================
// INTERACTION
// ============================================================

function onMouseMove(event) {
  const rect = renderer.domElement.getBoundingClientRect();
  mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
  mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
  
  raycaster.setFromCamera(mouse, camera);
  const intersects = raycaster.intersectObjects([...jobs, ...skills]);
  
  if (intersects.length > 0) {
    const object = intersects[0].object;
    
    if (hoveredObject !== object) {
      // Reset previous
      if (hoveredObject) {
        hoveredObject.material.uniforms.uHover.value = 0;
        hoveredObject.scale.set(1, 1, 1);
      }
      
      hoveredObject = object;
      hoveredObject.material.uniforms.uHover.value = 1;
      hoveredObject.scale.set(1.3, 1.3, 1.3);
      
      playHoverSound();
      showTooltip(object.userData.data);
    }
  } else {
    if (hoveredObject) {
      hoveredObject.material.uniforms.uHover.value = 0;
      hoveredObject.scale.set(1, 1, 1);
      hoveredObject = null;
      hideTooltip();
    }
  }
}

function onMouseClick(event) {
  if (!hoveredObject) return;
  
  const data = hoveredObject.userData.data;
  
  if (hoveredObject.userData.type === 'job') {
    selectedJob = data;
    playWarpSound();
    warpToJob(hoveredObject);
    showJobDetail(data);
  } else if (hoveredObject.userData.type === 'skill') {
    focusOnSkill(hoveredObject);
  }
}

function onScroll(event) {
  const zoomSpeed = 0.15;
  camera.position.z += event.deltaY * zoomSpeed;
  camera.position.z = Math.max(80, Math.min(600, camera.position.z));
}

function onResize() {
  const container = renderer.domElement.parentElement;
  camera.aspect = container.clientWidth / container.clientHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(container.clientWidth, container.clientHeight);
  composer.setSize(container.clientWidth, container.clientHeight);
}

// ============================================================
// CAMERA MOVEMENT
// ============================================================

function warpToJob(orb) {
  const targetPosition = orb.position.clone();
  const startPosition = camera.position.clone();
  const duration = 2000;
  const startTime = Date.now();
  
  warpTarget = orb;
  warpProgress = 0;
  
  function animateWarp() {
    const elapsed = Date.now() - startTime;
    const progress = Math.min(elapsed / duration, 1);
    warpProgress = progress;
    
    // Ease in-out cubic
    const easeProgress = progress < 0.5
      ? 4 * progress * progress * progress
      : 1 - Math.pow(-2 * progress + 2, 3) / 2;
    
    camera.position.lerpVectors(startPosition, targetPosition, easeProgress);
    camera.position.z += 40;
    camera.lookAt(targetPosition);
    
    if (progress < 1) {
      requestAnimationFrame(animateWarp);
    } else {
      warpTarget = null;
    }
  }
  
  animateWarp();
}

function focusOnSkill(star) {
  const targetPosition = star.position.clone();
  const startPosition = camera.position.clone();
  const duration = 1500;
  const startTime = Date.now();
  
  function animateFocus() {
    const elapsed = Date.now() - startTime;
    const progress = Math.min(elapsed / duration, 1);
    const easeProgress = 1 - Math.pow(1 - progress, 2);
    
    camera.position.lerpVectors(startPosition, targetPosition, easeProgress);
    camera.position.z += 60;
    camera.lookAt(targetPosition);
    
    if (progress < 1) {
      requestAnimationFrame(animateFocus);
    }
  }
  
  animateFocus();
}

// ============================================================
// UI OVERLAY
// ============================================================

function showTooltip(data) {
  let tooltip = document.getElementById('galaxy-tooltip');
  if (!tooltip) {
    tooltip = document.createElement('div');
    tooltip.id = 'galaxy-tooltip';
    tooltip.style.cssText = `
      position: fixed;
      background: rgba(12, 59, 67, 0.95);
      color: #F6F0E6;
      padding: 14px 18px;
      border-radius: 10px;
      font-family: 'Inter', sans-serif;
      font-size: 14px;
      pointer-events: none;
      z-index: 1000;
      max-width: 320px;
      box-shadow: 0 12px 40px rgba(0,0,0,0.4);
      backdrop-filter: blur(12px);
      border: 1px solid rgba(233, 162, 59, 0.3);
    `;
    document.body.appendChild(tooltip);
  }
  
  if (data.title) {
    tooltip.innerHTML = `
      <strong style="font-size:16px;">${data.title}</strong><br>
      <span style="opacity:0.7;font-size:13px;">${data.employer}</span><br>
      <span style="color:#E9A23B;font-weight:600;margin-top:4px;display:inline-block;">Match: ${(data.match_score * 100).toFixed(0)}%</span>
    `;
  } else if (data.name) {
    tooltip.innerHTML = `
      <strong style="font-size:16px;">${data.name}</strong><br>
      <span style="opacity:0.7;font-size:13px;">${data.connections} connections</span>
    `;
  }
  
  tooltip.style.display = 'block';
  tooltip.style.left = (event.clientX + 18) + 'px';
  tooltip.style.top = (event.clientY + 18) + 'px';
}

function hideTooltip() {
  const tooltip = document.getElementById('galaxy-tooltip');
  if (tooltip) tooltip.style.display = 'none';
}

function showJobDetail(job) {
  const modal = document.createElement('div');
  modal.id = 'job-detail-modal';
  modal.style.cssText = `
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(10, 10, 10, 0.92);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 2000;
    backdrop-filter: blur(20px);
  `;
  
  modal.innerHTML = `
    <div style="
      background: rgba(246, 240, 230, 0.98);
      padding: 48px;
      border-radius: 24px;
      max-width: 640px;
      width: 92%;
      max-height: 85vh;
      overflow-y: auto;
      color: #242424;
      box-shadow: 0 24px 80px rgba(0,0,0,0.5);
    ">
      <h2 style="font-family:'Fraunces',serif;font-size:36px;margin-bottom:12px;">${job.title}</h2>
      <p style="font-size:19px;color:#666;margin-bottom:24px;">${job.employer}</p>
      <div style="display:flex;gap:24px;margin-bottom:36px;flex-wrap:wrap;">
        <div>
          <strong style="font-size:12px;text-transform:uppercase;letter-spacing:0.08em;color:#999;">Match Score</strong><br>
          <span style="font-size:28px;color:#E9A23B;font-weight:700;">${(job.match_score * 100).toFixed(0)}%</span>
        </div>
        ${job.salary ? `<div><strong style="font-size:12px;text-transform:uppercase;letter-spacing:0.08em;color:#999;">Salary</strong><br><span style="font-size:28px;font-weight:700;">KES ${job.salary.toLocaleString()}</span></div>` : ''}
      </div>
      <div style="display:flex;gap:12px;flex-wrap:wrap;">
        <a href="/job/${job.id}" style="
          background:#E9A23B;color:#0C3B43;padding:14px 28px;border-radius:30px;
          text-decoration:none;font-weight:700;font-size:15px;
          transition:all 0.2s;
        ">View Full Job</a>
        <button onclick="closeJobModal()" style="
          background:transparent;border:2px solid #0C3B43;color:#0C3B43;
          padding:14px 28px;border-radius:30px;cursor:pointer;font-weight:700;font-size:15px;
          transition:all 0.2s;
        ">Close</button>
      </div>
    </div>
  `;
  
  document.body.appendChild(modal);
}

window.closeJobModal = function() {
  const modal = document.getElementById('job-detail-modal');
  if (modal) modal.remove();
};

function updateSearchHighlights() {
  jobs.forEach(orb => {
    const job = orb.userData.data;
    const matches = searchQuery && (
      job.title.toLowerCase().includes(searchQuery) ||
      job.employer.toLowerCase().includes(searchQuery)
    );
    orb.material.uniforms.uSearchMatch.value = matches ? 1 : 0;
  });
}

// ============================================================
// ANIMATION
// ============================================================

function animate() {
  requestAnimationFrame(animate);
  
  const elapsed = clock.getElapsedTime();
  
  // Rotate groups
  galaxyGroup.rotation.y += CONFIG.rotationSpeed;
  skillGroup.rotation.y -= CONFIG.rotationSpeed * 0.5;
  
  // Update shader uniforms
  jobs.forEach(orb => {
    orb.material.uniforms.uTime.value = elapsed;
  });
  
  nebulae.forEach(nebula => {
    nebula.material.uniforms.uTime.value = elapsed;
  });
  
  // Autopilot
  if (autopilotMode && !warpTarget) {
    autopilotTime += 0.001;
    camera.position.x = Math.sin(autopilotTime) * CONFIG.cameraDistance;
    camera.position.z = Math.cos(autopilotTime) * CONFIG.cameraDistance;
    camera.position.y = Math.sin(autopilotTime * 0.5) * 30;
    camera.lookAt(0, 0, 0);
  }
  
  // Render
  composer.render();
  
  // Minimap
  if (minimapRenderer && minimapCamera) {
    minimapCamera.position.x = camera.position.x;
    minimapCamera.position.z = camera.position.z;
    minimapRenderer.render(scene, minimapCamera);
  }
}

// ============================================================
// UPDATE
// ============================================================

function updateGalaxy(newData) {
  while (galaxyGroup.children.length > 0) galaxyGroup.remove(galaxyGroup.children[0]);
  while (skillGroup.children.length > 0) skillGroup.remove(skillGroup.children[0]);
  while (nebulaGroup.children.length > 0) nebulaGroup.remove(nebulaGroup.children[0]);
  
  jobs = []; skills = []; nebulae = []; connections = [];
  
  createNebulae(newData.nebulae);
  createSkillStars(newData.skills);
  createJobOrbs(newData.jobs);
  createConnections(newData.jobs, newData.skills);
}
