(function initializeNavigationModeControl(global) {
    'use strict';

    const components = global.DabomDashboardComponents = global.DabomDashboardComponents || {};
    const controls = components.controls = components.controls || {};
    const instances = controls.navigationModes = controls.navigationModes || [];

    function canRender(root) {
        return Boolean(root?.ownerDocument?.createElement && root.querySelector && root.append);
    }

    function ensureButtons(root) {
        if (!root?.querySelector) return [];
        let mapping = root.querySelector('#navigation-mode-mapping') || root.querySelector('[data-navigation-mode="MAPPING"]');
        let driving = root.querySelector('#navigation-mode-driving') || root.querySelector('[data-navigation-mode="DRIVING"]');
        if (!mapping && canRender(root)) {
            mapping = root.ownerDocument.createElement('button');
            mapping.type = 'button';
            mapping.textContent = 'Mapping';
            mapping.className = 'dashboard-mode-button';
            mapping.dataset.navigationMode = 'MAPPING';
            root.append(mapping);
        }
        if (!driving && canRender(root)) {
            driving = root.ownerDocument.createElement('button');
            driving.type = 'button';
            driving.textContent = 'Driving';
            driving.className = 'dashboard-mode-button';
            driving.dataset.navigationMode = 'DRIVING';
            root.append(driving);
        }
        if (mapping) mapping.dataset.navigationMode = 'MAPPING';
        if (driving) driving.dataset.navigationMode = 'DRIVING';
        return [mapping, driving].filter(Boolean);
    }

    controls.mountNavigationMode = function mountNavigationMode(root, handlers = {}) {
        if (!root) return null;
        root.dataset.dashboardComponent = 'navigation-mode-control';
        const existing = root._dabomNavigationModeController;
        if (existing) {
            existing.handlers = { ...existing.handlers, ...handlers };
            return existing;
        }
        const controller = {
            root,
            handlers,
            mode: '',
            pending: false,
            buttons: [],
            request(mode) {
                const normalized = String(mode || '').toUpperCase();
                const request = this.handlers.request || global.navigationControl?.requestNavigationMode;
                return request?.(normalized);
            },
            sync(mode, options = {}) {
                this.mode = String(mode || '').toUpperCase();
                this.pending = Boolean(options.pending);
                root.dataset.navigationMode = this.mode;
                this.buttons.forEach(button => {
                    const active = button.dataset.navigationMode === this.mode;
                    button.classList.toggle('active', active);
                    button.setAttribute('aria-pressed', String(active));
                    button.disabled = this.pending;
                });
                this.handlers.sync?.(this.mode, options);
            },
        };
        controller.buttons = ensureButtons(root);
        controller.buttons.forEach(button => {
            if (button.dataset.navigationModeBound === 'true') return;
            button.dataset.navigationModeBound = 'true';
            button.addEventListener('click', event => {
                event.preventDefault();
                event.stopPropagation();
                controller.request(button.dataset.navigationMode);
            });
        });
        root._dabomNavigationModeController = controller;
        instances.push(controller);
        controls.navigationMode = controller;
        return controller;
    };

    controls.syncNavigationMode = function syncNavigationMode(mode, options = {}) {
        instances.forEach(controller => controller.sync(mode, options));
    };
})(window);
