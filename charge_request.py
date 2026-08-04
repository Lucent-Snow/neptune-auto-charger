"""构造 Neptune beginCharge 请求参数。"""

from typing import Union


DEFAULT_CHARGE_MONEY = 7


def build_charge_params(
    devaddress: str,
    port: Union[str, int],
    beforemoney: int,
    device_info: dict,
    area_id: int,
    open_id: str,
    charge_money: int = DEFAULT_CHARGE_MONEY,
) -> dict:
    """构造启动充电参数，并保持物理端口号原样发送。"""
    return {
        "devaddress": devaddress,
        "port": port,
        "money": charge_money,
        "areaId": area_id,
        "openId": open_id,
        "beforemoney": beforemoney,
        "devtypeid": device_info.get("devtypeid", 40),
        "fullStop": 0,
        "payType": 1,
        "safeOpen": 0,
        "safeCharge": device_info.get("safeCharge", 9),
        "edtType": 0,
        "efee": device_info.get("efee", 110),
        "eCharge": device_info.get("eCharge", 55),
        "serviceCharge": device_info.get("serviceCharge", 55),
        "userId": 0,
        "yuan7": 0,
    }
