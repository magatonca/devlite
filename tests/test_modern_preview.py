import unittest
import xml.etree.ElementTree as ET
from pipeline.devlite.modern_preview import panel,render_channel,wallpaper,check_space,RESERVE

PANEL = """<channel name="xfce4-panel" version="1.0"><property name="panels" type="array"><value type="int" value="1"/><property name="panel-1" type="empty"><property name="plugin-ids" type="array"><value type="int" value="1"/><value type="int" value="2"/></property></property></property><property name="plugins" type="empty"><property name="plugin-1" type="string" value="whiskermenu"/><property name="plugin-2" type="string" value="pulseaudio"><property name="enable-keyboard-shortcuts" type="bool" value="true"/></property></property></channel>"""
class ModernPreviewTests(unittest.TestCase):
    def test_preserves_plugin_tree_and_ids(self):
        before=ET.fromstring(PANEL);after=ET.fromstring(panel(PANEL))
        for path in ["property[@name='plugins']","property[@name='panels']/property[@name='panel-1']/property[@name='plugin-ids']"]:
            self.assertEqual(ET.tostring(before.find(path)),ET.tostring(after.find(path)))
    def test_bottom_opaque_no_autohide(self):
        p=ET.fromstring(panel(PANEL)).find("property[@name='panels']/property[@name='panel-1']")
        values={x.get('name'):x.get('value') for x in p}
        self.assertEqual(values['position'],'p=10;x=0;y=0')
        self.assertEqual(values['enter-opacity'],'100');self.assertEqual(values['leave-opacity'],'100')
        self.assertEqual(values['autohide-behavior'],'0')
    def test_panel_idempotent(self):self.assertEqual(panel(panel(PANEL)),panel(PANEL))
    def test_rejects_other_channel(self):
        with self.assertRaises(ValueError):panel(PANEL.replace('xfce4-panel','other'))
    def test_rejects_extra_panel(self):
        with self.assertRaises(ValueError):panel(PANEL.replace('<value type="int" value="1"/>','<value type="int" value="1"/><value type="int" value="2"/>',1))
    def test_rejects_duplicate_property(self):
        bad=PANEL.replace('<property name="panel-1" type="empty">','<property name="panel-1" type="empty"><property name="size"/><property name="size"/>')
        with self.assertRaises(ValueError):panel(bad)
    def test_preserves_unrelated_channel_properties(self):
        text='<channel name="xsettings"><property name="Net" type="empty"><property name="Other" type="string" value="keep"/></property></channel>'
        out=render_channel(text,'xsettings',[('Net/ThemeName','string','Greybird-dark')]);root=ET.fromstring(out)
        self.assertEqual(root.find("property/property[@name='Other']").get('value'),'keep')
        self.assertEqual(root.find("property/property[@name='ThemeName']").get('value'),'Greybird-dark')
    def test_rejects_wrong_channel(self):
        with self.assertRaises(ValueError):render_channel('<channel name="other"/>','xsettings',[])
    def test_reserve_not_relaxed(self):
        with self.assertRaises(ValueError):check_space(RESERVE)
        check_space(RESERVE+16*1024**2)
    def test_wallpaper_static_self_contained(self):
        text=wallpaper();ET.fromstring(text)
        for forbidden in ['<script','<image','<animate','<filter','href=']:
            self.assertNotIn(forbidden,text)
        self.assertIn('#171c24',text);self.assertIn('#348bd6',text)
