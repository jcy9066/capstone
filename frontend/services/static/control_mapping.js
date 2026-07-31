// ===================================================
// 웹 D-Pad → 실제 로봇 구동 재매핑
// ===================================================
//
// 현재 펌웨어에서 확인된 실제 동작:
//
// rotate_left     → 전진
// rotate_right    → 후진
// forward         → 시계 방향 회전
// backward        → 반시계 방향 회전
// left            → 오른쪽 전진 회전
// right           → 왼쪽 후진 회전
// forward_left    → 오른쪽 전진 회전
// forward_right   → 왼쪽 후진 회전
// backward_left   → 왼쪽 전진 회전
// backward_right  → 오른쪽 후진 회전
//
// 따라서 웹 화살표를 아래 명령으로 재매핑한다.
//
// ↑  → 전진
// ↓  → 후진
// ←  → 반시계 방향 회전
// →  → 시계 방향 회전
// ↖ → 좌회전
// ↗ → 우회전
// ↙ → 왼쪽으로 후진
// ↘ → 오른쪽으로 후진
//

window.directionToCommand = function directionToCommand(direction) {
    const map = {
        // 직선 이동
        '↑': 'rotate_left',
        '↓': 'rotate_right',

        // 제자리 회전
        '←': 'backward',
        '→': 'forward',

        // 대각선 이동
        '↖': 'backward_left',
        '↗': 'forward_left',
        '↙': 'forward_right',
        '↘': 'backward_right',
    };

    return map[direction] || direction;
};


// ===================================================
// 키보드 방향 입력
// ===================================================
//
// 중앙 버튼을 제거했기 때문에 실제 방향 버튼의 DOM 순서는:
//
// 0: ↖
// 1: ↑
// 2: ↗
// 3: ←
// 4: →
// 5: ↙
// 6: ↓
// 7: ↘
//

window.getDirectionFromKeys = function getDirectionFromKeys() {
    const up =
        pressedKeys.has('ArrowUp') ||
        pressedKeys.has('w');

    const down =
        pressedKeys.has('ArrowDown') ||
        pressedKeys.has('s');

    const left =
        pressedKeys.has('ArrowLeft') ||
        pressedKeys.has('a');

    const right =
        pressedKeys.has('ArrowRight') ||
        pressedKeys.has('d');

    if (up && left) {
        return {
            direction: '↖',
            btnIndex: 0,
        };
    }

    if (up && right) {
        return {
            direction: '↗',
            btnIndex: 2,
        };
    }

    if (down && left) {
        return {
            direction: '↙',
            btnIndex: 5,
        };
    }

    if (down && right) {
        return {
            direction: '↘',
            btnIndex: 7,
        };
    }

    if (up) {
        return {
            direction: '↑',
            btnIndex: 1,
        };
    }

    if (down) {
        return {
            direction: '↓',
            btnIndex: 6,
        };
    }

    if (left) {
        return {
            direction: '←',
            btnIndex: 3,
        };
    }

    if (right) {
        return {
            direction: '→',
            btnIndex: 4,
        };
    }

    return null;
};


console.log('[control] 실제 모터 구동 기준 방향 매핑 적용 완료');