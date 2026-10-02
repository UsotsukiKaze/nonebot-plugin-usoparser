from anyio import Path
import nonebot_plugin_localstore as store

cache_dir: Path = Path(store.get_plugin_cache_dir())
config_dir: Path = Path(store.get_plugin_config_dir())
data_dir: Path = Path(store.get_plugin_data_dir())
