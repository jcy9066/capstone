(() => {
    'use strict';

    const DEFAULT_ENDPOINTS = {
        robotState: '/api/robots/pi-01',
        alertLog: '',
        deviceLogs: '',
        patrolLogs: ''
    };
    const endpoints = {
        ...DEFAULT_ENDPOINTS,
        ...(window.DABOM_DASHBOARD_ENDPOINTS || {})
    };
    const unavailableEndpoints = new Set();
    const ROBOT_STATUS_STALE_MS = 5000;
    let lastRobotConnected = null;

    const byId = id => document.getElementById(id);
    const asObject = value => value && typeof value === 'object' ? value : {};
    const firstValue = (...values) => values.find(value => value !== undefined && value !== null && value !== '');

    function parseDate(value) {
        if (value === undefined || value === null || value === '') return null;
        const numeric = Number(value);
        const parsed = Number.isFinite(numeric)
            ? new Date(numeric < 1e12 ? numeric * 1000 : numeric)
            : new Date(value);
        return Number.isNaN(parsed.getTime()) ? null : parsed;
    }

    function hasFreshStatus(source) {
        if (!Object.prototype.hasOwnProperty.call(source, 'updated_at')) return true;
        const updatedAt = parseDate(source.updated_at);
        return Boolean(updatedAt && Date.now() - updatedAt.getTime() <= ROBOT_STATUS_STALE_MS);
    }

    function setText(id, value, stateClass = '') {
        const element = byId(id);
        if (!element) return;
        element.textContent = value;
        element.classList.remove('state-danger', 'state-success');
        if (stateClass) element.classList.add(stateClass);
        element.title = String(value);
    }

    function markUpdated(timestamp) {
        const element = byId('server-state-updated');
        if (!element) return;
        const parsed = parseDate(timestamp) || new Date();
        element.textContent = `확인 ${parsed.toLocaleTimeString('ko-KR', { hour12: false })}`;
    }

    function setPiState(value, available = true) {
        const element = byId('pi-connection-status');
        if (!element) return;
        if (available && typeof value === 'boolean') lastRobotConnected = value;
        element.classList.remove('state-online', 'state-offline', 'state-unknown');
        if (!available || typeof value !== 'boolean') {
            element.textContent = 'UNKNOWN';
            element.classList.add('state-unknown');
        } else if (value) {
            element.textContent = 'ONLINE';
            element.classList.add('state-online');
        } else {
            element.textContent = 'OFFLINE';
            element.classList.add('state-offline');
        }
    }

    function setRobotMode(value) {
        const element = byId('robot-mode-status');
        if (!element) return;
        const mode = String(value || '').trim().toLowerCase();
        element.classList.remove('state-auto', 'state-manual', 'state-unknown');
        if (mode === 'auto' || mode === 'manual') {
            element.textContent = mode.toUpperCase();
            element.classList.add(mode === 'auto' ? 'state-auto' : 'state-manual');
        } else {
            element.textContent = 'UNKNOWN';
            element.classList.add('state-unknown');
        }
    }

    function formatOperationMode(value) {
        const mode = String(value || '').trim().toLowerCase();
        const labels = {
            mapping: 'MAPPING',
            driving: 'DRIVING',
            localization_nav2: 'LOCALIZATION + NAV2',
            localization: 'LOCALIZATION',
            scan_only: 'SCAN ONLY'
        };
        return labels[mode] || (mode ? mode.toUpperCase() : 'UNKNOWN');
    }

    function summarizeGoal(value) {
        if (!value) return 'UNAVAILABLE';
        if (typeof value === 'string' || typeof value === 'number') return String(value);
        const goal = asObject(value);
        const label = firstValue(goal.label, goal.name, goal.id, goal.goal_id);
        if (label) return String(label);
        const pose = asObject(firstValue(goal.pose, goal.position, goal));
        if (Number.isFinite(Number(pose.x)) && Number.isFinite(Number(pose.y))) {
            return `X ${Number(pose.x).toFixed(2)} / Y ${Number(pose.y).toFixed(2)}`;
        }
        return 'AVAILABLE';
    }

    function summarizePath(value) {
        if (!value) return 'UNAVAILABLE';
        if (typeof value === 'string') return value;
        const path = Array.isArray(value)
            ? value
            : firstValue(value.poses, value.points, value.path);
        if (Array.isArray(path)) return `${path.length} POINTS`;
        return 'AVAILABLE';
    }

    function renderAlerts(items) {
        const target = byId('alertBox');
        if (!target || !Array.isArray(items)) return;
        target.replaceChildren();
        if (!items.length) {
            const empty = document.createElement('div');
            empty.className = 'alert-entry alert-info';
            const message = document.createElement('span');
            message.className = 'alert-message';
            message.textContent = '조회된 실시간 알림이 없습니다.';
            empty.append(message);
            target.append(empty);
            return;
        }
        for (const item of items.slice(-100).reverse()) {
            const alert = asObject(item);
            const level = String(firstValue(alert.level, alert.severity, alert.type, 'info')).toLowerCase();
            const row = document.createElement('div');
            row.className = `alert-entry ${level.includes('danger') || level.includes('critical') ? 'alert-danger' : level.includes('warn') ? 'alert-warning' : 'alert-info'}`;
            const time = document.createElement('span');
            time.className = 'alert-time';
            const timestamp = firstValue(alert.timestamp, alert.created_at, alert.time);
            const parsed = parseDate(timestamp);
            time.textContent = parsed
                ? parsed.toLocaleTimeString('ko-KR', { hour12: false })
                : String(timestamp || '--:--:--');
            const message = document.createElement('span');
            message.className = 'alert-message';
            message.textContent = String(firstValue(alert.message, alert.content, alert.description, '-'));
            row.append(time, message);
            target.append(row);
        }
    }

    function renderAlertsUnavailable() {
        const target = byId('alertBox');
        if (!target) return;
        target.replaceChildren();
        const row = document.createElement('div');
        row.className = 'alert-entry alert-info alert-unavailable';
        const time = document.createElement('span');
        time.className = 'alert-time';
        time.textContent = '--:--:--';
        const message = document.createElement('span');
        message.className = 'alert-message';
        message.textContent = '실시간 알림 상태를 확인할 수 없습니다.';
        row.append(time, message);
        target.append(row);
    }

    function applyNavigation(payload) {
        const source = asObject(payload);
        setText('operation-mode-status', formatOperationMode(firstValue(source.operation_mode, source.mode)));
        setText('navigation-state-status', String(firstValue(source.navigation_state, source.state, source.status, 'UNKNOWN')).toUpperCase());
        markUpdated(firstValue(source.updated_at, source.timestamp));
    }

    function applyActiveMap(payload) {
        const source = asObject(payload);
        const active = asObject(source.active_map);
        const state = String(source.state || '').toLowerCase();
        if (active.map_name) {
            setText('active-map-status', active.map_name, 'state-success');
        } else if (['loading', 'resetting_pose', 'verifying'].includes(state)) {
            setText('active-map-status', state.toUpperCase());
        } else {
            setText('active-map-status', state === 'unavailable' ? 'UNAVAILABLE' : 'NOT SELECTED');
        }
        markUpdated(firstValue(source.updated_at, source.timestamp));
    }

    function applyRobotSnapshot(payload) {
        const source = asObject(payload);
        const status = asObject(source.status);
        const navigation = asObject(firstValue(source.navigation, status.navigation));
        const connected = firstValue(source.connected, status.connected, status.pi_connected);
        if (typeof connected === 'boolean') {
            setPiState(connected, true);
            window.setDashboardRobotConnection?.(connected);
        }
        const hasActualMode = (
            connected !== false
            && hasFreshStatus(status)
        );
        const reportedMode = hasActualMode
            ? firstValue(status.mode, source.mode, source.robot_mode)
            : null;
        setRobotMode(reportedMode);
        window.applyServerPatrolMode?.(reportedMode);
        applyNavigation({
            ...navigation,
            operation_mode: firstValue(source.operation_mode, navigation.operation_mode, navigation.mode),
            navigation_state: firstValue(source.navigation_state, navigation.navigation_state, navigation.state, navigation.status),
            updated_at: firstValue(source.updated_at, status.updated_at, navigation.updated_at)
        });
        const goal = firstValue(source.current_goal, navigation.current_goal, navigation.goal, status.current_goal);
        const path = firstValue(source.planned_path, navigation.planned_path, navigation.path, status.planned_path);
        const emergencyStop = firstValue(source.emergency_stop, source.estop, status.emergency_stop, navigation.emergency_stop);
        setText('current-goal-status', summarizeGoal(goal));
        setText('planned-path-status', summarizePath(path));
        if (typeof emergencyStop === 'boolean') {
            setText('emergency-stop-status', emergencyStop ? 'ACTIVE' : 'CLEAR', emergencyStop ? 'state-danger' : 'state-success');
        } else {
            setText('emergency-stop-status', 'UNAVAILABLE');
        }
        const alerts = firstValue(source.alerts, source.alert_log, status.alerts);
        if (Array.isArray(alerts)) renderAlerts(alerts);
    }

    function clearRobotSnapshotState() {
        setText('current-goal-status', 'UNAVAILABLE');
        setText('planned-path-status', 'UNAVAILABLE');
        setText('emergency-stop-status', 'UNAVAILABLE');
        if (!endpoints.alertLog) renderAlertsUnavailable();
    }

    async function requestJson(endpoint) {
        if (!endpoint || unavailableEndpoints.has(endpoint)) return { state: 'unavailable' };
        try {
            const response = await fetch(endpoint, { credentials: 'same-origin', cache: 'no-store' });
            const payload = await response.json().catch(() => ({}));
            if (response.status === 404 || response.status === 405) {
                unavailableEndpoints.add(endpoint);
                return { state: 'unavailable' };
            }
            if (!response.ok || payload.ok === false) {
                return { state: 'error', message: payload.detail || payload.error || `HTTP ${response.status}` };
            }
            return { state: 'ready', payload };
        } catch (error) {
            return { state: 'error', message: error.message };
        }
    }

    function extractRows(payload) {
        if (Array.isArray(payload)) return payload;
        const source = asObject(payload);
        return firstValue(source.rows, source.items, source.logs, source.records, source.data, []);
    }

    function splitTimestamp(row) {
        const source = asObject(row);
        if (source.date && source.time) return { date: source.date, time: source.time };
        const value = firstValue(source.timestamp, source.created_at, source.recorded_at, source.updated_at);
        const parsed = parseDate(value);
        if (!parsed) return { date: source.date || '-', time: source.time || '-' };
        return {
            date: parsed.toLocaleDateString('sv-SE'),
            time: parsed.toLocaleTimeString('ko-KR', { hour12: false })
        };
    }

    function normalizeStatusRow(value) {
        const row = asObject(value);
        const timestamp = splitTimestamp(row);
        const pose = asObject(firstValue(row.location, row.pose));
        const location = typeof row.location === 'string'
            ? row.location
            : Number.isFinite(Number(pose.x)) && Number.isFinite(Number(pose.y))
                ? `(${pose.x}, ${pose.y}, ${firstValue(pose.z, 0)})`
                : '-';
        return {
            ...timestamp,
            cpu_usage: firstValue(row.cpu_usage, row.cpu, '-'),
            cpu_temp: firstValue(row.cpu_temp, row.temperature, '-'),
            ram_usage: firstValue(row.ram_usage, row.memory_usage, row.ram, '-'),
            battery: firstValue(row.battery, row.battery_level, '-'),
            ping: firstValue(row.ping, row.latency_ms, '-'),
            location
        };
    }

    function normalizePatrolRow(value) {
        const row = asObject(value);
        return {
            ...splitTimestamp(row),
            state: firstValue(row.state, row.status, '-'),
            location: firstValue(row.location, row.position, '-'),
            content: firstValue(row.content, row.message, row.description, '-'),
            reported: firstValue(row.reported, row.report_status, '-')
        };
    }

    async function fetchLogRows(type) {
        const endpoint = type === 'statusModal' ? endpoints.deviceLogs : endpoints.patrolLogs;
        if (!endpoint) {
            return {
                state: 'unavailable',
                rows: [],
                message: '조회 API가 아직 연결되지 않았습니다.'
            };
        }
        const result = await requestJson(endpoint);
        if (result.state !== 'ready') {
            return {
                state: result.state,
                rows: [],
                message: result.message || '조회 API를 사용할 수 없습니다.'
            };
        }
        const rows = extractRows(result.payload);
        if (!Array.isArray(rows)) {
            return { state: 'error', rows: [], message: '서버 응답 형식을 확인할 수 없습니다.' };
        }
        return {
            state: 'ready',
            rows: rows.map(type === 'statusModal' ? normalizeStatusRow : normalizePatrolRow),
            message: ''
        };
    }

    async function pollRobotState() {
        const result = await requestJson(endpoints.robotState);
        if (result.state === 'ready') applyRobotSnapshot(result.payload);
        else clearRobotSnapshotState();
    }

    async function pollAlerts() {
        if (!endpoints.alertLog) return;
        const result = await requestJson(endpoints.alertLog);
        if (result.state === 'ready') {
            const rows = extractRows(result.payload);
            if (Array.isArray(rows)) renderAlerts(rows);
        }
    }

    document.addEventListener('dabom:robot-status', event => {
        const detail = asObject(event.detail);
        if (detail.available) {
            const payload = asObject(detail.payload);
            const hasActualMode = hasFreshStatus(payload);
            setRobotMode(hasActualMode && lastRobotConnected !== false ? payload.mode : null);
            markUpdated(payload.updated_at);
        } else {
            setRobotMode(null);
        }
    });

    document.addEventListener('dabom:system-control-status', event => {
        const detail = asObject(event.detail);
        if (!detail.available) {
            setPiState(null, false);
            return;
        }
        const pi = Array.isArray(detail.payload?.pi) ? detail.payload.pi : [];
        const reachableValues = pi
            .map(component => component?.reachable)
            .filter(value => typeof value === 'boolean');
        const connected = reachableValues.length ? reachableValues.some(Boolean) : null;
        setPiState(connected, reachableValues.length > 0);
        if (typeof connected === 'boolean') window.setDashboardRobotConnection?.(connected);
        markUpdated(detail.payload?.updated_at);
    });

    document.addEventListener('dabom:navigation-status', event => {
        const detail = asObject(event.detail);
        if (detail.available) applyNavigation(detail.payload);
        else {
            setText('operation-mode-status', 'UNKNOWN');
            setText('navigation-state-status', 'UNKNOWN');
        }
    });

    document.addEventListener('dabom:active-map-status', event => {
        const detail = asObject(event.detail);
        if (detail.available) applyActiveMap(detail.payload);
        else setText('active-map-status', 'UNAVAILABLE');
    });

    window.DabomDashboardState = {
        fetchLogRows,
        applyRobotSnapshot,
        configure(nextEndpoints = {}) {
            Object.assign(endpoints, nextEndpoints);
            Object.values(nextEndpoints).forEach(endpoint => unavailableEndpoints.delete(endpoint));
        },
        refresh() {
            pollRobotState();
            pollAlerts();
        }
    };

    pollRobotState();
    pollAlerts();
    window.setInterval(pollRobotState, 1000);
    window.setInterval(pollAlerts, 2000);
})();
