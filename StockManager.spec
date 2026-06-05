# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['run_server.py'],
    pathex=[],
    binaries=[],
    datas=[('stock/templates', 'templates'), ('staticfiles', 'staticfiles'), ('stock/migrations', 'stock/migrations'), ('stock/templatetags', 'stock/templatetags'), ('core', 'core'), ('stock', 'stock')],
    hiddenimports=['django.contrib.admin', 'django.contrib.auth', 'django.contrib.contenttypes', 'django.contrib.sessions', 'django.contrib.messages', 'django.contrib.staticfiles', 'whitenoise', 'whitenoise.middleware', 'PIL', 'stock', 'stock.apps', 'stock.models', 'stock.views', 'stock.urls', 'stock.signals', 'stock.context_processors', 'stock.templatetags.stock_tags'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='StockManager',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
