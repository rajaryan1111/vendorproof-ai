from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Category = Literal["registration", "tax", "bank", "insurance", "agreement"]


class Rule(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    category: Category
    when_jurisdiction: str | None = Field(None, min_length=1, max_length=50)
    when_type: str | None = Field(None, min_length=1, max_length=50)
    expiry: bool = False
    issue_date: bool = False
    identifier_scheme: Literal["uk_company", "exact_local"] | None = None


class Policy(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    jurisdiction: str | None = Field(None, min_length=1, max_length=50)
    supplier_type: str | None = Field(None, min_length=1, max_length=50)
    days: int = Field(default=30, ge=0, le=365)
    legal_suffix_aliases: bool = False
    rules: list[Rule] = Field(default_factory=list, max_length=5)

    @model_validator(mode="after")
    def distinct(self):
        if len(self.rules) != len({r.category for r in self.rules}):
            raise ValueError("duplicate category")
        if any(
            rule.category == "registration"
            and rule.expiry
            and not rule.when_jurisdiction
            for rule in self.rules
        ):
            raise ValueError(
                "Registration expiry requires a jurisdiction-specific rule"
            )
        return self

    def applies(self, rule):
        unknown = False
        for expected, actual in (
            (rule.when_type, self.supplier_type),
            (rule.when_jurisdiction, self.jurisdiction),
        ):
            if expected and actual and expected.casefold() != actual.casefold():
                return False
            if expected and not actual:
                unknown = True
        return None if unknown else True
