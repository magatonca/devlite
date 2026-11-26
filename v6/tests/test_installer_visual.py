import unittest
from html.parser import HTMLParser

import yaml

from v6.payload import OVERLAY

PROVISION = OVERLAY / 'usr/share/desktop-provision'


def luminance(hex_color):
    channels = [int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
              for c in channels]
    return sum(value * weight for value, weight in zip(linear, (0.2126, 0.7152, 0.0722)))


def contrast(first, second):
    dark, light = sorted((luminance(first), luminance(second)))
    return (light + 0.05) / (dark + 0.05)


class SlideParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.attributes = {}

    def handle_starttag(self, tag, attrs):
        self.attributes.setdefault(tag, []).append(dict(attrs))


class InstallerVisualTests(unittest.TestCase):
    def test_shared_theme_and_screen_images(self):
        config = yaml.safe_load((PROVISION / 'whitelabel.yaml').read_text())
        self.assertEqual(config['flavor'], 'xubuntu')
        self.assertEqual(config['app-name'], 'Instalar DevLite OS 1.0')
        for theme in config['theme'].values():
            self.assertGreaterEqual(contrast(theme['elevated-button-color'],
                                             theme['elevated-button-text-color']), 4.5)
        for page in ('locale', 'try-or-install', 'keyboard', 'network', 'source-selection',
                     'storage', 'storage-icon', 'identity', 'confirm', 'done'):
            self.assertEqual(config['pages'][page], {'image': 'devlite.png'})
        self.assertNotIn('mode', config)

    def test_all_slides_use_the_same_readable_palette(self):
        for locale, language in (('pt_BR', 'pt-BR'), ('en_US', 'en-US')):
            for page in range(1, 5):
                with self.subTest(locale=locale, page=page):
                    slide = PROVISION / 'slides' / str(page) / f'slide_{locale}.html'
                    text = slide.read_text()
                    parser = SlideParser()
                    parser.feed(text)
                    body = dict(item.split(':', 1) for item in
                                parser.attributes['body'][0]['style'].split(';'))
                    background = body['background-color']
                    self.assertGreaterEqual(contrast(background, body['color']), 4.5)
                    self.assertEqual(parser.attributes['html'][0]['lang'], language)
                    self.assertEqual(len(parser.attributes['h1']), 1)
                    self.assertNotIn('table', parser.attributes)
                    self.assertNotIn('Xubuntu Minimal', text)
                    for anchor in parser.attributes.get('a', []):
                        self.assertGreaterEqual(contrast(background, anchor['style'].split(':')[1]), 4.5)
                        self.assertTrue(anchor['href'].startswith('https://'))
                    if page == 1:
                        self.assertEqual(parser.attributes['img'][0]['src'], 'devlite.svg')
