(function initializeRecordFilters(global) {
    'use strict';

    const components = global.DabomDashboardComponents = global.DabomDashboardComponents || {};
    const records = components.records = components.records || {};

    records.createFilterState = function createFilterState(initialValues = {}) {
        const initial = { ...initialValues };
        let values = { ...initial };
        return {
            get values() { return { ...values }; },
            update(nextValues = {}) {
                values = { ...values, ...nextValues };
                return this.values;
            },
            reset() {
                values = { ...initial };
                return this.values;
            },
        };
    };
})(window);
