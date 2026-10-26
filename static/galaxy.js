/**
 * KAZI-KASI GALAXY — 3D Job Universe
 * 
 * This is not a feed. This is a spatial experience.
 * Jobs are celestial bodies. Skills are stars. You navigate by warping.
 */

// ============================================================
// INITIALIZATION
// ============================================================

let scene, camera, renderer, clock;
let jobs = [], skills = [], nebulae = [], connections = [];
let hoveredObject = null, selectedJob = null;
let raycaster, mouse;
let galaxyGroup, skillGroup, nebulaGroup;
let autopilotMode = false;

// Audio context for sound design
let audioCtx = null;

// Galaxy config
const GALAXY_CONFIG = {
  jobOrbSize: { min: 1.5, max: 6 },
  cameraDistance: 250,
  cameraFov: 60,
  particleCount: 2000,
  glowIntensity: 1.5,
  rotationSpeed: 0.0003,
};

// ============================================================
// SHADERS
// ============================================================

const JOB_VERTEX_SHADER = `
  varying vec3 vNormal;
  varying vec3 vPosition;
  uniform float uTime;
  
  void main() {
    vNormal = normalize(normalMatrix * normal);
    vPosition = position;
    
    // Subtle pulsing
    float pulse = sin(uTime * 2.0) * 0.05 + 1.0;
    vec3 newPosition = position * pulse;
    
    gl_Position = projectionMatrix * modelViewMatrix * vec4(newPosition, 1.0);
  }
`;

const JOB_FRAGMENT_SHADER = `
  uniform vec3 uColor;
  uniform float uIntensity;
  uniform float uTime;
  varying vec3 vNormal;
  varying vec3 vPosition;
  
  void main() {
    // Fresnel glow effect
    float fresnel = pow(1.0 - abs(dot(vNormal, vec3(0.0, 0.0, 1.0))), 2.0);
    
    // Pulsing core
    float core = sin(uTime * 3.0) * 0.2 + 0.8;
    
    vec3 glowColor = uColor * uIntensity;
    vec3 coreColor = mix(uColor, vec3(1.0), 0.5) * core;
    
    vec3 finalColor = mix(coreColor, glowColor, fresnel);
    
    gl_FragColor = vec4(finalColor, 1.0);
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
  
  // Simplex noise function
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
    // Generate noise-based nebula texture
    vec3 pos = vPosition * 0.5;
    float noise = snoise(pos + uTime * 0.1);
    float noise2 = snoise(pos * 2.0 - uTime * 0.15);
    
    float alpha = smoothstep(-0.3, 0.8, noise) * 0.3;
    alpha += smoothstep(0.0, 1.0, noise2) * 0.15;
    alpha *= uOpacity;
    
    vec3 color = uColor * (0.8 + noise * 0.4);
    
    gl_FragColor = vec4(color, alpha);
  }
`;

// ============================================================
// INITIALIZATION
// ============================================================

export function initGalaxy(container, galaxyData, options = {}) {
  // Setup Three.js
  scene = new THREE.Scene();
  camera = new THREE.PerspectiveCamera(
    GALAXY_CONFIG.cameraFov,
    container.clientWidth / container.clientHeight,
    0.1,
    2000
  );
  camera.position.z = GALAXY_CONFIG.cameraDistance;
  
  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setSize(container.clientWidth, container.clientHeight);
  renderer.setPixelRatio(window.devicePixelRatio);
  container.appendChild(renderer.domElement);
  
  clock = new THREE.Clock();
  raycaster = new THREE.Raycaster();
  mouse = new THREE.Vector2();
  
  // Initialize audio on first interaction
  container.addEventListener('click', initAudio, { once: true });
  
  // Create galaxy groups
  galaxyGroup = new THREE.Group();
  skillGroup = new THREE.Group();
  nebulaGroup = new THREE.Group();
  
  scene.add(galaxyGroup);
  scene.add(skillGroup);
  scene.add(nebulaGroup);
  
  // Build the galaxy
  createStarfield();
  createNebulae(galaxyData.nebulae);
  createSkillStars(galaxyData.skills);
  createJobOrbs(galaxyData.jobs);
  createConnections(galaxyData.jobs, galaxyData.skills);
  
  // Event listeners
  container.addEventListener('mousemove', onMouseMove);
  container.addEventListener('click', onMouseClick);
  container.addEventListener('wheel', onScroll, { passive: true });
  window.addEventListener('resize', onResize);
  
  // Start animation
  animate();
  
  return {
    update: (newData) => updateGalaxy(newData),
    enableAutopilot: () => { autopilotMode = true; },
    disableAutopilot: () => { autopilotMode = false; },
  };
}

// ============================================================
// AUDIO DESIGN
// ============================================================

function initAudio() {
  if (audioCtx) return;
  audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  playAmbientDrone();
}

function playAmbientDrone() {
  if (!audioCtx) return;
  
  // Create a subtle ambient drone
  const oscillator = audioCtx.createOscillator();
  const gainNode = audioCtx.createGain();
  const filter = audioCtx.createBiquadFilter();
  
  oscillator.type = 'sine';
  oscillator.frequency.value = 80; // Deep bass
  
  filter.type = 'lowpass';
  filter.frequency.value = 200;
  
  gainNode.gain.value = 0.03; // Very quiet
  
  oscillator.connect(filter);
  filter.connect(gainNode);
  gainNode.connect(audioCtx.destination);
  
  oscillator.start();
  
  // Slowly modulate frequency
  setInterval(() => {
    const freq = 60 + Math.random() * 40;
    oscillator.frequency.exponentialRampToValueAtTime(freq, audioCtx.currentTime + 2);
  }, 3000);
}

function playHoverSound() {
  if (!audioCtx) return;
  
  const oscillator = audioCtx.createOscillator();
  const gainNode = audioCtx.createGain();
  
  oscillator.type = 'sine';
  oscillator.frequency.value = 800;
  
  gainNode.gain.setValueAtTime(0.05, audioCtx.currentTime);
  gainNode.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.3);
  
  oscillator.connect(gainNode);
  gainNode.connect(audioCtx.destination);
  
  oscillator.start();
  oscillator.stop(audioCtx.currentTime + 0.3);
}

function playWarpSound() {
  if (!audioCtx) return;
  
  const oscillator = audioCtx.createOscillator();
  const gainNode = audioCtx.createGain();
  const filter = audioCtx.createBiquadFilter();
  
  oscillator.type = 'sawtooth';
  oscillator.frequency.setValueAtTime(200, audioCtx.currentTime);
  oscillator.frequency.exponentialRampToValueAtTime(2000, audioCtx.currentTime + 0.5);
  
  filter.type = 'lowpass';
  filter.frequency.value = 1000;
  
  gainNode.gain.setValueAtTime(0.1, audioCtx.currentTime);
  gainNode.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 1.0);
  
  oscillator.connect(filter);
  filter.connect(gainNode);
  gainNode.connect(audioCtx.destination);
  
  oscillator.start();
  oscillator.stop(audioCtx.currentTime + 1.0);
}

// ============================================================
// CREATE OBJECTS
// ============================================================

function createStarfield() {
  const geometry = new THREE.BufferGeometry();
  const positions = new Float32Array(GALAXY_CONFIG.particleCount * 3);
  const colors = new Float32Array(GALAXY_CONFIG.particleCount * 3);
  
  for (let i = 0; i < GALAXY_CONFIG.particleCount; i++) {
    const i3 = i * 3;
    positions[i3] = (Math.random() - 0.5) * 1000;
    positions[i3 + 1] = (Math.random() - 0.5) * 1000;
    positions[i3 + 2] = (Math.random() - 0.5) * 1000;
    
    // Subtle color variation
    colors[i3] = 0.8 + Math.random() * 0.2;
    colors[i3 + 1] = 0.8 + Math.random() * 0.2;
    colors[i3 + 2] = 0.9 + Math.random() * 0.1;
  }
  
  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
  
  const material = new THREE.PointsMaterial({
    size: 1.5,
    vertexColors: true,
    transparent: true,
    opacity: 0.6,
  });
  
  const stars = new THREE.Points(geometry, material);
  scene.add(stars);
}

function createNebulae(nebulaData) {
  nebulaData.forEach((nebula, idx) => {
    const geometry = new THREE.SphereGeometry(30, 32, 32);
    const material = new THREE.ShaderMaterial({
      vertexShader: NEBULA_VERTEX_SHADER,
      fragmentShader: NEBULA_FRAGMENT_SHADER,
      uniforms: {
        uColor: { value: new THREE.Color(nebula.color) },
        uOpacity: { value: 0.15 },
        uTime: { value: 0 },
      },
      transparent: true,
      side: THREE.DoubleSide,
    });
    
    const nebulaMesh = new THREE.Mesh(geometry, material);
    nebulaMesh.position.set(
      nebula.position[0],
      nebula.position[1],
      nebula.position[2]
    );
    nebulaMesh.userData = { type: 'nebula', data: nebula };
    
    nebulaGroup.add(nebulaMesh);
    nebulae.push(nebulaMesh);
  });
}

function createSkillStars(skillData) {
  skillData.forEach((skill) => {
    const geometry = new THREE.SphereGeometry(2, 16, 16);
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
    
    // Add glow
    const glowGeometry = new THREE.SphereGeometry(4, 16, 16);
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
        uIntensity: { value: GALAXY_CONFIG.glowIntensity },
        uTime: { value: 0 },
      },
    });
    
    const orb = new THREE.Mesh(geometry, material);
    orb.position.set(
      job.position[0],
      job.position[1],
      job.position[2]
    );
    orb.userData = { type: 'job', data: job };
    
    // Add outer glow ring
    const ringGeometry = new THREE.RingGeometry(job.size * 1.5, job.size * 2, 32);
    const ringMaterial = new THREE.MeshBasicMaterial({
      color: job.color,
      transparent: true,
      opacity: 0.2,
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
      
      const geometry = new THREE.BufferGeometry().setFromPoints([
        jobOrb.position,
        skillStar.position,
      ]);
      
      const material = new THREE.LineBasicMaterial({
        color: job.color,
        transparent: true,
        opacity: 0.3,
      });
      
      const line = new THREE.Line(geometry, material);
      galaxyGroup.add(line);
      connections.push(line);
    });
  });
}

// ============================================================
// INTERACTION
// ============================================================

function onMouseMove(event) {
  const rect = renderer.domElement.getBoundingClientRect();
  mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
  mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
  
  // Raycast
  raycaster.setFromCamera(mouse, camera);
  const intersects = raycaster.intersectObjects([...jobs, ...skills]);
  
  if (intersects.length > 0) {
    const object = intersects[0].object;
    
    if (hoveredObject !== object) {
      // Reset previous
      if (hoveredObject) {
        hoveredObject.scale.set(1, 1, 1);
      }
      
      // Highlight new
      hoveredObject = object;
      hoveredObject.scale.set(1.2, 1.2, 1.2);
      
      playHoverSound();
      
      // Show tooltip
      showTooltip(object.userData.data);
    }
  } else {
    if (hoveredObject) {
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
  const zoomSpeed = 0.1;
  camera.position.z += event.deltaY * zoomSpeed;
  camera.position.z = Math.max(100, Math.min(500, camera.position.z));
}

function onResize() {
  const container = renderer.domElement.parentElement;
  camera.aspect = container.clientWidth / container.clientHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(container.clientWidth, container.clientHeight);
}

// ============================================================
// CAMERA MOVEMENT
// ============================================================

function warpToJob(orb) {
  const targetPosition = orb.position.clone();
  const startPosition = camera.position.clone();
  const duration = 1500;
  const startTime = Date.now();
  
  function animateWarp() {
    const elapsed = Date.now() - startTime;
    const progress = Math.min(elapsed / duration, 1);
    const easeProgress = 1 - Math.pow(1 - progress, 3); // Ease out cubic
    
    camera.position.lerpVectors(startPosition, targetPosition, easeProgress);
    camera.position.z += 30; // Stay a bit back
    
    if (progress < 1) {
      requestAnimationFrame(animateWarp);
    }
  }
  
  animateWarp();
}

function focusOnSkill(star) {
  const targetPosition = star.position.clone();
  const startPosition = camera.position.clone();
  const duration = 1000;
  const startTime = Date.now();
  
  function animateFocus() {
    const elapsed = Date.now() - startTime;
    const progress = Math.min(elapsed / duration, 1);
    const easeProgress = 1 - Math.pow(1 - progress, 2);
    
    camera.position.lerpVectors(startPosition, targetPosition, easeProgress);
    camera.position.z += 50;
    
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
      padding: 12px 16px;
      border-radius: 8px;
      font-family: 'Inter', sans-serif;
      font-size: 14px;
      pointer-events: none;
      z-index: 1000;
      max-width: 300px;
      box-shadow: 0 8px 32px rgba(0,0,0,0.3);
      backdrop-filter: blur(10px);
    `;
    document.body.appendChild(tooltip);
  }
  
  if (data.title) {
    tooltip.innerHTML = `
      <strong>${data.title}</strong><br>
      <span style="opacity: 0.7">${data.employer}</span><br>
      <span style="color: #E9A23B">Match: ${(data.match_score * 100).toFixed(0)}%</span>
    `;
  } else if (data.name) {
    tooltip.innerHTML = `
      <strong>${data.name}</strong><br>
      <span style="opacity: 0.7">${data.connections} connections</span>
    `;
  }
  
  tooltip.style.display = 'block';
  tooltip.style.left = (event.clientX + 15) + 'px';
  tooltip.style.top = (event.clientY + 15) + 'px';
}

function hideTooltip() {
  const tooltip = document.getElementById('galaxy-tooltip');
  if (tooltip) {
    tooltip.style.display = 'none';
  }
}

function showJobDetail(job) {
  // Create modal
  const modal = document.createElement('div');
  modal.id = 'job-detail-modal';
  modal.style.cssText = `
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(12, 59, 67, 0.9);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 2000;
    backdrop-filter: blur(20px);
  `;
  
  modal.innerHTML = `
    <div style="
      background: rgba(246, 240, 230, 0.95);
      padding: 40px;
      border-radius: 20px;
      max-width: 600px;
      width: 90%;
      max-height: 80vh;
      overflow-y: auto;
      color: #242424;
    ">
      <h2 style="font-family: 'Fraunces', serif; font-size: 32px; margin-bottom: 10px;">${job.title}</h2>
      <p style="font-size: 18px; color: #666; margin-bottom: 20px;">${job.employer}</p>
      <div style="display: flex; gap: 20px; margin-bottom: 30px;">
        <div>
          <strong>Match Score</strong><br>
          <span style="font-size: 24px; color: #E9A23B;">${(job.match_score * 100).toFixed(0)}%</span>
        </div>
        ${job.salary ? `<div><strong>Salary</strong><br><span style="font-size: 24px;">KES ${job.salary.toLocaleString()}</span></div>` : ''}
      </div>
      <div style="display: flex; gap: 10px; margin-bottom: 30px;">
        <a href="/job/${job.id}" style="
          background: #E9A23B;
          color: #0C3B43;
          padding: 12px 24px;
          border-radius: 30px;
          text-decoration: none;
          font-weight: 600;
        ">View Job</a>
        <button onclick="closeJobModal()" style="
          background: transparent;
          border: 2px solid #0C3B43;
          color: #0C3B43;
          padding: 12px 24px;
          border-radius: 30px;
          cursor: pointer;
          font-weight: 600;
        ">Close</button>
      </div>
    </div>
  `;
  
  document.body.appendChild(modal);
}

window.closeJobModal = function() {
  const modal = document.getElementById('job-detail-modal');
  if (modal) {
    modal.remove();
  }
};

// ============================================================
// ANIMATION LOOP
// ============================================================

function animate() {
  requestAnimationFrame(animate);
  
  const elapsed = clock.getElapsedTime();
  
  // Rotate galaxy slowly
  galaxyGroup.rotation.y += GALAXY_CONFIG.rotationSpeed;
  skillGroup.rotation.y -= GALAXY_CONFIG.rotationSpeed * 0.5;
  
  // Update shader uniforms
  jobs.forEach(orb => {
    if (orb.material.uniforms) {
      orb.material.uniforms.uTime.value = elapsed;
    }
  });
  
  nebulae.forEach(nebula => {
    if (nebula.material.uniforms) {
      nebula.material.uniforms.uTime.value = elapsed;
    }
  });
  
  // Autopilot mode: slowly rotate camera
  if (autopilotMode) {
    camera.position.x = Math.sin(elapsed * 0.1) * GALAXY_CONFIG.cameraDistance;
    camera.position.z = Math.cos(elapsed * 0.1) * GALAXY_CONFIG.cameraDistance;
    camera.lookAt(0, 0, 0);
  }
  
  renderer.render(scene, camera);
}

// ============================================================
// UPDATE
// ============================================================

function updateGalaxy(newData) {
  // Clear existing
  while (galaxyGroup.children.length > 0) {
    galaxyGroup.remove(galaxyGroup.children[0]);
  }
  while (skillGroup.children.length > 0) {
    skillGroup.remove(skillGroup.children[0]);
  }
  while (nebulaGroup.children.length > 0) {
    nebulaGroup.remove(nebulaGroup.children[0]);
  }
  
  jobs = [];
  skills = [];
  nebulae = [];
  connections = [];
  
  // Rebuild
  createNebulae(newData.nebulae);
  createSkillStars(newData.skills);
  createJobOrbs(newData.jobs);
  createConnections(newData.jobs, newData.skills);
}
