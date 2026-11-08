"""Resolve the active mode and demo from the visitor's cookie on a multi-demo server."""
from fastapi import Request

from app.container import AppState, state_for_mode

WORKSPACE_COOKIE = "stead_workspace"


def demo_for_request(request: Request) -> AppState:
    root: AppState = request.app.state.app
    _, _, persona = request.cookies.get(WORKSPACE_COOKIE, "").partition(":")
    if persona in root.demo_states:
        return root.demo_states[persona]
    return state_for_mode(root, "historical")


def active_state(request: Request) -> AppState:
    root: AppState = request.app.state.app
    if root.demo_states:
        mode, _, _ = request.cookies.get(WORKSPACE_COOKIE, "").partition(":")
        if mode == "historical":
            return demo_for_request(request)
        if mode == "live":
            return state_for_mode(root, "live")
    return root
