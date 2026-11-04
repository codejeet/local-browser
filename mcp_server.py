"""Local Chrome bridge MCP stdio entry point."""
from mcp.server.fastmcp import FastMCP

from client import request, save_screenshot

# Keep SDK exception logging from copying browser error contents into stderr.
mcp = FastMCP('Local Chrome', log_level='CRITICAL')


@mcp.tool()
async def local_browser(action: str, params: dict, timeout: int = 30) -> dict:
    """Operates the user's real local Chrome, not a hosted browser. Use only on explicit owner tasks.

    Actions: status, tabs, open, navigate, close, activate, snapshot, html, eval,
    click, fill, scroll, key, screenshot, frames. Pass action arguments in params.
    status reports the relay connection. Use tabs first to select the intended tab.
    Screenshots capture the visible tab: activate the intended tab before screenshot.
    params: open {url,windowId?,active?}; all page actions require tabId.
    snapshot {tabId,frameId?,maxText?,limit?} returns text and element refs per frame.
    html {tabId,selector?,maxChars?}; frames {tabId} lists frame IDs.
    click {tabId,ref|selector}; fill {tabId,ref|selector,value}; take new snapshot after changes.
    scroll {tabId,x?,y?,ref?,selector?}; key {tabId,ref|selector,key,ctrlKey?,shiftKey?}.
    eval {tabId,code,world?,body?}: code is a JavaScript expression by default.
    Set body:true for statements with explicit return; async/await supported.
    world defaults to USER_SCRIPT; MAIN accesses page JS globals. Optional frameId/allFrames.
    navigate {tabId,url}; close/activate/screenshot {tabId}; activate also accepts focusWindow.
    click/fill/scroll/key are synthetic DOM actions,
    not trusted OS input. They cannot satisfy browser features requiring trusted input.
    A screenshot returns an absolute PNG path in the private local cache.
    Calls are never automatically retried. A timeout/disconnect can leave the action
    outcome unknown; inspect current state before repeating a mutation.
    """
    result = await request(action, params, timeout)
    if action == 'screenshot':
        return {'path': save_screenshot(result), 'mimeType': 'image/png'}
    return result if isinstance(result, dict) else {'result': result}


if __name__ == '__main__':
    mcp.run(transport='stdio')
