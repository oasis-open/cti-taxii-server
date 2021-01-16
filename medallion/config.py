import json
import pathlib

import attr
import environ
import jsonmerge

from . import backends

DEFAULT_CONFFILE = "/etc/medallion.conf"
DEFAULT_CONFDIR = "/etc/medallion.d/"


@environ.config(prefix="TAXII")
class TAXIIConfig(object):
    max_page_size = environ.var(None)


@environ.config(prefix="MEDALLION")
class MedallionConfig(object):
    backend = environ.group(backends.BackendConfig)
    taxii = environ.group(TAXIIConfig)

    @classmethod
    def __strip(cls, dict_):
        for k, v in tuple(dict_.items()):
            if isinstance(v, dict):
                cls.__strip(v)
            if v is None or v == {}:
                del dict_[k]

    def as_dict(self):
        dictified = attr.asdict(self)
        self.__strip(dictified)
        return dictified


def load_config(conf_file=DEFAULT_CONFFILE, conf_dir=DEFAULT_CONFDIR):
    # Load configuration from the default config file or a value passed in
    if conf_file is not None:
        conf_file_p = pathlib.Path(conf_file)
        try:
            config_data = json.load(conf_file_p.open())
        except FileNotFoundError as exc:
            if conf_file is not DEFAULT_CONFFILE:
                raise exc
            else:
                config_data = dict()
    # Load extra configuration from a config.d style directory at either the
    # default path or one passed in
    if conf_dir is not None:
        conf_dir_p = pathlib.Path(conf_dir)
        try:
            for conf_file_p in conf_dir_p.iterdir():
                if conf_file_p.suffix in {".json", ".conf"}:
                    try:
                        new_data = json.load(conf_file_p.open())
                    except IsADirectoryError:
                        pass
                    else:
                        config_data = jsonmerge.merge(config_data, new_data)
        except FileNotFoundError as exc:
            if conf_dir is not DEFAULT_CONFDIR:
                raise exc
    # Load extra configuration from the environment
    env_config = MedallionConfig.from_environ().as_dict()
    config_data = jsonmerge.merge(config_data, env_config)
    # We promote backend config for the `module_class` which will be used
    try:
        backend_kind = config_data["backend"]["module_class"]
    except KeyError:
        raise ValueError(
            "No module_class parameter provided for the TAXII server."
        )
    # Clean up any residual nested backend config structures
    config_data["backend"] = dict(
        **{
            k: v for k, v in config_data["backend"].items()
            if k in {"module", "module_class"}
        },
        **config_data["backend"].get(backend_kind, {}),
    )
    # Return the finalised configuration dictionary
    return config_data
