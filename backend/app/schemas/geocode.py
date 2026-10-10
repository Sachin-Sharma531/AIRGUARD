from pydantic import BaseModel, Field, field_validator


class GeocodeRequest(BaseModel):
    """A human-readable address to resolve into geographic coordinates."""

    address: str = Field(
        ...,
        min_length=2,
        max_length=250,
        description="Address or place name, for example 'Rohini, Delhi'",
        examples=["Delhi Technological University, Delhi"],
    )

    @field_validator("address")
    @classmethod
    def address_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Address must contain at least 2 non-space characters.")
        return value


class GeocodeResponse(BaseModel):
    formatted_address: str = Field(..., description="Provider-formatted address")
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
