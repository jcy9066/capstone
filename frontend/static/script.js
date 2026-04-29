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
function fetchRobotStatus() {
    fetch('/get_status')
        .then(response => response.json())
        .then(data => {
            document.getElementById('sys-cpu-usage').innerText = data.cpu_usage;
            document.getElementById('sys-cpu-temp').innerText = data.cpu_temp;
            document.getElementById('sys-ram').innerText = data.ram_usage;
            document.getElementById('sys-battery').innerText = data.battery;
            document.getElementById('sys-internet').innerText = data.internet;
        })
        .catch(error => console.error('상태 업데이트 오류:', error));
}
setInterval(fetchRobotStatus, 1000);

// ===================================================
// 카메라 에러 처리
// ===================================================
function handleCameraError() {
    document.getElementById('camera-stream').style.display = 'none';
    document.getElementById('no-camera-msg').style.display = 'flex';
}

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
        minimapExpanded = true;
    } else {
        minimap.style.width = '';
        minimap.style.height = '';
        minimap.style.bottom = '';
        minimap.style.right = '';
        minimap.style.zIndex = '';
        btn.textContent = '⛶';
        btn.title = '미니맵 확대';
        minimapExpanded = false;
    }
}

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
    statusModal:  { allRows: [], filtered: [], timer: null },
    patrolModal:  { allRows: [], filtered: [], timer: null },
    bookmarkModal:{ allRows: [], filtered: [], timer: null },
};

// ===================================================
// 필터 적용 (초 단위까지 지원)
// ===================================================
function applyFilter(type) {
    const st = modalState[type];
    const startDate = document.getElementById(`${type}-start-date`)?.value;
    const endDate   = document.getElementById(`${type}-end-date`)?.value;
    const startTime = document.getElementById(`${type}-start-time`)?.value;
    const endTime   = document.getElementById(`${type}-end-time`)?.value;

    const startDT = startDate && startTime ? new Date(`${startDate}T${startTime}`) : null;
    const endDT   = endDate   && endTime   ? new Date(`${endDate}T${endTime}`)     : null;

    if (startDT && endDT && startDT > endDT) {
        alert("종료 일시는 시작 일시보다 빠를 수 없습니다. 다시 확인해 주세요.");
        return;
    }

    st.filtered = st.allRows.filter(row => {
        const rowDT = new Date(`${row.date}T${row.time}`);
        if (startDT && rowDT < startDT) return false;
        if (endDT   && rowDT > endDT)   return false;
        return true;
    });
    renderTable(type);
}

function resetFilter(type) {
    const today = todayStr();
    document.getElementById(`${type}-start-date`).value = today;
    document.getElementById(`${type}-end-date`).value   = today;
    document.getElementById(`${type}-start-time`).value = startOfDayTimeStr();
    document.getElementById(`${type}-end-time`).value   = nowTimeStr();
    modalState[type].filtered = [...modalState[type].allRows];
    renderTable(type);
}

// ===================================================
// 테이블 렌더링
// ===================================================
function renderTable(type) {
    const tbody = document.getElementById(`${type}-tbody`);
    const countEl = document.getElementById(`${type}-count`);
    if (!tbody) return;

    const rows = modalState[type].filtered;
    if (countEl) countEl.innerHTML = `총 <span>${rows.length}</span> 건`;

    if (rows.length === 0) {
        tbody.innerHTML = `<tr><td colspan="20"><div class="table-empty">조건에 맞는 데이터가 없습니다</div></td></tr>`;
        return;
    }

    tbody.innerHTML = rows.slice().reverse().map((row, idx) => {
        const realIdx = modalState[type].filtered.length - 1 - idx;
        if (type === 'statusModal') {
            const cpuClass  = row.cpu_usage > 80 ? 'danger' : row.cpu_usage > 60 ? 'warn' : 'accent';
            const tempClass = row.cpu_temp  > 80 ? 'danger' : row.cpu_temp  > 65 ? 'warn' : '';
            const batClass  = row.battery   < 20 ? 'danger' : row.battery   < 40 ? 'warn' : 'success';
            const pingClass = row.ping > 150 ? 'danger' : row.ping > 100 ? 'warn' : '';
            return `<tr>
                <td class="muted">${row.date}</td>
                <td class="muted">${row.time}</td>
                <td class="${cpuClass}">${row.cpu_usage}%</td>
                <td class="${tempClass}">${row.cpu_temp}°C</td>
                <td class="${row.ram_usage>80?'warn':''}">${row.ram_usage}%</td>
                <td class="${batClass}">${row.battery}%</td>
                <td class="${pingClass}">${row.ping}ms</td>
                <td class="muted">${row.location}</td>
            </tr>`;
        } else if (type === 'patrolModal') {
            const stateClass = row.state==='이상 감지'?'danger':row.state==='장애물 우회'?'warn':row.state==='정상 완료'?'success':'accent';
            const repClass   = row.reported==='예'?'danger':'muted';
            return `<tr>
                <td class="muted">${row.date}</td>
                <td class="muted">${row.time}</td>
                <td><span class="status-badge status-${stateClass==='danger'?'danger':stateClass==='warn'?'warning':stateClass==='success'?'normal':'patrol'}">${row.state}</span></td>
                <td class="muted">${row.location}</td>
                <td>${row.content}</td>
                <td class="${repClass}">${row.reported}</td>
            </tr>`;
        } else {
            // bookmarkModal
            const stClass = row.state==='이상 감지'?'danger':row.state==='경고'?'warning':'normal';
            return `<tr>
                <td class="muted">${row.date}</td>
                <td class="muted">${row.time}</td>
                <td>${row.location}</td>
                <td>${row.snapshot || '-'}</td>
                <td><span class="status-badge status-${stClass}">${row.state}</span></td>
                <td>
                    <button class="del-btn" onclick="deleteBookmark(${realIdx})">삭제</button>
                </td>
            </tr>`;
        }
    }).join('');
}

// ===================================================
// 북마크 삭제
// ===================================================
function deleteBookmark(idx) {
    if (confirm('이 기록을 삭제하시겠습니까?')) {
        modalState['bookmarkModal'].allRows.splice(idx, 1);
        applyFilter('bookmarkModal');
    }
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
            <th>RAM Usage</th><th>Battery</th><th>Ping</th><th>위치 (X,Y,Z)</th>
        </tr>`;
    } else if (type === 'patrolModal') {
        tableHead = `<tr>
            <th>날짜</th><th>시각</th><th>상태</th><th>위치 (X,Y,Z)</th>
            <th>내용</th><th>신고여부</th>
        </tr>`;
    } else {
        tableHead = `<tr>
            <th>날짜</th><th>시각</th><th>위치</th><th>스냅샷</th><th>저장 당시 상태</th><th>삭제</th>
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
function openModal(type) {
    const modal  = document.getElementById('commonModal');
    const title  = document.getElementById('modalTitle');
    const body   = document.getElementById('modalBody');

    const titles = {
        statusModal:   '기기 상태 로그',
        patrolModal:   '순찰 기록',
        bookmarkModal: '북마크 조회',
        galleryModal:  '위험 감지 갤러리'
    };

    title.innerText = titles[type] || type;

    if (type === 'galleryModal') {
        body.innerHTML = `
            <div style="display:flex; align-items:center; justify-content:center; padding:60px 20px; color:var(--text-muted); font-family:var(--mono); font-size:12px; letter-spacing:1px; flex-direction:column; gap:8px;">
                <span style="font-size:11px; opacity:0.4;">[ 갤러리 비어있음 ]</span>
                <span>위험 감지 시 캡쳐된 이미지가 여기에 표시됩니다.</span>
            </div>`;
        modal.style.display = 'flex';
        return;
    }

    modalState[type].filtered = [...modalState[type].allRows];
    body.innerHTML = buildModalHTML(type);
    modal.style.display = 'flex';
    renderTable(type);

    // 기기상태 로그는 서버에서 실시간으로 받아오는 구조 (현재는 /get_status 폴링)
    // 순찰 기록, 북마크는 버튼 누를 때만 추가됨 → 자동 추가 타이머 없음
}

function closeModal() {
    document.getElementById('commonModal').style.display = 'none';
    Object.values(modalState).forEach(st => {
        if (st.timer) { clearInterval(st.timer); st.timer = null; }
    });
}

window.onclick = function(event) {
    const modal = document.getElementById('commonModal');
    if (event.target == modal) closeModal();
};

// ===================================================
// 현재 화면 북마크 기록 (요구사항 8)
// ===================================================
function recordBookmark() {
    const now = new Date();
    const date = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')}`;
    const time = `${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}:${String(now.getSeconds()).padStart(2,'0')}`;

    const newRow = {
        date,
        time,
        location: '현재 위치',   // 실제 위치 데이터 연동 시 교체
        snapshot: '화면 기록됨',
        state: '정상'             // 실제 감지 상태 연동 시 교체
    };

    modalState['bookmarkModal'].allRows.push(newRow);

    // 짧은 피드백
    const btn = document.querySelector('.bookmark-record-btn');
    if (btn) {
        const orig = btn.textContent;
        btn.textContent = '✅ 기록 완료!';
        btn.style.color = 'var(--success-color)';
        btn.style.borderColor = 'var(--success-color)';
        setTimeout(() => {
            btn.textContent = orig;
            btn.style.color = '';
            btn.style.borderColor = '';
        }, 1500);
    }
}

// ===================================================
// 텔레그램 신고
// ===================================================
function reportDanger(isAuto = false) {
    let confirmReport = true;
    if (!isAuto) confirmReport = confirm("신고? - Telegram");

    if (confirmReport) {
        fetch('/send_telegram', { method: 'POST', headers: { 'Content-Type': 'application/json' } })
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
    sendRobotCommand({ type: 'speak', text: '경고합니다. 즉시 물러나십시오.' })
        .then(ok => {
            if (ok) alert("⚠️ 경고 방송 명령을 전송했습니다.");
            else alert("경고 방송 명령 전송에 실패했습니다.");
        });
}

// ===================================================
// 수동/자동 순찰 모드 토글
// ===================================================
let currentPatrolMode = 'auto';
const ROBOT_ID = 'pi-01';

function directionToCommand(direction) {
    const map = {
        '↑': 'forward',
        '↓': 'backward',
        '←': 'left',
        '→': 'right',
        '↖': 'forward_left',
        '↗': 'forward_right',
        '↙': 'backward_left',
        '↘': 'backward_right',
        '제자리 회전(반시계)': 'rotate_left',
        '제자리 회전(시계)': 'rotate_right',
    };
    return map[direction] || direction;
}

function sendRobotCommand(payload) {
    return fetch(`/api/robots/${ROBOT_ID}/command`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    })
        .then(response => response.json().then(data => ({ ok: response.ok && data.ok, data })))
        .then(({ ok, data }) => {
            if (!ok) console.warn('로봇 명령 전송 실패:', data);
            return ok;
        })
        .catch(error => {
            console.error('로봇 명령 통신 오류:', error);
            return false;
        });
}

function togglePatrolMode() {
    const targetMode = currentPatrolMode === 'auto' ? 'manual' : 'auto';
    const modeName   = targetMode === 'auto' ? '자동' : '수동';

    if (confirm(`${modeName} 순찰 모드로 변경하시겠습니까?`)) {
        currentPatrolMode = targetMode;
        sendRobotCommand({ type: 'mode', mode: currentPatrolMode });

        const switchUi    = document.getElementById('mode-switch-ui');
        const dPadArea    = document.getElementById('d-pad-area');
        const labelAuto   = document.getElementById('label-auto');
        const labelManual = document.getElementById('label-manual');

        if (currentPatrolMode === 'auto') {
            switchUi.classList.remove('manual');
            dPadArea.classList.add('disabled');
            labelAuto.classList.add('active');   labelAuto.classList.remove('inactive');
            labelManual.classList.add('inactive'); labelManual.classList.remove('active');
        } else {
            switchUi.classList.add('manual');
            dPadArea.classList.remove('disabled');
            labelAuto.classList.add('inactive');   labelAuto.classList.remove('active');
            labelManual.classList.add('active');   labelManual.classList.remove('inactive');
        }
    }
}

// ===================================================
// 로봇 이동 명령 (요구사항 5: 키보드 방향키 지원)
// ===================================================
window.moveRobot = function(direction) {
    if (currentPatrolMode !== 'manual') {
        console.warn("수동 순찰 모드에서만 로봇을 조작할 수 있습니다.");
        return;
    }
    console.log(`로봇 이동 명령: ${direction}`);
    sendRobotCommand({
        type: 'move',
        direction: directionToCommand(direction),
        speed: 0.4,
    });
};

function stopRobot(reason = 'manual_stop') {
    sendRobotCommand({ type: 'stop', reason });
}

// 키보드 방향키 이벤트 (요구사항 5)
// 상하좌우 단독 → 4방향 / 두 키 동시 → 대각선 4방향
const pressedKeys = new Set();

// d-pad 버튼 인덱스 (3x3 그리드, rotate 제외)
// 0:↖  1:↑  2:↗
// 3:←  4:center(회전들)  5:→
// 6:↙  7:↓  8:↘
// querySelectorAll('.d-pad .d-btn:not(.rotate-btn)') 순서와 동일

function getDirectionFromKeys() {
    const up    = pressedKeys.has('ArrowUp')    || pressedKeys.has('w');
    const down  = pressedKeys.has('ArrowDown')  || pressedKeys.has('s');
    const left  = pressedKeys.has('ArrowLeft')  || pressedKeys.has('a');
    const right = pressedKeys.has('ArrowRight') || pressedKeys.has('d');

    if (up   && left)  return { direction: '↖', btnIndex: 0 };
    if (up   && right) return { direction: '↗', btnIndex: 2 };
    if (down && left)  return { direction: '↙', btnIndex: 6 };
    if (down && right) return { direction: '↘', btnIndex: 8 };
    if (up)            return { direction: '↑', btnIndex: 1 };
    if (down)          return { direction: '↓', btnIndex: 7 };
    if (left)          return { direction: '←', btnIndex: 3 };
    if (right)         return { direction: '→', btnIndex: 5 };
    return null;
}

let keyMoveInterval = null;

function startKeyMove() {
    if (keyMoveInterval) return;
    keyMoveInterval = setInterval(() => {
        if (currentPatrolMode !== 'manual') return;
        const result = getDirectionFromKeys();
        if (!result) return;

        moveRobot(result.direction);

        // 해당 버튼 시각적 하이라이트
        const buttons = document.querySelectorAll('.d-pad .d-btn:not(.rotate-btn)');
        buttons.forEach(b => b.classList.remove('active-key'));
        if (result.btnIndex !== -1 && buttons[result.btnIndex]) {
            buttons[result.btnIndex].classList.add('active-key');
        }
    }, 100);
}

function stopKeyMove() {
    if (keyMoveInterval) { clearInterval(keyMoveInterval); keyMoveInterval = null; }
    const buttons = document.querySelectorAll('.d-pad .d-btn:not(.rotate-btn)');
    buttons.forEach(b => b.classList.remove('active-key'));
    if (currentPatrolMode === 'manual') stopRobot('key_release');
}

document.addEventListener('keydown', (event) => {
    const dirKeys = ['ArrowUp','ArrowDown','ArrowLeft','ArrowRight','w','a','s','d'];
    if (!dirKeys.includes(event.key)) return;
    event.preventDefault();
    if (currentPatrolMode !== 'manual') return;

    pressedKeys.add(event.key);
    startKeyMove();
});

document.addEventListener('keyup', (event) => {
    pressedKeys.delete(event.key);
    if (pressedKeys.size === 0 || !['ArrowUp','ArrowDown','ArrowLeft','ArrowRight','w','a','s','d'].some(k => pressedKeys.has(k))) {
        stopKeyMove();
    }
});

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
    const saved = localStorage.getItem('darkMode');
    if (saved === '1') toggleDarkMode();

    // D-Pad 초기 상태 동기화
    const dPadArea = document.getElementById('d-pad-area');
    const switchUi = document.getElementById('mode-switch-ui');
    if (currentPatrolMode !== 'manual') {
        dPadArea.classList.add('disabled');
        switchUi.classList.remove('manual');
    }
});
