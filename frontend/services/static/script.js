// ===================================================
// 시간 유틸리티
// ===================================================
function getCurrentTime() {
    return new Date().toLocaleTimeString('ko-KR', { hour12: false, hour: '2-digit', minute:'2-digit', second:'2-digit' });
}

function getFormattedDateTime() {
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const day = String(now.getDate()).padStart(2, '0');
    const hours = String(now.getHours()).padStart(2, '0');
    const minutes = String(now.getMinutes()).padStart(2, '0');
    const seconds = String(now.getSeconds()).padStart(2, '0');
    return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
}

function todayStr() {
    const n = new Date();
    return `${n.getFullYear()}-${String(n.getMonth()+1).padStart(2,'0')}-${String(n.getDate()).padStart(2,'0')}`;
}
function nowTimeStr() { return new Date().toTimeString().slice(0,8); } // HH:MM:SS
function startOfDayTimeStr() { return '00:00:00'; }

// 1초마다 카메라 상단 시간 업데이트
setInterval(() => {
    document.getElementById('camera-datetime').innerText = getFormattedDateTime();
}, 1000);

// ===================================================
// 서버 상태 폴링
// ===================================================
const ROBOT_STATUS_STALE_MS = 5000;

function parseStatusTimestamp(value) {
    if (value === undefined || value === null || value === '') return null;
    const numeric = Number(value);
    const parsed = Number.isFinite(numeric)
        ? new Date(numeric < 1e12 ? numeric * 1000 : numeric)
        : new Date(value);
    return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function hasFreshRobotReport(data) {
    if (!Object.prototype.hasOwnProperty.call(data, 'updated_at')) return true;
    const updatedAt = parseStatusTimestamp(data.updated_at);
    return Boolean(updatedAt && Date.now() - updatedAt.getTime() <= ROBOT_STATUS_STALE_MS);
}

function fetchRobotStatus() {
    fetch('/get_status')
        .then(response => {
            if (!response.ok) {
                throw new Error(
                    `status HTTP ${response.status}`,
                );
            }

            return response.json();
        })
        .then(data => {
            document.getElementById(
                'sys-cpu-usage',
            ).innerText = data.cpu_usage;

            document.getElementById(
                'sys-cpu-temp',
            ).innerText = data.cpu_temp;

            document.getElementById(
                'sys-ram',
            ).innerText = data.ram_usage;

            document.getElementById(
                'sys-internet',
            ).innerText = data.internet;

            const reportedMode = String(
                data.mode || '',
            )
                .trim()
                .toLowerCase();
            const hasActualReport = hasFreshRobotReport(data);

            if (
                hasActualReport
                && (
                    reportedMode === 'auto'
                    || reportedMode === 'manual'
                )
            ) {
                applyServerPatrolMode(reportedMode);
            } else {
                applyServerPatrolMode(null);
            }

            document.dispatchEvent(new CustomEvent(
                'dabom:robot-status',
                { detail: { available: true, payload: data } },
            ));
        })
        .catch(error => {
            applyServerPatrolMode(null);
            document.dispatchEvent(new CustomEvent(
                'dabom:robot-status',
                { detail: { available: false, error: error.message } },
            ));
            console.error(
                '상태 업데이트 오류:',
                error,
            );
        });
}
setInterval(fetchRobotStatus, 1000);

// ===================================================
// 카메라 연결 상태 폴링
// ===================================================
function setLiveBadge(isLive) {
    const badge = document.querySelector('.live-badge');
    if (!badge) return;
    badge.classList.toggle('offline', !isLive);
    badge.textContent = isLive ? 'LIVE' : 'OFFLINE';
}

function showCameraLive() {
    const videoWrapper = document.getElementById('video-wrapper');
    const cameraStream = document.getElementById('camera-stream');
    const messageBox = document.getElementById('no-camera-msg');

    if (videoWrapper) videoWrapper.classList.remove('camera-offline');
    if (cameraStream) cameraStream.style.display = '';
    if (messageBox) messageBox.style.display = 'none';
    setLiveBadge(true);
}

function showCameraDisconnected(message, hideStream = false) {
    const videoWrapper = document.getElementById('video-wrapper');
    const cameraStream = document.getElementById('camera-stream');
    const messageBox = document.getElementById('no-camera-msg');

    if (videoWrapper) videoWrapper.classList.add('camera-offline');
    if (cameraStream) cameraStream.style.display = hideStream ? 'none' : '';
    if (messageBox) {
        messageBox.innerText = message || '카메라 연결 상태를 확인할 수 없습니다';
        messageBox.style.display = 'flex';
    }
    setLiveBadge(false);
}

function updateCameraStatus(data) {
    if (data.camera_state === 'live') {
        showCameraLive();
        return;
    }

    showCameraDisconnected(data.message, true);
}

function fetchCameraStatus() {
    fetch('/api/stream_status')
        .then(response => response.json())
        .then(updateCameraStatus)
        .catch(() => showCameraDisconnected('서버와 연결이 끊겼습니다', true));
}

setInterval(fetchCameraStatus, 1000);
fetchCameraStatus();

// ===================================================
// 카메라 에러 처리
// ===================================================
function handleCameraError() {
    showCameraDisconnected('영상 스트림을 불러올 수 없습니다', true);
}

const cameraStream = document.getElementById('camera-stream');
if (cameraStream) {
    cameraStream.addEventListener('error', handleCameraError);
}

// ===================================================
// LiDAR map 시각화
// ===================================================
const LIDAR_STALE_SECONDS = 3;
const LIDAR_OFFLINE_SECONDS = 8;
const SCAN_PULSE_DURATION_MS = 850;

const lidarState = {
    status: null,
    map: null,
    pose: null,
    scan: null,
    mapImage: null,
    mapImageKey: null,
    renderPending: false,
    lastScanKey: null,
    lastScanSeenAtMs: 0,
    lastScanPulseAtMs: 0,
    scanIntervalsMs: [],
};

function fetchOptionalJson(url) {
    return fetch(url)
        .then(response => {
            if (!response.ok) return null;
            return response.json();
        })
        .catch(() => null);
}

function formatAgeSeconds(age) {
    return typeof age === 'number' && Number.isFinite(age) ? `${age.toFixed(1)}s` : '--';
}

function getScanKey(scan) {
    if (!scan || !Array.isArray(scan.ranges)) return null;
    const first = scan.ranges.length ? scan.ranges[0] : '';
    const last = scan.ranges.length ? scan.ranges[scan.ranges.length - 1] : '';
    return `${scan.timestamp || ''}:${scan.received_at || ''}:${scan.ranges.length}:${first}:${last}`;
}

function noteScanUpdate(scan) {
    const key = getScanKey(scan);
    if (!key || key === lidarState.lastScanKey) return;

    const now = performance.now();
    if (lidarState.lastScanSeenAtMs > 0) {
        const interval = now - lidarState.lastScanSeenAtMs;
        if (interval >= 80 && interval <= 10000) {
            lidarState.scanIntervalsMs.push(interval);
            if (lidarState.scanIntervalsMs.length > 8) lidarState.scanIntervalsMs.shift();
        }
    }

    lidarState.lastScanKey = key;
    lidarState.lastScanSeenAtMs = now;
    lidarState.lastScanPulseAtMs = now;
}

function getScanReceiveHz() {
    if (!lidarState.scanIntervalsMs.length) return null;
    const total = lidarState.scanIntervalsMs.reduce((sum, value) => sum + value, 0);
    const avg = total / lidarState.scanIntervalsMs.length;
    return avg > 0 ? 1000 / avg : null;
}

function getNavigationAgeSec() {
    const statusAge = lidarState.status?.last_update_age_sec;
    if (typeof statusAge === 'number' && Number.isFinite(statusAge)) return statusAge;
    if (lidarState.lastScanSeenAtMs > 0) return (performance.now() - lidarState.lastScanSeenAtMs) / 1000;
    return null;
}

function getLidarLiveState() {
    const backendStatus = lidarState.status?.status;
    const hasData = Boolean(lidarState.map || lidarState.scan || lidarState.pose);
    const age = getNavigationAgeSec();

    if (!hasData) {
        return { level: 'offline', label: 'OFFLINE', title: 'LiDAR OFFLINE', detail: 'NO SCAN DATA', age };
    }
    if (backendStatus === 'offline') {
        return { level: 'offline', label: 'OFFLINE', title: 'LiDAR OFFLINE', detail: `LAST ${formatAgeSeconds(age)} AGO`, age };
    }
    if (typeof age === 'number' && age > LIDAR_OFFLINE_SECONDS) {
        return { level: 'offline', label: 'OFFLINE', title: 'LiDAR OFFLINE', detail: `LAST ${formatAgeSeconds(age)} AGO`, age };
    }
    if (backendStatus === 'stale' || (typeof age === 'number' && age > LIDAR_STALE_SECONDS)) {
        return { level: 'stale', label: 'STALE', title: 'LiDAR STALE', detail: `LAST ${formatAgeSeconds(age)} AGO`, age };
    }
    return { level: 'live', label: 'LIVE', title: 'LiDAR LIVE', detail: `AGE ${formatAgeSeconds(age)}`, age };
}

function decodeRleMap(runs, expectedLength) {
    const output = new Int16Array(expectedLength);
    let index = 0;
    if (!Array.isArray(runs)) return output;
    for (const run of runs) {
        if (!Array.isArray(run) || run.length < 2) continue;
        const value = Number(run[0]);
        const count = Number(run[1]);
        for (let i = 0; i < count && index < expectedLength; i += 1) {
            output[index] = value;
            index += 1;
        }
        if (index >= expectedLength) break;
    }
    return output;
}

function buildMapImage(map) {
    const width = Number(map?.width || 0);
    const height = Number(map?.height || 0);
    if (!width || !height || !map?.data) return null;

    const key = `${map.timestamp || ''}:${map.received_at || ''}:${width}x${height}`;
    if (lidarState.mapImage && lidarState.mapImageKey === key) return lidarState.mapImage;

    const cells = decodeRleMap(map.data, width * height);
    const offscreen = document.createElement('canvas');
    offscreen.width = width;
    offscreen.height = height;
    const ctx = offscreen.getContext('2d');
    const image = ctx.createImageData(width, height);

    for (let row = 0; row < height; row += 1) {
        for (let col = 0; col < width; col += 1) {
            const src = row * width + col;
            const dstRow = height - 1 - row;
            const dst = (dstRow * width + col) * 4;
            const value = cells[src];
            let r = 54, g = 65, b = 84;
            if (value === 0) {
                r = 230; g = 238; b = 246;
            } else if (value > 0) {
                const shade = Math.max(26, 92 - Math.round(value * 0.58));
                r = shade; g = shade + 6; b = shade + 16;
            }
            image.data[dst] = r;
            image.data[dst + 1] = g;
            image.data[dst + 2] = b;
            image.data[dst + 3] = 255;
        }
    }

    ctx.putImageData(image, 0, 0);
    lidarState.mapImage = offscreen;
    lidarState.mapImageKey = key;
    return offscreen;
}

function getCanvasLayout(canvas, map) {
    const padding = minimapExpanded ? 24 : 8;
    const width = canvas.width;
    const height = canvas.height;
    const mapWidth = Number(map?.width || 0);
    const mapHeight = Number(map?.height || 0);
    const resolution = Number(map?.resolution || 0.05);
    const worldWidth = mapWidth > 0 ? mapWidth * resolution : 8;
    const worldHeight = mapHeight > 0 ? mapHeight * resolution : 8;
    const scale = Math.min(
        (width - padding * 2) / Math.max(worldWidth, 0.1),
        (height - padding * 2) / Math.max(worldHeight, 0.1)
    );
    const drawWidth = worldWidth * scale;
    const drawHeight = worldHeight * scale;
    return {
        padding,
        scale,
        x: (width - drawWidth) / 2,
        y: (height - drawHeight) / 2,
        width: drawWidth,
        height: drawHeight,
        worldWidth,
        worldHeight,
        originX: Number(map?.origin?.x || 0),
        originY: Number(map?.origin?.y || 0),
        originYaw: Number(map?.origin?.yaw || 0),
    };
}

function worldToCanvas(x, y, layout) {
    const dx = x - layout.originX;
    const dy = y - layout.originY;
    const cosYaw = Math.cos(layout.originYaw);
    const sinYaw = Math.sin(layout.originYaw);
    const localX = cosYaw * dx + sinYaw * dy;
    const localY = -sinYaw * dx + cosYaw * dy;
    return {
        x: layout.x + localX * layout.scale,
        y: layout.y + layout.height - localY * layout.scale,
    };
}

function canvasToWorld(x, y, layout) {
    const localX = (x - layout.x) / layout.scale;
    const localY = (layout.y + layout.height - y) / layout.scale;
    if (localX < 0 || localY < 0 || localX >= layout.worldWidth || localY >= layout.worldHeight) {
        return null;
    }
    const cosYaw = Math.cos(layout.originYaw);
    const sinYaw = Math.sin(layout.originYaw);
    return {
        x: layout.originX + cosYaw * localX - sinYaw * localY,
        y: layout.originY + sinYaw * localX + cosYaw * localY,
    };
}

function drawRobot(ctx, pose, layout) {
    if (!pose) return;
    const point = worldToCanvas(Number(pose.x || 0), Number(pose.y || 0), layout);
    const yaw = Number(pose.yaw || 0);
    const size = minimapExpanded ? 13 : 8;

    ctx.save();
    ctx.translate(point.x, point.y);
    ctx.rotate(-yaw);
    ctx.beginPath();
    ctx.moveTo(size, 0);
    ctx.lineTo(-size * 0.65, -size * 0.55);
    ctx.lineTo(-size * 0.35, 0);
    ctx.lineTo(-size * 0.65, size * 0.55);
    ctx.closePath();
    ctx.fillStyle = '#e11d48';
    ctx.strokeStyle = 'rgba(255,255,255,0.86)';
    ctx.lineWidth = minimapExpanded ? 2 : 1.2;
    ctx.fill();
    ctx.stroke();
    ctx.restore();
}

function drawScan(ctx, scan, pose, layout) {
    if (!scan || !Array.isArray(scan.ranges) || scan.ranges.length === 0) return;
    const hasPose = Boolean(pose);
    const robotX = hasPose ? Number(pose.x || 0) : layout.originX + layout.worldWidth / 2;
    const robotY = hasPose ? Number(pose.y || 0) : layout.originY + layout.worldHeight / 2;
    const robotYaw = hasPose ? Number(pose.yaw || 0) : 0;
    const angleMin = Number(scan.angle_min || 0);
    const angleIncrement = Number(scan.angle_increment || 0);
    const rangeMin = Number(scan.range_min || 0);
    const rangeMax = Number(scan.range_max || 12);

    ctx.save();
    ctx.fillStyle = '#22d3ee';
    ctx.shadowColor = 'rgba(34, 211, 238, 0.5)';
    ctx.shadowBlur = minimapExpanded ? 5 : 2;
    const radius = minimapExpanded ? 2.2 : 1.4;
    for (let i = 0; i < scan.ranges.length; i += 1) {
        const range = scan.ranges[i];
        if (range === null || range === undefined) continue;
        const distance = Number(range);
        if (!Number.isFinite(distance) || distance < rangeMin || distance > rangeMax) continue;
        const angle = robotYaw + angleMin + angleIncrement * i;
        const x = robotX + Math.cos(angle) * distance;
        const y = robotY + Math.sin(angle) * distance;
        const point = worldToCanvas(x, y, layout);
        if (point.x < layout.x - 2 || point.x > layout.x + layout.width + 2) continue;
        if (point.y < layout.y - 2 || point.y > layout.y + layout.height + 2) continue;
        ctx.beginPath();
        ctx.arc(point.x, point.y, radius, 0, Math.PI * 2);
        ctx.fill();
    }
    ctx.restore();
}

function drawScanPulse(ctx, pose, layout) {
    if (!lidarState.lastScanPulseAtMs) return false;

    const elapsed = performance.now() - lidarState.lastScanPulseAtMs;
    if (elapsed < 0 || elapsed > SCAN_PULSE_DURATION_MS) return false;

    const progress = elapsed / SCAN_PULSE_DURATION_MS;
    const robotX = pose ? Number(pose.x || 0) : layout.originX + layout.worldWidth / 2;
    const robotY = pose ? Number(pose.y || 0) : layout.originY + layout.worldHeight / 2;
    const center = worldToCanvas(robotX, robotY, layout);
    const baseRadius = minimapExpanded ? 12 : 6;
    const spread = minimapExpanded ? 80 : 28;
    const radius = baseRadius + spread * progress;
    const alpha = Math.max(0, 0.78 * (1 - progress));

    ctx.save();
    ctx.beginPath();
    ctx.arc(center.x, center.y, radius, 0, Math.PI * 2);
    ctx.strokeStyle = `rgba(34, 211, 238, ${alpha})`;
    ctx.lineWidth = minimapExpanded ? 3 : 1.8;
    ctx.shadowColor = `rgba(34, 211, 238, ${alpha})`;
    ctx.shadowBlur = minimapExpanded ? 16 : 8;
    ctx.stroke();
    ctx.restore();
    return true;
}

function drawEmptyLidar(ctx, canvas) {
    ctx.fillStyle = '#101827';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.strokeStyle = 'rgba(34, 211, 238, 0.14)';
    ctx.lineWidth = 1;
    const step = minimapExpanded ? 32 : 16;
    for (let x = 0; x < canvas.width; x += step) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, canvas.height);
        ctx.stroke();
    }
    for (let y = 0; y < canvas.height; y += step) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(canvas.width, y);
        ctx.stroke();
    }
}

function updateLidarLabels() {
    const statusEl = document.getElementById('lidar-map-status');
    const metaEl = document.getElementById('lidar-map-meta');
    const badgeEl = document.getElementById('lidar-live-badge');
    const overlayEl = document.getElementById('lidar-stale-overlay');
    const overlayTitleEl = document.getElementById('lidar-stale-title');
    const overlayDetailEl = document.getElementById('lidar-stale-detail');
    if (!statusEl || !metaEl) return;

    const liveState = getLidarLiveState();
    const hasData = Boolean(lidarState.map || lidarState.scan || lidarState.pose);
    const ageText = formatAgeSeconds(liveState.age);
    const map = lidarState.map;
    const pose = lidarState.pose;
    const scanHz = getScanReceiveHz();
    const scanText = scanHz ? `RX ${scanHz.toFixed(1)}Hz` : 'RX --';

    statusEl.classList.toggle('has-data', hasData);
    statusEl.classList.toggle('stale', liveState.level !== 'live');
    statusEl.textContent = hasData ? liveState.label : 'MAP AREA';

    if (badgeEl) {
        badgeEl.classList.remove('live', 'stale', 'offline');
        badgeEl.classList.add(liveState.level);
        badgeEl.textContent = liveState.level === 'live' ? `LiDAR ${liveState.label}` : liveState.label;
    }

    if (overlayEl) {
        overlayEl.classList.toggle('visible', liveState.level !== 'live');
        overlayEl.classList.remove('stale', 'offline');
        overlayEl.classList.add(liveState.level === 'stale' ? 'stale' : 'offline');
    }
    if (overlayTitleEl) overlayTitleEl.textContent = liveState.title;
    if (overlayDetailEl) overlayDetailEl.textContent = liveState.detail;

    if (map) {
        const x = pose ? Number(pose.x || 0).toFixed(2) : '--';
        const y = pose ? Number(pose.y || 0).toFixed(2) : '--';
        metaEl.textContent = `${liveState.label} / ${scanText} / ${map.width}x${map.height} / AGE ${ageText} / X ${x} Y ${y}`;
    } else if (lidarState.scan) {
        metaEl.textContent = `${liveState.label} / ${scanText} / AGE ${ageText}`;
    } else {
        metaEl.textContent = 'LiDAR OFFLINE';
    }
}

function renderLidarMap() {
    const canvas = document.getElementById('lidar-map-canvas');
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    const nextWidth = Math.max(1, Math.floor(rect.width * dpr));
    const nextHeight = Math.max(1, Math.floor(rect.height * dpr));
    if (canvas.width !== nextWidth || canvas.height !== nextHeight) {
        canvas.width = nextWidth;
        canvas.height = nextHeight;
    }
    const ctx = canvas.getContext('2d');
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    const map = lidarState.map;
    const pose = lidarState.pose;
    const scan = lidarState.scan;
    const layout = getCanvasLayout(canvas, map);

    drawEmptyLidar(ctx, canvas);
    if (map) {
        const image = buildMapImage(map);
        if (image) {
            ctx.imageSmoothingEnabled = false;
            ctx.drawImage(image, layout.x, layout.y, layout.width, layout.height);
        }
        ctx.strokeStyle = 'rgba(34, 211, 238, 0.32)';
        ctx.lineWidth = Math.max(1, dpr);
        ctx.strokeRect(layout.x, layout.y, layout.width, layout.height);
    }
    drawScan(ctx, scan, pose, layout);
    const pulseActive = drawScanPulse(ctx, pose, layout);
    drawRobot(ctx, pose, layout);
    if (window.navigationControlOverlay?.draw) {
        window.navigationControlOverlay.draw(ctx, layout, worldToCanvas);
    }
    updateLidarLabels();
    if (pulseActive) requestLidarRender();
}

function requestLidarRender() {
    if (lidarState.renderPending) return;
    lidarState.renderPending = true;
    requestAnimationFrame(() => {
        lidarState.renderPending = false;
        renderLidarMap();
    });
}

function defaultNavigationMapName() {
    const now = new Date();
    const yyyy = now.getFullYear();
    const mm = String(now.getMonth() + 1).padStart(2, '0');
    const dd = String(now.getDate()).padStart(2, '0');
    const hh = String(now.getHours()).padStart(2, '0');
    const mi = String(now.getMinutes()).padStart(2, '0');
    const ss = String(now.getSeconds()).padStart(2, '0');
    return `patrol_area_${yyyy}${mm}${dd}_${hh}${mi}${ss}`;
}

function saveCurrentNavigationMap() {
    const button = document.getElementById('lidarMapSaveBtn');
    if (!lidarState.map) {
        alert('저장할 LiDAR map이 아직 없습니다. mapping 데이터 수신 후 다시 시도하세요.');
        return;
    }
    const mapName = prompt('저장할 map 이름을 입력하세요.', defaultNavigationMapName());
    if (mapName === null) return;
    const trimmedName = mapName.trim();
    if (!trimmedName) {
        alert('map 이름이 비어 있습니다.');
        return;
    }

    if (button) {
        button.disabled = true;
        button.textContent = '...';
    }

    fetch('/api/navigation/maps/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ map_name: trimmedName }),
    })
        .then(response => response.json().then(data => ({ ok: response.ok && data.ok, data })))
        .then(({ ok, data }) => {
            if (!ok) {
                alert(`map 저장 실패: ${data.error || 'unknown error'}`);
                return;
            }
            const savedName = data.map?.map_name || trimmedName;
            alert(`map 저장 완료: ${savedName}`);
        })
        .catch(error => {
            console.error('map 저장 오류:', error);
            alert('서버 통신 오류로 map을 저장하지 못했습니다.');
        })
        .finally(() => {
            if (button) {
                button.disabled = false;
                button.textContent = 'SAVE';
            }
        });
}

function fetchNavigationStatus() {
    fetchOptionalJson('/api/navigation/status').then(data => {
        if (data) lidarState.status = data;
        document.dispatchEvent(new CustomEvent(
            'dabom:navigation-status',
            { detail: { available: Boolean(data), payload: data } },
        ));
        requestLidarRender();
    });
}

function fetchNavigationMap() {
    fetchOptionalJson('/api/navigation/map').then(data => {
        if (data?.ok) {
            lidarState.map = data.available ? data.map : null;
            if (!data.available) {
                lidarState.mapImage = null;
                lidarState.mapImageKey = null;
            }
        }
        if (data?.status) lidarState.status = data.status;
        requestLidarRender();
    });
}

function fetchNavigationPoseAndScan() {
    Promise.all([
        fetchOptionalJson('/api/navigation/pose'),
        fetchOptionalJson('/api/navigation/scan'),
    ]).then(([poseData, scanData]) => {
        if (poseData?.ok) {
            lidarState.pose = poseData.available ? poseData.pose : null;
        }
        if (poseData?.status) lidarState.status = poseData.status;
        if (scanData?.ok) {
            lidarState.scan = scanData.available ? scanData.scan : null;
            if (scanData.available && scanData.scan) {
                noteScanUpdate(scanData.scan);
            } else {
                lidarState.lastScanKey = null;
                lidarState.lastScanSeenAtMs = 0;
                lidarState.lastScanPulseAtMs = 0;
                lidarState.scanIntervalsMs = [];
            }
        }
        if (scanData?.status) lidarState.status = scanData.status;
        requestLidarRender();
    });
}

setInterval(fetchNavigationStatus, 1000);
setInterval(fetchNavigationMap, 1500);
setInterval(fetchNavigationPoseAndScan, 500);
window.addEventListener('resize', requestLidarRender);
requestLidarRender();

// ===================================================
// 전체화면
// ===================================================
function toggleFullscreen(elementId) {
    const elem = document.getElementById(elementId);
    if (!document.fullscreenElement) {
        if (elem.requestFullscreen) elem.requestFullscreen();
        else if (elem.webkitRequestFullscreen) elem.webkitRequestFullscreen();
        else if (elem.msRequestFullscreen) elem.msRequestFullscreen();
    } else {
        if (document.exitFullscreen) document.exitFullscreen();
    }
}

// ===================================================
// 미니맵 확대 토글 (카메라 화면 크기만큼 확장)
// ===================================================
let minimapExpanded = false;
function toggleMinimapExpand() {
    const minimap = document.getElementById('minimap-overlay');
    const videoWrapper = document.getElementById('video-wrapper');
    const btn = document.getElementById('minimapExpandBtn');

    if (!minimapExpanded) {
        // 카메라 화면 크기 가져오기
        const wRect = videoWrapper.getBoundingClientRect();
        minimap.style.width = wRect.width + 'px';
        minimap.style.height = wRect.height + 'px';
        minimap.style.bottom = '0';
        minimap.style.right = '0';
        minimap.style.borderRadius = '6px';
        minimap.style.zIndex = '50';
        btn.textContent = '⊡';
        btn.title = '미니맵 축소';
        minimap.classList.add('expanded');
        minimapExpanded = true;
        requestLidarRender();
    } else {
        minimap.style.width = '';
        minimap.style.height = '';
        minimap.style.bottom = '';
        minimap.style.right = '';
        minimap.style.zIndex = '';
        btn.textContent = '⛶';
        btn.title = '미니맵 확대';
        minimap.classList.remove('expanded');
        minimapExpanded = false;
        requestLidarRender();
    }
}

window.navigationMapView = {
    canvasToWorld(event) {
        const canvas = document.getElementById('lidar-map-canvas');
        if (!canvas || !lidarState.map) return null;
        const rect = canvas.getBoundingClientRect();
        const scaleX = canvas.width / Math.max(rect.width, 1);
        const scaleY = canvas.height / Math.max(rect.height, 1);
        const layout = getCanvasLayout(canvas, lidarState.map);
        return canvasToWorld(
            (event.clientX - rect.left) * scaleX,
            (event.clientY - rect.top) * scaleY,
            layout,
        );
    },
    snapshot() {
        return {
            map: lidarState.map,
            pose: lidarState.pose,
            expanded: minimapExpanded,
        };
    },
    requestRender: requestLidarRender,
};

// ===================================================
// 알림 지우기
// ===================================================
function clearAlerts() {
    if (confirm("정말 모든 알림 내역을 삭제하시겠습니까?")) {
        document.getElementById('alertBox').innerHTML = `
            <div class="alert-entry alert-info">
                <span class="alert-time">${getCurrentTime()}</span>
                <span class="alert-message">알림 내역이 삭제되었습니다. 대기 중...</span>
            </div>`;
    }
}

// ===================================================
// 알림은 실제 서버/AI 감지 데이터만 표시
// (더미 자동 알림 생성 제거됨)
// ===================================================
// 실제 위험 감지 시 서버에서 push 또는 polling으로 받아올 것
// 예시: 서버에서 /get_alerts 엔드포인트 구현 후 아래처럼 연결
// function fetchAlerts() { ... }
// setInterval(fetchAlerts, 3000);

// ===================================================
// 모달 상태 (실제 데이터만, 더미 없음)
// ===================================================
const modalState = {
    statusModal:  { allRows: [], filtered: [], timer: null, loadState: 'idle', message: '' },
    patrolModal:  { allRows: [], filtered: [], timer: null, loadState: 'idle', message: '' },
    actionsModal: { allRows: [], filtered: [], timer: null, loadState: 'idle', message: '' },
};

const ACTION_TYPE_LABELS = {
    WARNING: '경고',
    MANUAL_MOVING: '수동 주행',
    REPORT: '신고',
    COMMUNICATION: '직접 통신',
    NOTE: '상황 기록',
};

const currentSituationState = {
    frameToken: null,
    previewUrl: null,
    submitting: false,
};

const galleryState = {
    source: 'all',
    items: [],
    selectedIndex: -1,
    loadState: 'idle',
    message: '',
};

let dashboardRecordsCsrfPromise = null;

// ===================================================
// 필터 적용 (초 단위까지 지원, 서버 재조회)
// ===================================================
function modalDateTimeRange(type) {
    const startDate = document.getElementById(`${type}-start-date`)?.value;
    const endDate   = document.getElementById(`${type}-end-date`)?.value;
    const startTime = document.getElementById(`${type}-start-time`)?.value;
    const endTime   = document.getElementById(`${type}-end-time`)?.value;

    const startDT = startDate && startTime ? new Date(`${startDate}T${startTime}`) : null;
    const endDT   = endDate   && endTime   ? new Date(`${endDate}T${endTime}`)     : null;

    if (startDT && endDT && startDT > endDT) {
        return null;
    }
    return {
        startAt: startDate && startTime ? `${startDate}T${startTime}` : '',
        endAt: endDate && endTime ? `${endDate}T${endTime}` : '',
    };
}

async function loadModalRows(type) {
    const range = modalDateTimeRange(type);
    if (!range) {
        alert("종료 일시는 시작 일시보다 빠를 수 없습니다. 다시 확인해 주세요.");
        return;
    }

    const state = modalState[type];
    state.loadState = 'loading';
    state.message = '';
    state.allRows = [];
    state.filtered = [];
    renderTable(type);

    const result = await window.DabomDashboardState?.fetchLogRows(type, range);
    if (!result || document.getElementById('commonModal')?.style.display === 'none') return;
    state.loadState = result.state;
    state.message = result.message || '';
    state.allRows = Array.isArray(result.rows) ? result.rows : [];
    state.filtered = [...state.allRows];
    renderTable(type);
}

async function applyFilter(type) {
    await loadModalRows(type);
}

async function resetFilter(type) {
    const today = todayStr();
    document.getElementById(`${type}-start-date`).value = today;
    document.getElementById(`${type}-end-date`).value   = today;
    document.getElementById(`${type}-start-time`).value = startOfDayTimeStr();
    document.getElementById(`${type}-end-time`).value   = nowTimeStr();
    await loadModalRows(type);
}

// ===================================================
// 테이블 렌더링
// ===================================================
function escapeHtml(value) {
    const node = document.createElement('span');
    node.textContent = value == null ? '' : String(value);
    return node.innerHTML;
}

function formatLogValue(value, suffix = '') {
    if (value === undefined || value === null || value === '') return '-';
    return `${escapeHtml(value)}${suffix}`;
}

function formatBooleanState(value, yesLabel, noLabel) {
    if (value === true || value === 1 || value === '1') return yesLabel;
    if (value === false || value === 0 || value === '0') return noLabel;
    return '-';
}

function recordImageCell(source, id, hasImage) {
    if (!hasImage || id === undefined || id === null) return '<span class="muted">-</span>';
    const endpoint = source === 'event'
        ? `/api/media/events/${encodeURIComponent(id)}`
        : `/api/media/actions/${encodeURIComponent(id)}`;
    if (source === 'event') {
        return `<button type="button" class="record-thumbnail-button" data-record-id="${escapeHtml(id)}" onclick="openPatrolGalleryDetail(this.dataset.recordId)" aria-label="이 순찰 기록의 갤러리 상세 열기">
            <img class="record-thumbnail" src="${endpoint}" alt="순찰 기록 이미지" loading="lazy">
        </button>`;
    }
    return `<img class="record-thumbnail" src="${endpoint}" alt="기록 이미지" loading="lazy">`;
}

function renderTable(type) {
    const tbody = document.getElementById(`${type}-tbody`);
    const countEl = document.getElementById(`${type}-count`);
    if (!tbody) return;

    const rows = modalState[type].filtered;
    if (countEl) countEl.innerHTML = `총 <span>${rows.length}</span> 건`;

    const loadState = modalState[type].loadState;
    if (loadState === 'loading') {
        tbody.innerHTML = '<tr><td colspan="20"><div class="table-empty is-loading">서버 데이터를 불러오는 중입니다.</div></td></tr>';
        return;
    }
    if (loadState === 'error') {
        const message = modalState[type].message || '서버 데이터를 불러오지 못했습니다.';
        tbody.innerHTML = `<tr><td colspan="20"><div class="table-empty is-error">${escapeHtml(message)}</div></td></tr>`;
        return;
    }
    if (loadState === 'unavailable') {
        const message = modalState[type].message || '연결된 조회 API가 없습니다.';
        tbody.innerHTML = `<tr><td colspan="20"><div class="table-empty is-unavailable">${escapeHtml(message)}</div></td></tr>`;
        return;
    }

    if (rows.length === 0) {
        tbody.innerHTML = '<tr><td colspan="20"><div class="table-empty">조회된 데이터가 없습니다.</div></td></tr>';
        return;
    }

    tbody.innerHTML = rows.slice().reverse().map((row, idx) => {
        const realIdx = modalState[type].filtered.length - 1 - idx;
        if (type === 'statusModal') {
            const cpuClass  = row.cpu_usage > 80 ? 'danger' : row.cpu_usage > 60 ? 'warn' : 'accent';
            const tempClass = row.cpu_temperature > 80 ? 'danger' : row.cpu_temperature > 65 ? 'warn' : '';
            const pingClass = row.ping > 150 ? 'danger' : row.ping > 100 ? 'warn' : '';
            return `<tr>
                <td class="muted">${escapeHtml(row.date)}</td>
                <td class="muted">${escapeHtml(row.time)}</td>
                <td class="${cpuClass}">${formatLogValue(row.cpu_usage, '%')}</td>
                <td class="${tempClass}">${formatLogValue(row.cpu_temperature, '°C')}</td>
                <td class="${row.ram_usage>80?'warn':''}">${formatLogValue(row.ram_usage, '%')}</td>
                <td class="${pingClass}">${formatLogValue(row.ping, 'ms')}</td>
                <td>${formatBooleanState(row.is_autonomous, '자동', '수동')}</td>
                <td>${formatLogValue(row.speed)}</td>
                <td class="muted">${formatLogValue(row.gps_lat)} / ${formatLogValue(row.gps_lng)} / ${formatLogValue(row.gps_alt)}</td>
                <td class="muted">${formatLogValue(row.lidar_x)} / ${formatLogValue(row.lidar_y)}</td>
            </tr>`;
        } else if (type === 'patrolModal') {
            const confidence = Number.isFinite(Number(row.confidence))
                ? `${(Number(row.confidence) * 100).toFixed(1)}%`
                : '-';
            return `<tr>
                <td class="muted">${escapeHtml(row.date)}</td>
                <td class="muted">${escapeHtml(row.time)}</td>
                <td>${escapeHtml(row.event_source)}</td>
                <td><span class="status-badge status-patrol">${escapeHtml(row.event_type)}</span></td>
                <td>${confidence}</td>
                <td class="muted">${formatLogValue(row.lidar_x)} / ${formatLogValue(row.lidar_y)}</td>
                <td class="muted">${formatLogValue(row.gps_lat)} / ${formatLogValue(row.gps_lng)} / ${formatLogValue(row.gps_alt)}</td>
                <td>${formatBooleanState(row.is_resolved, '완료', '미조치')}</td>
                <td>${formatBooleanState(row.is_reported, '신고', '미신고')}</td>
                <td>${formatBooleanState(row.is_alerted, '경고', '미경고')}</td>
                <td>
                    <span class="false-alarm-state ${row.is_false_alarm ? 'is-active' : ''}">${row.is_false_alarm ? '오탐' : '정상'}</span>
                    <button type="button" class="false-alarm-btn" onclick="setEventFalseAlarm(${Number(row.event_id)}, ${!row.is_false_alarm}, this)" ${Number.isFinite(Number(row.event_id)) ? '' : 'disabled'}>
                        ${row.is_false_alarm ? '오탐 취소' : '오탐 처리'}
                    </button>
                </td>
                <td>${recordImageCell('event', row.event_id, row.has_image)}</td>
            </tr>`;
        } else {
            return `<tr>
                <td class="muted">${escapeHtml(row.date)}</td>
                <td class="muted">${escapeHtml(row.time)}</td>
                <td>${escapeHtml(row.administrator_name)}</td>
                <td><span class="status-badge status-normal">${escapeHtml(ACTION_TYPE_LABELS[row.action_type] || row.action_type)}</span></td>
                <td>${row.event_id == null ? '-' : escapeHtml(row.event_id)}</td>
                <td class="record-description">${escapeHtml(row.description_content)}</td>
                <td>${recordImageCell('action', row.action_id, row.has_image)}</td>
            </tr>`;
        }
    }).join('');
}

// ===================================================
// 모달 HTML 생성 (시간 필드 초 단위까지 step="1")
// ===================================================
function buildModalHTML(type) {
    const today = todayStr();
    const now   = nowTimeStr();

    const filterBar = `
    <div class="modal-filter-bar">
        <label>시작</label>
        <input type="date" id="${type}-start-date" value="${today}">
        <input type="time" id="${type}-start-time" value="00:00:00" step="1">
        <span class="filter-sep">~</span>
        <label>종료</label>
        <input type="date" id="${type}-end-date" value="${today}">
        <input type="time" id="${type}-end-time" value="${now}" step="1">
        <button class="filter-btn" onclick="applyFilter('${type}')">조회</button>
        <button class="filter-btn secondary" onclick="resetFilter('${type}')">초기화</button>
        <span class="filter-count" id="${type}-count">총 <span>0</span> 건</span>
    </div>`;

    let tableHead = '';
    if (type === 'statusModal') {
        tableHead = `<tr>
            <th>날짜</th><th>시각</th><th>CPU Usage</th><th>CPU Temp</th>
            <th>RAM Usage</th><th>Ping</th><th>주행</th><th>속도</th>
            <th>GPS (위도/경도/고도)</th><th>LiDAR (X/Y)</th>
        </tr>`;
    } else if (type === 'patrolModal') {
        tableHead = `<tr>
            <th>날짜</th><th>시각</th><th>출처</th><th>유형</th><th>신뢰도</th>
            <th>LiDAR (X/Y)</th><th>GPS (위도/경도/고도)</th>
            <th>조치</th><th>신고</th><th>경고</th><th>오탐</th><th>이미지</th>
        </tr>`;
    } else {
        tableHead = `<tr>
            <th>날짜</th><th>시각</th><th>관리자</th><th>조치 유형</th>
            <th>관련 이벤트</th><th>내용</th><th>이미지</th>
        </tr>`;
    }

    return `
    ${filterBar}
    <div class="modal-table-wrapper">
        <table class="data-table">
            <thead>${tableHead}</thead>
            <tbody id="${type}-tbody"></tbody>
        </table>
    </div>`;
}

// ===================================================
// 모달 열기/닫기
// ===================================================
async function openModal(type) {
    const modal  = document.getElementById('commonModal');
    const title  = document.getElementById('modalTitle');
    const body   = document.getElementById('modalBody');

    const titles = {
        statusModal:   '기기 상태 로그',
        patrolModal:   '순찰 기록',
        actionsModal:  '관리자 조치 기록',
        galleryModal:  '갤러리'
    };

    title.innerText = titles[type] || type;

    if (type === 'galleryModal') {
        modal.style.display = 'flex';
        await openGalleryModal();
        return;
    }

    modalState[type].filtered = [...modalState[type].allRows];
    body.innerHTML = buildModalHTML(type);
    modal.style.display = 'flex';
    renderTable(type);

    if (type === 'statusModal' || type === 'patrolModal' || type === 'actionsModal') {
        await loadModalRows(type);
    }
}

function closeModal() {
    document.getElementById('commonModal').style.display = 'none';
    releaseCurrentSituationPreview();
    galleryState.selectedIndex = -1;
    Object.values(modalState).forEach(st => {
        if (st.timer) { clearInterval(st.timer); st.timer = null; }
    });
}

window.onclick = function(event) {
    const modal = document.getElementById('commonModal');
    if (event.target == modal) closeModal();
};

// ===================================================
// 현재 상황 기록
// ===================================================
function dashboardRecordsCsrfToken() {
    if (!dashboardRecordsCsrfPromise) {
        dashboardRecordsCsrfPromise = fetch('/api/auth/csrf', { credentials: 'same-origin' })
            .then(async response => {
                const data = await response.json().catch(() => ({}));
                if (!response.ok || !data.csrf_token) throw new Error('보안 토큰을 준비하지 못했습니다.');
                return data.csrf_token;
            })
            .catch(error => {
                dashboardRecordsCsrfPromise = null;
                throw error;
            });
    }
    return dashboardRecordsCsrfPromise;
}

async function setEventFalseAlarm(eventId, isFalseAlarm, button) {
    if (!Number.isFinite(Number(eventId))) return;
    const previousText = button?.textContent;
    if (button) {
        button.disabled = true;
        button.textContent = '처리 중...';
    }
    try {
        const csrfToken = await dashboardRecordsCsrfToken();
        const response = await fetch(`/api/logs/events/${encodeURIComponent(eventId)}/false-alarm`, {
            method: 'PATCH',
            credentials: 'same-origin',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRF-Token': csrfToken,
            },
            body: JSON.stringify({ is_false_alarm: Boolean(isFalseAlarm) }),
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.detail || data.error || `오탐 상태 변경 실패 (HTTP ${response.status})`);

        const row = modalState.patrolModal.allRows.find(item => String(item.event_id) === String(eventId));
        if (row) row.is_false_alarm = Boolean(isFalseAlarm);
        modalState.patrolModal.filtered = [...modalState.patrolModal.allRows];
        renderTable('patrolModal');
    } catch (error) {
        alert(error.message || '오탐 상태를 변경하지 못했습니다.');
        if (button) {
            button.disabled = false;
            button.textContent = previousText;
        }
    }
}

function releaseCurrentSituationPreview() {
    if (currentSituationState.previewUrl) URL.revokeObjectURL(currentSituationState.previewUrl);
    currentSituationState.previewUrl = null;
    currentSituationState.frameToken = null;
    currentSituationState.submitting = false;
}

async function openCurrentSituationModal() {
    releaseCurrentSituationPreview();
    const modal = document.getElementById('commonModal');
    document.getElementById('modalTitle').innerText = '현재 상황 기록';
    document.getElementById('modalBody').innerHTML = `
        <form class="current-situation-form" onsubmit="submitCurrentSituation(event)">
            <label class="record-field-label">현재 카메라 이미지</label>
            <div class="privacy-preview-frame">
                <img id="currentSituationPreview" alt="개인정보 보호 처리된 현재 카메라 미리보기" hidden>
                <div id="currentSituationPreviewState" class="preview-state is-loading">개인정보 보호 미리보기를 불러오는 중입니다.</div>
            </div>
            <label class="record-field-label" for="currentSituationDescription">상황 내용</label>
            <textarea id="currentSituationDescription" rows="5" placeholder="현재 상황을 입력하세요. 예: 1층 출입구 주변 확인 필요"></textarea>
            <label class="record-image-option">
                <input id="currentSituationIncludeImage" type="checkbox" disabled>
                <span>위 이미지를 함께 저장</span>
            </label>
            <p class="record-requirement">※ 텍스트 또는 이미지 중 최소 하나는 기록해야 합니다.</p>
            <div id="currentSituationError" class="record-error" role="alert"></div>
            <div class="record-form-actions">
                <button type="button" class="filter-btn secondary" onclick="closeModal()">취소</button>
                <button id="currentSituationSubmit" type="submit" class="filter-btn">기록</button>
            </div>
        </form>`;
    modal.style.display = 'flex';

    const stateElement = document.getElementById('currentSituationPreviewState');
    const checkbox = document.getElementById('currentSituationIncludeImage');
    try {
        const csrfToken = await dashboardRecordsCsrfToken();
        const response = await fetch('/api/logs/current-situation/preview', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'X-CSRF-Token': csrfToken },
        });
        if (response.status === 503) throw new Error('PREVIEW_UNAVAILABLE');
        if (!response.ok || !response.headers.get('Content-Type')?.includes('image/jpeg')) {
            throw new Error('PREVIEW_FAILED');
        }
        const frameToken = response.headers.get('X-Frame-Token');
        if (!frameToken) throw new Error('PREVIEW_FAILED');
        const blob = await response.blob();
        if (modal.style.display === 'none') return;
        currentSituationState.frameToken = frameToken;
        currentSituationState.previewUrl = URL.createObjectURL(blob);
        const preview = document.getElementById('currentSituationPreview');
        preview.src = currentSituationState.previewUrl;
        preview.hidden = false;
        stateElement.hidden = true;
        checkbox.disabled = false;
        checkbox.checked = false;
    } catch (error) {
        stateElement.className = 'preview-state is-unavailable';
        stateElement.textContent = error.message === 'PREVIEW_UNAVAILABLE'
            ? '현재 카메라 이미지를 사용할 수 없습니다. 텍스트 기록은 계속할 수 있습니다.'
            : '미리보기를 불러오지 못했습니다. 텍스트 기록은 계속할 수 있습니다.';
        checkbox.checked = false;
        checkbox.disabled = true;
    }
}

async function submitCurrentSituation(event) {
    event.preventDefault();
    if (currentSituationState.submitting) return;
    const description = document.getElementById('currentSituationDescription').value.trim();
    const includeImage = document.getElementById('currentSituationIncludeImage').checked;
    const errorElement = document.getElementById('currentSituationError');
    if (!description && !includeImage) {
        errorElement.textContent = '텍스트 또는 이미지 중 최소 하나를 기록해 주세요.';
        return;
    }
    if (includeImage && !currentSituationState.frameToken) {
        errorElement.textContent = '저장할 이미지 토큰이 유효하지 않습니다. 미리보기를 다시 열어 주세요.';
        return;
    }

    currentSituationState.submitting = true;
    errorElement.textContent = '';
    const submitButton = document.getElementById('currentSituationSubmit');
    submitButton.disabled = true;
    submitButton.textContent = '기록 중...';
    try {
        const csrfToken = await dashboardRecordsCsrfToken();
        const response = await fetch('/api/logs/current-situation', {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRF-Token': csrfToken,
            },
            body: JSON.stringify({
                description_content: description,
                include_image: includeImage,
                frame_token: includeImage ? currentSituationState.frameToken : null,
            }),
        });
        const data = await response.json().catch(() => ({}));
        if (response.status !== 201) throw new Error(data.detail || data.error || `기록 실패 (HTTP ${response.status})`);
        closeModal();
        alert('현재 상황이 기록되었습니다.');
    } catch (error) {
        errorElement.textContent = error.message || '현재 상황을 기록하지 못했습니다.';
        submitButton.disabled = false;
        submitButton.textContent = '기록';
        currentSituationState.submitting = false;
    }
}

// ===================================================
// 갤러리
// ===================================================
function extractRecordRows(payload) {
    if (Array.isArray(payload)) return payload;
    for (const key of ['items', 'rows', 'records', 'data']) {
        if (Array.isArray(payload?.[key])) return payload[key];
    }
    return [];
}

function galleryItemSource(item) {
    if (item.source === 'event' || item.source === 'action') return item.source;
    if (item.event_id != null) return 'event';
    return 'action';
}

function galleryItemId(item) {
    return galleryItemSource(item) === 'event' ? item.event_id ?? item.id : item.action_id ?? item.id;
}

function galleryImageUrl(item) {
    const source = galleryItemSource(item);
    const id = galleryItemId(item);
    if (id === undefined || id === null) return '';
    return source === 'event'
        ? `/api/media/events/${encodeURIComponent(id)}`
        : `/api/media/actions/${encodeURIComponent(id)}`;
}

function galleryItemTimestamp(item) {
    return item.detected_at || item.created_at || item.timestamp || '-';
}

function gallerySourceLabel(item) {
    return galleryItemSource(item) === 'event' ? 'AI 자동 감지' : '수동 기록';
}

function renderGallery() {
    const grid = document.getElementById('galleryGrid');
    if (!grid) return;
    if (galleryState.loadState === 'loading') {
        grid.innerHTML = '<div class="gallery-empty is-loading">갤러리를 불러오는 중입니다.</div>';
        return;
    }
    if (galleryState.loadState !== 'ready') {
        grid.innerHTML = `<div class="gallery-empty is-error">${escapeHtml(galleryState.message || '갤러리를 불러오지 못했습니다.')}</div>`;
        return;
    }
    if (!galleryState.items.length) {
        grid.innerHTML = '<div class="gallery-empty">저장된 이미지가 없습니다.</div>';
        return;
    }
    grid.innerHTML = galleryState.items.map((item, index) => {
        const source = galleryItemSource(item);
        const type = source === 'event' ? item.event_type : ACTION_TYPE_LABELS[item.action_type] || item.action_type;
        return `<button type="button" class="gallery-card" onclick="openGalleryDetail(${index})">
            <img src="${galleryImageUrl(item)}" alt="${escapeHtml(gallerySourceLabel(item))} 이미지" loading="lazy">
            <span class="gallery-card-source source-${source}">${escapeHtml(gallerySourceLabel(item))}</span>
            <strong>${escapeHtml(type || '기록')}</strong>
            <time>${escapeHtml(galleryItemTimestamp(item))}</time>
        </button>`;
    }).join('');
}

async function loadGallery(source) {
    galleryState.source = source;
    galleryState.loadState = 'loading';
    galleryState.message = '';
    galleryState.selectedIndex = -1;
    document.querySelectorAll('.gallery-filter-btn').forEach(button => {
        button.classList.toggle('active', button.dataset.source === source);
    });
    document.getElementById('galleryDetail')?.setAttribute('hidden', '');
    renderGallery();
    try {
        const response = await fetch(`/api/gallery?source=${encodeURIComponent(source)}`, {
            credentials: 'same-origin',
            cache: 'no-store',
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.detail || data.error || `HTTP ${response.status}`);
        galleryState.items = extractRecordRows(data);
        galleryState.loadState = 'ready';
    } catch (error) {
        galleryState.items = [];
        galleryState.loadState = 'error';
        galleryState.message = error.message || '갤러리를 불러오지 못했습니다.';
    }
    renderGallery();
}

async function openGalleryModal(initialSource = 'all') {
    document.getElementById('modalBody').innerHTML = `
        <div class="gallery-toolbar" role="group" aria-label="갤러리 분류">
            <button type="button" class="gallery-filter-btn" data-source="all" onclick="loadGallery('all')">전체</button>
            <button type="button" class="gallery-filter-btn" data-source="event" onclick="loadGallery('event')">AI 자동 감지</button>
            <button type="button" class="gallery-filter-btn" data-source="action" onclick="loadGallery('action')">수동 기록</button>
        </div>
        <div id="galleryGrid" class="gallery-grid"></div>
        <section id="galleryDetail" class="gallery-detail" hidden aria-label="갤러리 상세"></section>`;
    await loadGallery(initialSource);
}

async function openPatrolGalleryDetail(eventId) {
    const modal = document.getElementById('commonModal');
    document.getElementById('modalTitle').innerText = '갤러리';
    modal.style.display = 'flex';
    await openGalleryModal('event');
    if (galleryState.loadState !== 'ready') return;
    const index = galleryState.items.findIndex(item => String(item.event_id ?? item.id) === String(eventId));
    if (index >= 0) openGalleryDetail(index);
}

function galleryMetadata(item) {
    const source = galleryItemSource(item);
    if (source === 'event') {
        return [
            ['출처', item.event_source],
            ['유형', item.event_type],
            ['신뢰도', item.confidence == null ? '-' : `${(Number(item.confidence) * 100).toFixed(1)}%`],
            ['LiDAR X/Y', `${item.lidar_x ?? '-'} / ${item.lidar_y ?? '-'}`],
            ['GPS', `${item.gps_lat ?? '-'} / ${item.gps_lng ?? '-'} / ${item.gps_alt ?? '-'}`],
            ['조치/신고/경고', `${formatBooleanState(item.is_resolved, '완료', '미조치')} / ${formatBooleanState(item.is_reported, '신고', '미신고')} / ${formatBooleanState(item.is_alerted, '경고', '미경고')}`],
        ];
    }
    return [
        ['관리자', item.administrator_name || item.user_name || item.name || item.user_id],
        ['조치 유형', ACTION_TYPE_LABELS[item.action_type] || item.action_type],
        ['관련 이벤트', item.event_id ?? '-'],
        ['내용', item.description_content || '-'],
    ];
}

function openGalleryDetail(index) {
    if (index < 0 || index >= galleryState.items.length) return;
    galleryState.selectedIndex = index;
    const item = galleryState.items[index];
    const detail = document.getElementById('galleryDetail');
    detail.hidden = false;
    detail.innerHTML = `
        <div class="gallery-detail-header">
            <strong>${escapeHtml(gallerySourceLabel(item))} 상세</strong>
            <button type="button" class="gallery-detail-close" onclick="closeGalleryDetail()" aria-label="상세 닫기">&times;</button>
        </div>
        <img class="gallery-detail-image" src="${galleryImageUrl(item)}" alt="기록 상세 이미지">
        <dl class="gallery-metadata">
            <div><dt>기록 시각</dt><dd>${escapeHtml(galleryItemTimestamp(item))}</dd></div>
            ${galleryMetadata(item).map(([label, value]) => `<div><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value ?? '-')}</dd></div>`).join('')}
        </dl>
        <div class="gallery-detail-actions">
            <button type="button" onclick="changeGalleryDetail(-1)" ${index === 0 ? 'disabled' : ''}>← 이전</button>
            <button type="button" class="gallery-delete-btn" onclick="deleteGalleryItem(${index}, this)">이미지 삭제</button>
            <button type="button" onclick="changeGalleryDetail(1)" ${index === galleryState.items.length - 1 ? 'disabled' : ''}>다음 →</button>
        </div>`;
    detail.scrollIntoView({ block: 'nearest' });
}

async function deleteGalleryItem(index, button) {
    if (index < 0 || index >= galleryState.items.length) return;
    const item = galleryState.items[index];
    const source = galleryItemSource(item);
    const recordId = galleryItemId(item);
    if (recordId === undefined || recordId === null) {
        alert('삭제할 기록을 확인할 수 없습니다.');
        return;
    }
    if (!confirm('이 이미지를 갤러리에서 삭제하시겠습니까?')) return;

    const previousText = button?.textContent;
    if (button) {
        button.disabled = true;
        button.textContent = '삭제 중...';
    }
    try {
        const csrfToken = await dashboardRecordsCsrfToken();
        const response = await fetch(`/api/gallery/${source}/${encodeURIComponent(recordId)}`, {
            method: 'DELETE',
            credentials: 'same-origin',
            headers: { 'X-CSRF-Token': csrfToken },
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.detail || data.error || `이미지 삭제 실패 (HTTP ${response.status})`);

        const removedIndex = galleryState.items.findIndex(candidate =>
            galleryItemSource(candidate) === source && String(galleryItemId(candidate)) === String(recordId));
        if (removedIndex < 0) return;
        galleryState.items.splice(removedIndex, 1);
        renderGallery();
        if (!galleryState.items.length) {
            closeGalleryDetail();
            return;
        }
        openGalleryDetail(Math.min(removedIndex, galleryState.items.length - 1));
    } catch (error) {
        alert(error.message || '이미지를 삭제하지 못했습니다.');
        if (button) {
            button.disabled = false;
            button.textContent = previousText;
        }
    }
}

function closeGalleryDetail() {
    galleryState.selectedIndex = -1;
    document.getElementById('galleryDetail')?.setAttribute('hidden', '');
}

function changeGalleryDetail(offset) {
    openGalleryDetail(galleryState.selectedIndex + offset);
}

document.addEventListener('keydown', event => {
    if (galleryState.selectedIndex < 0 || document.getElementById('commonModal')?.style.display === 'none') return;
    if (event.key === 'ArrowLeft') changeGalleryDetail(-1);
    if (event.key === 'ArrowRight') changeGalleryDetail(1);
});

// ===================================================
// 텔레그램 신고
// ===================================================
async function reportDanger(isAuto = false) {
    let confirmReport = true;
    if (!isAuto) confirmReport = confirm("신고? - Telegram");

    if (confirmReport) {
        fetch('/api/auth/csrf', { credentials: 'same-origin' })
            .then(r => r.json())
            .then(csrf => fetch('/send_telegram', {
                method: 'POST',
                credentials: 'same-origin',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': csrf.csrf_token,
                },
                body: JSON.stringify({}),
            }))
            .then(r => r.json())
            .then(data => {
                if (data.status === 'success') {
                    if (!isAuto) alert("🚨 긴급 알림이 전송되었습니다.");
                    console.log("텔레그램 알림 전송 완료");
                } else {
                    if (!isAuto) alert("알림 전송에 실패했습니다.");
                }
            })
            .catch(err => {
                console.error("Error:", err);
                if (!isAuto) alert("서버 통신 오류로 알림을 보내지 못했습니다.");
            });
    }
}

function warnTrespasser() {
    if (window.navigationControl?.warning) {
        window.navigationControl.warning();
        return;
    }
    sendRobotCommand({ type: 'speak', text: '경고합니다. 즉시 물러나십시오.' })
        .then(ok => {
            if (ok) alert("⚠️ 경고 방송 명령을 전송했습니다.");
            else alert("경고 방송 명령 전송에 실패했습니다.");
        });
}

// ===================================================
// 수동/자동 순찰 모드 및 실제 주행 제어
// ===================================================
let currentPatrolMode = null;
let modeChangePending = false;
let currentRobotConnected = null;


function applyServerPatrolMode(mode) {
    const normalized = String(mode || '').trim().toLowerCase();
    currentPatrolMode = (
        currentRobotConnected !== false
        && (normalized === 'auto' || normalized === 'manual')
    ) ? normalized : null;
    setPatrolModeUi(currentPatrolMode);
}


function setDashboardRobotConnection(connected) {
    currentRobotConnected = typeof connected === 'boolean' ? connected : null;
    if (connected === false) {
        stopAllLocalInputs(false);
        applyServerPatrolMode(null);
    }
}


window.applyServerPatrolMode = applyServerPatrolMode;
window.setDashboardRobotConnection = setDashboardRobotConnection;

const ROBOT_ID = 'pi-01';
const MANUAL_SPEED = 0.35;
const COMMAND_REPEAT_MS = 120;

const DRIVE_KEYS = [
    'ArrowUp',
    'ArrowDown',
    'ArrowLeft',
    'ArrowRight',
    'w',
    'a',
    's',
    'd',
];

let pointerMoveInterval = null;
let activePointerButton = null;

const pressedKeys = new Set();
let keyMoveInterval = null;
let robotCommandCsrfPromise = null;


function directionToCommand(direction) {
    const map = {
        '↑': 'rotate_left',
        '↓': 'rotate_right',
        '←': 'backward',
        '→': 'forward',
        '↖': 'backward_left',
        '↗': 'forward_left',
        '↙': 'forward_right',
        '↘': 'backward_right',
    };

    return map[direction] || direction;
}


function robotCommandCsrfToken() {
    if (!robotCommandCsrfPromise) {
        robotCommandCsrfPromise = fetch(
            '/api/auth/csrf',
            { credentials: 'same-origin' },
        )
            .then(async response => {
                const data = await response.json().catch(() => ({}));
                if (!response.ok || !data.csrf_token) {
                    throw new Error('robot command CSRF token unavailable');
                }
                return data.csrf_token;
            })
            .catch(error => {
                robotCommandCsrfPromise = null;
                throw error;
            });
    }
    return robotCommandCsrfPromise;
}


async function sendRobotCommand(
    payload,
    keepalive = false,
) {
    try {
        const csrfToken = await robotCommandCsrfToken();
        const response = await fetch(
            `/api/robots/${ROBOT_ID}/command`,
            {
                method: 'POST',
                credentials: 'same-origin',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': csrfToken,
                },
                body: JSON.stringify(payload),
                keepalive,
            },
        );
        const data = await response.json().catch(() => ({}));
        const ok = response.ok && data.ok;

        if (!ok) {
            console.warn('로봇 명령 전송 실패:', data);
        }

        return ok;
    } catch (error) {
        console.error('로봇 명령 통신 오류:', error);
        return false;
    }
}


function setPatrolModeUi(mode) {
    const switchUi = document.getElementById(
        'mode-switch-ui',
    );

    const dPadArea = document.getElementById(
        'd-pad-area',
    );

    const labelAuto = document.getElementById(
        'label-auto',
    );

    const labelManual = document.getElementById(
        'label-manual',
    );

    switchUi.classList.toggle('unknown', mode !== 'auto' && mode !== 'manual');

    if (mode === 'auto') {
        switchUi.classList.remove('manual');
        dPadArea.classList.add('disabled');

        labelAuto.classList.add('active');
        labelAuto.classList.remove('inactive');

        labelManual.classList.add('inactive');
        labelManual.classList.remove('active');

    } else if (mode === 'manual') {
        switchUi.classList.add('manual');
        dPadArea.classList.remove('disabled');

        labelAuto.classList.add('inactive');
        labelAuto.classList.remove('active');

        labelManual.classList.add('active');
        labelManual.classList.remove('inactive');
    } else {
        switchUi.classList.remove('manual');
        dPadArea.classList.add('disabled');

        labelAuto.classList.add('inactive');
        labelAuto.classList.remove('active');

        labelManual.classList.add('inactive');
        labelManual.classList.remove('active');
    }
}


async function togglePatrolMode() {
    if (modeChangePending) {
        return;
    }

    if (
        currentPatrolMode !== 'auto'
        && currentPatrolMode !== 'manual'
    ) {
        alert(
            '로봇의 현재 모드를 아직 '
            + '확인하지 못했습니다.',
        );

        return;
    }

    const targetMode = (
        currentPatrolMode === 'auto'
            ? 'manual'
            : 'auto'
    );

    const modeName = (
        targetMode === 'auto'
            ? '자동'
            : '수동'
    );

    if (
        !confirm(
            `${modeName} 순찰 모드로 변경하시겠습니까?`,
        )
    ) {
        return;
    }

    stopAllLocalInputs(false);
    modeChangePending = true;

    try {
        const ok = await sendRobotCommand({
            type: 'mode',
            mode: targetMode,
        });

        if (!ok) {
            alert(
                '로봇이 연결되지 않아 '
                + '모드를 변경하지 못했습니다.',
            );

            return;
        }

        /*
         * 여기서 currentPatrolMode와 UI를
         * 직접 변경하지 않는다.
         *
         * Pi가 실제 모드를 서버에 보고하면
         * fetchRobotStatus()가 화면에 반영한다.
         */
        setTimeout(
            fetchRobotStatus,
            300,
        );
    } finally {
        modeChangePending = false;
    }
}


window.moveRobot = function moveRobot(direction) {
    if (currentPatrolMode !== 'manual') {
        console.warn(
            '수동 순찰 모드에서만 '
            + '로봇을 조작할 수 있습니다.',
        );

        return Promise.resolve(false);
    }

    return sendRobotCommand({
        type: 'move',
        direction: directionToCommand(direction),
        speed: MANUAL_SPEED,
    });
};


function stopRobot(
    reason = 'manual_stop',
    keepalive = false,
) {
    return sendRobotCommand(
        {
            type: 'stop',
            reason,
        },
        keepalive,
    );
}


function emergencyStopRobot(
    reason = 'dashboard_emergency_stop',
    keepalive = false,
) {
    stopAllLocalInputs(false);

    if (window.navigationControl?.emergencyStop) {
        return window.navigationControl.emergencyStop(reason, keepalive);
    }

    return sendRobotCommand(
        {
            type: 'emergency_stop',
            reason,
        },
        keepalive,
    );
}


function startButtonMove(
    direction,
    event,
) {
    if (
        event.isPrimary === false
        || event.button !== 0
    ) {
        return;
    }

    if (currentPatrolMode !== 'manual') {
        return;
    }

    event.preventDefault();

    stopPointerMove(false);

    activePointerButton = event.currentTarget;
    activePointerButton.classList.add(
        'active-key',
    );

    if (
        activePointerButton.setPointerCapture
        && event.pointerId !== undefined
    ) {
        try {
            activePointerButton.setPointerCapture(
                event.pointerId,
            );
        } catch (_) {
            // Pointer capture 미지원 브라우저
        }
    }

    moveRobot(direction);

    pointerMoveInterval = setInterval(
        () => moveRobot(direction),
        COMMAND_REPEAT_MS,
    );
}


document.querySelectorAll(
    '.d-pad .d-btn[data-drive-direction]',
).forEach(button => {
    button.addEventListener(
        'pointerdown',
        event => startButtonMove(
            button.dataset.driveDirection,
            event,
        ),
    );

    button.addEventListener(
        'lostpointercapture',
        () => stopPointerMove(
            true,
            'button_release',
        ),
    );
});


function stopPointerMove(
    sendStop = true,
    reason = 'button_release',
) {
    const wasActive = (
        pointerMoveInterval !== null
        || activePointerButton !== null
    );

    if (pointerMoveInterval !== null) {
        clearInterval(pointerMoveInterval);
        pointerMoveInterval = null;
    }

    if (activePointerButton) {
        activePointerButton.classList.remove(
            'active-key',
        );

        activePointerButton = null;
    }

    if (
        sendStop
        && wasActive
        && currentPatrolMode === 'manual'
    ) {
        stopRobot(reason);
    }
}


function normalizeDriveKey(key) {
    if (
        [
            'ArrowUp',
            'ArrowDown',
            'ArrowLeft',
            'ArrowRight',
        ].includes(key)
    ) {
        return key;
    }

    return String(key).toLowerCase();
}


function getDirectionFromKeys() {
    const up = (
        pressedKeys.has('ArrowUp')
        || pressedKeys.has('w')
    );

    const down = (
        pressedKeys.has('ArrowDown')
        || pressedKeys.has('s')
    );

    const left = (
        pressedKeys.has('ArrowLeft')
        || pressedKeys.has('a')
    );

    const right = (
        pressedKeys.has('ArrowRight')
        || pressedKeys.has('d')
    );

    if (up && left) {
        return { direction: '↖' };
    }

    if (up && right) {
        return { direction: '↗' };
    }

    if (down && left) {
        return { direction: '↙' };
    }

    if (down && right) {
        return { direction: '↘' };
    }

    if (up) {
        return { direction: '↑' };
    }

    if (down) {
        return { direction: '↓' };
    }

    if (left) {
        return { direction: '←' };
    }

    if (right) {
        return { direction: '→' };
    }

    return null;
}


function highlightKeyboardButton(direction) {
    const buttons = document.querySelectorAll(
        '.d-pad .d-btn[data-drive-direction]',
    );

    buttons.forEach(button => {
        button.classList.toggle(
            'active-key',
            button.dataset.driveDirection
                === direction,
        );
    });
}


function sendCurrentKeyDirection() {
    if (currentPatrolMode !== 'manual') {
        return;
    }

    const result = getDirectionFromKeys();

    if (!result) {
        return;
    }

    moveRobot(result.direction);

    highlightKeyboardButton(
        result.direction,
    );
}


function startKeyMove() {
    sendCurrentKeyDirection();

    if (keyMoveInterval !== null) {
        return;
    }

    keyMoveInterval = setInterval(
        sendCurrentKeyDirection,
        COMMAND_REPEAT_MS,
    );
}


function stopKeyMove(
    sendStop = true,
    reason = 'key_release',
) {
    if (keyMoveInterval !== null) {
        clearInterval(keyMoveInterval);
        keyMoveInterval = null;
    }

    pressedKeys.clear();
    highlightKeyboardButton(null);

    if (
        sendStop
        && currentPatrolMode === 'manual'
    ) {
        stopRobot(reason);
    }
}


function stopAllLocalInputs(
    sendStop = true,
    reason = 'input_cancelled',
) {
    stopPointerMove(false);
    stopKeyMove(false);

    if (
        sendStop
        && currentPatrolMode === 'manual'
    ) {
        stopRobot(reason);
    }
}


document.addEventListener(
    'keydown',
    event => {
        const key = normalizeDriveKey(
            event.key,
        );

        if (!DRIVE_KEYS.includes(key)) {
            return;
        }

        event.preventDefault();

        if (currentPatrolMode !== 'manual') {
            return;
        }

        if (pressedKeys.has(key)) {
            return;
        }

        pressedKeys.add(key);
        startKeyMove();
    },
);


document.addEventListener(
    'keyup',
    event => {
        const key = normalizeDriveKey(
            event.key,
        );

        if (!DRIVE_KEYS.includes(key)) {
            return;
        }

        pressedKeys.delete(key);

        if (!getDirectionFromKeys()) {
            stopKeyMove(
                true,
                'key_release',
            );
        } else {
            sendCurrentKeyDirection();
        }
    },
);


document.addEventListener(
    'pointerup',
    () => stopPointerMove(
        true,
        'button_release',
    ),
);


document.addEventListener(
    'pointercancel',
    () => stopPointerMove(
        true,
        'pointer_cancel',
    ),
);


window.addEventListener(
    'blur',
    () => {
        if (currentPatrolMode === 'manual') {
            emergencyStopRobot(
                'window_blur',
            );
        }
    },
);


document.addEventListener(
    'visibilitychange',
    () => {
        if (
            document.hidden
            && currentPatrolMode === 'manual'
        ) {
            emergencyStopRobot(
                'page_hidden',
                true,
            );
        }
    },
);

// ===================================================
// 사이드바 메뉴 (요구사항 7)
// ===================================================
function openSidebar() {
    document.getElementById('sidebar').classList.add('open');
    document.getElementById('sidebarOverlay').classList.add('open');
}
function closeSidebar() {
    document.getElementById('sidebar').classList.remove('open');
    document.getElementById('sidebarOverlay').classList.remove('open');
}

// ===================================================
// 다크 모드 (요구사항 7)
// ===================================================
let darkMode = false;
function toggleDarkMode() {
    darkMode = !darkMode;
    document.body.classList.toggle('dark-mode', darkMode);
    document.getElementById('darkToggle').classList.toggle('active', darkMode);
    localStorage.setItem('darkMode', darkMode ? '1' : '0');
}

// 저장된 다크모드 설정 복원
window.addEventListener('DOMContentLoaded', () => {
    initializeDashboardComponentFoundation();

    const saved = localStorage.getItem('darkMode');
    if (saved === '1') toggleDarkMode();

    // Pi가 보고한 실제 모드로 초기 UI 동기화
    fetchRobotStatus();
});

function initializeDashboardComponentFoundation() {
    const components = window.DabomDashboardComponents;
    if (!components) return;

    components.mounts = components.mounts || {};
    components.mounts.recordsToolbar = document.getElementById('records-toolbar-mount');
    components.mounts.dashboardModeControls = document.getElementById('dashboard-mode-controls-mount');
    components.mounts.dpadCenterAction = document.getElementById('dpad-center-action-mount');
    components.mounts.currentSituation = document.getElementById('current-situation-mount');

    components.modal?.mount({
        root: '#commonModal',
        title: '#modalTitle',
        body: '#modalBody',
    });
    components.records?.mount(components.mounts.recordsToolbar, {
        open: openModal,
        close: closeModal,
    });
    components.controls?.mountDriveMode(components.mounts.dashboardModeControls);
    components.controls?.mountNavigationMode(document.getElementById('navigation-control-panel'));
    components.gallery?.mountImageDetail({
        open: openGalleryDetail,
        close: closeGalleryDetail,
        change: changeGalleryDetail,
    });
    components.currentSituation?.mount(components.mounts.currentSituation, {
        open: openCurrentSituationModal,
        close: closeModal,
    });
}

// ===================================================
// Session logout
// ===================================================
async function logout() {
    const button = document.getElementById('logoutBtn');
    if (button) button.disabled = true;
    try {
        const csrfResponse = await fetch('/api/auth/csrf', { credentials: 'same-origin' });
        const csrfData = await csrfResponse.json();
        if (!csrfResponse.ok || !csrfData.csrf_token) {
            throw new Error('\ubcf4\uc548 \ud1a0\ud070\uc744 \uc900\ube44\ud558\uc9c0 \ubabb\ud588\uc2b5\ub2c8\ub2e4.');
        }
        const response = await fetch('/api/auth/logout', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'X-CSRF-Token': csrfData.csrf_token },
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok || !data.ok) {
            throw new Error(data.detail || '\ub85c\uadf8\uc544\uc6c3\uc5d0 \uc2e4\ud328\ud588\uc2b5\ub2c8\ub2e4.');
        }
        window.location.assign(data.redirect_url || '/login');
    } catch (error) {
        console.error('logout failed:', error);
        alert(error.message || '\ub85c\uadf8\uc544\uc6c3\uc5d0 \uc2e4\ud328\ud588\uc2b5\ub2c8\ub2e4.');
        if (button) button.disabled = false;
    }
}
