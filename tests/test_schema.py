import json
import pathlib
from unittest import TestCase

import jsonschema


SCHEMA = pathlib.Path("data/config-schema.json")
CONFIG_VALID_FP = pathlib.Path("tests/data/config-test.json")
CONFIG_WRONG_FPS = [
    pathlib.Path("tests/data/config-invalid-loglevel.json"),
    pathlib.Path("tests/data/config-broken-soa.json"),
    pathlib.Path("tests/data/config-missing-global-property.json"),
    pathlib.Path("tests/data/config-missing-handler-property.json"),
    pathlib.Path("tests/data/config-missing-vpspec-property.json"),
]


class TestConfigSchemaValidation(TestCase):
    def setUp(self):
        with open(SCHEMA, "r", encoding="utf8") as fd:
            self.schema = json.load(fd)

    def test_schema_check_correct(self):
        with open(CONFIG_VALID_FP, "r", encoding="utf8") as fd:
            config = json.load(fd)
            jsonschema.validate(config, self.schema)

    def test_schema_check_incorrect(self):
        for fp in CONFIG_WRONG_FPS:
            with open(fp, "r", encoding="utf8") as fd:
                config = json.load(fd)
                with self.assertRaises(jsonschema.ValidationError):
                    jsonschema.validate(config, self.schema)
