Bundled data files. Everything in this tree is shipped inside the wheel and
copied into the PyInstaller bundle, where it ends up as a top-level "assets"
folder - which is what resources.assets_root() looks for.

    images/   sprites and backgrounds   resources.load_image("images", "castle.png")
    sounds/   sound effects             pygame.mixer.Sound(resources.asset_path(...))
    fonts/    bundled .ttf files        resources.load_font(16, "fonts", "pixel.ttf")

Load everything through bummsschloss.resources rather than open() or a bare
path: those helpers cache by name, cope with being frozen, and are cleared
together when pygame is restarted.

The game currently draws everything with plain pygame primitives and the
default font, so these folders are still empty. Drop files in, point the
drawing code at them, and nothing about packaging has to change.
