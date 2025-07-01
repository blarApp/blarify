# Blarify Documentation

Simple Sphinx documentation for Blarify.

## Build

```bash
cd docs
pip install -r requirements.txt
make html
```

The documentation will be in `build/html/index.html`.

## Structure

- `source/index.rst` - Main page
- `source/quickstart.rst` - Installation and basic usage
- `source/conf.py` - Sphinx configuration

## Adding Content

Just edit the `.rst` files and run `make html` to rebuild.
