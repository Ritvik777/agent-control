from .base import BaseModel


class Rule(BaseModel):
    pass

class Control(BaseModel):
    rules: list[Rule]

class Policy(BaseModel):
    controls: list[Control]
