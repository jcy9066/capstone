(function initializeRecordTable(global) {
    'use strict';

    const components = global.DabomDashboardComponents = global.DabomDashboardComponents || {};
    const records = components.records = components.records || {};

    records.renderTableState = function renderTableState(target, options = {}) {
        if (!target) return false;
        const state = options.state || 'ready';
        if (state === 'ready') return false;
        const messages = {
            loading: '서버 데이터를 불러오는 중입니다.',
            empty: '조회된 데이터가 없습니다.',
            unavailable: '연결된 조회 API가 없습니다.',
            error: '서버 데이터를 불러오지 못했습니다.',
        };
        const message = options.message || messages[state] || messages.error;
        const row = document.createElement('tr');
        const cell = document.createElement('td');
        const content = document.createElement('div');
        cell.colSpan = options.colspan || 1;
        content.className = `table-empty is-${state}`;
        content.textContent = message;
        cell.appendChild(content);
        row.appendChild(cell);
        target.replaceChildren(row);
        return true;
    };
})(window);
