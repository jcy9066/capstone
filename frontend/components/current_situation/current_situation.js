(function initializeCurrentSituation(global) {
    'use strict';

    const components = global.DabomDashboardComponents = global.DabomDashboardComponents || {};
    const currentSituation = components.currentSituation = components.currentSituation || {};

    currentSituation.mount = function mountCurrentSituation(root, handlers = {}) {
        if (!root) return null;
        root.dataset.dashboardComponent = 'current-situation';
        const controller = {
            root,
            open() { return handlers.open?.(); },
            close() { return handlers.close?.(); },
        };
        currentSituation.controller = controller;
        return controller;
    };
})(window);
