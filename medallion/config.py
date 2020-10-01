import collections.abc
import json
import pathlib

import attr
import environ
import jsonmerge

from . import backends

DEFAULT_CONFFILE = "/etc/medallion.conf"
DEFAULT_CONFDIR = "/etc/medallion.d/"
CONFDIR_SUFFIXES = {".json", ".conf"}


@environ.config(prefix="TAXII")
class TAXIIConfig(object):
    max_page_size = environ.var(None, converter=lambda i: int(i) if i else i)


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


def _load_config_file(conf_file_p):
    try:
        config_data = json.load(conf_file_p.open())
    except json.decoder.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON data in {conf_file_p}") from exc
    if not isinstance(config_data, collections.abc.Mapping):
        raise TypeError(f"{conf_file_p} must contain a JSON object")
    return config_data


def load_config(conf_file=DEFAULT_CONFFILE, conf_dir=DEFAULT_CONFDIR):
    conf_files = list()
    # Sanity check that both the `conf_file` and `conf_dir` exist by resolving
    # them with strictness determined by whether they are the defaults or not
    if conf_file is not None:
        conf_file_p = pathlib.Path(conf_file).resolve(
            strict=conf_file is not DEFAULT_CONFFILE
        )
        conf_files.append(conf_file_p)
    # Build a lexicographically sorted list of children of the `conf_dir` which
    # are both files and have an acceptable file suffix. We allow the potential
    # `NotADirectoryError` here to bubble up since `DEFAULT_CONFDIR` existing
    # but not being a directory seems like a problem. There's an option for
    # disabling the use of a config dir so we won't feel bad about doing this.
    if conf_dir is not None:
        conf_dir_p = pathlib.Path(conf_dir).resolve(
            strict=conf_dir is not DEFAULT_CONFDIR
        )
        conf_dir_files = (
            p for p in conf_dir_p.iterdir() if p.suffix in CONFDIR_SUFFIXES
        )
        try:
            conf_files.extend(sorted(conf_dir_files,  key=lambda p: p.name))
        except FileNotFoundError:
            pass
    # Start with an empty config and progressively merge in data from files
    config_data = dict()
    for conf_file_p in conf_files:
        try:
            new_data = _load_config_file(conf_file_p)
        except (FileNotFoundError, IsADirectoryError):
            # Skip missing files since we haven't already exploded which means
            # they're probably not important enough to care about (or TOCTOU?).
            # We also don't care about sub-directories of the config dir.
            pass
        else:
            config_data = jsonmerge.merge(config_data, new_data)
    # Load extra configuration from the environment
    env_config = MedallionConfig.from_environ().as_dict()
    config_data = jsonmerge.merge(config_data, env_config)
    # We promote config pulled from the environment for the specified backend
    # `module_class` since the `environ-config` variable layout will nest it.
    # Any of the following statements could `KeyError` if the configuration is
    # incomplete or no config was sourced from the environment, but we're
    # lenient about this here in favour of validating in the main app logic.
    try:
        backend_config = config_data["backend"]
        backend_kind = backend_config["module_class"]
        backend_kind_config = backend_config.pop(backend_kind)
    except KeyError:
        pass
    else:
        backend_config.update(backend_kind_config)
    # Return the finalised configuration dictionary
    return config_data
