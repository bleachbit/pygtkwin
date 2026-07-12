import importlib.util
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


MODULE_PATH = Path(__file__).with_name('filter_glib_gir.py')
SPEC = importlib.util.spec_from_file_location('filter_glib_gir', MODULE_PATH)
FILTER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FILTER)


class FilterGirTest(unittest.TestCase):
    def test_removes_only_symbols_defined_by_platform_gir(self):
        base = '''<?xml version="1.0"?>
<repository xmlns="http://www.gtk.org/introspection/core/1.0"
            xmlns:c="http://www.gtk.org/introspection/c/1.0">
  <namespace name="GLib" version="2.0">
    <function name="duplicate" c:identifier="g_win32_duplicate"/>
    <record name="Duplicate" c:type="GWin32Duplicate"/>
    <function-macro name="DLLMAIN" c:identifier="G_WIN32_DLLMAIN_FOR_DLL_NAME"/>
    <function name="base" c:identifier="g_base"/>
  </namespace>
</repository>
'''
        platform = '''<?xml version="1.0"?>
<repository xmlns="http://www.gtk.org/introspection/core/1.0"
            xmlns:c="http://www.gtk.org/introspection/c/1.0">
  <namespace name="GLibWin32" version="2.0">
    <function name="duplicate" c:identifier="g_win32_duplicate"/>
    <record name="Duplicate" c:type="GWin32Duplicate"/>
  </namespace>
</repository>
'''

        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            base_path = directory / 'GLib-2.0.gir'
            platform_path = directory / 'GLibWin32-2.0.gir'
            output_path = directory / 'GLib-2.0.filtered.gir'
            base_path.write_text(base)
            platform_path.write_text(platform)

            self.assertEqual(FILTER.filter_gir(base_path, platform_path, output_path), 2)

            namespace = next(iter(ET.parse(output_path).getroot()))
            identifiers = {
                element.get(FILTER.C_IDENTIFIER)
                for element in namespace
            }
            self.assertEqual(identifiers, {'G_WIN32_DLLMAIN_FOR_DLL_NAME', 'g_base'})

    def test_platform_girs_expose_glib_288_win32_api(self):
        glib = ET.parse(MODULE_PATH.with_name('GLibWin32-2.0.gir'))
        gio = ET.parse(MODULE_PATH.with_name('GioWin32-2.0.gir'))
        glib_namespace = next(element for element in glib.getroot() if element.tag.endswith('namespace'))
        gio_namespace = next(element for element in gio.getroot() if element.tag.endswith('namespace'))

        command_line = next(
            element for element in glib_namespace
            if element.get(FILTER.C_IDENTIFIER) == 'g_win32_get_command_line'
        )
        self.assertEqual(command_line.find('{*}return-value').get('transfer-ownership'), 'full')

        classes = {
            element.get('name'): element
            for element in gio_namespace
            if element.tag.endswith('class')
        }
        for class_name in ('InputStream', 'OutputStream'):
            methods = {
                element.get('name'): element
                for element in classes[class_name]
                if element.tag.endswith('method')
            }
            self.assertEqual(set(methods), {'get_close_handle', 'get_handle', 'set_close_handle'})
            for method in methods.values():
                self.assertIsNotNone(method.find('{*}parameters/{*}instance-parameter'))

        registry_backend = next(
            element for element in gio_namespace
            if element.get(FILTER.C_IDENTIFIER) == 'g_registry_settings_backend_new'
        )
        registry_key = registry_backend.find('{*}parameters/{*}parameter')
        self.assertEqual(registry_key.get('nullable'), '1')
        self.assertEqual(registry_key.get('allow-none'), '1')


if __name__ == '__main__':
    unittest.main()
