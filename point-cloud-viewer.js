(() => {
  const canvas = document.getElementById('point-cloud');
  const buttons = [...document.querySelectorAll('[data-scene]')];
  const loading = document.querySelector('.pointcloud-loading');
  const errorMessage = document.querySelector('.pointcloud-error');
  const yawInput = document.getElementById('yaw-angle');
  const pitchInput = document.getElementById('pitch-angle');
  const yawOutput = document.querySelector('output[for="yaw-angle"]');
  const pitchOutput = document.querySelector('output[for="pitch-angle"]');
  const posePanel = document.querySelector('.pose-panel');
  const savePoseButton = document.getElementById('save-pose');
  if (!canvas || !buttons.length) return;

  const context = canvas.getContext('2d', { alpha: true });
  if (!context) return;

  const scenePoses = window.EGO_POINT_CLOUD_POSES || {};
  let currentScene = 'laboratory';
  const initialPose = scenePoses[currentScene] || {};
  let points = null;
  let pointCount = 0;
  let image = null;
  let depthBuffer = null;
  let yaw = Number.isFinite(initialPose.yaw) ? initialPose.yaw : 0.55;
  let pitch = Number.isFinite(initialPose.pitch) ? initialPose.pitch : -0.22;
  let zoom = 1;
  let loadedScene = '';
  let activeRequest = null;
  let scheduledFrame = 0;
  if (scenePoses.saved === true) {
    posePanel.hidden = true;
  }

  function draw() {
    if (!points || !image || !depthBuffer) return;
    const width = canvas.width;
    const height = canvas.height;
    const pixels = image.data;
    pixels.fill(0);
    depthBuffer.fill(Infinity);

    const cosYaw = Math.cos(yaw);
    const sinYaw = Math.sin(yaw);
    const cosPitch = Math.cos(pitch);
    const sinPitch = Math.sin(pitch);
    const aspect = width / Math.max(height, 1);

    for (let point = 0; point < pointCount; point += 1) {
      const offset = point * 16;
      const x = points.getFloat32(offset, true);
      const y = points.getFloat32(offset + 4, true);
      const z = points.getFloat32(offset + 8, true);
      const rotatedX = cosYaw * x + sinYaw * z;
      const rotatedZ = -sinYaw * x + cosYaw * z;
      const rotatedY = cosPitch * y - sinPitch * rotatedZ;
      const finalZ = sinPitch * y + cosPitch * rotatedZ;
      const depth = 3.2 - finalZ;
      if (depth <= 0.2) continue;

      const focal = 2.55 * zoom / depth;
      const screenX = Math.round((rotatedX * focal / aspect * 0.5 + 0.5) * width);
      const screenY = Math.round((0.5 - rotatedY * focal * 0.5) * height);
      if (screenX < 1 || screenY < 1 || screenX >= width - 1 || screenY >= height - 1) continue;

      const red = points.getUint8(offset + 12);
      const green = points.getUint8(offset + 13);
      const blue = points.getUint8(offset + 14);
      const pixel = screenY * width + screenX;
      if (depth >= depthBuffer[pixel]) continue;
      depthBuffer[pixel] = depth;
      const color = pixel * 4;
      pixels[color] = red;
      pixels[color + 1] = green;
      pixels[color + 2] = blue;
      pixels[color + 3] = 255;
    }

    context.putImageData(image, 0, 0);
  }

  function scheduleDraw() {
    if (scheduledFrame) return;
    scheduledFrame = requestAnimationFrame(() => {
      scheduledFrame = 0;
      draw();
    });
  }

  function resize() {
    const bounds = canvas.getBoundingClientRect();
    const pixelRatio = Math.min(window.devicePixelRatio || 1, 1.5);
    const width = Math.max(1, Math.round(bounds.width * pixelRatio));
    const height = Math.max(1, Math.round(bounds.height * pixelRatio));
    if (canvas.width === width && canvas.height === height) return;
    canvas.width = width;
    canvas.height = height;
    image = context.createImageData(width, height);
    depthBuffer = new Float32Array(width * height);
    scheduleDraw();
  }

  function setSelectedScene(scene) {
    buttons.forEach((button) => {
      button.setAttribute('aria-pressed', String(button.dataset.scene === scene));
    });
  }

  function getScenePose(scene) {
    const pose = scenePoses[scene] || {};
    return {
      yaw: Number.isFinite(pose.yaw) ? pose.yaw : 0.55,
      pitch: Number.isFinite(pose.pitch) ? pose.pitch : -0.22,
    };
  }

  function rememberCurrentPose() {
    scenePoses[currentScene] = { yaw, pitch };
  }

  function syncPoseInputs() {
    const yawDegrees = (yaw * 180 / Math.PI % 360 + 360) % 360;
    const pitchDegrees = (pitch * 180 / Math.PI % 360 + 360) % 360;
    const yawValue = Math.round(yawDegrees);
    const pitchValue = Math.round(pitchDegrees);
    yawInput.value = String(yawValue);
    pitchInput.value = String(pitchValue);
    yawOutput.textContent = `${yawValue}°`;
    pitchOutput.textContent = `${pitchValue}°`;
  }

  function loadInlinePreview(scene, signal) {
    return new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = `assets/point-clouds/${scene}.js`;
      script.async = true;

      const cleanup = () => {
        signal.removeEventListener('abort', abort);
        script.remove();
      };
      const abort = () => {
        cleanup();
        reject(new DOMException('Point cloud load aborted', 'AbortError'));
      };

      script.onload = () => {
        const previews = window.EGO_POINT_CLOUD_PREVIEWS;
        const encoded = previews && previews[scene];
        if (previews) delete previews[scene];
        if (signal.aborted) return;
        if (!encoded) {
          cleanup();
          reject(new Error('Point cloud preview is empty'));
          return;
        }

        try {
          const binary = atob(encoded);
          const bytes = new Uint8Array(binary.length);
          for (let index = 0; index < binary.length; index += 1) {
            bytes[index] = binary.charCodeAt(index);
          }
          cleanup();
          resolve(bytes.buffer);
        } catch (error) {
          cleanup();
          reject(error);
        }
      };
      script.onerror = () => {
        cleanup();
        reject(new Error('Point cloud preview script could not be loaded'));
      };

      signal.addEventListener('abort', abort, { once: true });
      if (signal.aborted) {
        abort();
        return;
      }
      document.head.appendChild(script);
    });
  }

  async function loadScene(scene) {
    if (scene === loadedScene) return;
    rememberCurrentPose();
    currentScene = scene;
    const pose = getScenePose(scene);
    yaw = pose.yaw;
    pitch = pose.pitch;
    syncPoseInputs();
    if (activeRequest) activeRequest.abort();
    const request = new AbortController();
    activeRequest = request;
    setSelectedScene(scene);
    loading.hidden = false;
    errorMessage.hidden = true;

    try {
      const file = await loadInlinePreview(scene, request.signal);
      const header = new DataView(file);
      if (header.byteLength < 8 || header.getUint32(0, false) !== 0x45474f31) {
        throw new Error('Invalid point cloud preview');
      }
      const count = header.getUint32(4, true);
      if (header.byteLength !== 8 + count * 16) throw new Error('Incomplete point cloud preview');
      points = new DataView(file, 8);
      pointCount = count;
      loadedScene = scene;
      draw();
    } catch (error) {
      if (error.name !== 'AbortError') {
        console.error(error);
        errorMessage.textContent = 'Point cloud preview could not be loaded.';
        errorMessage.hidden = false;
        if (loadedScene) {
          currentScene = loadedScene;
          const previousPose = getScenePose(loadedScene);
          yaw = previousPose.yaw;
          pitch = previousPose.pitch;
          syncPoseInputs();
          setSelectedScene(loadedScene);
        }
      }
    } finally {
      if (activeRequest === request) loading.hidden = true;
    }
  }

  let dragging = false;
  let previousX = 0;
  let previousY = 0;
  canvas.addEventListener('pointerdown', (event) => {
    dragging = true;
    previousX = event.clientX;
    previousY = event.clientY;
    canvas.setPointerCapture(event.pointerId);
  });
  canvas.addEventListener('pointermove', (event) => {
    if (!dragging) return;
    const bounds = canvas.getBoundingClientRect();
    const canvasWidth = Math.max(bounds.width, 1);
    const canvasHeight = Math.max(bounds.height, 1);
    yaw += (event.clientX - previousX) * (Math.PI * 2 / canvasWidth);
    pitch += (event.clientY - previousY) * (Math.PI * 2 / canvasHeight);
    previousX = event.clientX;
    previousY = event.clientY;
    syncPoseInputs();
    scheduleDraw();
  });
  canvas.addEventListener('pointerup', () => { dragging = false; });
  canvas.addEventListener('pointercancel', () => { dragging = false; });

  // ── slow auto-orbit ──────────────────────────────────────────────────────
  // The scenes read as flat stills until they turn. Spin gently, yield to the
  // pointer, and stop entirely when the canvas is off-screen: draw() is a CPU
  // rasteriser over ~180k points and should not run against a hidden element.
  const SPIN_RATE = 0.075;        // rad/s
  const SPIN_FPS = 24;
  let spinResumeAt = 0, spinLast = 0, spinAcc = 0, spinVisible = true;

  canvas.addEventListener('pointerdown', () => { spinResumeAt = Infinity; });
  const resumeSpin = () => { spinResumeAt = performance.now() + 2500; };
  canvas.addEventListener('pointerup', resumeSpin);
  canvas.addEventListener('pointercancel', resumeSpin);
  canvas.addEventListener('wheel', resumeSpin, { passive: true });

  if (typeof IntersectionObserver === 'function') {
    new IntersectionObserver((entries) => { spinVisible = entries[0].isIntersecting; },
                             { threshold: 0.04 }).observe(canvas);
  }

  function spinStep(now) {
    if (!spinLast) spinLast = now;
    const dt = Math.min((now - spinLast) / 1000, 0.12);
    spinLast = now;
    if (spinVisible && !dragging && now >= spinResumeAt &&
        !document.hidden && !prefersReducedMotion) {
      spinAcc += dt;
      if (spinAcc >= 1 / SPIN_FPS) {
        yaw += SPIN_RATE * spinAcc;
        spinAcc = 0;
        syncPoseInputs();
        scheduleDraw();
      }
    }
    requestAnimationFrame(spinStep);
  }
  const prefersReducedMotion =
    window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  requestAnimationFrame(spinStep);
  canvas.addEventListener('wheel', (event) => {
    event.preventDefault();
    zoom = Math.max(0.6, Math.min(2.4, zoom * (event.deltaY < 0 ? 1.08 : 0.92)));
    scheduleDraw();
  }, { passive: false });
  yawInput.addEventListener('input', () => {
    yaw = Number(yawInput.value) * Math.PI / 180;
    syncPoseInputs();
    scheduleDraw();
  });
  pitchInput.addEventListener('input', () => {
    pitch = Number(pitchInput.value) * Math.PI / 180;
    syncPoseInputs();
    scheduleDraw();
  });
  savePoseButton.addEventListener('click', () => {
    try {
      rememberCurrentPose();
      const savedPoses = { saved: true };
      buttons.forEach((button) => {
        const pose = getScenePose(button.dataset.scene);
        savedPoses[button.dataset.scene] = {
          yaw: Number(pose.yaw.toFixed(8)),
          pitch: Number(pose.pitch.toFixed(8)),
        };
      });
      const source = `window.EGO_POINT_CLOUD_POSES = ${JSON.stringify(savedPoses, null, 2)};\n`;
      const file = new Blob([source], { type: 'text/javascript' });
      const url = URL.createObjectURL(file);
      const download = document.createElement('a');
      download.href = url;
      download.download = 'point-cloud-pose.js';
      document.body.appendChild(download);
      download.click();
      download.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      posePanel.hidden = true;
      errorMessage.hidden = true;
    } catch (error) {
      console.error(error);
      errorMessage.textContent = 'The pose could not be saved in this browser.';
      errorMessage.hidden = false;
    }
  });
  buttons.forEach((button) => button.addEventListener('click', () => loadScene(button.dataset.scene)));
  const videoViewport = document.getElementById('video-viewport');
  if (videoViewport) {
    const track = videoViewport.querySelector('.video-track');
    const videos = [...track.querySelectorAll('video')];
    const spacers = track.querySelectorAll('.video-spacer');
    const indicatorsContainer = document.getElementById('video-indicators');
    const indicators = videos.map((video, index) => {
      const indicator = document.createElement('button');
      indicator.type = 'button';
      indicator.setAttribute('aria-label', `Go to video ${index + 1}`);
      indicator.addEventListener('click', () => scrollToVideo(index));
      indicatorsContainer.appendChild(indicator);
      return indicator;
    });
    const scrollToVideo = (index) => {
      const video = videos[index];
      if (!video) return;
      const viewportLeft = videoViewport.getBoundingClientRect().left;
      const videoBounds = video.getBoundingClientRect();
      videoViewport.scrollTo({
        left: videoViewport.scrollLeft + videoBounds.left - viewportLeft + videoBounds.width / 2 - videoViewport.clientWidth / 2,
        behavior: 'smooth',
      });
    };
    const markCenteredVideo = () => {
      const viewportCenter = videoViewport.getBoundingClientRect().left + videoViewport.clientWidth / 2;
      let centeredVideo = null;
      let centeredIndex = 0;
      let nearestDistance = Infinity;
      videos.forEach((video, index) => {
        const bounds = video.getBoundingClientRect();
        const distance = Math.abs(bounds.left + bounds.width / 2 - viewportCenter);
        if (distance < nearestDistance) {
          nearestDistance = distance;
          centeredVideo = video;
          centeredIndex = index;
        }
      });
      videos.forEach((video) => video.classList.toggle('is-centered', video === centeredVideo));
      indicators.forEach((indicator, index) => {
        if (index === centeredIndex) indicator.setAttribute('aria-current', 'step');
        else indicator.removeAttribute('aria-current');
      });
    };
    const updateVideoLayout = () => {
      const videoWidth = videos[0]?.offsetWidth || 0;
      const sideSpace = Math.max(0, (videoViewport.clientWidth - videoWidth) / 2);
      spacers.forEach((spacer) => spacer.style.flexBasis = `${sideSpace}px`);
      markCenteredVideo();
    };

    videoViewport.addEventListener('scroll', markCenteredVideo, { passive: true });
    window.addEventListener('resize', updateVideoLayout);
    document.querySelectorAll('[data-video-scroll]').forEach((button) => {
      button.addEventListener('click', () => {
        const currentIndex = Math.max(0, videos.findIndex((video) => video.classList.contains('is-centered')));
        const nextIndex = Math.min(videos.length - 1, Math.max(0, currentIndex + Number(button.dataset.videoScroll)));
        scrollToVideo(nextIndex);
      });
    });
    updateVideoLayout();
    window.requestAnimationFrame(updateVideoLayout);
  }
  window.addEventListener('resize', resize);
  if ('ResizeObserver' in window) new ResizeObserver(resize).observe(canvas);
  syncPoseInputs();
  resize();
  loadScene('laboratory');
})();
