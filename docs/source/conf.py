import os
import sys
sys.path.insert(0, os.path.abspath('../../'))

project = 'Blarify'
copyright = '2025, Juan Vargas, Benjamín Errazuriz'
author = 'Juan Vargas, Benjamín Errazuriz'
release = '1.1.0'

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.viewcode',
    'sphinx.ext.napoleon',
]

templates_path = ['_templates']
exclude_patterns = []

html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']

autodoc_default_options = {
    'members': True,
    'undoc-members': True,
    'show-inheritance': True,
}

napoleon_google_docstring = True
napoleon_numpy_docstring = True
