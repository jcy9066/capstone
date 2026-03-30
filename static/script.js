// 시간 포맷 생성 함수
function getCurrentTime() {
    return new Date().toLocaleTimeString('ko-KR', { hour12: false, hour: '2-digit', minute:'2-digit', second:'2-digit' });
}

// YYYY-MM-DD HH:MM:SS 형식 반환 함수 (카메라 오버레이용)
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

// 1초마다 카메라 상단 시간 업데이트
setInterval(() => {
    document.getElementById('camera-datetime').innerText = getFormattedDateTime();
}, 1000);

// 1초마다 서버에서 로봇 상태 가져오기 (상태 바 업데이트)
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

function handleCameraError() {
    document.getElementById('camera-stream').style.display = 'none';
    document.getElementById('no-camera-msg').style.display = 'flex';
}

function captureScreen() { alert("현재 화면이 캡쳐되었습니다."); }

function toggleFullscreen(elementId) {
    const elem = document.getElementById(elementId);
    if (!document.fullscreenElement) {
        if (elem.requestFullscreen) { elem.requestFullscreen(); } 
        else if (elem.webkitRequestFullscreen) { elem.webkitRequestFullscreen(); } 
        else if (elem.msRequestFullscreen) { elem.msRequestFullscreen(); }
    } else {
        if (document.exitFullscreen) { document.exitFullscreen(); }
    }
}

// 알림 지우기 (확인 창 추가)
function clearAlerts() {
    if (confirm("정말 모든 알림 내역을 삭제하시겠습니까?")) {
        document.getElementById('alertBox').innerHTML = `
            <div class="alert-entry alert-info">
                <span class="alert-time">${getCurrentTime()}</span>
                <span class="alert-message">알림 내역이 삭제되었습니다. 대기 중...</span>
            </div>`;
    }
}

// 랜덤 알림 생성 (더미)
const dummyAlerts = [
    { type: 'warning', msg: '전방 2m 앞 미확인 장애물 감지' },
    { type: 'danger', msg: '외부인 침입 의심 (YOLO_Person_Detect)' },
    { type: 'warning', msg: '바퀴 모터(우측) 온도 상승' }
];

setInterval(() => {
    if (Math.random() > 0.8) {
        const alertBox = document.getElementById('alertBox');
        const alertData = dummyAlerts[Math.floor(Math.random() * dummyAlerts.length)];
        
        const newAlert = document.createElement('div');
        newAlert.className = `alert-entry alert-${alertData.type}`;
        newAlert.innerHTML = `
            <span class="alert-time">${getCurrentTime()}</span>
            <span class="alert-message" style="color: ${alertData.type === 'danger' ? 'var(--danger-color)' : 'var(--warning-color)'}">
                ${alertData.msg}
            </span>
        `;
        
        alertBox.appendChild(newAlert);
        alertBox.scrollTop = alertBox.scrollHeight;

        // [요구사항 2] danger 타입일 경우 자동으로 텔레그램 전송 함수 실행 (팝업 없이)
        if (alertData.type === 'danger') {
            reportDanger(true);
        }
    }
}, 4000);


// --- 모달 창 제어 로직 ---
// --- 모달 창 제어 로직 ---
function openModal(type) {
    const modal = document.getElementById('commonModal');
    const title = document.getElementById('modalTitle');
    const body = document.getElementById('modalBody');

    if (type === 'statusModal') {
        title.innerText = "기기 상태 로그";
        body.innerHTML = `
            <p><strong>최근 점검일시:</strong> ${getFormattedDateTime()}</p>
            <p><strong>네트워크 지연율(Ping):</strong> 24ms</p>
            <p><strong>저장소 여유 공간:</strong> 14GB / 32GB</p>
            <hr style="border: 0; border-top: 1px solid #eee; margin: 15px 0;">
            <p style="color: #666; font-size: 13px;">시스템이 안정적으로 작동 중입니다.</p>
        `;
    } else if (type === 'patrolModal') {
        title.innerText = "순찰 기록 내역";
        body.innerHTML = `
            <ul style="padding-left: 20px; line-height: 1.8;">
                <li>[13:00] 정문 A구역 순찰 완료 (이상 없음)</li>
                <li>[12:30] 후문 B구역 순찰 완료 (이상 없음)</li>
                <li>[11:45] 주차장 C구역 순찰 중 장애물 우회</li>
                <li>[11:00] 시스템 부팅 및 순찰 개시</li>
            </ul>
        `;
    // [추가된 부분] 북마크 보기 모달
    } else if (type === 'bookmarkModal') {
        title.innerText = "저장된 북마크 위치";
        body.innerHTML = `
            <ul style="padding-left: 20px; line-height: 1.8;">
                <li>📍 <strong>공학관 1층 로비</strong> - 어제 15:30 저장</li>
                <li>📍 <strong>연구실 앞 복도</strong> - 2일 전 저장</li>
                <li>📍 <strong>야외 주차장 A구역</strong> - 3일 전 저장</li>
            </ul>
            <p style="color: #666; font-size: 12px; margin-top: 15px;">※ 목록 클릭 시 해당 위치로 자율주행 경로를 탐색합니다.</p>
        `;
    // [추가된 부분] 갤러리 모달
    } else if (type === 'galleryModal') {
        title.innerText = "위험 감지 갤러리 (캡쳐)";
        body.innerHTML = `
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
                <div style="background: #e2e8f0; height: 100px; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 12px; color: #64748b;">이미지 1<br>(11:45 침입자)</div>
                <div style="background: #e2e8f0; height: 100px; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 12px; color: #64748b;">이미지 2<br>(10:20 장애물)</div>
                <div style="background: #e2e8f0; height: 100px; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 12px; color: #64748b;">이미지 3<br>(어제 23:00)</div>
                <div style="background: #e2e8f0; height: 100px; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 12px; color: #64748b;">이미지 4<br>(어제 21:15)</div>
            </div>
        `;
    }
    
    modal.style.display = 'flex';
}

function closeModal() {
    document.getElementById('commonModal').style.display = 'none';
}

// 모달 바깥 배경 클릭 시 닫기
window.onclick = function(event) {
    const modal = document.getElementById('commonModal');
    if (event.target == modal) {
        modal.style.display = "none";
    }
}

// 텔레그램 전송 함수 (isAuto 플래그를 추가하여 자동 전송 시 팝업창 생략)
function reportDanger(isAuto = false) {
    let confirmReport = true;
    
    // 수동으로 [신고] 버튼을 눌렀을 때만 확인창을 띄움
    if (!isAuto) {
        confirmReport = confirm("신고? - Telegram");
    }
    
    if(confirmReport) {
        // Flask 백엔드로 텔레그램 전송 요청을 보냄
        fetch('/send_telegram', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        })
        .then(response => response.json())
        .then(data => {
            if(data.status === 'success') {
                if(!isAuto) alert("🚨 긴급 알림이 전송되었습니다.");
                console.log("텔레그램 알림 전송 완료");
            } else {
                if(!isAuto) alert("알림 전송에 실패했습니다.");
            }
        })
        .catch(error => {
            console.error("Error:", error);
            if(!isAuto) alert("서버 통신 오류로 알림을 보내지 못했습니다.");
        });
    }
}

// [요구사항 1] 알림창에 기록 띄우는 코드 삭제
function moveRobot(direction) {
    console.log(`로봇 이동 명령: ${direction}`);
    
    // 추후 이곳에 백엔드로 방향 데이터를 전송하는 fetch 로직을 추가하시면 됩니다.
}

// script.js 맨 아래에 추가/수정

let currentPatrolMode = 'auto'; // 초기 상태는 자동 순찰

// 스위치 클릭 시 모드 변경 (confirm 창 및 텍스트 투명도 처리 포함)
function togglePatrolMode() {
    const targetMode = currentPatrolMode === 'auto' ? 'manual' : 'auto';
    const modeName = targetMode === 'auto' ? '자동' : '수동';
    
    // confirm 창 띄우기
    if (confirm(`${modeName} 순찰 모드로 변경하시겠습니까?`)) {
        currentPatrolMode = targetMode; // 상태 업데이트
        
        const switchUi = document.getElementById('mode-switch-ui');
        const dPadArea = document.getElementById('d-pad-area');
        const labelAuto = document.getElementById('label-auto');
        const labelManual = document.getElementById('label-manual');
        
        if (currentPatrolMode === 'auto') {
            // 스위치 및 방향키 UI 처리
            switchUi.classList.remove('manual');
            dPadArea.classList.add('disabled');
            
            // 텍스트 반투명 처리 교차
            labelAuto.classList.add('active');
            labelAuto.classList.remove('inactive');
            labelManual.classList.add('inactive');
            labelManual.classList.remove('active');
            
            console.log("모드 변경: 자동 순찰");
        } else {
            // 스위치 및 방향키 UI 처리
            switchUi.classList.add('manual');
            dPadArea.classList.remove('disabled');
            
            // 텍스트 반투명 처리 교차
            labelAuto.classList.add('inactive');
            labelAuto.classList.remove('active');
            labelManual.classList.add('active');
            labelManual.classList.remove('inactive');
            
            console.log("모드 변경: 수동 순찰");
        }
    }
}

// 기존 moveRobot 함수 덮어쓰기 (수동 모드일 때만 동작하도록 보안 적용)
window.moveRobot = function(direction) {
    if (currentPatrolMode !== 'manual') {
        console.warn("수동 순찰 모드에서만 로봇을 조작할 수 있습니다.");
        return; 
    }
    console.log(`로봇 이동 명령: ${direction}`);
    
    // 추후 백엔드(app.py)로 방향 데이터를 전송하는 fetch 로직 삽입
};

// 키보드(방향키, WASD) 제어 이벤트 리스너
document.addEventListener('keydown', (event) => {
    // 수동 모드가 아니면 키보드 입력 무시
    if (currentPatrolMode !== 'manual') return;

    let direction = null;
    let btnIndex = -1; 

    switch (event.key) {
        case 'ArrowUp': case 'w': direction = '↑'; btnIndex = 1; break;
        case 'ArrowDown': case 's': direction = '↓'; btnIndex = 7; break;
        case 'ArrowLeft': case 'a': direction = '←'; btnIndex = 3; break;
        case 'ArrowRight': case 'd': direction = '→'; btnIndex = 5; break;
    }

    if (direction) {
        event.preventDefault(); // 방향키 입력 시 화면 스크롤 방지
        moveRobot(direction);

        // 누른 키에 해당하는 HTML 버튼에 시각적 클릭 효과 주기
        const buttons = document.querySelectorAll('.d-pad .d-btn:not(.rotate-btn)');
        if (btnIndex !== -1 && buttons[btnIndex]) {
            buttons[btnIndex].classList.add('active-key');
            setTimeout(() => buttons[btnIndex].classList.remove('active-key'), 150);
        }
    }
});

// script.js 맨 아래에 추가 (초기 UI 완벽 동기화)
window.addEventListener('DOMContentLoaded', () => {
    const dPadArea = document.getElementById('d-pad-area');
    const switchUi = document.getElementById('mode-switch-ui');
    
    // 현재 모드가 수동이 아니라면 무조건 방향키 패드를 시각적/물리적으로 차단
    if (currentPatrolMode !== 'manual') {
        dPadArea.classList.add('disabled');
        switchUi.classList.remove('manual');
    }
});