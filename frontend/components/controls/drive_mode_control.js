(function initializeDriveModeControl(global) {
    'use strict';

    const components = global.DabomDashboardComponents = global.DabomDashboardComponents || {};
    const controls = components.controls = components.controls || {};

    controls.mountDriveMode = function mountDriveMode(root, handlers = {}) {
        if (!root) return null;
        root.dataset.dashboardComponent = 'drive-mode-control';
        const controller = {
            root,
            request(mode) { return handlers.request?.(mode); },
            sync(mode) {
                root.dataset.driveMode = mode || '';
                handlers.sync?.(mode);
            },
        };
        controls.driveMode = controller;
        return controller;
    };
})(window);
