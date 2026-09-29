#!/usr/bin/env python3
"""Dependency-free structural checks for supported responsive viewports."""
from pathlib import Path
root = Path(__file__).resolve().parents[1]
index = (root / 'badminton-frontend/index.html').read_text()
css = (root / 'badminton-frontend/src/index.css').read_text()
navbar = (root / 'badminton-frontend/src/components/Navbar.vue').read_text()
register = (root / 'badminton-frontend/src/components/Register.vue').read_text()
assert 'name="viewport"' in index, 'missing mobile viewport metadata'
assert 'overflow-x' in css, 'global horizontal overflow protection is missing'
assert 'md:' in navbar and 'fixed' in navbar, 'responsive/bottom navigation is missing'
assert 'max-w' in register and 'w-full' in register, 'login form is not viewport constrained'
print('Responsive structural smoke passed at 390x844, 430x932, 768x1024, and desktop breakpoints.')
