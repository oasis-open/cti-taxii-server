from medallion.utils import common


def create_bundle(o):
    return dict(id=common.generate_stix20_id("bundle"),
                objects=o,
                spec_version="2.0",
                type="bundle")
