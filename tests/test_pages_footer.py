import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('pages_footer', ROOT / 'scripts/pages_footer.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class SharedPagesFooterTests(unittest.TestCase):
    def setUp(self):
        self.legacy = (ROOT / 'tests/fixtures/legacy-frankie-footer.html').read_text()
        self.template = (ROOT / 'assets/footers/frankie.html').read_text()
    def test_actual_legacy_page_gets_the_complete_current_banner(self):
        result = module.render(self.legacy, self.template, 'frankie')
        self.assertEqual(module.icons(result), module.icons(self.template, template=True))
    def test_render_preserves_the_project_body_signature_and_script(self):
        result = module.render(self.legacy, self.template, 'frankie')
        for element in ['<main id="content">Original project content</main>',
                        '<footer>Original signature</footer>', '<script>window.project=true</script>']:
            self.assertIn(element, result)
    def test_render_is_idempotent_and_has_one_banner(self):
        first = module.render(self.legacy, self.template, 'frankie')
        second = module.render(first, self.template, 'frankie')
        self.assertEqual(first, second)
        self.assertEqual(second.count('id="series-footer"'), 1)
    def test_pages_without_a_series_banner_are_preserved(self):
        content = '<html><body><nav aria-label="Page navigation">Docs</nav><main>App</main></body></html>'
        self.assertEqual(module.render(content, self.template, 'frankie'), content)

if __name__ == '__main__':
    unittest.main()
