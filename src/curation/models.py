from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

from .categories import Season, TimeOfDay, Weather


class ImageRef(BaseModel):
    url: HttpUrl
    thumb_url: HttpUrl | None = Field(None, alias="thumbUrl")
    model_config = ConfigDict(populate_by_name=True)


class Candidate(BaseModel):
    id: str
    source: Literal["aic", "met", "cma"]
    title: str
    artist: str = "Unknown"
    date: str = ""
    image: ImageRef
    source_url: HttpUrl = Field(alias="sourceUrl")
    credit: str
    subjects: list[str] = Field(default_factory=list)
    public_domain: bool = True
    model_config = ConfigDict(populate_by_name=True)

    @model_validator(mode="after")
    def require_public_domain(self):
        if not self.public_domain:
            raise ValueError("only public-domain/CC0 works are allowed")
        return self


class Tags(BaseModel):
    weather: list[Weather]
    time: list[TimeOfDay]
    season: list[Season] = Field(default_factory=list)

    @model_validator(mode="after")
    def required_axes(self):
        if not self.weather or not self.time:
            raise ValueError("weather and time require at least one tag")
        return self


class AxisScores(BaseModel):
    sky: dict[str, float] = Field(default_factory=dict)
    weather: dict[str, float] = Field(default_factory=dict)
    time: dict[str, float] = Field(default_factory=dict)
    season: dict[str, float] = Field(default_factory=dict)


class Classified(Candidate):
    tags: Tags
    scores: AxisScores = Field(default_factory=AxisScores)
    confidence: float = Field(ge=0, le=1)
    sky_visible: bool = True
    color_features: dict[str, float] = Field(default_factory=dict)


class Review(BaseModel):
    status: Literal["approved", "rejected", "skipped"]
    tags: Tags | None = None
    updated_at: str
