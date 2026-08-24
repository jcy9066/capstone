(function initializeRecordModal(global) {
    'use strict';

    const components = global.DabomDashboardComponents = global.DabomDashboardComponents || {};
    const records = components.records = components.records || {};

    records.mount = function mountRecords(root, handlers = {}) {
        if (!root) return null;
        root.dataset.dashboardComponent = 'records-toolbar';
        const controller = {
            root,
            open(type) { return handlers.open?.(type); },
            close() { return handlers.close?.(); },
        };
        records.controller = controller;
        return controller;
    };
})(window);
