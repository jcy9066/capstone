(function initializeNavigationModeControl(global) {
    'use strict';

    const components = global.DabomDashboardComponents = global.DabomDashboardComponents || {};
    const controls = components.controls = components.controls || {};

    controls.mountNavigationMode = function mountNavigationMode(root, handlers = {}) {
        if (!root) return null;
        root.dataset.dashboardComponent = 'navigation-mode-control';
        const controller = {
            root,
            request(mode) { return handlers.request?.(mode); },
            sync(mode) {
                root.dataset.navigationMode = mode || '';
                handlers.sync?.(mode);
            },
        };
        controls.navigationMode = controller;
        return controller;
    };
})(window);
