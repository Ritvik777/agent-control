from .base import BaseModel


class Rule(BaseModel):
    rule: dict

class Control(BaseModel):
    rules: list[Rule]

class Policy(BaseModel):
    controls: list[Control]
