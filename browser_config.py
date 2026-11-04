"""Shared, dependency-free local-browser paths."""
import os
from pathlib import Path


def config_path(explicit=None):
    """CLI override, environment override, then the current Hermes home."""
    override = explicit or os.environ.get('HERMES_LOCAL_BROWSER_CONFIG')
    if override:
        return Path(override).expanduser().absolute()
    home = Path(os.environ.get('HERMES_HOME') or Path.home() / '.hermes').expanduser()
    return (home / 'local-browser' / 'config.json').absolute()


def cache_path():
    """Keep screenshots beside the selected local-browser configuration."""
    return config_path().parent / 'cache'
