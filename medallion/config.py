import collections.abc
import json
import logging
import pathlib

import attr
import environ
import jsonmerge

from . import backends

DEFAULT_CONFFILE = "/etc/medallion.conf"
DEFAULT_CONFDIR = "/etc/medallion.d/"
CONFDIR_SUFFIXES = {".json", ".conf"}

LOGGER = logging.getLogger(__name__)


class _LazyJSONDumper(object):
    """An lazy stringifier for dumping objects as JSON, e.g. for logging."""
    def __init__(self, obj, cls=json.JSONEncoder, indent=None):
        super(_LazyJSONDumper, self).__init__()
        # Beware: If `obj` is mutable then we'll get future mutations. This
        # isn't really an issue for logging format evaluation, but it might be
        # in other contexts/multi-thread. We concretise on the first call to
        # `__str__()` so the output's immutable/repeatable after that at least.
        self._obj = obj
        self._dumpcls = cls
        self._indent = indent

    def __str__(self):
        # The first stringification will concretise `obj`
        if not isinstance(self._obj, str):
            self._obj = json.dumps(
                self._obj, cls=self._dumpcls, indent=self._indent,
            )
        return self._obj

    def __repr__(self):  # pragma: no cover
        return repr(str(self))


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
    LOGGER.debug(
        "Attempting to load configuration from '%s' and '%s'",
        conf_file, conf_dir,
    )
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
    LOGGER.debug(
        "Configuration files to load in order: %s",
        ", ".join(repr(str(p)) for p in conf_files),
    )
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
            LOGGER.debug(
                "Configuration data from '%s' to be merged: %s",
                conf_file_p, _LazyJSONDumper(new_data, indent=2),
            )
            config_data = jsonmerge.merge(config_data, new_data)
    # Load extra configuration from the environment
    env_config = MedallionConfig.from_environ().as_dict()
    LOGGER.debug(
        "Configuration data from environment to be merged: %s",
        _LazyJSONDumper(env_config, indent=2),
    )
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
    LOGGER.debug(
        "Merged configuration: %s",
        _LazyJSONDumper(config_data, indent=2),
    )
    return config_data
