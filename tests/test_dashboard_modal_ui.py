import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPONENTS = ROOT / "frontend" / "components"
TEMPLATE = (ROOT / "frontend" / "templates" / "index.html").read_text(encoding="utf-8")
STYLE = (ROOT / "frontend" / "services" / "static" / "style.css").read_text(encoding="utf-8")


class DashboardModalUiTests(unittest.TestCase):
    def test_header_and_backdrop_always_close_the_complete_modal_stack(self):
        source = r"""
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');

class FakeNode {}
class FakeElement extends FakeNode {
    constructor() {
        super();
        this.listeners = {};
        this.dataset = {};
        this.style = {};
        this.scrollTop = 0;
        this.innerHTML = '';
        this.textContent = '';
    }
    addEventListener(name, handler) { this.listeners[name] = handler; }
    querySelector(selector) { return selector === '[data-modal-close]' ? closeButton : null; }
    replaceChildren(value) { this.child = value; }
    dispatch(name, target = this) {
        this.listeners[name]?.({ target, preventDefault() {} });
    }
}

const closeButton = new FakeElement();
const root = new FakeElement();
const title = new FakeElement();
const body = new FakeElement();
const context = { console, Node: FakeNode };
context.window = context;
vm.createContext(context);
vm.runInContext(fs.readFileSync('frontend/components/modal/modal_manager.js', 'utf8'), context);

const Manager = context.DabomDashboardComponents.modal.ModalManager;
const manager = new Manager({ root, title, body });
manager.register('records', { title: 'records', render: () => 'records' });
manager.register('detail', { title: 'detail', render: () => 'detail' });

(async () => {
    await manager.open('records');
    await manager.open('detail');
    assert.strictEqual(manager.stack.length, 1);
    closeButton.dispatch('click');
    assert.strictEqual(manager.activeView, null);
    assert.strictEqual(manager.stack.length, 0);
    assert.strictEqual(root.style.display, 'none');

    await manager.open('records');
    await manager.open('detail');
    root.dispatch('click', body);
    assert.strictEqual(manager.activeView.name, 'detail');
    root.dispatch('click', root);
    assert.strictEqual(manager.activeView, null);
    assert.strictEqual(manager.stack.length, 0);
})().catch(error => { console.error(error); process.exitCode = 1; });
"""
        completed = subprocess.run(
            ["node", "-e", source], cwd=ROOT, capture_output=True, text=True, check=False
        )
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)

    def test_detail_back_is_distinct_from_common_close(self):
        gallery = (COMPONENTS / "gallery" / "image_detail.js").read_text(encoding="utf-8")
        current = (COMPONENTS / "current_situation" / "current_situation.js").read_text(encoding="utf-8")
        modal = (COMPONENTS / "modal" / "modal_manager.js").read_text(encoding="utf-8")

        self.assertIn('data-modal-close', TEMPLATE)
        self.assertNotIn('onclick="closeModal()"', TEMPLATE)
        self.assertIn("if (event.target === this.root) this.close();", modal)
        self.assertIn('data-detail-back>← 이전 화면</button>', gallery)
        self.assertIn("manager.back()", gallery)
        self.assertIn("close() { return manager?.close()", gallery)
        self.assertNotIn("stopImmediatePropagation", current)

        records = (COMPONENTS / "records" / "record_modal.js").read_text(encoding="utf-8")
        controller_close = records.split("            close() {", 1)[1].split("            },", 1)[0]
        self.assertIn("manager.close()", controller_close)
        self.assertNotIn("manager.back()", controller_close)

    def test_toolbar_dom_and_tab_order_matches_visible_order(self):
        toolbar_start = TEMPLATE.index('id="records-toolbar-mount"')
        toolbar_end = TEMPLATE.index("\n            </div>\n        </div>", toolbar_start)
        toolbar = TEMPLATE[toolbar_start:toolbar_end]
        views = ("patrolModal", "galleryModal", "currentSituation", "actionsModal", "statusModal")
        positions = [toolbar.index(f'data-record-view="{view}"') for view in views]

        self.assertEqual(positions, sorted(positions))
        self.assertNotIn('data-record-view="patrolModal"] { order:', STYLE)
        self.assertNotIn('.current-situation-record-btn { order:', STYLE)

    def test_scoped_component_assets_are_cache_busted_consistently(self):
        version = "?v=20260827-dashboard-visual-assets"
        for asset in (
            "/components/modal/modal.css",
            "/components/controls/controls.css",
            "/components/modal/modal_manager.js",
            "/components/gallery/image_detail.js",
            "/components/current_situation/current_situation.js",
        ):
            self.assertIn(f'{asset}{version}', TEMPLATE)


if __name__ == "__main__":
    unittest.main()
