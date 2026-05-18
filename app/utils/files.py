from typing import TypeVar

import yaml
from pydantic import BaseModel


def read_file(path: str) -> str:
    with open(path, encoding="utf-8") as file:
        return file.read()


def read_yaml(path: str) -> dict:
    return yaml.safe_load(read_file(path))


TModel = TypeVar("T", bound=BaseModel)


def read_yaml_model[TModel](path: str, model: type[TModel]) -> TModel:
    data = yaml.safe_load(read_file(path))
    return model.model_validate(data)
