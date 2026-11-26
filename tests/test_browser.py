import copy
import json
import unittest
import tempfile
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path
from pipeline.devlite.browser import (validate, settings, replace_keys, effective_status,
    audit_transaction, audit_configuration, resolve_browser, selection_with_browser, FILES, HELPERS, MIMES, DESKTOP, REQUIRED_PACKAGES)
from pipeline.devlite.customize.manifest import SpecError
ROOT = Path(__file__).resolve().parents[1]

def status(packages):
    return '\n\n'.join('Package: '+k+'\nStatus: install ok installed\nArchitecture: amd64\nVersion: '+v for k,v in packages.items())+'\n'
def manifest(packages): return ''.join(k+'\t'+v+'\n' for k,v in packages.items())

class BrowserTests(unittest.TestCase):
    def test_native_ubuntu_both_views_and_no_execution(self):
        validate(json.loads((ROOT/'packages/browser.json').read_text()))
    def test_execution_snap_or_visual_flags_rejected(self):
        for key in ('snap_required','visual_changes','generate_iso','install_authorized','download_authorized'):
            with self.subTest(key=key):
                d=json.loads((ROOT/'packages/browser.json').read_text());d[key]=True
                with self.assertRaises(SpecError):validate(d)
    def test_missing_or_extra_package_rejected(self):
        d=json.loads((ROOT/'packages/browser.json').read_text());d['requested'].append('firefox')
        with self.assertRaises(SpecError):validate(d)
    def test_external_or_escaping_input_rejected(self):
        for value in ('/tmp/root','work/../other','work/a/b'):
            d=json.loads((ROOT/'packages/browser.json').read_text());d['input_job']=value
            with self.assertRaises(SpecError):validate(d)
    def test_helpers_preserve_other_preferences_and_comments(self):
        old='# defaults\nWebBrowser=firefox\nTerminalEmulator=xfce4-terminal\nFileManager=thunar\n'
        out=settings({HELPERS[0]:old})[HELPERS[0]]
        self.assertEqual(out,old.replace('WebBrowser=firefox','WebBrowser=epiphany'))
    def test_mime_merge_preserves_pdf_and_other_sections(self):
        key='etc/xdg/xfce-mimeapps.list'
        old='[Default Applications]\napplication/pdf=atril.desktop;\nx-scheme-handler/http=firefox.desktop;\n[Added Associations]\ntext/plain=mousepad.desktop;\n'
        out=settings({key:old})[key]
        self.assertIn('application/pdf=atril.desktop;',out)
        self.assertIn('[Added Associations]\ntext/plain=mousepad.desktop;',out)
        self.assertNotIn('firefox',out)
        for mime in MIMES:self.assertIn(mime+'='+DESKTOP+';',out)
    def test_settings_are_idempotent(self):
        self.assertEqual(settings(settings({})),settings({}))
    def test_all_default_locations_exported(self):
        self.assertEqual(set(settings({})),set(FILES))
    def test_duplicate_section_or_browser_key_fails_closed(self):
        for old in ('[Default Applications]\n[Default Applications]\n',
                    '[Default Applications]\ntext/html=a\ntext/html=b\n'):
            with self.assertRaises(SpecError):replace_keys(old,{'text/html':DESKTOP},'Default Applications')
    def test_preserves_final_newline_and_missing_sections(self):
        out=replace_keys('# comment',{'text/html':DESKTOP},'Default Applications')
        self.assertEqual(out,'# comment\n[Default Applications]\ntext/html='+DESKTOP+'\n')
    def test_only_declared_settings_paths_allowed(self):
        with self.assertRaises(SpecError):settings({'etc/shadow':''})
    def test_binary_settings_rejected(self):
        with self.assertRaises(SpecError):settings({HELPERS[0]:'\x00'})
    def test_live_delta_with_status_resolves_full_view(self):
        b={'base':'1'};l={'base':'1','installer':'2'}
        texts=effective_status(status(b),status(l),manifest(b),manifest(l)+'snap:test\t1\t99\n')
        self.assertEqual(texts['live'],status(l))
    def test_live_delta_without_status_must_match_base(self):
        b={'base':'1'}
        self.assertEqual(effective_status(status(b),None,manifest(b),manifest(b))['base'],status(b))
        with self.assertRaises(SpecError):effective_status(status(b),None,manifest(b),manifest({'base':'1','installer':'2'}))
    def test_manifest_status_mismatch_rejected(self):
        with self.assertRaises(SpecError):effective_status(status({'base':'1'}),None,manifest({'base':'2'}),manifest({'base':'2'}))
    def target(self):
        before={'php':'1','docker.io':'1','snapd':'1'}
        final={**before,**{p:'1' for p in REQUIRED_PACKAGES}}
        return before,{'final_versions':final,'changes':[{'package':p,'previous':None} for p in REQUIRED_PACKAGES]}
    def test_browser_only_additions_preserve_baseline(self):
        b,t=self.target();self.assertTrue(audit_transaction(t,b))
    def test_incidental_upgrade_or_removal_rejected(self):
        for change in ('upgrade','remove'):
            b,t=self.target()
            if change=='upgrade':t['final_versions']['php']='2'
            else:del t['final_versions']['docker.io']
            with self.assertRaises(SpecError):audit_transaction(t,b)
    def test_snap_transitional_or_conflicting_packages_rejected(self):
        for package in ('snapd','firefox','chromium-browser','nodejs','docker-ce'):
            b,t=self.target();t['changes'].append({'package':package,'previous':None})
            with self.assertRaises(SpecError):audit_transaction(t,b)
    def test_missing_browser_or_support_rejected(self):
        b,t=self.target();del t['final_versions']['epiphany-browser']
        with self.assertRaises(SpecError):audit_transaction(t,b)


    def fixture(self):
        versions={p:'1' for p in REQUIRED_PACKAGES}
        desktop='[Desktop Entry]\nType=Application\nName=Web\nExec=epiphany %U\nCategories=Network;WebBrowser;\nMimeType='+';'.join(MIMES)+';\n'
        helper='[Desktop Entry]\nType=X-XFCE-Helper\nX-XFCE-Category=WebBrowser\nX-XFCE-Binaries=epiphany;\n'
        return settings({}),desktop,helper,status(versions),versions
    def test_static_audit_does_not_claim_graphical_approval(self):
        result=audit_configuration(*self.fixture())
        self.assertEqual(result['static_integration'],'passed')
        self.assertEqual(result['graphical_launch'],'not_tested')
        self.assertEqual(result['post_install_persistence'],'not_tested')
    def test_hidden_nonxfce_or_downloader_launcher_rejected(self):
        for bad in ('Hidden=true\n','NoDisplay=true\n','OnlyShowIn=GNOME;\n','NotShowIn=XFCE;\n'):
            args=list(self.fixture());args[1]+=bad
            with self.assertRaises(SpecError):audit_configuration(*args)
        args=list(self.fixture());args[1]=args[1].replace('Exec=epiphany','Exec=curl')
        with self.assertRaises(SpecError):audit_configuration(*args)
    def test_missing_mime_or_helper_or_config_rejected(self):
        args=list(self.fixture());args[1]=args[1].replace('x-scheme-handler/https;','')
        with self.assertRaises(SpecError):audit_configuration(*args)
        args=list(self.fixture());args[2]=args[2].replace('X-XFCE-Binaries=epiphany;','X-XFCE-Binaries=firefox;')
        with self.assertRaises(SpecError):audit_configuration(*args)
        args=list(self.fixture());args[0].pop(HELPERS[0])
        with self.assertRaises(SpecError):audit_configuration(*args)
    def test_materialized_dpkg_must_match_frozen_plan(self):
        args=list(self.fixture());args[4]=dict(args[4],php='2')
        with self.assertRaises(SpecError):audit_configuration(*args)


    def test_composed_selection_keeps_historical_recipe_unchanged(self):
        spec=json.loads((ROOT/'packages/browser.json').read_text())
        old=json.loads((ROOT/'packages/selection.json').read_text());before=copy.deepcopy(old)
        result=selection_with_browser(old,spec)
        self.assertEqual(old,before)
        self.assertTrue(any(p['id']=='epiphany-browser' for p in result['categories']['interface']))
        self.assertEqual(selection_with_browser(result,spec),result)
    def test_resolver_pins_every_existing_package_and_never_dpkg_host(self):
        packages={p:'1' for p in REQUIRED_PACKAGES};packages['php']='1'
        with tempfile.TemporaryDirectory() as folder:
            w=Path(folder)
            with patch('pipeline.devlite.browser.run',return_value=SimpleNamespace(returncode=0,stdout='')) as mock:
                result=resolve_browser(w,'base',status(packages),sorted(REQUIRED_PACKAGES),set())
            preferences=(w/'base.preferences').read_text()
            for package in packages:self.assertIn('Package: '+package+'\nPin: version 1\nPin-Priority: 1001',preferences)
            self.assertEqual(result['final_versions'],packages)
            config=(w/'base.apt.conf').read_text()
            self.assertIn('Dir::Bin::dpkg "/bin/false"',config)
            self.assertIn(str(w/'base.status'),config)
            for call in mock.call_args_list:self.assertIn('-s',call.args[2])

if __name__=='__main__':unittest.main()
