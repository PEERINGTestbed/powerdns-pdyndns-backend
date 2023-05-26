#!/usr/bin/env python3

import argparse
import json
import logging
import pathlib
import resource
import sys

import jsonschema


def create_parser() -> argparse.ArgumentParser:
    desc = """Configuration checker for pdyndns using JSON schema"""
    parser = argparse.ArgumentParser(description=desc)
    parser.add_argument(
        "--config",
        dest="config",
        action="store",
        metavar="JSON",
        type=pathlib.Path,
        required=True,
        help="File containing JSON configuration",
    )
    parser.add_argument(
        "--schema",
        dest="schema",
        action="store",
        metavar="JSON",
        type=pathlib.Path,
        required=True,
        help="File containing configuration schema",
    )
    return parser


def main() -> int:
    resource.setrlimit(resource.RLIMIT_AS, (1 << 26, 1 << 26))
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG, format="%(message)s")

    parser = create_parser()
    args = parser.parse_args()

    with open(args.config, "r", encoding="utf8") as fd:
        config = json.load(fd)
    with open(args.schema, "r", encoding="utf8") as fd:
        schema = json.load(fd)

    try:
        jsonschema.validate(config, schema)
        logging.info("Configuration file is valid")
        return 0
    except jsonschema.ValidationError as ve:
        logging.exception(ve)
        return 1
    except jsonschema.SchemaError as se:
        logging.exception(se)
        return 1


if __name__ == "__main__":
    sys.exit(main())
