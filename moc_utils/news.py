import json
import time
from base64 import b64encode
from dataclasses import dataclass
from hashlib import md5
from typing import Any
from typing import Literal
from typing import Optional
from typing import TypedDict

import requests

from .asset_api import REGION
from .asset_api import AssetAPIHandler
from .asset_api import FileInfo

NEWS_TYPE = Literal["game", "activity"]
LANGUAGE = Literal["zh_CN", "zh_TW", "en_US", "ja_JP", "ko_KR", "th_TH", "id_ID", "pt_BR"]


class AnnouncementResponseListEntry(TypedDict):
    id: int
    type: str
    short_title: str
    jump_location: str
    jump_link: str
    publish_time: int
    expire_time: int


class AnnouncementDetail(TypedDict):
    id: int
    content: str  # json encoded
    short_title: str
    long_title: str


class AnnouncementResponse(TypedDict):
    list: list[AnnouncementResponseListEntry]
    lastest: AnnouncementDetail


@dataclass
class TapSDKBillboard:
    client_id: str
    client_token: str
    server_url: str
    billboard_location: str
    billboard_server_url: str
    # following aren't required for the class to work
    # so as some of them might be missing in one version or another
    # they get flagged as optional to not crash the class init
    appId: Optional[str] = None
    db_config: Optional[dict[str, str]] = None
    tap_support_pid: Optional[str] = None
    tap_support_categoryid: Optional[str] = None
    billboard_platform_ios: Optional[str] = None
    billboard_platform_android: Optional[str] = None
    permissions: Optional[str] = None

    @classmethod
    def from_online(cls, cdn_region: REGION, channel: Optional[REGION] = None) -> "TapSDKBillboard":
        handler = AssetAPIHandler.fetch(cdn_region, channel)
        return cls.from_online_handler(handler)

    @classmethod
    def from_online_handler(cls, handler: AssetAPIHandler) -> "TapSDKBillboard":
        gamefileinfo = handler.get_gamefileinfo_win()
        xdconfig_info: FileInfo
        for entry in gamefileinfo["FileInfos"]:
            if entry["FileName"].endswith("XDConfig.json"):
                xdconfig_info = entry
                break
        else:
            raise FileNotFoundError("XDConfig.json not found in GameFileInfo.json")

        xdconfig = json.loads(handler.get_gamefile_pc(xdconfig_info))
        return cls(**xdconfig["tapsdk"])

    @classmethod
    def from_file(cls, fp: str) -> "TapSDKBillboard":
        with open(fp, "r") as f:
            data = json.load(f)
        return cls(**data["tapsdk"])

    def generate_view_url(self) -> str:
        business_query_string = b64encode(
            "&".join(
                [
                    # f"lang={lang}",
                    # f'dimension_list=[{{"platform":"{platform}"}},{{"location":"{billboard_location}"}}]',
                    "template=navigate",
                    f"query_nameless={self.client_token}",
                ]
            ).encode("utf8")
        ).decode()
        return f"{self.billboard_server_url}/webapp/{self.client_id}?business={business_query_string}"

    def get_all_announcement_details(
        self, news_type: NEWS_TYPE = "activity", language: LANGUAGE = "en_US"
    ) -> dict[int, AnnouncementDetail]:
        announcement_response = self.get_announcement_json(news_type, language)
        res: dict[int, AnnouncementDetail] = {}
        latest = announcement_response["lastest"]
        res[latest["id"]] = latest
        for entry in announcement_response["list"]:
            if entry["id"] in res:
                continue
            res[entry["id"]] = self.get_announcement_detail_json(entry["id"], language)
        return res

    def get_announcement_json(
        self, news_type: NEWS_TYPE = "activity", language: LANGUAGE = "en_US"
    ) -> AnnouncementResponse:
        url = f"{self.billboard_server_url}/billboard/rest-api/v1/announcement/list?client_id={self.client_id}"
        content = json.dumps(
            {
                "type": news_type,
                "lang": language,
                "template": "navigate",
                "dimension_list": [],
            }
        )
        headers = self._get_announcement_headers()
        res = requests.post(url, data=content, headers=headers)
        return self._process_announcement_response(res)  # type: ignore

    def get_announcement_detail_json(self, news_id: int, language: LANGUAGE = "en_US") -> AnnouncementDetail:
        url = f"{self.billboard_server_url}/billboard/rest-api/v1/announcement/detail"
        query = {
            "id": str(news_id),
            "lang": language,
            "client_id": self.client_id,
        }
        headers = self._get_announcement_headers()
        res = requests.get(url, params=query, headers=headers)
        return self._process_announcement_response(res)  # type: ignore

    def _process_announcement_response(self, response: requests.Response) -> dict[str, Any]:
        content = response.json()
        if not content["success"]:
            raise ValueError(f'{content["error"]}: {content["msg"]}')
        return content["data"]

    def _get_announcement_headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "x-lc-id": self.client_id,
            "x-lc-sign": self._generate_x_lc_sign(),
        }

    def _generate_x_lc_sign(self) -> str:
        # x_lc_id == query_nameless == client_token
        now = int(time.time() * 1000)
        val = f"{now}{self.client_token}"
        return f"{md5(val.encode()).hexdigest()},{now}"


if __name__ == "__main__":
    bb = TapSDKBillboard.from_online("us-prod", "us-prod")
    print(bb.generate_view_url())
    res = bb.get_announcement_json()
    # news = bb.get_announcement_json()
    print()
