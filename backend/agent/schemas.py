"""
The base for every schema a model fills in.

Claude writes `null` for a field it has nothing to say in, where the OpenAI-
style models wrote "". Pydantic rejects None for a plain `str`, and one null
in an eight-question readiness report failed the whole report. Here None
becomes "" for strings and [] for lists, and the report goes through.
"""
import typing

from pydantic import BaseModel, field_validator


class Lenient(BaseModel):
    @field_validator("*", mode="before")
    @classmethod
    def _none_to_empty(cls, value, info):
        if value is None:
            annotation = cls.model_fields[info.field_name].annotation
            if annotation is str:
                return ""
            if annotation is list or typing.get_origin(annotation) is list:
                return []
        return value
