"""Bridge WebSocket state — tracks active connections for kill switch."""

_bridge_connections = {}


def set_bridge_ws(user_id, ws):
    _bridge_connections[user_id] = ws


def get_bridge_ws(user_id):
    return _bridge_connections.get(user_id)


def remove_bridge_ws(user_id):
    _bridge_connections.pop(user_id, None)
