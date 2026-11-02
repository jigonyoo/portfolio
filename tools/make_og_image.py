#!/usr/bin/env python3
"""Generate the share image offline: python3 tools/make_og_image.py.

Requires Pillow with ImageFont.load_default(size=...) support (10.1+).
Uses only Pillow's bundled font; no system fonts or network resources.
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def main():
    image = Image.new('RGB', (1200, 630), '#10172f')
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 19, 629), fill='#a080ff')
    draw.text((80, 64), 'Jigon Yoo', font=ImageFont.load_default(size=64), fill='#ffffff')
    draw.text((80, 156), 'Freelance AI & data reliability engineer',
              font=ImageFont.load_default(size=32), fill='#ffab66')

    headline = ('I find where your AI agents and data pipelines go wrong, '
                'and prove the fix with numbers.')
    font = ImageFont.load_default(size=48)
    lines = []
    line = ''
    for word in headline.split():
        candidate = f'{line} {word}'.strip()
        if draw.textlength(candidate, font=font) > 1040:
            lines.append(line)
            line = word
        else:
            line = candidate
    lines.append(line)
    draw.multiline_text((80, 260), '\n'.join(lines), font=font, fill='#ffffff', spacing=16)
    draw.text((80, 544), 'jigonyoo.com', font=ImageFont.load_default(size=30), fill='#c4b5fd')
    output = Path(__file__).resolve().parents[1] / 'assets/og-default.png'
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)


if __name__ == '__main__':
    main()
