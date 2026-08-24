(function initializeRecordPagination(global) {
    'use strict';

    const components = global.DabomDashboardComponents = global.DabomDashboardComponents || {};
    const records = components.records = components.records || {};

    records.DEFAULT_PAGE_SIZE = 50;
    records.createPaginationState = function createPaginationState(options = {}) {
        let page = Math.max(1, Number(options.page) || 1);
        let total = Math.max(0, Number(options.total) || 0);
        const pageSize = Math.max(1, Number(options.pageSize) || records.DEFAULT_PAGE_SIZE);
        return {
            get page() { return page; },
            get pageSize() { return pageSize; },
            get total() { return total; },
            get totalPages() { return Math.max(1, Math.ceil(total / pageSize)); },
            setPage(nextPage) {
                page = Math.min(Math.max(1, Number(nextPage) || 1), this.totalPages);
                return page;
            },
            setTotal(nextTotal) {
                total = Math.max(0, Number(nextTotal) || 0);
                page = Math.min(page, this.totalPages);
                return total;
            },
            reset() {
                page = 1;
            },
        };
    };
})(window);
