from pydantic import BaseModel, ConfigDict, Field


class GroupHotspot(BaseModel):
    model_config = ConfigDict(title="Wi-Fi Hotspot")

    enabled: bool = Field(
        default=True,
        description="Start a guest Wi-Fi hotspot when the booth launches (Ubuntu NetworkManager).",
    )
    ssid: str = Field(
        default="InstaBooth",
        description="Hotspot network name shown to guests.",
    )
    password: str = Field(
        default="instabooth-guest",
        min_length=8,
        description="WPA password for the guest hotspot (minimum 8 characters).",
    )
    interface: str = Field(
        default="",
        description="Wi-Fi interface name (empty = auto-detect first wifi device).",
    )
