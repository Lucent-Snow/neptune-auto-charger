"""充电桩端口编号与状态字符串之间的映射。"""

from typing import Optional, Union


def get_port_status(portstatur: str, port: Union[str, int]) -> Optional[str]:
    """返回物理端口的状态；端口号无效时返回 ``None``。

    Neptune 接口的物理端口号从 1 开始，而 ``portstatur`` 字符串的下标
    从 0 开始，因此物理端口 N 对应 ``portstatur[N - 1]``。
    """
    try:
        port_number = int(port)
    except (TypeError, ValueError):
        return None

    if not isinstance(portstatur, str):
        return None
    if not 1 <= port_number <= len(portstatur):
        return None

    return portstatur[port_number - 1]


def is_port_free(portstatur: str, port: Union[str, int]) -> bool:
    """检查物理端口是否空闲。"""
    return get_port_status(portstatur, port) == "0"
