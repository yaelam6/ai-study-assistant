import sys, glob, os
from PIL import Image, ImageDraw
files = sorted(glob.glob('stills/*.png'))
out = sys.argv[1]; per = 6
for k in range(0, len(files), per):
    g = Image.new('RGB', (1920, 1620), 'black')
    for i, f in enumerate(files[k:k+per]):
        im = Image.open(f).resize((960, 540))
        ImageDraw.Draw(im).text((10, 10), os.path.basename(f), fill='red')
        g.paste(im, ((i % 2) * 960, (i // 2) * 540))
    g.save(f'{out}_{k//per}.png')
