(() => {
    'use strict';

    const labels = {
        title: '\uc800\uc7a5 \uc9c0\ub3c4 \uc120\ud0dd',
        description: '\uc9c0\ub3c4\ub97c \ubd88\ub7ec\uc624\uba74 \ud604\uc7ac localization \uc704\uce58\uac00 \ucd08\uae30\ud654\ub429\ub2c8\ub2e4.',
        active: '\ud604\uc7ac \uc0ac\uc6a9 \uc911',
        cancel: '\ucde8\uc18c',
        load: '\uc120\ud0dd \uc9c0\ub3c4 \ubd88\ub7ec\uc624\uae30',
        loading: '\uc9c0\ub3c4 \ubd88\ub7ec\uc624\ub294 \uc911...',
        resetting: '\u0041\u004d\u0043\u004c \ucd08\uae30 \uc704\uce58 \uc124\uc815 \uc911...',
        verifying: '\uc9c0\ub3c4 \ubc0f localization \ud655\uc778 \uc911...',
        unavailable: '\uc0c1\ud0dc \ud655\uc778 \ubd88\uac00',
        notSelected: '\uc120\ud0dd\ub418\uc9c0 \uc54a\uc74c',
        positionX: '\u0058 \uc704\uce58 (m)',
        positionY: '\u0059 \uc704\uce58 (m)',
        heading: '\ubc29\ud5a5 (degree)',
        noMaps: '\ubd88\ub7ec\uc62c \uc218 \uc788\ub294 \uc800\uc7a5 \uc9c0\ub3c4\uac00 \uc5c6\uc2b5\ub2c8\ub2e4.',
        confirmSuffix: ' \uc9c0\ub3c4\ub97c \ubd88\ub7ec\uc624\uc2dc\uaca0\uc2b5\ub2c8\uae4c?\n\ud604\uc7ac localization \uc704\uce58\uac00 \ucd08\uae30\ud654\ub429\ub2c8\ub2e4.',
        success: '\uc9c0\ub3c4\ub97c \ubd88\ub7ec\uc654\uc2b5\ub2c8\ub2e4.',
        renameHint: '\uc6b0\ud074\ub9ad\ud558\uc5ec \uc774\ub984 \ubcc0\uacbd',
        renamePrompt: '\uc0c8 \uc9c0\ub3c4 \uc774\ub984\uc744 \uc785\ub825\ud558\uc138\uc694.',
        renaming: '\uc9c0\ub3c4 \uc774\ub984 \ubcc0\uacbd \uc911...',
        renameSuccess: '\uc9c0\ub3c4 \uc774\ub984\uc744 \ubcc0\uacbd\ud588\uc2b5\ub2c8\ub2e4.',
        mapPrefix: '\u004d\u0041\u0050: '
    };
    const state = { maps: [], active: null, activeApiAvailable: true, busy: false };

    const create = (tag, className, value) => {
        const element = document.createElement(tag);
        if (className) element.className = className;
        if (value !== undefined) element.textContent = value;
        return element;
    };

    const formatSavedAt = value => {
        if (!value) return '--';
        const date = new Date(value);
        return Number.isNaN(date.getTime()) ? value : date.toLocaleString('ko-KR', { hour12: false });
    };

    function setMinimapMapLabel(activeResponse) {
        let label = document.getElementById('lidar-active-map-status');
        const minimap = document.getElementById('minimap-overlay');
        if (!label && minimap) {
            label = create('div', 'lidar-active-map-status');
            label.id = 'lidar-active-map-status';
            minimap.append(label);
        }
        if (!label) return;
        if (activeResponse?.state === 'active' && activeResponse.active_map?.map_name) {
            label.textContent = `${labels.mapPrefix}${activeResponse.active_map.map_name}`;
        } else if (activeResponse?.state === 'loading' || activeResponse?.state === 'resetting_pose' || activeResponse?.state === 'verifying') {
            label.textContent = `${labels.mapPrefix}${labels.loading}`;
        } else if (activeResponse?.state === 'unavailable') {
            label.textContent = `${labels.mapPrefix}${labels.unavailable}`;
        } else {
            label.textContent = `${labels.mapPrefix}${labels.notSelected}`;
        }
    }

    async function requestJson(url, options = {}) {
        const response = await fetch(url, { credentials: 'same-origin', ...options });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok || payload.ok === false) {
            const error = new Error(payload.error || payload.detail || `HTTP ${response.status}`);
            error.status = response.status;
            error.code = payload.error_code;
            throw error;
        }
        return payload;
    }

    async function refreshActiveMap() {
        if (!state.activeApiAvailable) return null;
        try {
            const payload = await requestJson('/api/navigation/maps/active');
            state.active = payload;
            setMinimapMapLabel(payload);
            return payload;
        } catch (error) {
            if (error.status === 404) state.activeApiAvailable = false;
            setMinimapMapLabel({ state: 'unavailable' });
            return null;
        }
    }

    async function csrfToken() {
        const payload = await requestJson('/api/auth/csrf');
        if (!payload.csrf_token) throw new Error(labels.unavailable);
        return payload.csrf_token;
    }

    function closeMapModal() {
        const modal = document.getElementById('commonModal');
        if (modal) modal.style.display = 'none';
    }

    function selectedMapName(container) {
        return container.querySelector('input[name="saved-navigation-map"]:checked')?.value || null;
    }

    function showMessage(target, value, isError = false) {
        target.textContent = value;
        target.style.color = isError ? 'var(--danger-color)' : '';
    }

    function friendlyLoadError(error) {
        const messages = {
            MAP_SERVER_UNAVAILABLE: '\ub9f5 \uc11c\ubc84\uac00 \uc2e4\ud589 \uc911\uc778\uc9c0 \ud655\uc778\ud558\uc138\uc694.',
            LOCALIZATION_NOT_ACTIVE: 'map_server\uc640 AMCL\uc774 \ud65c\uc131 \uc0c1\ud0dc\uc778\uc9c0 \ud655\uc778\ud558\uc138\uc694.',
            MAPPING_MODE_ACTIVE: 'Mapping \ubaa8\ub4dc\uc5d0\uc11c\ub294 \uc800\uc7a5 \uc9c0\ub3c4\ub97c \ubd88\ub7ec\uc62c \uc218 \uc5c6\uc2b5\ub2c8\ub2e4.',
            MAP_VERIFICATION_FAILED: '\uc9c0\ub3c4 \uba54\ud0c0\ub370\uc774\ud130 \ud655\uc778\uc5d0 \uc2e4\ud328\ud588\uc2b5\ub2c8\ub2e4.',
            AMCL_VERIFICATION_FAILED: '\u0041\u004d\u0043\u004c \ucd08\uae30 \uc704\uce58\ub97c \ud655\uc778\ud558\uc9c0 \ubabb\ud588\uc2b5\ub2c8\ub2e4.',
            INITIAL_POSE_OUT_OF_BOUNDS: '\ucd08\uae30 \uc704\uce58\uac00 \uc120\ud0dd\ud55c \uc9c0\ub3c4 \ubc94\uc704\ub97c \ubc97\uc5b4\ub0a9\ub2c8\ub2e4.',
            MAP_LOAD_IN_PROGRESS: '\ub2e4\ub978 \uc9c0\ub3c4 \ubd88\ub7ec\uc624\uae30\uac00 \ucc98\ub9ac \uc911\uc785\ub2c8\ub2e4.',
            MAP_OPERATION_IN_PROGRESS: '\ub2e4\ub978 \uc800\uc7a5 \uc9c0\ub3c4 \uc791\uc5c5\uc774 \ucc98\ub9ac \uc911\uc785\ub2c8\ub2e4.',
            MAP_NAME_ALREADY_EXISTS: '\uc774\ubbf8 \uac19\uc740 \uc774\ub984\uc758 \uc800\uc7a5 \uc9c0\ub3c4\uac00 \uc788\uc2b5\ub2c8\ub2e4.',
            MAP_NAME_UNCHANGED: '\uc0c8 \uc9c0\ub3c4 \uc774\ub984\uc774 \uae30\uc874 \uc774\ub984\uacfc \uac19\uc2b5\ub2c8\ub2e4.',
            INVALID_MAP_NAME: '\uc9c0\ub3c4 \uc774\ub984\uc740 \uc601\ubb38, \uc22b\uc790, \ub9c8\uce68\ud45c, \ud558\uc774\ud508, \ubc11\uc904\ub9cc \uc0ac\uc6a9\ud560 \uc218 \uc788\uc2b5\ub2c8\ub2e4.'
        };
        return messages[error.code] || error.message || labels.unavailable;
    }

    async function renameSavedMap(map, container, progress) {
        if (state.busy) return;
        const requestedName = window.prompt(labels.renamePrompt, map.map_name);
        if (requestedName === null) return;
        const newMapName = requestedName.trim();
        if (!newMapName) {
            showMessage(progress, friendlyLoadError({ code: 'INVALID_MAP_NAME' }), true);
            return;
        }

        state.busy = true;
        container.querySelectorAll('button, input').forEach(element => { element.disabled = true; });
        showMessage(progress, labels.renaming);
        try {
            const token = await csrfToken();
            const payload = await requestJson('/api/navigation/maps/rename', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': token },
                body: JSON.stringify({ map_name: map.map_name, new_map_name: newMapName })
            });
            const [active, maps] = await Promise.all([
                refreshActiveMap(),
                requestJson('/api/navigation/maps')
            ]);
            state.maps = maps.maps || [];
            buildModal(
                state.maps,
                active,
                `${payload.map.map_name} ${labels.renameSuccess}`
            );
        } catch (error) {
            showMessage(progress, `\uc9c0\ub3c4 \uc774\ub984 \ubcc0\uacbd \uc2e4\ud328: ${friendlyLoadError(error)}`, true);
            container.querySelectorAll('button, input').forEach(element => { element.disabled = false; });
        } finally {
            state.busy = false;
        }
    }

    async function loadSelectedMap(container, progress) {
        const mapName = selectedMapName(container);
        if (!mapName || state.busy) return;
        if (!window.confirm(`${mapName}${labels.confirmSuffix}`)) return;

        const x = Number(container.querySelector('#saved-map-pose-x').value);
        const y = Number(container.querySelector('#saved-map-pose-y').value);
        const yawDegrees = Number(container.querySelector('#saved-map-pose-yaw').value);
        if (![x, y, yawDegrees].every(Number.isFinite)) {
            showMessage(progress, '\ucd08\uae30 \uc704\uce58\uc5d0\ub294 \uc720\ud55c \uc22b\uc790\ub9cc \uc785\ub825\ud560 \uc218 \uc788\uc2b5\ub2c8\ub2e4.', true);
            return;
        }

        state.busy = true;
        container.querySelectorAll('button, input').forEach(element => { element.disabled = true; });
        showMessage(progress, labels.loading);
        const progressTimer = window.setTimeout(() => showMessage(progress, labels.resetting), 700);
        const verificationTimer = window.setTimeout(() => showMessage(progress, labels.verifying), 1800);
        try {
            const token = await csrfToken();
            const payload = await requestJson('/api/navigation/maps/load', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': token },
                body: JSON.stringify({
                    map_name: mapName,
                    initial_pose: { x, y, yaw_degrees: yawDegrees }
                })
            });
            showMessage(progress, `${payload.active_map.map_name} ${labels.success}`);
            await refreshActiveMap();
            window.setTimeout(closeMapModal, 700);
        } catch (error) {
            showMessage(progress, `\uc9c0\ub3c4 \ubd88\ub7ec\uc624\uae30 \uc2e4\ud328: ${friendlyLoadError(error)}`, true);
            container.querySelectorAll('button, input').forEach(element => { element.disabled = false; });
        } finally {
            window.clearTimeout(progressTimer);
            window.clearTimeout(verificationTimer);
            state.busy = false;
        }
    }

    function buildModal(maps, activeResponse, feedback = '', feedbackIsError = false) {
        const modal = document.getElementById('commonModal');
        const title = document.getElementById('modalTitle');
        const body = document.getElementById('modalBody');
        if (!modal || !title || !body) return;
        title.textContent = labels.title;
        body.replaceChildren();
        const container = create('div', 'saved-map-modal');
        container.append(create('p', 'saved-map-description', `${labels.description} ${labels.renameHint}`));
        const list = create('div', 'saved-map-list');
        const activeName = activeResponse?.active_map?.map_name;
        for (const map of maps) {
            const option = create('label', 'saved-map-option');
            option.title = labels.renameHint;
            const radio = create('input');
            radio.type = 'radio';
            radio.name = 'saved-navigation-map';
            radio.value = map.map_name;
            radio.checked = map.map_name === activeName || (!activeName && map === maps[0]);
            const details = create('div');
            const heading = create('div', 'saved-map-name-row');
            heading.append(create('span', 'saved-map-name', map.map_name));
            if (map.active || map.map_name === activeName) heading.append(create('span', 'saved-map-active', 'ACTIVE'));
            const mapDetails = `${formatSavedAt(map.saved_at)} | ${map.width} x ${map.height} | ${Number(map.resolution).toFixed(2)}m`;
            details.append(heading, create('div', 'saved-map-details', mapDetails));
            option.append(radio, details);
            option.addEventListener('contextmenu', event => {
                event.preventDefault();
                renameSavedMap(map, container, progress);
            });
            list.append(option);
        }
        if (!maps.length) list.append(create('div', 'saved-map-details', labels.noMaps));
        container.append(list);

        const pose = create('div', 'saved-map-pose');
        for (const [id, label] of [
            ['saved-map-pose-x', labels.positionX],
            ['saved-map-pose-y', labels.positionY],
            ['saved-map-pose-yaw', labels.heading]
        ]) {
            const field = create('label', '', label);
            const input = create('input');
            input.id = id;
            input.type = 'number';
            input.step = 'any';
            input.value = '0';
            field.append(input);
            pose.append(field);
        }
        container.append(pose);
        const progress = create('div', 'saved-map-progress', feedback);
        if (feedback) showMessage(progress, feedback, feedbackIsError);
        container.append(progress);
        const actions = create('div', 'saved-map-actions');
        const cancel = create('button', '', labels.cancel);
        cancel.type = 'button';
        cancel.addEventListener('click', closeMapModal);
        const load = create('button', 'saved-map-load', labels.load);
        load.type = 'button';
        load.disabled = !maps.length;
        load.addEventListener('click', () => loadSelectedMap(container, progress));
        actions.append(cancel, load);
        container.append(actions);
        body.append(container);
        modal.style.display = 'flex';
    }

    async function openSavedMapModal() {
        try {
            const [active, maps] = await Promise.all([
                refreshActiveMap(),
                requestJson('/api/navigation/maps')
            ]);
            state.maps = maps.maps || [];
            buildModal(state.maps, active);
        } catch (error) {
            const modal = document.getElementById('commonModal');
            const title = document.getElementById('modalTitle');
            const body = document.getElementById('modalBody');
            if (!modal || !title || !body) return;
            title.textContent = labels.title;
            body.textContent = `\uc9c0\ub3c4 \ubaa9\ub85d \uc870\ud68c \uc2e4\ud328: ${error.message}`;
            modal.style.display = 'flex';
        }
    }

    function initialize() {
        window.openSavedMapModal = openSavedMapModal;
        refreshActiveMap();
        window.setInterval(refreshActiveMap, 3000);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initialize, { once: true });
    } else {
        initialize();
    }
})();
