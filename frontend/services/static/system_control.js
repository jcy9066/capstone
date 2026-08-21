(() => {
    'use strict';

    const state = { status: null, pending: new Set() };

    const text = {
        gpu: '\u0047\u0050\u0055 \uc11c\ubc84 \uc81c\uc5b4',
        pi: '\u0050\u0049 \uc81c\uc5b4',
        checking: '\ud655\uc778 \uc911',
        unavailable: '\ud655\uc778 \ubd88\uac00',
        processing: '\ucc98\ub9ac \uc911',
        instances: '\uc2e4\ud589 \uc778\uc2a4\ud134\uc2a4',
        normalize: '\uc911\ubcf5 \uc815\ub9ac',
        manual: '\u0052\u004f\u0053 \uc81c\uc5b4 \ub9e4\ub274\uc5bc',
        noStatus: '\uc0c1\ud0dc \uc815\ubcf4\uac00 \uc5c6\uc2b5\ub2c8\ub2e4.',
        actionFailed: '\u0052\u004f\u0053 \uc81c\uc5b4 \uc2e4\ud328',
        start: '\uc2dc\uc791',
        stop: '\uc911\uc9c0',
        duplicate: '\uc911\ubcf5',
        error: '\uc624\ub958',
        manualTitle: '\u0052\u004f\u0053 \ud504\ub85c\uc138\uc2a4 \uc81c\uc5b4 \uc548\ub0b4',
        manualBody: '\u0050\u0049 LiDAR \uc11c\ube44\uc2a4\ub97c \uc2dc\uc791\ud55c \ud6c4 GPU \uc5f0\uacb0\uc744 \ud655\uc778\ud558\uc138\uc694. GPU\uc5d0\uc11c LiDAR Bridge, Encoder Bridge, Wheel Odometry\ub97c \uc2dc\uc791\ud55c \ub4a4 SLAM Mapping\uc744 \uc2dc\uc791\ud569\ub2c8\ub2e4. PI \uc11c\ube44\uc2a4 \uc2e4\uc81c \uc81c\uc5b4\ub294 PI \ud074\ub77c\uc774\uc5b8\ud2b8\uac00 systemd \uc81c\uc5b4\uba85\ub839\uc744 \uc9c0\uc6d0\ud560 \ub54c\uae4c\uc9c0 \ud328\ub110\uc5d0\uc11c \ube44\ud65c\uc131\ud654\ub429\ub2c8\ub2e4.'
    };

    const make = (tag, className, value) => {
        const node = document.createElement(tag);
        if (className) node.className = className;
        if (value !== undefined) node.textContent = value;
        return node;
    };

    function stateLabel(component) {
        if (component.state === 'on') return 'ON';
        if (component.state === 'off') return 'OFF';
        if (component.state === 'duplicate') return text.duplicate;
        if (component.state === 'unreachable') return text.unavailable;
        if (component.state === 'error') return text.error;
        return text.processing;
    }

    function createPanel() {
        const body = document.querySelector('.sidebar-body');
        const slot = document.getElementById('systemControlPanelSlot');
        if (!body || document.getElementById('systemControlPanel')) return;

        const wrapper = make('div', '', undefined);
        wrapper.id = 'systemControlPanel';
        const gpu = make('section', 'system-control-panel');
        const gpuHeading = make('div', 'system-control-heading');
        gpuHeading.append(make('span', '', text.gpu));
        gpuHeading.append(make('span', 'system-control-refresh', text.checking));
        gpuHeading.lastChild.id = 'systemControlUpdated';
        gpu.append(gpuHeading, make('div', 'system-control-list'));
        gpu.lastChild.id = 'gpuSystemControls';

        const divider = make('div', 'sidebar-divider system-control-divider');
        const pi = make('section', 'system-control-panel');
        const piHeading = make('div', 'system-control-heading', text.pi);
        pi.append(piHeading, make('div', 'system-control-list'));
        pi.lastChild.id = 'piSystemControls';

        const manual = make('button', 'system-control-manual', text.manual);
        manual.type = 'button';
        manual.addEventListener('click', openManual);
        wrapper.append(gpu, divider, pi, manual);
        if (slot) {
            slot.append(wrapper);
        } else {
            body.append(wrapper);
        }
    }

    function renderGroup(targetId, components, group) {
        const target = document.getElementById(targetId);
        if (!target) return;
        target.replaceChildren();
        if (!Array.isArray(components) || !components.length) {
            target.append(make('div', 'system-control-message', text.noStatus));
            return;
        }
        for (const component of components) {
            const key = `${group}:${component.id}`;
            const pending = state.pending.has(key);
            const unreachable = component.control_available === false || component.state === 'unreachable';
            const card = make('article', `system-control-card${unreachable ? ' is-unreachable' : ''}`);
            const row = make('div', 'system-control-row');
            const details = make('div');
            details.append(make('div', 'system-control-name', component.label || component.id));
            details.append(make('div', 'system-control-description', component.description || ''));
            const action = component.state === 'on' || component.state === 'duplicate' ? 'stop' : 'start';
            const button = make('button', `system-control-switch state-${component.state || 'error'}`, pending ? text.processing : stateLabel(component));
            button.type = 'button';
            button.disabled = pending || unreachable;
            button.addEventListener('click', () => control(group, component.id, action));
            row.append(details, button);
            card.append(row);

            const count = Number.isInteger(component.instance_count) ? `${text.instances}: ${component.instance_count}` : `${text.instances}: ${text.unavailable}`;
            const pids = Array.isArray(component.pids) && component.pids.length ? ` | PID: ${component.pids.join(', ')}` : '';
            card.append(make('div', 'system-control-meta', `${count}${pids}`));
            if (component.message) card.append(make('div', 'system-control-message', component.message));
            if (component.duplicate) {
                const normalize = make('button', 'system-control-normalize', text.normalize);
                normalize.type = 'button';
                normalize.disabled = pending || unreachable;
                normalize.addEventListener('click', () => control(group, component.id, 'normalize'));
                card.append(normalize);
            }
            target.append(card);
        }
    }

    function render(status) {
        state.status = status;
        renderGroup('gpuSystemControls', status.gpu, 'gpu');
        renderGroup('piSystemControls', status.pi, 'pi');
        const updated = document.getElementById('systemControlUpdated');
        if (updated) updated.textContent = status.updated_at ? `\ucd5c\uc885 \ud655\uc778 ${new Date(status.updated_at).toLocaleTimeString('ko-KR')}` : text.unavailable;
    }

    async function fetchStatus() {
        try {
            const response = await fetch('/api/system-control/status', { credentials: 'same-origin' });
            const payload = await response.json();
            if (!response.ok || !payload.ok) throw new Error(payload.detail || text.unavailable);
            render(payload);
            document.dispatchEvent(new CustomEvent('dabom:system-control-status', {
                detail: { available: true, payload }
            }));
        } catch (error) {
            render({ updated_at: null, gpu: [], pi: [{
                id: 'lidar_ros', label: 'LiDAR ROS Service', description: '', state: 'unreachable',
                instance_count: null, control_available: false, message: error.message
            }] });
            document.dispatchEvent(new CustomEvent('dabom:system-control-status', {
                detail: { available: false, error: error.message }
            }));
        }
    }

    async function csrfToken() {
        const response = await fetch('/api/auth/csrf', { credentials: 'same-origin' });
        const payload = await response.json();
        if (!response.ok || !payload.csrf_token) throw new Error(text.unavailable);
        return payload.csrf_token;
    }

    async function control(group, componentId, action) {
        const key = `${group}:${componentId}`;
        if (state.pending.has(key)) return;
        state.pending.add(key);
        if (state.status) render(state.status);
        try {
            const token = await csrfToken();
            const response = await fetch(`/api/system-control/${group}/${encodeURIComponent(componentId)}/${action}`, {
                method: 'POST', credentials: 'same-origin', headers: { 'X-CSRF-Token': token }
            });
            const payload = await response.json();
            if (!response.ok || !payload.ok) throw new Error(payload.detail || text.actionFailed);
        } catch (error) {
            window.alert(`${text.actionFailed}: ${error.message}`);
        } finally {
            state.pending.delete(key);
            await fetchStatus();
        }
    }

    function openManual() {
        const modal = document.getElementById('commonModal');
        const title = document.getElementById('modalTitle');
        const body = document.getElementById('modalBody');
        if (!modal || !title || !body) return;
        title.textContent = text.manualTitle;
        body.replaceChildren(make('p', '', text.manualBody));
        modal.style.display = 'flex';
    }

    function initialize() {
        createPanel();
        fetchStatus();
        window.setInterval(fetchStatus, 1000);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initialize, { once: true });
    } else {
        initialize();
    }
})();
