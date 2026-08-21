# -*- mode: python ; coding: utf-8 -*-
import sys, os
sys.setrecursionlimit(sys.getrecursionlimit() * 5)
from PyInstaller.utils.hooks import copy_metadata, collect_data_files, collect_dynamic_libs

metadata_datas = []
for pkg in ('pandas', 'numpy', 'holoviews', 'panel', 'bokeh', 'param', 'hvplot'):
    metadata_datas += copy_metadata(pkg)

gdal_datas = collect_data_files('rasterio', subdir='gdal_data')
pyogrio_datas = collect_data_files('pyogrio')
pyogrio_binaries = collect_dynamic_libs('pyogrio')

conda_prefix = os.environ.get('CONDA_PREFIX', r'C:\Users\awestfall\miniforge3\envs\calview')
gdal_bin_dir = os.path.join(conda_prefix, 'Library', 'bin')
gdal_share_dir = os.path.join(conda_prefix, 'Library', 'share', 'gdal')
proj_share_dir = os.path.join(conda_prefix, 'Library', 'share', 'proj')

geo_binaries = [
    (os.path.join(gdal_bin_dir, 'gdal.dll'), '.'),
    (os.path.join(gdal_bin_dir, 'proj_9.dll'), '.'),
]
geo_data_files = [
    (gdal_share_dir, 'gdal-data'),
    (proj_share_dir, 'proj-data'),
]

a = Analysis(
    ['calview_all.py'],
    pathex=[],
    binaries=pyogrio_binaries + geo_binaries,
    datas=[
        ('inputs/TR_fields.txt', 'inputs/.'),
        ('inputs/TR_fields_CSH_alternate.txt', 'inputs/.'),
        ('inputs/TR_fields_temperature.txt', 'inputs/.'),
        ('inputs/TR_fields_salinity.txt', 'inputs/.'),
        ('inputs/usbr_logo.jpg', 'inputs/.'),
        ('inputs/WBAs', 'inputs/WBAs'),
        ('inputs/DUs', 'inputs/DUs'),
    ] + metadata_datas + gdal_datas + pyogrio_datas + geo_data_files,
    hiddenimports=[
        'rasterio.sample',
        'rasterio._io',
        'rasterio.control',
        'rasterio.crs',
        'rasterio.transform',
        'rasterio.vrt',
        'rasterio._features',
        'rasterio._warp',
        'rasterio._base',
        'rasterio._env',
        'pyogrio._geometry',
        'pyogrio._io',
        'pyogrio._err',
        'pyogrio._ogr',
        'pyogrio._vsi',
    ],
    hookspath=['src/hook-panel.py'],
    hooksconfig={},
    runtime_hooks=['src/hook-gdal-runtime.py'],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='CalViewAll',
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