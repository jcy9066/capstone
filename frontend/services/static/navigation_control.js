(() => {
    'use strict';

    const POLL_MS = 750;
    const state = {
        control: null,
        draftGoal: null,
        pointerId: null,
        pointerStart: null,
        csrf: null,
        busy: false,
    };

    const $ = id => document.getElementById(id);

    async function requestJson(url, options = {}) {
        const response = await fetch(url, { credentials: 'same-origin', ...options });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok || payload.ok === false) {
            const error = new Error(payload.error || payload.detail || `HTTP ${response.status}`);
            error.code = payload.error_code;
            throw error;
        }
        return payload;
    }

    async function csrfToken() {
        if (state.csrf) return state.csrf;
        const payload = await requestJson('/api/auth/csrf');
        state.csrf = payload.csrf_token;
        return state.csrf;
    }

    async function mutate(path, payload = {}, keepalive = false) {
        const token = await csrfToken();
        return requestJson(path, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': token },
            body: JSON.stringify(payload),
            keepalive,
        });
    }

    function setFeedback(message, error = false) {
        const element = $('navigation-control-feedback');
        if (!element) return;
        element.textContent = message || '';
        element.classList.toggle('error', error);
    }

    function applyControlState(payload) {
        state.control = payload;
        const mode = payload?.navigation_mode || 'UNKNOWN';
        const navState = payload?.navigation_state || 'UNKNOWN';
        const modeLabel = $('navigation-mode-label');
        const stateLabel = $('navigation-state-label');
        if (modeLabel) modeLabel.textContent = mode;
        if (stateLabel) stateLabel.textContent = navState;
        $('navigation-mode-mapping')?.classList.toggle('active', mode === 'MAPPING');
        $('navigation-mode-driving')?.classList.toggle('active', mode === 'DRIVING');

        const ready = mode === 'DRIVING' && payload.localization_ready && payload.nav2_ready;
        const pathReady = navState === 'PATH_READY' && Array.isArray(payload.planned_path) && payload.planned_path.length > 1;
        const stopped = Boolean(payload.emergency_stop);
        if ($('navigation-start')) $('navigation-start').hidden = !pathReady;
        if ($('navigation-cancel')) $('navigation-cancel').hidden = !payload.active_goal;
        if ($('navigation-resume')) $('navigation-resume').hidden = !stopped;
        if ($('navigation-estop')) $('navigation-estop').classList.toggle('latched', stopped);
        const hint = $('navigation-goal-hint');
        if (hint) {
            hint.textContent = ready
                ? '확대 지도에서 누른 뒤 드래그하여 Goal 방향을 지정하세요.'
                : 'DRIVING 및 localization/Nav2 준비 후 Goal을 지정할 수 있습니다.';
        }
        window.navigationMapView?.requestRender();
    }

    async function refreshState() {
        try {
            applyControlState(await requestJson('/api/navigation/control/state'));
        } catch (error) {
            setFeedback(`상태 조회 실패: ${error.message}`, true);
        }
    }

    function canSetGoal() {
        const control = state.control;
        const view = window.navigationMapView?.snapshot();
        return Boolean(
            view?.expanded
            && control?.navigation_mode === 'DRIVING'
            && control?.localization_ready
            && control?.nav2_ready
            && !control?.emergency_stop
        );
    }

    function beginGoal(event) {
        if ((event.button !== 0 && event.button !== 2) || !canSetGoal()) return;
        const point = window.navigationMapView?.canvasToWorld(event);
        if (!point) {
            setFeedback('지도 밖에는 Goal을 지정할 수 없습니다.', true);
            return;
        }
        event.preventDefault();
        state.pointerId = event.pointerId;
        state.pointerStart = point;
        state.draftGoal = { ...point, yaw: 0 };
        event.currentTarget.setPointerCapture?.(event.pointerId);
        window.navigationMapView?.requestRender();
    }

    function moveGoal(event) {
        if (state.pointerId !== event.pointerId || !state.pointerStart) return;
        const point = window.navigationMapView?.canvasToWorld(event);
        if (!point) return;
        state.draftGoal = {
            ...state.pointerStart,
            yaw: Math.atan2(point.y - state.pointerStart.y, point.x - state.pointerStart.x),
        };
        window.navigationMapView?.requestRender();
    }

    async function finishGoal(event) {
        if (state.pointerId !== event.pointerId || !state.draftGoal) return;
        event.preventDefault();
        const goal = { ...state.draftGoal };
        state.pointerId = null;
        state.pointerStart = null;
        setFeedback('경로를 계산하는 중입니다...');
        try {
            applyControlState(await mutate('/api/navigation/control/goal', { goal }));
            state.draftGoal = null;
            setFeedback('경로 미리보기가 준비되었습니다. 주행 시작 전에는 로봇이 움직이지 않습니다.');
        } catch (error) {
            setFeedback(`경로 계산 실패: ${error.message}`, true);
        } finally {
            window.navigationMapView?.requestRender();
        }
    }

    function cancelGoalDraft(event) {
        if (state.pointerId !== event.pointerId) return;
        state.pointerId = null;
        state.pointerStart = null;
        state.draftGoal = null;
        setFeedback('Goal 지정을 취소했습니다.');
        window.navigationMapView?.requestRender();
    }

    function drawArrow(ctx, goal, worldToCanvas, layout, color) {
        if (!goal) return;
        const point = worldToCanvas(goal.x, goal.y, layout);
        const length = Math.max(20, 0.45 * layout.scale);
        const endX = point.x + Math.cos(goal.yaw) * length;
        const endY = point.y - Math.sin(goal.yaw) * length;
        ctx.save();
        ctx.strokeStyle = color;
        ctx.fillStyle = color;
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.moveTo(point.x, point.y);
        ctx.lineTo(endX, endY);
        ctx.stroke();
        ctx.translate(endX, endY);
        ctx.rotate(-goal.yaw);
        ctx.beginPath();
        ctx.moveTo(0, 0);
        ctx.lineTo(-11, -6);
        ctx.lineTo(-11, 6);
        ctx.closePath();
        ctx.fill();
        ctx.restore();
    }

    window.navigationControlOverlay = {
        draw(ctx, layout, worldToCanvas) {
            const path = state.control?.planned_path || [];
            if (path.length > 1) {
                ctx.save();
                ctx.strokeStyle = '#a855f7';
                ctx.lineWidth = 3;
                ctx.shadowColor = 'rgba(168, 85, 247, 0.55)';
                ctx.shadowBlur = 5;
                ctx.beginPath();
                path.forEach((item, index) => {
                    const point = worldToCanvas(item.x, item.y, layout);
                    if (index === 0) ctx.moveTo(point.x, point.y);
                    else ctx.lineTo(point.x, point.y);
                });
                ctx.stroke();
                ctx.restore();
            }
            drawArrow(
                ctx,
                state.draftGoal || state.control?.active_goal,
                worldToCanvas,
                layout,
                state.draftGoal ? '#f59e0b' : '#a855f7',
            );
        },
    };

    async function setMappingMode() {
        if (state.busy || state.control?.navigation_mode === 'MAPPING') return;
        if (!window.confirm('Mapping 모드로 전환하면 실행 중인 Nav2 goal이 취소됩니다. 계속하시겠습니까?')) return;
        state.busy = true;
        setFeedback('Mapping 모드로 전환 중...');
        try {
            applyControlState(await mutate('/api/navigation/control/mode', { mode: 'MAPPING' }));
            setFeedback('Mapping 모드입니다. Nav2 주행은 비활성화되었습니다.');
        } catch (error) {
            setFeedback(`모드 전환 실패: ${error.message}`, true);
        } finally {
            state.busy = false;
        }
    }

    function field(label, id, value = '0') {
        const wrapper = document.createElement('label');
        wrapper.textContent = label;
        const input = document.createElement('input');
        input.id = id;
        input.type = id.includes('name') ? 'text' : 'number';
        input.step = 'any';
        input.value = value;
        wrapper.append(input);
        return wrapper;
    }

    function initialPose(container) {
        return {
            x: Number(container.querySelector('#navigation-pose-x').value),
            y: Number(container.querySelector('#navigation-pose-y').value),
            yaw_degrees: Number(container.querySelector('#navigation-pose-yaw').value),
        };
    }

    async function submitDriving(container, source) {
        const pose = initialPose(container);
        if (!Object.values(pose).every(Number.isFinite)) {
            setFeedback('초기 위치에는 유한한 숫자만 입력할 수 있습니다.', true);
            return;
        }
        const mapName = source === 'save_current'
            ? container.querySelector('#navigation-map-name').value.trim()
            : container.querySelector('input[name="navigation-existing-map"]:checked')?.value;
        if (!mapName) {
            setFeedback('지도 이름 또는 기존 지도를 선택하세요.', true);
            return;
        }
        state.busy = true;
        container.querySelectorAll('button,input').forEach(item => { item.disabled = true; });
        setFeedback(source === 'save_current' ? 'Mapping 결과 저장 후 DRIVING 전환 중...' : '기존 지도와 localization을 준비하는 중...');
        try {
            const payload = await mutate('/api/navigation/control/mode', {
                mode: 'DRIVING',
                source,
                map_name: mapName,
                initial_pose: pose,
            });
            applyControlState(payload);
            closeModal();
            setFeedback('DRIVING 모드가 준비되었습니다. Goal을 지정하세요.');
        } catch (error) {
            setFeedback(`DRIVING 전환 실패: ${error.message}`, true);
            container.querySelectorAll('button,input').forEach(item => { item.disabled = false; });
        } finally {
            state.busy = false;
        }
    }

    function closeModal() {
        const modal = $('commonModal');
        if (modal) modal.style.display = 'none';
    }

    async function openDrivingModal() {
        if (state.busy || state.control?.navigation_mode === 'DRIVING') return;
        const modal = $('commonModal');
        const title = $('modalTitle');
        const body = $('modalBody');
        if (!modal || !title || !body) return;
        title.textContent = 'Mapping / Driving 전환';
        body.replaceChildren();
        const container = document.createElement('div');
        container.className = 'navigation-driving-modal';
        const question = document.createElement('p');
        question.textContent = '현재 Mapping 결과를 저장하시겠습니까?';
        const saveSection = document.createElement('section');
        saveSection.append(field('Map name', 'navigation-map-name', `mapping_${Date.now()}`));
        const existingSection = document.createElement('section');
        existingSection.className = 'navigation-existing-maps';
        existingSection.textContent = '저장 지도 불러오는 중...';
        try {
            const maps = await requestJson('/api/navigation/maps');
            existingSection.replaceChildren();
            for (const map of maps.maps || []) {
                const option = document.createElement('label');
                const radio = document.createElement('input');
                radio.type = 'radio';
                radio.name = 'navigation-existing-map';
                radio.value = map.map_name;
                radio.checked = !existingSection.children.length;
                option.append(radio, document.createTextNode(map.map_name));
                existingSection.append(option);
            }
            if (!existingSection.children.length) existingSection.textContent = '저장된 지도가 없습니다.';
        } catch (error) {
            existingSection.textContent = `지도 목록 실패: ${error.message}`;
        }
        const pose = document.createElement('div');
        pose.className = 'navigation-initial-pose';
        pose.append(
            field('Initial X (m)', 'navigation-pose-x'),
            field('Initial Y (m)', 'navigation-pose-y'),
            field('Initial yaw (deg)', 'navigation-pose-yaw'),
        );
        const actions = document.createElement('div');
        actions.className = 'navigation-modal-actions';
        for (const [label, action, className] of [
            ['저장 후 주행', () => submitDriving(container, 'save_current'), 'primary'],
            ['기존 지도 선택', () => submitDriving(container, 'existing'), 'secondary'],
            ['취소', closeModal, ''],
        ]) {
            const button = document.createElement('button');
            button.type = 'button';
            button.textContent = label;
            button.className = className;
            button.addEventListener('click', action);
            actions.append(button);
        }
        container.append(question, saveSection, existingSection, pose, actions);
        body.append(container);
        modal.style.display = 'flex';
    }

    async function simpleAction(path, progress) {
        if (state.busy) return;
        state.busy = true;
        setFeedback(progress);
        try {
            const response = await mutate(path);
            if (response.navigation_mode && response.navigation_state) {
                applyControlState(response);
            }
            setFeedback('요청이 적용되었습니다.');
        } catch (error) {
            setFeedback(`요청 실패: ${error.message}`, true);
        } finally {
            state.busy = false;
        }
    }

    async function emergencyStop(reason = 'dashboard_emergency_stop', keepalive = false) {
        setFeedback('긴급 정지 및 Nav2 goal 취소 중...');
        try {
            applyControlState(await mutate('/api/navigation/control/emergency-stop', { reason }, keepalive));
            setFeedback('긴급 정지가 유지됩니다. 자동 재개하지 않습니다.');
            return true;
        } catch (error) {
            setFeedback(`긴급 정지 요청 실패: ${error.message}`, true);
            return false;
        }
    }

    async function warning() {
        try {
            await mutate('/api/navigation/control/warning', { led_duration_ms: 3000 });
            setFeedback('경고 방송과 LED 명령을 전송했습니다.');
        } catch (error) {
            setFeedback(`경고 명령 실패: ${error.message}`, true);
        }
    }

    function initialize() {
        const canvas = $('lidar-map-canvas');
        canvas?.addEventListener('contextmenu', event => event.preventDefault());
        canvas?.addEventListener('pointerdown', beginGoal);
        canvas?.addEventListener('pointermove', moveGoal);
        canvas?.addEventListener('pointerup', finishGoal);
        canvas?.addEventListener('pointercancel', cancelGoalDraft);
        $('navigation-mode-mapping')?.addEventListener('click', setMappingMode);
        $('navigation-mode-driving')?.addEventListener('click', openDrivingModal);
        $('navigation-start')?.addEventListener('click', () => simpleAction('/api/navigation/control/start', 'NavigateToPose 시작 중...'));
        $('navigation-cancel')?.addEventListener('click', () => simpleAction('/api/navigation/control/cancel', '목표 취소 중...'));
        $('navigation-estop')?.addEventListener('click', () => emergencyStop());
        $('navigation-resume')?.addEventListener('click', () => simpleAction('/api/navigation/control/resume', '현재 pose에서 경로를 재계산하고 재개하는 중...'));
        $('navigation-led-test')?.addEventListener('click', () => simpleAction('/api/navigation/control/led-test', 'LED test 명령 전송 중...'));
        window.navigationControl = { emergencyStop, warning, refreshState };
        csrfToken().catch(() => {});
        refreshState();
        window.setInterval(refreshState, POLL_MS);
    }

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initialize, { once: true });
    else initialize();
})();
