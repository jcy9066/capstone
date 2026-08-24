(function initializeRecordModal(global) {
    'use strict';

    const components = global.DabomDashboardComponents = global.DabomDashboardComponents || {};
    const records = components.records = components.records || {};

    const ACTION_LABELS = Object.freeze({
        WARNING: '경고',
        MANUAL_MOVING: '수동 주행',
        REPORT: '신고',
        COMMUNICATION: '직접 통신',
        NOTE: '상황 기록',
    });
    const TITLES = Object.freeze({
        statusModal: '기기 상태 조회',
        patrolModal: '순찰 기록 조회',
        actionsModal: '관리자 조치 조회',
    });
    const DEFAULT_SORT = Object.freeze({
        statusModal: 'recorded_at',
        patrolModal: 'detected_at',
        actionsModal: 'created_at',
    });

    function initialFilters() {
        return {
            startAt: '', endAt: '', eventType: '', confidenceMin: '', confidenceMax: '',
            isResolved: '', isReported: '', isAlerted: '', isFalseAlarm: '',
            userName: '', actionType: '',
        };
    }

    function valueClass(value, warn, danger) {
        const numeric = Number(value);
        if (!Number.isFinite(numeric)) return '';
        if (numeric > danger) return 'danger';
        if (numeric > warn) return 'warn';
        return '';
    }

    function imageCell(row, source, index) {
        if (!row.has_image || !row.image_url) return '<span class="muted">-</span>';
        const label = source === 'event' ? '순찰 기록 이미지 상세 열기' : '관리자 조치 이미지 상세 열기';
        return `<button type="button" class="record-thumbnail-button" data-image-row="${index}" aria-label="${label}"><img class="record-thumbnail" src="${records.escapeHtml(row.image_url)}" alt="${label}" loading="lazy"></button>`;
    }

    function rowTimestamp(row) {
        return `${records.escapeHtml(row.date || '-')}<br><span class="muted">${records.escapeHtml(row.time || '-')}</span>`;
    }

    function columnsFor(type) {
        if (type === 'statusModal') return [
            { label: '기록 시간', sort: 'recorded_at' },
            { label: 'CPU 사용률', sort: 'cpu_usage' },
            { label: 'CPU 온도', sort: 'cpu_temperature' },
            { label: 'RAM 사용률', sort: 'ram_usage' },
            { label: 'Ping', sort: 'ping' },
            { label: 'Battery' },
            { label: '주행' },
            { label: '속도', sort: 'speed' },
            { label: 'GPS (위도/경도/고도)' },
            { label: 'LiDAR (X/Y)' },
        ];
        if (type === 'patrolModal') return [
            { label: '기록 시간', sort: 'detected_at' },
            { label: '유형', sort: 'event_type' },
            { label: '신뢰도', sort: 'confidence' },
            { label: 'LiDAR (X/Y)' },
            { label: 'GPS (위도/경도/고도)' },
            { label: '조치', sort: 'is_resolved' },
            { label: '신고', sort: 'is_reported' },
            { label: '경고', sort: 'is_alerted' },
            { label: '오탐', sort: 'is_false_alarm' },
            { label: '이미지' },
        ];
        return [
            { label: '기록 시간', sort: 'created_at' },
            { label: '관리자', sort: 'user_name' },
            { label: '조치 유형', sort: 'action_type' },
            { label: '관련 이벤트', sort: 'event_id' },
            { label: '내용' },
            { label: '이미지' },
        ];
    }

    class RecordViewController {
        constructor(type, manager) {
            this.type = type;
            this.manager = manager;
            this.filters = records.createFilterState(initialFilters());
            this.pagination = records.createPaginationState();
            this.sort = { by: DEFAULT_SORT[type], direction: 'desc', touched: false };
            this.rows = [];
            this.loadState = 'idle';
            this.message = '';
            this.metadata = { page: 1, page_size: 50, total: 0, total_pages: 0 };
            this.requestVersion = 0;
            this.cycleControllers = [];
            this.tableScrollTop = 0;
        }

        snapshot() {
            return {
                filters: this.filters.values,
                pagination: this.pagination.snapshot(),
                sort: { ...this.sort },
                rows: this.rows.map(row => ({ ...row })),
                loadState: this.loadState,
                message: this.message,
                metadata: { ...this.metadata },
                tableScrollTop: this.root()?.querySelector('.modal-table-wrapper')?.scrollTop || 0,
            };
        }

        restore(snapshot) {
            if (!snapshot) {
                this.filters.reset();
                this.pagination = records.createPaginationState();
                this.sort = { by: DEFAULT_SORT[this.type], direction: 'desc', touched: false };
                this.rows = [];
                this.loadState = 'idle';
                this.message = '';
                this.metadata = { page: 1, page_size: 50, total: 0, total_pages: 0 };
                this.tableScrollTop = 0;
                return;
            }
            this.filters.replace(snapshot.filters);
            this.pagination.update(snapshot.pagination || snapshot.metadata);
            this.sort = { ...this.sort, ...(snapshot.sort || {}) };
            this.rows = Array.isArray(snapshot.rows) ? snapshot.rows.map(row => ({ ...row })) : [];
            this.loadState = snapshot.loadState || 'ready';
            this.message = snapshot.message || '';
            this.metadata = { ...this.metadata, ...(snapshot.metadata || {}) };
            this.tableScrollTop = Math.max(0, Number(snapshot.tableScrollTop) || 0);
        }

        filterControls() {
            const dateRange = `
                <label>시작 <input type="datetime-local" step="1" data-filter="startAt"></label>
                <span class="filter-sep">~</span>
                <label>종료 <input type="datetime-local" step="1" data-filter="endAt"></label>`;
            if (this.type === 'patrolModal') return `${dateRange}
                <button type="button" class="record-cycle-filter" data-cycle="eventType"></button>
                <label>신뢰도 <input class="confidence-filter" type="number" min="0" max="100" step="1" data-filter="confidenceMin" placeholder="최소 %" aria-label="최소 신뢰도"></label>
                <label><input class="confidence-filter" type="number" min="0" max="100" step="1" data-filter="confidenceMax" placeholder="최대 %" aria-label="최대 신뢰도"></label>
                <button type="button" class="record-cycle-filter" data-cycle="resolved"></button>
                <button type="button" class="record-cycle-filter" data-cycle="reported"></button>
                <button type="button" class="record-cycle-filter" data-cycle="alerted"></button>
                <button type="button" class="record-cycle-filter" data-cycle="falseAlarm"></button>`;
            if (this.type === 'actionsModal') return `${dateRange}
                <label>관리자 <input type="search" data-filter="userName" placeholder="이름 일부 검색"></label>
                <button type="button" class="record-cycle-filter" data-cycle="actionType"></button>`;
            return dateRange;
        }

        build() {
            const columns = columnsFor(this.type);
            return `<section class="records-view records-view-${this.type}" data-dashboard-modal-view data-record-type="${this.type}">
                <div class="modal-filter-bar record-filter-bar">
                    ${this.filterControls()}
                    <button type="button" class="filter-btn" data-action="query">조회</button>
                    <button type="button" class="filter-btn secondary" data-action="reset">초기화</button>
                    <span class="filter-count" data-record-count>총 <span>${Number(this.metadata.total) || 0}</span> 건</span>
                </div>
                <p class="record-filter-error" data-filter-error role="alert"></p>
                <div class="modal-table-wrapper">
                    <table class="data-table record-data-table">
                        <thead><tr>${records.tableHeaderHtml(columns, this.sort)}</tr></thead>
                        <tbody data-record-tbody></tbody>
                    </table>
                </div>
                <nav class="records-pagination" data-record-pagination aria-label="기록 페이지" hidden></nav>
            </section>`;
        }

        root() { return this.manager.body?.querySelector('[data-dashboard-modal-view]'); }

        setInputValues() {
            const root = this.root();
            const values = this.filters.values;
            root?.querySelectorAll('[data-filter]').forEach(input => {
                const value = values[input.dataset.filter];
                if (input.dataset.filter === 'confidenceMin' || input.dataset.filter === 'confidenceMax') {
                    input.value = value === '' || value == null ? '' : String(Number(value) * 100);
                } else {
                    input.value = value ?? '';
                }
            });
        }

        bind() {
            const root = this.root();
            if (!root) return;
            this.cycleControllers = [];
            this.setInputValues();
            root.querySelectorAll('[data-cycle]').forEach(button => {
                const key = button.dataset.cycle;
                const options = records.CYCLE_FILTER_OPTIONS[key] || [];
                const filterKey = {
                    eventType: 'eventType', resolved: 'isResolved', reported: 'isReported',
                    alerted: 'isAlerted', falseAlarm: 'isFalseAlarm', actionType: 'actionType',
                }[key];
                const currentValue = this.filters.values[filterKey];
                const index = Math.max(0, options.findIndex(option => option.value === currentValue));
                const CycleFilterButton = components.controls?.CycleFilterButton;
                if (!CycleFilterButton) return;
                this.cycleControllers.push(new CycleFilterButton(button, {
                    options, index,
                    onChange: value => {
                        this.filters.update({ [filterKey]: value });
                        this.pagination.reset();
                    },
                }));
            });
            root.querySelector('[data-action="query"]')?.addEventListener('click', () => this.query());
            root.querySelector('[data-action="reset"]')?.addEventListener('click', () => this.reset());
            root.querySelectorAll('[data-filter]').forEach(input => {
                input.addEventListener('input', () => this.pagination.reset());
                input.addEventListener('keydown', event => {
                    if (event.key === 'Enter') this.query();
                });
            });
            records.bindSortHeaders(root, sortBy => this.changeSort(sortBy));
        }

        collectFilters() {
            const root = this.root();
            const range = records.readDateTimeRange(root);
            const next = { ...this.filters.values, ...range };
            root?.querySelectorAll('[data-filter]').forEach(input => {
                const key = input.dataset.filter;
                if (key === 'confidenceMin' || key === 'confidenceMax') {
                    next[key] = input.value === '' ? '' : Number(input.value) / 100;
                } else {
                    next[key] = input.value.trim();
                }
            });
            if (next.confidenceMin !== '' && next.confidenceMax !== '' && next.confidenceMin > next.confidenceMax) {
                throw new Error('최대 신뢰도는 최소 신뢰도보다 작을 수 없습니다.');
            }
            this.filters.replace(next);
        }

        async query() {
            try {
                this.collectFilters();
                this.pagination.reset();
                this.setFilterError('');
                await this.load();
            } catch (error) {
                this.setFilterError(error.message);
            }
        }

        async reset() {
            this.filters.reset();
            this.pagination.reset();
            this.sort = { by: DEFAULT_SORT[this.type], direction: 'desc', touched: false };
            this.manager.setBody(this.build());
            this.bind();
            await this.load();
        }

        async changeSort(sortBy) {
            if (!this.sort.touched || this.sort.by !== sortBy) {
                this.sort = { by: sortBy, direction: 'desc', touched: true };
            } else {
                this.sort.direction = this.sort.direction === 'desc' ? 'asc' : 'desc';
            }
            this.pagination.reset();
            await this.load();
        }

        setFilterError(message) {
            const target = this.root()?.querySelector('[data-filter-error]');
            if (target) target.textContent = message || '';
        }

        requestFilters() {
            return {
                ...this.filters.values,
                page: this.pagination.page,
                pageSize: records.DEFAULT_PAGE_SIZE,
                sortBy: this.sort.by,
                sortDirection: this.sort.direction,
            };
        }

        async load() {
            const version = ++this.requestVersion;
            this.loadState = 'loading';
            this.message = '';
            this.renderRows();
            const result = await global.DabomDashboardState?.fetchLogRows(this.type, this.requestFilters());
            if (version !== this.requestVersion || !result) return;
            this.loadState = result.state;
            this.message = result.message || '';
            this.rows = Array.isArray(result.rows) ? result.rows : [];
            this.metadata = {
                page: result.page || this.pagination.page,
                page_size: result.page_size || records.DEFAULT_PAGE_SIZE,
                total: result.total || 0,
                total_pages: result.total_pages || 0,
            };
            this.pagination.update(this.metadata);
            this.renderRows();
        }

        rowHtml(row, index) {
            if (this.type === 'statusModal') return `<tr>
                <td>${rowTimestamp(row)}</td>
                <td class="${valueClass(row.cpu_usage, 60, 80)}">${records.formatValue(row.cpu_usage, '%')}</td>
                <td class="${valueClass(row.cpu_temperature, 65, 80)}">${records.formatValue(row.cpu_temperature, '°C')}</td>
                <td class="${valueClass(row.ram_usage, 60, 80)}">${records.formatValue(row.ram_usage, '%')}</td>
                <td class="${valueClass(row.ping, 100, 150)}">${records.formatValue(row.ping, 'ms')}</td>
                <td>${records.formatValue(row.battery_level, '%')}</td>
                <td>${records.formatBoolean(row.is_autonomous, '자동', '수동')}</td>
                <td>${records.formatValue(row.speed)}</td>
                <td class="muted">${records.formatValue(row.gps_lat)} / ${records.formatValue(row.gps_lng)} / ${records.formatValue(row.gps_alt)}</td>
                <td class="muted">${records.formatValue(row.lidar_x)} / ${records.formatValue(row.lidar_y)}</td>
            </tr>`;
            if (this.type === 'patrolModal') {
                const confidence = Number.isFinite(Number(row.confidence)) ? `${(Number(row.confidence) * 100).toFixed(1)}%` : '-';
                const eventId = Number(row.event_id);
                return `<tr>
                    <td>${rowTimestamp(row)}</td>
                    <td><span class="status-badge status-patrol">${records.escapeHtml(row.event_type)}</span></td>
                    <td>${confidence}</td>
                    <td class="muted">${records.formatValue(row.lidar_x)} / ${records.formatValue(row.lidar_y)}</td>
                    <td class="muted">${records.formatValue(row.gps_lat)} / ${records.formatValue(row.gps_lng)} / ${records.formatValue(row.gps_alt)}</td>
                    <td>${records.formatBoolean(row.is_resolved, '완료', '미조치')}</td>
                    <td>${records.formatBoolean(row.is_reported, '신고', '미신고')}</td>
                    <td>${records.formatBoolean(row.is_alerted, '경고', '미경고')}</td>
                    <td><span class="false-alarm-state ${row.is_false_alarm ? 'is-active' : ''}">${row.is_false_alarm ? '오탐' : '정상'}</span><button type="button" class="false-alarm-btn" data-false-alarm-row="${index}" ${Number.isFinite(eventId) ? '' : 'disabled'}>${row.is_false_alarm ? '오탐 취소' : '오탐 처리'}</button></td>
                    <td>${imageCell(row, 'event', index)}</td>
                </tr>`;
            }
            return `<tr>
                <td>${rowTimestamp(row)}</td>
                <td>${records.escapeHtml(row.administrator_name)}</td>
                <td><span class="status-badge status-normal">${records.escapeHtml(ACTION_LABELS[row.action_type] || row.action_type)}</span></td>
                <td>${row.event_id == null ? '-' : records.escapeHtml(row.event_id)}</td>
                <td class="record-description">${records.escapeHtml(row.description_content)}</td>
                <td>${imageCell(row, 'action', index)}</td>
            </tr>`;
        }

        renderRows() {
            const root = this.root();
            const tbody = root?.querySelector('[data-record-tbody]');
            const count = root?.querySelector('[data-record-count] span');
            if (!tbody) return;
            if (count) count.textContent = String(this.metadata.total || 0);
            if (this.loadState !== 'ready') {
                records.renderTableState(tbody, { state: this.loadState === 'idle' ? 'loading' : this.loadState, message: this.message, colspan: columnsFor(this.type).length });
            } else if (!this.rows.length) {
                records.renderTableState(tbody, { state: 'empty', colspan: columnsFor(this.type).length });
            } else {
                tbody.innerHTML = this.rows.map((row, index) => this.rowHtml(row, index)).join('');
            }
            root.querySelector('thead tr').innerHTML = records.tableHeaderHtml(columnsFor(this.type), this.sort);
            records.bindSortHeaders(root, sortBy => this.changeSort(sortBy));
            root.querySelectorAll('[data-image-row]').forEach(button => {
                button.addEventListener('click', () => components.gallery?.openRecordDetail?.(this.rows[Number(button.dataset.imageRow)], this.type));
            });
            root.querySelectorAll('[data-false-alarm-row]').forEach(button => {
                button.addEventListener('click', () => this.toggleFalseAlarm(Number(button.dataset.falseAlarmRow), button));
            });
            records.renderPagination(root.querySelector('[data-record-pagination]'), this.metadata, page => {
                this.pagination.setPage(page);
                this.load();
            });
            root.querySelector('.modal-table-wrapper').scrollTop = this.tableScrollTop;
        }

        async toggleFalseAlarm(index, button) {
            const row = this.rows[index];
            if (!row || !Number.isFinite(Number(row.event_id))) return;
            const nextValue = !row.is_false_alarm;
            button.disabled = true;
            button.textContent = '처리 중...';
            try {
                const csrfResponse = await fetch('/api/auth/csrf', { credentials: 'same-origin' });
                const csrf = await csrfResponse.json().catch(() => ({}));
                if (!csrfResponse.ok || !csrf.csrf_token) throw new Error('보안 토큰을 준비하지 못했습니다.');
                const response = await fetch(`/api/logs/events/${encodeURIComponent(row.event_id)}/false-alarm`, {
                    method: 'PATCH', credentials: 'same-origin',
                    headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf.csrf_token },
                    body: JSON.stringify({ is_false_alarm: nextValue }),
                });
                const data = await response.json().catch(() => ({}));
                if (!response.ok) throw new Error(data.detail || data.error || `HTTP ${response.status}`);
                await this.load();
            } catch (error) {
                this.setFilterError(error.message || '오탐 상태를 변경하지 못했습니다.');
                button.disabled = false;
                button.textContent = row.is_false_alarm ? '오탐 취소' : '오탐 처리';
            }
        }
    }

    records.mount = function mountRecords(root, handlers = {}) {
        if (!root) return null;
        root.dataset.dashboardComponent = 'records-toolbar';
        const manager = components.modal?.getDefault?.();
        const legacyOpen = handlers.open;
        const legacyClose = handlers.close;
        const viewControllers = {};

        if (manager) {
            Object.keys(TITLES).forEach(type => {
                const view = new RecordViewController(type, manager);
                viewControllers[type] = view;
                manager.register(type, {
                    title: TITLES[type],
                    render: (context, snapshot) => {
                        view.restore(snapshot);
                        return view.build();
                    },
                    onOpen: async (context, snapshot) => {
                        view.bind();
                        if (snapshot) view.renderRows();
                        else await view.load();
                    },
                    captureState: () => view.snapshot(),
                    restoreState: () => {
                        view.bind();
                        view.renderRows();
                    },
                });
            });
            components.gallery?.registerModalViews?.(manager);
        }

        const controller = {
            root,
            views: viewControllers,
            open(type) {
                if (manager && TITLES[type]) return manager.open(type, {}, { replace: true });
                if (manager && type === 'galleryModal') return components.gallery?.openGallery?.();
                return legacyOpen?.(type);
            },
            close() {
                if (manager?.activeView?.name === 'recordImageDetail' && manager.stack.length) {
                    return manager.back();
                }
                if (manager?.activeView) return manager.close();
                return legacyClose?.();
            },
        };
        records.controller = controller;

        if (manager) {
            global.openModal = type => controller.open(type);
            global.closeModal = () => controller.close();
            global.applyFilter = type => viewControllers[type]?.query();
            global.resetFilter = type => viewControllers[type]?.reset();
        }
        return controller;
    };
})(window);
