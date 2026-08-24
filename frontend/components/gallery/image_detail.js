(function initializeImageDetail(global) {
    'use strict';

    const components = global.DabomDashboardComponents = global.DabomDashboardComponents || {};
    const gallery = components.gallery = components.gallery || {};

    gallery.mountImageDetail = function mountImageDetail(handlers = {}) {
        const controller = {
            open(index) { return handlers.open?.(index); },
            close() { return handlers.close?.(); },
            change(offset) { return handlers.change?.(offset); },
        };
        gallery.imageDetail = controller;
        return controller;
    };
})(window);
