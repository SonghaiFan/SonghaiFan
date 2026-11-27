from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class SeriesRevisionTests(unittest.TestCase):
    def test_external_renderer_changes_update_the_project_revision(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            repo, source = base / 'project', base / 'shared'
            (repo / '.github/workflows').mkdir(parents=True)
            (source / 'assets/footers').mkdir(parents=True)
            (source / 'scripts').mkdir()
            (repo / 'README.md').write_text('# Project\n\nOriginal project description.\n')
            (repo / '.github/workflows/pages.yml').write_text('uses: SonghaiFan/SonghaiFan/.github/actions/series-footer@main\n')
            (source / 'assets/footers/frankie.html').write_text((ROOT / 'assets/footers/frankie.html').read_text())
            renderer = source / 'scripts/pages_footer.py'
            renderer.write_text((ROOT / 'scripts/pages_footer.py').read_text())
            command = ['python3', str(ROOT / 'scripts/apply-series-footer.py'), '--series', 'frankie',
                       '--templates-root', str(source), '--repo-root', str(repo)]
            subprocess.run(command, check=True, capture_output=True)
            revision = repo / '.github/series-footer.version'
            self.assertTrue(revision.exists(), 'A renderer update needs a project revision for the next Pages build')
            first = revision.read_text()
            subprocess.run(command, check=True, capture_output=True)
            self.assertEqual(first, revision.read_text())
            renderer.write_text(renderer.read_text() + '\n# New shared renderer version\n')
            subprocess.run(command, check=True, capture_output=True)
            self.assertNotEqual(first, revision.read_text())
            self.assertIn('Original project description.', (repo / 'README.md').read_text())

if __name__ == '__main__':
    unittest.main()
